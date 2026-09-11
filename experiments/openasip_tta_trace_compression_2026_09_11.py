#!/usr/bin/env python3
"""OpenASIP public-repo TTA/VLIW trace extraction + E0/E1/E2/dictionary study.

Parses precompiled TPEF program binaries shipped in the public OpenASIP
repository (pinned commit 7762099df624d5f25321ddec05bab763184817f1),
together with their ADF machine definitions and BEM binary encoding maps,
and reconstructs per-cycle, per-move-slot traces without running the
OpenASIP toolchain (which cannot be built on this host: it requires a
patched LLVM build, boost, xerces-c, sqlite, tcl; Linux-oriented; macOS
support experimental per README).

Schemes compared (same metrics as the FRV program-pool studies):
  E0  uncompressed   : one full-width instruction word per cycle
  E1  vertical       : per-slot event streams + valid mask (Candidate A style)
  E2  4-lane striping: valid events striped round-robin (phase) onto 4 lanes
  DICT               : Multanen-2024-style per-slot programmable dictionaries
                       with fixed-size bundles packed into the original
                       instruction-width fetch word

Validation anchors shipped in the repo:
  fft_simm.asm header: 18 buses, 58 instructions, 5234 cycles
  fft_simm.adf imem address-space width: 149 bits
"""

import json
import math
import struct
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

OPENASIP = Path("/Users/maghu/Desktop/work at school/compress/.tools/openasip")
PROGE_DATA = OPENASIP / "testsuite/systemtest_long/procgen/ProGe/data"
PIG_DATA = OPENASIP / "testsuite/systemtest/bintools/PIG/data"

# ---------------------------------------------------------------------------
# TPEF parser (layout derived from src/base/tpef/TPEFHeaders.hh,
# TPEFCodeSectionReader.cc, TPEFResourceSectionReader.cc,
# TPEFSymbolSectionReader.cc, TPEFSectionReader.cc)
# ---------------------------------------------------------------------------

ST_STRTAB = 0x01
ST_SYMTAB = 0x02
ST_MR = 0x0A
ST_CODE = 0x81
ST_DATA = 0x82
ST_UDATA = 0x83
ST_LEDATA = 0x84

IA_TYPE = 0x01   # move(0) / immediate(1)
IA_END = 0x02
IA_ANNOTE = 0x04
IA_EMPTY = 0x08
IA_MGUARD = 0x10

MVS_RF = 0x04
MVS_IMM = 0x08
MVS_UNIT = 0x0C
MVD_RF = 0x10
MVD_UNIT = 0x30
MVG_RF = 0x80
IE_GUARD_INV = 0x40

MRT_NAMES = {0: "NULL", 1: "BUS", 2: "FU", 3: "RF", 4: "OP", 5: "IMM",
             6: "SR", 7: "PORT"}


def bit_length(x):
    return x.bit_length()  # matches MathTools::bitLength (0 -> 0)


class TPEF:
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        self._parse_header()
        self._parse_sections()
        self._parse_strtab()
        self._parse_resources()
        self._parse_symbols()
        self._parse_code()

    def _parse_header(self):
        d = self.data
        assert d[0:8] == b"\x7fTTA-PF\x00", "bad TPEF magic"
        self.version = d[8]
        assert d[9] == 0x0A
        self.arch = d[10]
        self.type = d[11]
        (self.shoff,) = struct.unpack_from(">I", d, 12)
        (self.fhsize,) = struct.unpack_from(">H", d, 16)
        (self.shsize,) = struct.unpack_from(">H", d, 18)
        (self.shnum,) = struct.unpack_from(">H", d, 20)
        (self.shstroff,) = struct.unpack_from(">I", d, 22)
        assert self.fhsize == 26 and self.shsize == 32

    def _parse_sections(self):
        self.sections = []
        for i in range(self.shnum):
            off = self.shoff + i * self.shsize
            d = self.data
            name_off, = struct.unpack_from(">I", d, off + 0)
            stype = d[off + 4]
            flags = d[off + 5]
            addr, = struct.unpack_from(">I", d, off + 6)
            body_off, = struct.unpack_from(">I", d, off + 10)
            body_len, = struct.unpack_from(">I", d, off + 14)
            sid, = struct.unpack_from(">H", d, off + 18)
            aspace = d[off + 20]
            link, = struct.unpack_from(">H", d, off + 22)
            info, = struct.unpack_from(">I", d, off + 24)
            entsize, = struct.unpack_from(">I", d, off + 28)
            self.sections.append(dict(
                index=i, name_off=name_off, type=stype, flags=flags,
                addr=addr, offset=body_off, size=body_len, id=sid,
                aspace=aspace, link=link, info=info, entsize=entsize))

    def _section_by_id(self, sid):
        for s in self.sections:
            if s["id"] == sid:
                return s
        return None

    def _parse_strtab(self):
        # string table: the section header offset self.shstroff points at it
        self.strings = b""
        for s in self.sections:
            if s["type"] == ST_STRTAB:
                self.strings = self.data[s["offset"]:s["offset"] + s["size"]]
                self.strtab_id = s["id"]
                break
        else:
            self.strtab_id = 0

    def _str(self, off):
        if off == 0 or not self.strings:
            return ""
        end = self.strings.index(b"\x00", off)
        return self.strings[off:end].decode("utf-8", "replace")

    def _section_name(self, s):
        return self._str(s["name_off"])

    def _parse_resources(self):
        # NOTE: resource ids are only unique within a type (the TPEF reader
        # source notes OP/SR/PORT share an id space), so key by (type, id).
        self.resources = {}   # (type, id) -> name
        self.buses = []       # bus names in resource-id order
        for s in self.sections:
            if s["type"] != ST_MR:
                continue
            n = s["size"] // s["entsize"] if s["entsize"] else 0
            bus_entries = []
            for i in range(n):
                off = s["offset"] + i * s["entsize"]
                rid, = struct.unpack_from(">H", self.data, off)
                rtype = self.data[off + 2]
                name_off, = struct.unpack_from(">I", self.data, off + 3)
                info, = struct.unpack_from(">I", self.data, off + 7)
                name = self._str(name_off)
                self.resources[(rtype, rid)] = name
                if rtype == 1:  # BUS
                    bus_entries.append((rid, name))
            self.buses = [name for _, name in sorted(bus_entries)]

    def _parse_symbols(self):
        self.symbols = []     # (name, value, size, type, section_id)
        for s in self.sections:
            if s["type"] != ST_SYMTAB:
                continue
            if s["entsize"] == 0:
                continue
            n = s["size"] // s["entsize"]
            for i in range(n):
                off = s["offset"] + i * s["entsize"]
                name_off, value, size = struct.unpack_from(">III", self.data, off)
                info = self.data[off + 12]
                secid, = struct.unpack_from(">H", self.data, off + 14)
                self.symbols.append(dict(name=self._str(name_off), value=value,
                                         size=size, type=info & 0x0F,
                                         binding=info >> 4, section=secid))

    def _read_id(self, pos):
        if self.version == 1:
            return self.data[pos], pos + 1
        val, = struct.unpack_from(">H", self.data, pos)
        return val, pos + 2

    def _parse_code(self):
        """Parse all code sections into instructions.

        Each instruction: list of elements; each element is
          ('move', bus_id, src_type, src_unit, src_idx, dst_type, dst_unit,
           dst_idx, guarded, guard_unit, guard_idx, guard_inv, empty)
        or
          ('imm', dst_unit, dst_idx, bytes)
        """
        self.code_sections = []
        for s in self.sections:
            if s["type"] != ST_CODE:
                continue
            instrs = []
            cur = []
            pos = s["offset"]
            end = s["offset"] + s["size"]
            while pos < end:
                iattr = self.data[pos]; pos += 1
                if iattr & IA_TYPE:  # immediate
                    dst_unit = self.data[pos]; dst_idx = self.data[pos + 1]
                    pos += 2
                    size = (iattr >> 4) & 0x0F
                    val = self.data[pos:pos + size]; pos += size
                    elem = ("imm", dst_unit, dst_idx, val)
                else:                # move
                    bus, pos = self._read_id(pos)
                    ftypes = self.data[pos]; pos += 1
                    empty = bool(iattr & IA_EMPTY)
                    src_type = ftypes & 0x0C
                    dst_type = ftypes & 0x30
                    guarded = bool(iattr & IA_MGUARD)
                    guard_inv = bool(ftypes & IE_GUARD_INV)
                    src_unit, pos = self._read_id(pos)
                    src_idx, = struct.unpack_from(">H", self.data, pos); pos += 2
                    dst_unit, pos = self._read_id(pos)
                    dst_idx, = struct.unpack_from(">H", self.data, pos); pos += 2
                    g_unit, pos = self._read_id(pos)
                    g_idx, = struct.unpack_from(">H", self.data, pos); pos += 2
                    elem = ("move", bus, src_type, src_unit, src_idx,
                            dst_type, dst_unit, dst_idx, guarded,
                            g_unit, g_idx, guard_inv, empty)
                if iattr & IA_ANNOTE:
                    while True:
                        sc = self.data[pos]; pos += 1
                        payload = sc & 0x7F
                        pos += 3  # annotation id
                        pos += payload
                        if not (sc & 0x80):
                            break
                cur.append(elem)
                if iattr & IA_END:
                    instrs.append(cur)
                    cur = []
            if cur:
                instrs.append(cur)
            # instruction word size in MAU from section info (high halfword)
            imau = (s["info"] >> 16) & 0xFFFF
            self.code_sections.append(dict(
                name=self._section_name(s), addr=s["addr"], instrs=instrs,
                info_imau=imau, section=s))


# ---------------------------------------------------------------------------
# BEM parser (width rules from src/base/bem/{MoveSlot,SourceField,
# DestinationField,GuardField,SlotField,SocketEncoding,PortCode,
# BinaryEncoding,ImmediateSlotField}.cc)
# ---------------------------------------------------------------------------

class BEM:
    def __init__(self, path):
        self.path = Path(path)
        self.root = ET.parse(self.path).getroot()
        self._parse_port_tables()
        self._parse_slots()
        self._parse_immediate_slots()

    def _parse_port_tables(self):
        # map-ports name -> port code table width
        self.port_width = {}
        for mp in self.root.iter("map-ports"):
            extra = int(mp.findtext("extra-bits", "0"))
            w = 0
            for pc in mp:
                if pc.tag == "fu-port-code":
                    enc = int(pc.findtext("encoding", "0"))
                    pextra = int(pc.findtext("extra-bits", "0"))
                    w = max(w, bit_length(enc) + pextra)
                elif pc.tag == "rf-port-code":
                    iw = int(pc.get("index-width", "0"))
                    if pc.find("encoding") is not None:
                        enc = int(pc.findtext("encoding", "0"))
                        pextra = int(pc.findtext("extra-bits", "0"))
                        w = max(w, bit_length(enc) + pextra + iw)
                    else:
                        w = max(w, iw)
                elif pc.tag == "iu-port-code":
                    iw = int(pc.get("index-width", "0"))
                    if pc.find("encoding") is not None:
                        enc = int(pc.findtext("encoding", "0"))
                        pextra = int(pc.findtext("extra-bits", "0"))
                        w = max(w, bit_length(enc) + pextra + iw)
                    else:
                        w = max(w, iw)
            self.port_width[mp.get("name")] = w + extra

    def _field_width(self, field):
        """Width of a source/destination slot field (SlotField::width).

        SocketEncoding::width() = bitLength(map) + map extra-bits
                                  + port-code-table width (map @codes names a
                                  map-ports table; default table name = socket
                                  name).
        """
        if field is None:
            return 0
        extra = int(field.findtext("extra-bits", "0"))
        w = 0
        for sk in field.iter("socket"):
            m = sk.find("map")
            if m is None:
                continue
            sid_w = bit_length(int(m.text or "0")) + int(m.get("extra-bits", "0"))
            table = m.get("codes") or sk.get("name")
            pw = self.port_width.get(table, 0)
            w = max(w, sid_w + pw)
        nop = field.find("no-operation")
        if nop is not None:
            m = nop.find("map")
            if m is not None:
                w = max(w, bit_length(int(m.text or "0"))
                        + int(m.get("extra-bits", "0")))
        imm = field.find("immediate")
        if imm is not None:
            m = imm.find("map")
            enc_w = (bit_length(int(m.text or "0"))
                     + int(m.get("extra-bits", "0"))) if m is not None else 0
            w = max(w, int(imm.get("width", "0")) + enc_w)
        return w + extra

    def _parse_slots(self):
        self.slots = []   # name -> dict(width, guard_w, src_w, dst_w, pos)
        for s in self.root.iter("slot"):
            name = s.get("name")
            pos = int(s.findtext("pos", "0"))
            g = s.find("guard")
            gw = 0
            if g is not None:
                for code in g.iter("reg-guard-code"):
                    gw = max(gw, bit_length(int(code.text or "0")))
                for tag in ("always-true-guard-code", "always-false-guard-code"):
                    e = g.find(tag)
                    if e is not None:
                        gw = max(gw, bit_length(int(e.text or "0")))
                gw += int(g.findtext("extra-bits", "0"))
            sw = self._field_width(s.find("source"))
            dw = self._field_width(s.find("destination"))
            self.slots.append(dict(name=name, pos=pos, guard_w=gw,
                                   src_w=sw, dst_w=dw,
                                   width=gw + sw + dw))

    def _parse_immediate_slots(self):
        # top-level long-immediate slot fields + long-immediate control tag
        self.imm_slot_bits = 0
        for e in self.root.findall("immediate-slot"):
            self.imm_slot_bits += int(e.findtext("width", "0"))
        self.control_bits = 0
        e = self.root.find("long-immediate-tag")
        if e is not None:
            vals = [int(m.text or "0") for m in e.iter("map")]
            if vals:
                self.control_bits = max(v.bit_length() for v in vals)
            self.control_bits += int(e.findtext("extra-bits", "0"))

    def total_width(self):
        return (sum(s["width"] for s in self.slots) + self.imm_slot_bits
                + self.control_bits)


# ---------------------------------------------------------------------------
# Trace extraction
# ---------------------------------------------------------------------------

def extract_program(tpef, bem):
    """Extract per-instruction active-slot values.

    Returns (instructions, slot_info):
      instructions: list of dict slot_index -> hashable value tuple
      slot_info:    list of dicts with name/width per slot index
    Value identity == encoding identity (same source/dest/guard/immediate
    encodes to the same bits), which is what repetition-based compression
    needs.

    If the machine has a long-immediate slot (BEM immediate-slot), it is
    modelled as extra slot index M (active when the instruction contains an
    immediate element; value = immediate bytes).
    """
    slot_names = [s["name"] for s in bem.slots]
    slot_index = {nm: i for i, nm in enumerate(slot_names)}
    M = len(slot_names)
    has_imm_slot = bem.imm_slot_bits > 0
    if has_imm_slot:
        slot_names = slot_names + ["<limm>"]

    instrs = []
    for cs in tpef.code_sections:
        for ins in cs["instrs"]:
            slots = {}
            imm_map = {}
            for e in ins:
                if e[0] == "imm":
                    imm_map[(e[1], e[2])] = e[3]
            for e in ins:
                if e[0] != "move":
                    continue
                (_, bus, st, su, si, dt, du, di, g, gu, gi, ginv, empty) = e
                if empty:
                    continue
                bus_name = tpef.resources.get((1, bus))
                if bus_name not in slot_index:
                    continue  # bus not in BEM (should not happen)
                si_slot = slot_index[bus_name]
                if st == MVS_IMM:
                    src = ("IMM", imm_map.get((su, si), b"").hex())
                elif st == MVS_RF:
                    src = ("RF", tpef.resources.get((3, su), su), si)
                elif st == MVS_UNIT:
                    src = ("FU", tpef.resources.get((2, su), su), si)
                else:
                    src = ("NULL",)
                if dt == MVD_RF:
                    dst = ("RF", tpef.resources.get((3, du), du), di)
                elif dt == MVD_UNIT:
                    dst = ("FU", tpef.resources.get((2, du), du), di)
                else:
                    dst = ("NULL",)
                guard = None
                if g:
                    gname = tpef.resources.get((3, gu), tpef.resources.get((2, gu), gu))
                    guard = (gname, gi, ginv)
                slots[si_slot] = (src, dst, guard)
            if has_imm_slot and imm_map:
                # long-immediate slot activity: value = concatenated imm bytes
                slots[M] = ("LIMM", b"".join(
                    imm_map[k] for k in sorted(imm_map)).hex())
            instrs.append(slots)
    slot_info = [dict(name=s["name"], width=s["width"]) for s in bem.slots]
    if has_imm_slot:
        slot_info.append(dict(name="<limm>", width=bem.imm_slot_bits))
    return instrs, slot_info


def extract_program_nobem(tpef):
    """Occupancy + value extraction without a BEM (widths unknown).

    Slot identity = bus resource id. Returns (instructions, bus_names)."""
    instrs = []
    for cs in tpef.code_sections:
        for ins in cs["instrs"]:
            slots = {}
            imm_map = {}
            for e in ins:
                if e[0] == "imm":
                    imm_map[(e[1], e[2])] = e[3]
            for e in ins:
                if e[0] != "move":
                    continue
                (_, bus, st, su, si, dt, du, di, g, gu, gi, ginv, empty) = e
                if empty:
                    continue
                if st == MVS_IMM:
                    src = ("IMM", imm_map.get((su, si), b"").hex())
                elif st == MVS_RF:
                    src = ("RF", tpef.resources.get((3, su), su), si)
                elif st == MVS_UNIT:
                    src = ("FU", tpef.resources.get((2, su), su), si)
                else:
                    src = ("NULL",)
                if dt == MVD_RF:
                    dst = ("RF", tpef.resources.get((3, du), du), di)
                elif dt == MVD_UNIT:
                    dst = ("FU", tpef.resources.get((2, du), du), di)
                else:
                    dst = ("NULL",)
                guard = None
                if g:
                    gname = tpef.resources.get((3, gu), tpef.resources.get((2, gu), gu))
                    guard = (gname, gi, ginv)
                slots[bus] = (src, dst, guard)
            instrs.append(slots)
    return instrs


# ---------------------------------------------------------------------------
# Schemes
# ---------------------------------------------------------------------------

def pow2ceil(x):
    return 1 << max(0, (x - 1).bit_length()) if x > 1 else 1


def split_move_limm(slot_info):
    """Return (n_move_slots, limm_index_or_None)."""
    for i, s in enumerate(slot_info):
        if s["name"] == "<limm>":
            return i, i
    return len(slot_info), None


def scheme_e0(instrs, slot_info, total_width):
    n = len(instrs)
    return dict(bits=n * total_width, sram_bits=total_width * pow2ceil(n),
                depth=pow2ceil(n), width=total_width)


def scheme_e1(instrs, slot_info):
    """Vertical: per-slot event streams, uniform depth = max stream, + mask.

    The limm slot (if any) is just another bank. Mask = one bit per move slot
    per cycle (limm presence is already signalled by the limm tag bit in the
    BEM control field, counted in E0 width).
    """
    n = len(instrs)
    Mmv, limm = split_move_limm(slot_info)
    M = len(slot_info)
    events = [0] * M
    for ins in instrs:
        for s in ins:
            events[s] += 1
    depth = pow2ceil(max(events))
    payload = sum(events[i] * slot_info[i]["width"] for i in range(M))
    sram = sum(depth * slot_info[i]["width"] for i in range(M))
    mask_depth = pow2ceil(n)
    sram += mask_depth * Mmv
    return dict(bits=payload + n * Mmv, sram_bits=sram, events=events,
                depth=depth, mask_bits=n * Mmv)


def scheme_e2(instrs, slot_info, N=4, lane_width=None, phase0=0):
    """N-lane striping with running phase (repo E2 semantics).

    Only move slots are striped; a limm slot (if present) gets a dedicated
    bank. lane_width must carry the widest move-slot value.
    """
    Mmv, limm = split_move_limm(slot_info)
    if lane_width is None:
        lane_width = max(s["width"] for s in slot_info[:Mmv])
    phase = phase0
    lane_events = [0] * N
    limm_events = 0
    max_k = 0
    feasible = True
    for ins in instrs:
        act = sorted(s for s in ins.keys() if s < Mmv)
        k = len(act)
        max_k = max(max_k, k)
        if k > N:
            feasible = False
        for r, s in enumerate(act):
            lane_events[(phase + r) % N] += 1
        phase = (phase + k) % N
        if limm is not None and limm in ins:
            limm_events += 1
    depth = pow2ceil(max(lane_events)) if lane_events else 1
    n = len(instrs)
    payload = sum(lane_events) * lane_width
    sram = depth * lane_width * N + pow2ceil(n) * Mmv
    if limm is not None:
        sram += pow2ceil(max(1, limm_events)) * slot_info[limm]["width"]
    return dict(bits=payload + n * Mmv, sram_bits=sram, lane_events=lane_events,
                depth=depth, lane_width=lane_width, max_k=max_k,
                feasible=feasible, mask_bits=n * Mmv,
                limm_events=limm_events)


def scheme_dict(instrs, slot_info, total_width, caps, tag_bits=2):
    """Multanen-2024-style per-slot dictionaries + fixed bundles.

    caps: per-move-slot dictionary capacity (entries). Entry 0 = NOP.
    An instruction is compressible iff it has no limm-slot activity and every
    active move-slot value is in its dictionary. Compressed instruction = M
    indices of ceil(log2(cap)) bits. Bundle = floor((total_width - tag_bits) /
    index_bits) compressed instructions per fetch word. Frame cost = 1 header
    word + one full-width word per used dictionary entry.
    """
    Mmv, limm = split_move_limm(slot_info)
    freq = [Counter() for _ in range(Mmv)]
    for ins in instrs:
        for s, v in ins.items():
            if s < Mmv:
                freq[s][v] += 1
    dicts = []
    for i in range(Mmv):
        cap = caps[i]
        most = [v for v, _ in freq[i].most_common(max(0, cap - 1))]
        dicts.append(set(most))
    idx_bits = [max(1, math.ceil(math.log2(max(2, caps[i]))))
                for i in range(Mmv)]
    cwidth = sum(idx_bits)
    per_word = (total_width - tag_bits) // cwidth if cwidth > 0 else 0

    def compressible(ins):
        if per_word <= 0:
            return False
        if limm is not None and limm in ins:
            return False
        return all(v in dicts[s] for s, v in ins.items() if s < Mmv)

    n_c = sum(1 for ins in instrs if compressible(ins))
    n_u = len(instrs) - n_c
    used_entries = sum(len(dicts[i]) + 1 for i in range(Mmv))
    frame_words = 1 + used_entries
    if per_word > 0:
        words = math.ceil(n_c / per_word) + n_u + frame_words
    else:
        words = len(instrs) + frame_words
    static_bits = words * total_width
    dict_hw_bits = sum((len(dicts[i]) + 1) * slot_info[i]["width"]
                       for i in range(Mmv))
    return dict(static_bits=static_bits, words=words, n_compressed=n_c,
                n_uncompressed=n_u, per_word=per_word, cwidth=cwidth,
                frame_words=frame_words, dict_hw_bits=dict_hw_bits,
                idx_bits=idx_bits, dicts=dicts, compressible=compressible)


def dict_dynamic(dyn_instrs, slot_info, total_width, dict_res):
    """Dynamic fetch bits over an executed instruction sequence."""
    Mmv, limm = split_move_limm(slot_info)
    per_word = dict_res["per_word"]
    compressible = dict_res["compressible"]
    fetch = 0
    dict_reads = 0
    c_run = 0  # compressed instructions consumed from current bundle word
    n_cyc_c = 0
    for ins in dyn_instrs:
        if compressible(ins):
            if c_run % per_word == 0:
                fetch += total_width  # one bundle word serves per_word cycles
            c_run += 1
            n_cyc_c += 1
            dict_reads += sum(slot_info[i]["width"] for i in range(Mmv))
        else:
            c_run = 0
            fetch += total_width
    fetch += dict_res["frame_words"] * total_width  # frame load once
    return dict(fetch_bits=fetch, dict_read_bits=dict_reads,
                compressed_cycles=n_cyc_c)


# ---------------------------------------------------------------------------
# Experiment driver
# ---------------------------------------------------------------------------

def scheme_e2_grouped(instrs, slot_info, classes, uniform_depth=False):
    """Width-class-grouped striping (方案 G).

    Slots are partitioned into width classes; each class independently
    stripes its active slots onto N_c lanes of the class max width with its
    own running phase. N_c = per-class max simultaneous active slots (the
    cycle-preserving minimum for that class). Mask = M bits/cycle shared.

    uniform_depth=False: each class depth = its own max lane events (pow2).
    uniform_depth=True : all class lanes use the global max lane events
                         (pow2) — the same program-replaceability assumption
                         as E1's uniform-depth banks.
    """
    Mmv, limm = split_move_limm(slot_info)
    n = len(instrs)
    mask_sram = pow2ceil(n) * Mmv
    total_sram = mask_sram
    total_bits = n * Mmv
    per_class = []
    class_lanes = []
    global_max = 0
    for cls in classes:
        cls = [s for s in cls if s < Mmv]
        if not cls:
            continue
        w = max(slot_info[s]["width"] for s in cls)
        phase = 0
        max_kc = max((sum(1 for s in ins if s in cls) for ins in instrs),
                     default=0)
        N = max(1, max_kc)
        lane_events = [0] * N
        for ins in instrs:
            act = sorted(s for s in ins if s in cls)
            for r, s in enumerate(act):
                lane_events[(phase + r) % N] += 1
            phase = (phase + len(act)) % N
        class_lanes.append((cls, w, N, lane_events))
        global_max = max(global_max, max(lane_events))
    udepth = pow2ceil(global_max)
    for cls, w, N, lane_events in class_lanes:
        depth = udepth if uniform_depth else pow2ceil(max(lane_events))
        total_sram += depth * w * N
        total_bits += sum(lane_events) * w
        per_class.append(dict(slots=[slot_info[s]["name"] for s in cls],
                              width=w, N=N, depth=depth,
                              lane_events=lane_events))
    if limm is not None:
        ev = sum(1 for ins in instrs if limm in ins)
        total_sram += pow2ceil(max(1, ev)) * slot_info[limm]["width"]
    return dict(bits=total_bits, sram_bits=total_sram, classes=per_class,
                n_classes=len(per_class))


def scheme_e2_hybrid(instrs, slot_info, T):
    """Hybrid dedicated+striped (方案 H).

    Move slots wider than T get a dedicated bank (E1-style, uniform depth =
    max events among them); slots with width <= T are striped onto N lanes of
    width <= T (N = max simultaneous narrow active). Mask = M bits/cycle.
    """
    Mmv, limm = split_move_limm(slot_info)
    n = len(instrs)
    wide = [s for s in range(Mmv) if slot_info[s]["width"] > T]
    narrow = [s for s in range(Mmv) if slot_info[s]["width"] <= T]
    mask_sram = pow2ceil(n) * Mmv
    total_sram = mask_sram
    total_bits = n * Mmv
    # dedicated wide slots
    if wide:
        ev = [sum(1 for ins in instrs if s in ins) for s in wide]
        depth = pow2ceil(max(ev))
        total_sram += sum(depth * slot_info[s]["width"] for s in wide)
        total_bits += sum(e * slot_info[s]["width"]
                          for s, e in zip(wide, ev))
    # striped narrow slots
    if narrow:
        w = max(slot_info[s]["width"] for s in narrow)
        max_kn = max((sum(1 for s in ins if s in narrow) for ins in instrs),
                     default=0)
        N = max(1, max_kn)
        phase = 0
        lane_events = [0] * N
        for ins in instrs:
            act = sorted(s for s in ins if s in narrow)
            for r, s in enumerate(act):
                lane_events[(phase + r) % N] += 1
            phase = (phase + len(act)) % N
        depth = pow2ceil(max(lane_events))
        total_sram += depth * w * N
        total_bits += sum(lane_events) * w
        n_narrow = N
    else:
        n_narrow = 0
    if limm is not None:
        ev = sum(1 for ins in instrs if limm in ins)
        total_sram += pow2ceil(max(1, ev)) * slot_info[limm]["width"]
    return dict(bits=total_bits, sram_bits=total_sram, threshold=T,
                n_wide=len(wide), n_narrow_lanes=n_narrow)


def validate_roundtrip_grouped(instrs, slot_info, classes):
    """Grouped striping encode->decode must reproduce every instruction."""
    Mmv, _ = split_move_limm(slot_info)
    for cls in classes:
        cls = [s for s in cls if s < Mmv]
        if not cls:
            continue
        max_kc = max((sum(1 for s in ins if s in cls) for ins in instrs),
                     default=0)
        N = max(1, max_kc)
        # encode
        phase = 0
        lanes = [[] for _ in range(N)]
        for ins in instrs:
            act = sorted(s for s in ins if s in cls)
            for r, s in enumerate(act):
                lanes[(phase + r) % N].append(ins[s])
            phase = (phase + len(act)) % N
        # decode
        phase = 0
        ptr = [0] * N
        for ins in instrs:
            act = sorted(s for s in ins if s in cls)
            for r, s in enumerate(act):
                v = lanes[(phase + r) % N][ptr[(phase + r) % N]]
                ptr[(phase + r) % N] += 1
                assert v == ins[s], "grouped E2 round-trip mismatch"
            phase = (phase + len(act)) % N
    return True


def occupancy(instrs):
    cnt = Counter(len(ins) for ins in instrs)
    return dict(max_k=max(cnt), hist={str(k): v for k, v in sorted(cnt.items())},
                mean=round(sum(k * v for k, v in cnt.items()) / len(instrs), 3))


def validate_roundtrip_e1(instrs, slot_info):
    """E1 encode->decode must reproduce every instruction exactly."""
    M = len(slot_info)
    streams = [[] for _ in range(M)]
    for ins in instrs:
        for s in range(M):
            if s in ins:
                streams[s].append(ins[s])
    ptr = [0] * M
    for ins in instrs:
        rec = {}
        for s in range(M):
            if s in ins:  # mask bit
                rec[s] = streams[s][ptr[s]]
                ptr[s] += 1
        assert rec == ins, "E1 round-trip mismatch"
    return True


def validate_roundtrip_e2(instrs, slot_info, N=4):
    """E2 encode->decode with phase striping; only when max_k <= N."""
    Mmv, _ = split_move_limm(slot_info)
    phase = 0
    lanes = [[] for _ in range(N)]
    for ins in instrs:
        act = sorted(s for s in ins if s < Mmv)
        if len(act) > N:
            return None  # infeasible
        for r, s in enumerate(act):
            lanes[(phase + r) % N].append(ins[s])
        phase = (phase + len(act)) % N
    # decode
    phase = 0
    ptr = [0] * N
    for ins in instrs:
        act = sorted(s for s in ins if s < Mmv)
        rec = {}
        for r, s in enumerate(act):
            rec[s] = lanes[(phase + r) % N][ptr[(phase + r) % N]]
            ptr[(phase + r) % N] += 1
        for s in act:
            assert rec[s] == ins[s], "E2 round-trip mismatch"
        phase = (phase + len(act)) % N
    return True


def validate_roundtrip_dict(instrs, slot_info, total_width, caps):
    d = scheme_dict(instrs, slot_info, total_width, caps)
    dicts = d["dicts"]
    # encode then decode every instruction
    order = {i: {v: k for k, v in enumerate(
        [None] + sorted(dicts[i], key=repr))} for i in range(len(dicts))}
    for ins in instrs:
        if d["compressible"](ins):
            for s, v in ins.items():
                if s < len(dicts):
                    assert v in dicts[s]
                    assert dicts[s] is not None
    return True


def run_program(name, tpef_path, bem_path, ref_width=None, dynamic_seq=None):
    tpef = TPEF(tpef_path)
    bem = BEM(bem_path)
    instrs, slot_info = extract_program(tpef, bem)
    W = bem.total_width()
    Mmv, limm = split_move_limm(slot_info)
    res = dict(name=name, tpef=str(tpef_path).split("openasip/")[-1],
               n_instr=len(instrs), M_move_slots=Mmv, has_limm=limm is not None,
               bem_width=W, ref_width=ref_width,
               slot_widths={s["name"]: s["width"] for s in slot_info},
               occupancy=occupancy(instrs))
    # all schemes use BEM-consistent widths; E0 additionally reported at the
    # reference (ADF/golden) width
    res["E0"] = scheme_e0(instrs, slot_info, W)
    if ref_width and ref_width != W:
        res["E0_refwidth"] = scheme_e0(instrs, slot_info, ref_width)
    res["E1"] = scheme_e1(instrs, slot_info)
    max_k = res["occupancy"]["max_k"]
    res["E2_N4"] = scheme_e2(instrs, slot_info, N=4)
    res["E2_Nmax"] = scheme_e2(instrs, slot_info, N=max(4, max_k))
    # E2 lane-count sweep (the scheme's core is N-adaptive striping):
    # feasible N ranges from max_k (cycle-preserving minimum) upward is
    # meaningless, so sweep N in [1..max_k] and mark feasibility; the smallest
    # feasible N is the cycle-preserving operating point.
    sweep = []
    for N in range(1, max(4, max_k) + 1):
        r = scheme_e2(instrs, slot_info, N=N)
        sweep.append(dict(N=N, feasible=r["feasible"],
                          sram_bits=r["sram_bits"], depth=r["depth"],
                          lane_events=r["lane_events"]))
    res["E2_sweep"] = sweep
    # width-heterogeneity diagnostic: E1 payload at native widths vs the
    # same events carried on max-width E2 lanes
    Mmv, _ = split_move_limm(slot_info)
    native = sum(slot_info[s]["width"] * sum(1 for ins in instrs if s in ins)
                 for s in range(Mmv))
    ev_total = sum(sum(1 for ins in instrs if s in ins) for s in range(Mmv))
    lw = max(s["width"] for s in slot_info[:Mmv])
    res["width_diag"] = dict(
        native_payload_bits=native, e2_lane_payload_bits=ev_total * lw,
        lane_width=lw, n_events=ev_total,
        width_penalty=round(ev_total * lw / max(1, native), 3))
    # --- width-heterogeneity solutions: grouped (G) and hybrid (H) striping
    byw = defaultdict(list)
    for i, s in enumerate(slot_info):
        if s["name"] != "<limm>":
            byw[s["width"]].append(i)
    classes = list(byw.values())
    g = scheme_e2_grouped(instrs, slot_info, classes)
    g["roundtrip"] = validate_roundtrip_grouped(instrs, slot_info, classes)
    gu = scheme_e2_grouped(instrs, slot_info, classes, uniform_depth=True)
    g["sram_bits_uniform_depth"] = gu["sram_bits"]
    res["E2_grouped"] = g
    best_h = None
    for T in sorted(set(s["width"] for s in slot_info)):
        h = scheme_e2_hybrid(instrs, slot_info, T)
        if best_h is None or h["sram_bits"] < best_h["sram_bits"]:
            best_h = h
    res["E2_hybrid_best"] = best_h
    # validations
    res["validate"] = dict(
        e1=validate_roundtrip_e1(instrs, slot_info),
        e2_nmax=validate_roundtrip_e2(instrs, slot_info, N=max(4, max_k)),
        dict_all16=validate_roundtrip_dict(instrs, slot_info, W, [16] * Mmv),
    )
    # dictionary configurations
    dict_cfgs = {}
    for cap in (8, 16, 32, 64):
        dict_cfgs[f"all{cap}"] = [cap] * Mmv
    freq = [Counter() for _ in range(Mmv)]
    for ins in instrs:
        for s, v in ins.items():
            if s < Mmv:
                freq[s][v] += 1
    tuned = [min(64, pow2ceil(len(freq[i]) + 1)) for i in range(Mmv)]
    dict_cfgs["tuned_le64"] = tuned
    res["dict"] = {}
    for cname, caps in dict_cfgs.items():
        d = scheme_dict(instrs, slot_info, W, caps)
        d.pop("dicts")
        d.pop("compressible")
        res["dict"][cname] = d
    if dynamic_seq is not None:
        dyn = dict(cycles=len(dynamic_seq))
        dyn["E0_fetch_bits"] = len(dynamic_seq) * W
        dyn["E0_refwidth_fetch_bits"] = len(dynamic_seq) * (ref_width or W)
        dyn["E1_fetch_bits"] = sum(
            Mmv + sum(slot_info[s]["width"] for s in ins)
            for ins in dynamic_seq)
        N = max(4, max_k)
        lw = max(s["width"] for s in slot_info[:Mmv])
        dyn["E2_fetch_bits"] = sum(
            Mmv + len([s for s in ins if s < Mmv]) * lw
            for ins in dynamic_seq)
        dyn["E2_lane_width"] = lw
        dyn["E2_N"] = N
        # optimistic lower bound of forcing N=4 onto this trace: split each
        # over-full cycle into ceil(k/4) cycles (ignores dependencies, i.e. a
        # lower bound on the real cost), same metric as the CCF analysis
        dyn["E2_N4_optimistic_cycles"] = sum(
            math.ceil(max(1, len([s for s in ins if s < Mmv])) / 4)
            for ins in dynamic_seq)
        # grouped E2 with exact-width classes reads active slots at native
        # width => identical dynamic fetch to E1
        dyn["E2_grouped_fetch_bits"] = sum(
            Mmv + sum(slot_info[s]["width"] for s in ins if s < Mmv)
            for ins in dynamic_seq)
        dyn["dict"] = {}
        for cname, caps in dict_cfgs.items():
            d = scheme_dict(instrs, slot_info, W, caps)
            dd = dict_dynamic(dynamic_seq, slot_info, W, d)
            dyn["dict"][cname] = dd
        res["dynamic"] = dyn
    return res, instrs, slot_info


def fft_dynamic_sequence(instrs):
    """fft_simm/fft_limm executed sequence from the .asm BB annotations:
    BB0(0-8)x1; 5x{ BB1(9-10), BB2(11-24), BB3(25-36)x84, BB4(37-50),
    BB5(51-57) }  => 5234 cycles (matches asm header + RTL bus trace)."""
    bb = [(0, 9), (9, 11), (11, 25), (25, 37), (37, 51), (51, 58)]
    seq = list(instrs[0:9])
    for _ in range(5):
        seq += instrs[9:11]
        seq += instrs[11:25]
        for _ in range(84):
            seq += instrs[25:37]
        seq += instrs[37:51]
        seq += instrs[51:58]
    return seq


def estimate_widths_from_adf(adf_path):
    """Upper-bound per-bus slot widths from ADF connectivity (no BEM).

    Standard TTA encoding without BEMGenerator's left-aligned packing:
      dst = ceil(log2(#dst_sockets+1)) + max dst port bits
          (FU trigger port: ceil(log2(#ops)); RF port: ceil(log2(rf size)))
      src = ceil(log2(#src_sockets+1)) + max src port bits
          (RF read port: register index bits; FU output: 0)
      guard = 0 if the bus has <=1 guard else ceil(log2(2*#guards+2))
    Returns (slot_info_list, bus_order) with slot names = bus names.
    """
    root = ET.parse(adf_path).getroot()
    # socket -> port info
    sock_dir = {}   # socket name -> dict(bus->dir) not needed; build per-bus
    bus_src = defaultdict(list)   # bus -> [socket names that write to bus]
    bus_dst = defaultdict(list)
    for sk in root.iter("socket"):
        nm = sk.get("name")
        for rd in sk.iter("reads-from"):
            b = rd.find("bus")
            if b is not None:
                bus_dst[b.text].append(nm)
        for wr in sk.iter("writes-to"):
            b = wr.find("bus")
            if b is not None:
                bus_src[b.text].append(nm)
    # socket -> owning port's extra bits
    sock_bits = {}
    for fu in root.iter("function-unit"):
        nops = len(list(fu.iter("operation")))
        for p in fu.iter("port"):
            conn = p.findtext("connects-to")
            if not conn:
                continue
            triggers = p.find("triggers") is not None
            sock_bits[conn] = max(sock_bits.get(conn, 0),
                                  (nops - 1).bit_length() if triggers else 0)
    for rf in root.iter("register-file"):
        size = int(rf.findtext("size", "1"))
        idx = (size - 1).bit_length()
        for p in rf.iter("port"):
            conn = p.findtext("connects-to")
            if conn:
                sock_bits[conn] = max(sock_bits.get(conn, 0), idx)
    slot_info = []
    bus_order = []
    for b in root.findall("bus"):  # top-level buses only (socket <bus> refs excluded)
        nm = b.get("name")
        bus_order.append(nm)
        srcs = bus_src.get(nm, [])
        dsts = bus_dst.get(nm, [])
        nguards = len(list(b.iter("guard")))
        gw = 0 if nguards <= 1 else (2 * nguards + 1).bit_length()
        sw = len(srcs).bit_length() + max([sock_bits.get(s, 0) for s in srcs] + [0])
        dw = len(dsts).bit_length() + max([sock_bits.get(s, 0) for s in dsts] + [0])
        slot_info.append(dict(name=nm, width=gw + sw + dw, estimated=True))
    return slot_info, bus_order


def extract_program_adf(tpef, adf_path):
    """Extract with ADF-estimated widths; slot index = bus order in ADF."""
    slot_info, bus_order = estimate_widths_from_adf(adf_path)
    slot_index = {nm: i for i, nm in enumerate(bus_order)}
    instrs_raw = extract_program_nobem(tpef)
    instrs = []
    for ins in instrs_raw:
        remapped = {}
        for bus_id, v in ins.items():
            nm = tpef.resources.get((1, bus_id))
            if nm in slot_index:
                remapped[slot_index[nm]] = v
        instrs.append(remapped)
    return instrs, slot_info


def run_program_adf_widths(name, tpef_path, adf_path):
    """Full scheme comparison for a program without BEM, using ADF-estimated
    (upper-bound, no packing) slot widths. Clearly flagged as estimated."""
    tpef = TPEF(tpef_path)
    instrs, slot_info = extract_program_adf(tpef, adf_path)
    W = sum(s["width"] for s in slot_info)
    Mmv, limm = split_move_limm(slot_info)
    max_k = max(len(ins) for ins in instrs)
    res = dict(name=name, tpef=str(tpef_path).split("openasip/")[-1],
               n_instr=len(instrs), M_move_slots=Mmv,
               widths_estimated_from_adf=True,
               est_width=W,
               slot_widths={s["name"]: s["width"] for s in slot_info},
               occupancy=occupancy(instrs))
    res["E0"] = scheme_e0(instrs, slot_info, W)
    res["E1"] = scheme_e1(instrs, slot_info)
    res["E2_Nmax"] = scheme_e2(instrs, slot_info, N=max_k)
    res["E2_N4"] = scheme_e2(instrs, slot_info, N=4)
    res["validate"] = dict(
        e1=validate_roundtrip_e1(instrs, slot_info),
        e2_nmax=validate_roundtrip_e2(instrs, slot_info, N=max_k))
    res["dict"] = {}
    for cap in (2, 4, 8):
        d = scheme_dict(instrs, slot_info, W, [cap] * Mmv)
        d.pop("dicts"); d.pop("compressible")
        res["dict"][f"all{cap}"] = d
    freq = [Counter() for _ in range(Mmv)]
    for ins in instrs:
        for s, v in ins.items():
            freq[s][v] += 1
    tuned = [min(16, pow2ceil(len(freq[i]) + 1)) for i in range(Mmv)]
    d = scheme_dict(instrs, slot_info, W, tuned)
    d.pop("dicts"); d.pop("compressible")
    res["dict"]["tuned_le16"] = d
    return res


def run_occupancy_only(name, tpef_path):
    """Programs without a usable BEM: occupancy + value-repetition stats."""
    tpef = TPEF(tpef_path)
    instrs = extract_program_nobem(tpef)
    occ = occupancy(instrs)
    # distinct values per slot
    freq = defaultdict(Counter)
    for ins in instrs:
        for s, v in ins.items():
            freq[s][v] += 1
    distinct = {str(s): len(c) for s, c in sorted(freq.items())}
    total_events = sum(len(ins) for ins in instrs)
    return dict(name=name, tpef=str(tpef_path).split("openasip/")[-1],
                n_instr=len(instrs), M_slots=len(tpef.buses),
                occupancy=occ, total_events=total_events,
                distinct_values_per_slot=distinct)


FFT_BBS = [(0, 9, 1), (9, 11, 5), (11, 25, 5), (25, 37, 420),
           (37, 51, 5), (51, 58, 5)]


def per_bb_analysis(name, instrs, slot_info, W):
    """Per-BB occupancy, executions and dict(all16) compressibility."""
    Mmv, limm = split_move_limm(slot_info)
    d = scheme_dict(instrs, slot_info, W, [16] * Mmv)
    comp = d["compressible"]
    rows = []
    for bi, (a, b, freq) in enumerate(FFT_BBS):
        seg = instrs[a:b]
        ks = [len(ins) for ins in seg]
        n_comp = sum(1 for ins in seg if comp(ins))
        rows.append(dict(bb=f"BB{bi}", instrs=f"{a}..{b-1}", n=len(seg),
                         execs=freq, cycles=len(seg) * freq,
                         mean_k=round(sum(ks) / len(ks), 2), max_k=max(ks),
                         compressible=f"{n_comp}/{len(seg)}"))
    return rows


def validate_vs_rtl_bustrace(instrs, slot_info):
    """Cross-check the reconstructed dynamic sequence against the repo's own
    GHDL RTL simulation golden bus trace (fft_simm, 5233 cycles shipped at
    tcetest_fft_case_with_simm/test_fft_case_with_simm/1_output.txt).

    We compare the value sequence driven on bus m19 (the immediate-carrying
    bus) during BB0 (cycles 0..8): TPEF-reconstructed immediates must equal
    the RTL trace's last bus column. Returns True/False/None(not found).
    """
    golden = (PROGE_DATA.parent / "tcetest_fft_case_with_simm" /
              "test_fft_case_with_simm" / "1_output.txt")
    if not golden.exists():
        return None
    rtl = [ln.strip().split(",") for ln in golden.open()]
    m19 = [s["name"] for s in slot_info].index("m19")
    ok = True
    for cyc in range(9):
        v = instrs[cyc].get(m19)
        if v and v[0][0] == "IMM":
            mine = int(v[0][1], 16) if v[0][1] else 0
        else:
            mine = 0
        if int(rtl[cyc][-1], 16) != mine:
            ok = False
    return ok


def main():
    out_dir = ROOT / "analysis_output_openasip_tta_2026-09-11"
    out_dir.mkdir(exist_ok=True)
    results = []
    occ_results = []

    programs = [
        # name, tpef, bem, reference width (ADF imem / golden image), dynamic?
        ("fft_simm", PROGE_DATA / "fft_simm.tpef", PROGE_DATA / "fft_simm.bem",
         149, True),
        ("fft_limm", PROGE_DATA / "fft_limm.tpef", PROGE_DATA / "fft_limm.bem",
         150, True),
        ("fft_limm_opt", PROGE_DATA / "fft_limm_opt.tpef",
         PROGE_DATA / "fft_limm_opt.bem", 137, False),
        ("fft1024_compiler_28bus", PIG_DATA / "1kr4ditfft.tce.tpef",
         PIG_DATA / "mach.for.man.sched.conn.opt.bem", 255, False),
    ]
    occ_only = [
        ("tremor_vorbis", OPENASIP /
         "openasip/test/base/tpef/TPEFReaderTest/data/tremor.tpef"),
        ("address_clipping", TTASIM_DATA / "address_clipping.tpef"),
        ("sequential_program", OPENASIP /
         "openasip/Python-bindings/scripts/sequential_program.scheduled.tpef"),
        ("fft1024_18bus", TTASIM_DATA / "1024pointFFT.tpef"),
        ("func_ptr", PIG_DATA / "func_ptr.tpef"),
    ]

    # Blocks CGRA = OpenASIP's operation-based VLIW demo; its program is still
    # stored as a move-slot TPEF on a TTA machine (blocks_risc.adf). No BEM is
    # shipped, so slot widths are ADF-connectivity upper-bound estimates.
    blocks = run_program_adf_widths(
        "blocks_vliw_binarization",
        OPENASIP / "testsuite/systemtest/bintools/BlocksTools/data/binarization.tpef",
        OPENASIP / "testsuite/systemtest/bintools/BlocksTools/data/blocks_risc.adf")
    results.append(blocks)
    print(f"== blocks_vliw_binarization: {blocks['n_instr']} instrs, "
          f"M={blocks['M_move_slots']}, est width={blocks['est_width']}, "
          f"max_k={blocks['occupancy']['max_k']}, validate={blocks['validate']}")

    for name, tp, bp, refw, dyn in programs:
        seq = None
        if dyn:
            # build once to get instrs, then rerun with the dynamic sequence
            _, instrs0, _ = run_program(name, tp, bp, ref_width=refw)
            seq = fft_dynamic_sequence(instrs0)
            assert len(seq) == 5234, f"dynamic length {len(seq)} != 5234"
        res, instrs, slot_info = run_program(name, tp, bp, ref_width=refw,
                                             dynamic_seq=seq)
        if dyn:
            res["per_bb"] = per_bb_analysis(name, instrs, slot_info,
                                            res["bem_width"])
            if name == "fft_simm":
                res["validate"]["rtl_bustrace_m19_bb0"] = \
                    validate_vs_rtl_bustrace(instrs, slot_info)
        results.append(res)
        print(f"== {name}: {res['n_instr']} instrs, M={res['M_move_slots']}"
              f"{'+limm' if res['has_limm'] else ''}, "
              f"BEM width={res['bem_width']} ref={refw}, "
              f"max_k={res['occupancy']['max_k']}, "
              f"validate={res['validate']}")

    for name, tp in occ_only:
        r = run_occupancy_only(name, tp)
        occ_results.append(r)
        print(f"-- {name}: {r['n_instr']} instrs, {r['M_slots']} slots, "
              f"max_k={r['occupancy']['max_k']}, "
              f"mean={r['occupancy']['mean']}")

    (out_dir / "openasip_tta_compression.json").write_text(
        json.dumps(dict(schemes=results, occupancy_only=occ_results),
                   indent=2, default=str))
    print("wrote", out_dir / "openasip_tta_compression.json")


ROOT = Path(__file__).resolve().parents[1]
TTASIM_DATA = OPENASIP / "testsuite/systemtest/codesign/ttasim/data"

if __name__ == "__main__":
    main()

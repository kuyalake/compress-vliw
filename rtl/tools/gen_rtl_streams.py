#!/usr/bin/env python3
"""Generate RTL experiment data for the first hardware batch (rtl/plan.md).

Batch 1 cases: softmax_x64 / layernorm_x64 / gelu_x64, PRIORITY_STRATEGY=index.
Schedule families: max-5 (E0/E1), max-4 (E2), max-2 (E3/E4).

Currently implemented: E0 (171-bit uncompressed).
  per case outputs in rtl/data/<case>/:
    e0_instr171.memh   - 171-bit instruction words, 43 hex digits per line
    e0_meta.hex        - one hex value: program length T (cycles, incl. EOP)
    golden_issue5.txt  - per-cycle expected outputs with hold semantics:
                         "<load> <store> <vector> <scalar> <sfu> <eop>"
                         (5 x 9-hex 34-bit containers + 1-hex eop)
  and rtl/data/manifest.json summarizing all cases.

171-bit word layout (plan.md section 2):
  [170:137] LOAD | [136:103] STORE | [102:69] VECTOR | [68:35] SCALAR
  [34:1] SFU | [0] EOP

Hold semantics (plan.md section 3.4): a valid slot outputs its container;
an invalid slot outputs its last valid container with the OP field zeroed
(LOAD/STORE OP=[1:0], VECTOR/SCALAR/SFU OP=[3:0]); reset state is all-zero.

Python >= 3.9 compatible. No third-party packages.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # compress-vliw/
ISSUE5_ROOT = ROOT / "analysis_output_issue5_174_priority"
ISSUE4_ROOT = ROOT / "analysis_output_issue124_four_lane_174" / "sweep"
ISSUE2_ROOT = ROOT / "analysis_output_issue2_174_priority"
DATA_ROOT = ROOT / "rtl" / "data"
SRC_ROOT = ROOT / "rtl" / "src"

SLOT_BITS = 34
SLOT_NAMES = ("load", "store", "vector", "scalar", "sfu")
# OP field masks inside each 34-bit container (load, store, vector, scalar, sfu)
OP_MASKS = (0b11, 0b11, 0b1111, 0b1111, 0b1111)

CASES = {
    "softmax_x64":   {"y": 512,  "modes": (0, 1, 2)},
    "layernorm_x64": {"y": 768,  "modes": (0,)},
    "gelu_x64":      {"y": 3072, "modes": (2,)},
}

MAX_DEPTH = 8192  # sram_8192x171 capacity


def parse_schedule(path):
    """Parse a 174-bit schedule.txt into rows [load, store, vector, scalar, sfu, eop]."""
    rows = []
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        packed = int(line, 16)
        if packed >> 174:
            raise ValueError("%s:%d: value exceeds 174 bits" % (path, lineno))
        control = packed & 0xF
        packed >>= 4
        slots_lsb_first = []
        for _ in SLOT_NAMES:
            slots_lsb_first.append(packed & ((1 << SLOT_BITS) - 1))
            packed >>= SLOT_BITS
        if packed:
            raise ValueError("%s:%d: value exceeds 174 bits (tail)" % (path, lineno))
        slots = list(reversed(slots_lsb_first))  # load, store, vector, scalar, sfu
        rows.append(slots + [control & 1])       # control[0] = eop
    return rows


def validate_schedule(case, rows):
    if not rows:
        raise ValueError("%s: empty schedule" % case)
    if len(rows) > MAX_DEPTH:
        raise ValueError("%s: T=%d exceeds SRAM depth %d" % (case, len(rows), MAX_DEPTH))
    for i, row in enumerate(rows):
        eop = row[5]
        if i == len(rows) - 1:
            if eop != 1 or any(row[:5]):
                raise ValueError("%s: last row must be EOP with all-NOP slots" % case)
        elif eop != 0:
            raise ValueError("%s: row %d has unexpected eop=1" % (case, i))


def pick_schedule(case, family="issue5"):
    """Among candidate modes (index priority), pick min cycles; tie -> lower mode.

    family: "issue5" -> max-5 (E0/E1); "issue4" -> max-4 (E2);
    "issue2" -> max-2 (E3/E4).
    """
    root = {"issue5": ISSUE5_ROOT, "issue4": ISSUE4_ROOT,
            "issue2": ISSUE2_ROOT}[family]
    spec = CASES[case]
    best = None
    for mode in spec["modes"]:
        d = root / ("%s_y%d_mode%d_index" % (case, spec["y"], mode))
        sched = d / "schedule.txt"
        if not sched.exists():
            raise FileNotFoundError(str(sched))
        n = len(sched.read_text().splitlines())
        if best is None or n < best[1]:
            best = (mode, n, d)
    return best  # (mode, cycles, dir)


def encode_e0_word(row):
    """[load, store, vector, scalar, sfu, eop] -> 171-bit integer."""
    load, store, vector, scalar, sfu, eop = row
    word = (
        (load << 137) | (store << 103) | (vector << 69)
        | (scalar << 35) | (sfu << 1) | eop
    )
    if word >> 171:
        raise AssertionError("E0 word overflow")
    return word


def decode_e0_word(word):
    """Inverse of encode_e0_word (self-check)."""
    sfu = (word >> 1) & ((1 << 34) - 1)
    scalar = (word >> 35) & ((1 << 34) - 1)
    vector = (word >> 69) & ((1 << 34) - 1)
    store = (word >> 103) & ((1 << 34) - 1)
    load = (word >> 137) & ((1 << 34) - 1)
    return [load, store, vector, scalar, sfu, word & 1]


def gen_golden(rows):
    """Apply hold semantics: invalid slot -> last valid container with OP zeroed."""
    last = [0, 0, 0, 0, 0]
    golden = []
    for row in rows:
        out = []
        for s in range(5):
            if row[s] != 0:
                last[s] = row[s]
                out.append(row[s])
            else:
                out.append(last[s] & ~OP_MASKS[s])
        golden.append(out + [row[5]])
    return golden


def write_case(case, mode, rows):
    case_dir = DATA_ROOT / case
    case_dir.mkdir(parents=True, exist_ok=True)

    # E0 instruction memory image
    memh_path = case_dir / "e0_instr171.memh"
    with memh_path.open("w") as fh:
        for row in rows:
            fh.write("%043x\n" % encode_e0_word(row))

    # meta: program length
    meta_path = case_dir / "e0_meta.hex"
    meta_path.write_text("%x\n" % len(rows))

    # golden (hold semantics)
    golden = gen_golden(rows)
    golden_path = case_dir / "golden_issue5.txt"
    with golden_path.open("w") as fh:
        for grow in golden:
            fh.write(" ".join("%09x" % c for c in grow[:5]) + " %x\n" % grow[5])

    # raw golden (HOLD_EN=0 caliber: outputs equal the stored containers,
    # invalid slots are all-zero)
    raw_path = case_dir / "golden_raw_issue5.txt"
    with raw_path.open("w") as fh:
        for row in rows:
            fh.write(" ".join("%09x" % c for c in row[:5]) + " %x\n" % row[5])

    # ---- self-checks ----
    # 1) E0 packing roundtrip
    for i, row in enumerate(rows):
        if decode_e0_word(encode_e0_word(row)) != row:
            raise AssertionError("%s: E0 roundtrip mismatch at row %d" % (case, i))
    # 2) golden consistency vs original schedule
    last = [0, 0, 0, 0, 0]
    for i, (row, grow) in enumerate(zip(rows, golden)):
        for s in range(5):
            if row[s] != 0:
                if grow[s] != row[s]:
                    raise AssertionError("%s: golden valid mismatch row %d slot %d" % (case, i, s))
                last[s] = row[s]
            else:
                if grow[s] != (last[s] & ~OP_MASKS[s]) or (grow[s] & OP_MASKS[s]) != 0:
                    raise AssertionError("%s: golden hold mismatch row %d slot %d" % (case, i, s))
        if grow[5] != row[5]:
            raise AssertionError("%s: golden eop mismatch row %d" % (case, i))

    return {
        "case": case,
        "mode": mode,
        "cycles": len(rows),
        "files": {
            "e0_memh": str(memh_path.relative_to(ROOT)),
            "e0_meta": str(meta_path.relative_to(ROOT)),
            "golden_issue5": str(golden_path.relative_to(ROOT)),
        },
    }


# ---------------------------------------------------------------------------
# E1 (Candidate A): 5-bit mask config stream + five dedicated slot streams
# ---------------------------------------------------------------------------

E1_PAYLOAD_DEPTH = 2048
E1_CONFIG_DEPTH = 8192


def encode_e1(rows):
    """rows -> (config_masks[T-1], slot_streams[5]); EOP row contributes nothing."""
    config = []
    streams = [[], [], [], [], []]
    for row in rows[:-1]:  # last row is the EOP row (all-NOP + eop)
        mask = 0
        for s in range(5):
            if row[s] != 0:
                mask |= 1 << s
                streams[s].append(row[s])
        config.append(mask)  # 11111 is legal data (EOP is implicit via prog_len)
    return config, streams


def decode_e1(config, streams):
    """Software decode (self-check), mirrors the hardware pipeline."""
    rows = []
    pos = [0, 0, 0, 0, 0]
    for mask in config:
        row = [0, 0, 0, 0, 0]
        for s in range(5):
            if (mask >> s) & 1:
                row[s] = streams[s][pos[s]]
                pos[s] += 1
        rows.append(row + [0])
    rows.append([0, 0, 0, 0, 0, 1])  # implicit EOP row
    if any(pos[s] != len(streams[s]) for s in range(5)):
        raise AssertionError("E1 decode: unconsumed payload events")
    return rows


def write_case_e1(case, rows):
    """Per-case E1 files (for the record / debug)."""
    config, streams = encode_e1(rows)
    if decode_e1(config, streams) != rows:
        raise AssertionError("%s: E1 roundtrip mismatch" % case)
    case_dir = DATA_ROOT / case
    with (case_dir / "e1_config5.memh").open("w") as fh:
        for mask in config:
            fh.write("%02x\n" % mask)
    for s in range(5):
        with (case_dir / ("e1_slot%d.memh" % s)).open("w") as fh:
            for word in streams[s]:
                fh.write("%09x\n" % word)
    return {
        "config_entries": len(config),
        "slot_events": [len(streams[s]) for s in range(5)],
    }


def gen_pool_e1(all_rows):
    """E1 program pool: one config image (8192x5) + five slot images (2048x34).

    Layout order = CASES order (contiguous from 0 in each macro);
    run order is non-sequential in memory (same as E0).

    Outputs under rtl/data/:
      e1_pool_config5.memh, e1_pool_slot{0..4}.memh
      e1_pool_meta.hex - [N, cfg_total, tot0..4, then per program in RUN order:
                          cfg_base, prog_len, slot_base0..4], one hex per line
      e1_pool_map.txt  - "<run_pos> <case>" per line
    """
    layout_order = list(CASES.keys())
    run_order = ["gelu_x64", "softmax_x64", "layernorm_x64"]

    enc = {}
    for case in layout_order:
        config, streams = encode_e1(all_rows[case])
        enc[case] = (config, streams)

    # config pool layout
    cfg_bases = {}
    base = 0
    for case in layout_order:
        cfg_bases[case] = base
        base += len(enc[case][0])
    cfg_total = base
    if cfg_total > E1_CONFIG_DEPTH:
        raise ValueError("E1 config pool %d exceeds %d" % (cfg_total, E1_CONFIG_DEPTH))

    # slot pool layouts (per slot bank)
    slot_bases = {s: {} for s in range(5)}
    slot_totals = []
    for s in range(5):
        b = 0
        for case in layout_order:
            slot_bases[s][case] = b
            b += len(enc[case][1][s])
        slot_totals.append(b)
        if b > E1_PAYLOAD_DEPTH:
            raise ValueError("E1 slot %d pool %d exceeds %d"
                             % (s, b, E1_PAYLOAD_DEPTH))

    # pool images
    with (DATA_ROOT / "e1_pool_config5.memh").open("w") as fh:
        for case in layout_order:
            for mask in enc[case][0]:
                fh.write("%02x\n" % mask)
    for s in range(5):
        with (DATA_ROOT / ("e1_pool_slot%d.memh" % s)).open("w") as fh:
            for case in layout_order:
                for word in enc[case][1][s]:
                    fh.write("%09x\n" % word)

    # meta
    with (DATA_ROOT / "e1_pool_meta.hex").open("w") as fh:
        fh.write("%x\n" % len(run_order))
        fh.write("%x\n" % cfg_total)
        for s in range(5):
            fh.write("%x\n" % slot_totals[s])
        for case in run_order:
            fh.write("%x\n" % cfg_bases[case])
            fh.write("%x\n" % len(all_rows[case]))  # prog_len = T (incl. EOP)
            for s in range(5):
                fh.write("%x\n" % slot_bases[s][case])

    with (DATA_ROOT / "e1_pool_map.txt").open("w") as fh:
        for pos, case in enumerate(run_order):
            fh.write("%d %s\n" % (pos, case))

    # self-check: pool segments must equal per-case encodings
    cfg_lines = (DATA_ROOT / "e1_pool_config5.memh").read_text().splitlines()
    for case in layout_order:
        config, streams = enc[case]
        seg = cfg_lines[cfg_bases[case]:cfg_bases[case] + len(config)]
        if [int(x, 16) for x in seg] != config:
            raise AssertionError("E1 pool config segment mismatch: %s" % case)
        for s in range(5):
            lines = (DATA_ROOT / ("e1_pool_slot%d.memh" % s)).read_text().splitlines()
            seg = lines[slot_bases[s][case]:slot_bases[s][case] + len(streams[s])]
            if [int(x, 16) for x in seg] != streams[s]:
                raise AssertionError("E1 pool slot %d segment mismatch: %s" % (s, case))

    return {
        "config_total": cfg_total,
        "slot_totals": slot_totals,
        "run_order": run_order,
        "programs": [
            {"pos": pos, "case": case, "cfg_base": cfg_bases[case],
             "len": len(all_rows[case]),
             "slot_bases": [slot_bases[s][case] for s in range(5)]}
            for pos, case in enumerate(run_order)
        ],
    }


# ---------------------------------------------------------------------------
# E2 (adaptive 4-slot / four shared lanes): 5-bit mask + phase striping
# ---------------------------------------------------------------------------

E2_LANE_DEPTH = 2048
E2_CONFIG_DEPTH = 8192
E2_EOP = 0b11111  # in-band EOP code (five-active mask never occurs in max-4)


def encode_e2(rows):
    """rows -> (config[T] masks + EOP entry, lanes[4]); phase-striped striping.

    Active slots in ascending slot order; rank r-th active event goes to
    lane (phase + r) mod 4; phase advances by popcount(mask) mod 4.
    """
    config = []
    lanes = [[], [], [], []]
    phase = 0
    for row in rows:
        if row[5] == 1:
            config.append(E2_EOP)
            continue
        active = [s for s in range(5) if row[s] != 0]
        if len(active) > 4:
            raise AssertionError("E2: schedule exceeds four active slots")
        mask = 0
        for s in active:
            mask |= 1 << s
        if mask == E2_EOP:
            raise AssertionError("E2: five-active mask collides with EOP")
        for rank, s in enumerate(active):
            lanes[(phase + rank) % 4].append(row[s])
        config.append(mask)
        phase = (phase + len(active)) % 4
    return config, lanes


def decode_e2(config, lanes):
    """Software decode (self-check), mirrors the hardware pipeline."""
    rows = []
    pos = [0, 0, 0, 0]
    phase = 0
    for code in config:
        if code == E2_EOP:
            rows.append([0, 0, 0, 0, 0, 1])
            continue
        active = [s for s in range(5) if (code >> s) & 1]
        row = [0, 0, 0, 0, 0]
        for rank, s in enumerate(active):
            lane = (phase + rank) % 4
            row[s] = lanes[lane][pos[lane]]
            pos[lane] += 1
        rows.append(row + [0])
        phase = (phase + len(active)) % 4
    if any(pos[l] != len(lanes[l]) for l in range(4)):
        raise AssertionError("E2 decode: unconsumed lane events")
    return rows


def write_case_e2(case, rows4):
    """Per-case E2 files + the max-4 golden (golden_issue4.txt)."""
    config, lanes = encode_e2(rows4)
    if decode_e2(config, lanes) != rows4:
        raise AssertionError("%s: E2 roundtrip mismatch" % case)
    case_dir = DATA_ROOT / case
    with (case_dir / "e2_config5.memh").open("w") as fh:
        for mask in config:
            fh.write("%02x\n" % mask)
    for l in range(4):
        with (case_dir / ("e2_lane%d.memh" % l)).open("w") as fh:
            for word in lanes[l]:
                fh.write("%09x\n" % word)
    # golden for the max-4 schedule (hold semantics)
    golden = gen_golden(rows4)
    with (case_dir / "golden_issue4.txt").open("w") as fh:
        for grow in golden:
            fh.write(" ".join("%09x" % c for c in grow[:5]) + " %x\n" % grow[5])
    return {
        "config_entries": len(config),
        "lane_depths": [len(lanes[l]) for l in range(4)],
    }


def gen_pool_e2(all_rows4):
    """E2 program pool: one config image (8192x5) + four lane images (2048x34).

    e2_pool_meta.hex - [N, cfg_total, lane_totals(4), then per program in RUN
                        order: cfg_base, prog_len, lane_base0..3]
    e2_pool_map.txt  - "<run_pos> <case>" per line
    """
    layout_order = list(CASES.keys())
    run_order = ["gelu_x64", "softmax_x64", "layernorm_x64"]

    enc = {}
    for case in layout_order:
        config, lanes = encode_e2(all_rows4[case])
        enc[case] = (config, lanes)

    cfg_bases = {}
    base = 0
    for case in layout_order:
        cfg_bases[case] = base
        base += len(enc[case][0])
    cfg_total = base
    if cfg_total > E2_CONFIG_DEPTH:
        raise ValueError("E2 config pool %d exceeds %d" % (cfg_total, E2_CONFIG_DEPTH))

    lane_bases = {l: {} for l in range(4)}
    lane_totals = []
    for l in range(4):
        b = 0
        for case in layout_order:
            lane_bases[l][case] = b
            b += len(enc[case][1][l])
        lane_totals.append(b)
        if b > E2_LANE_DEPTH:
            raise ValueError("E2 lane %d pool %d exceeds %d" % (l, b, E2_LANE_DEPTH))

    with (DATA_ROOT / "e2_pool_config5.memh").open("w") as fh:
        for case in layout_order:
            for mask in enc[case][0]:
                fh.write("%02x\n" % mask)
    for l in range(4):
        with (DATA_ROOT / ("e2_pool_lane%d.memh" % l)).open("w") as fh:
            for case in layout_order:
                for word in enc[case][1][l]:
                    fh.write("%09x\n" % word)

    with (DATA_ROOT / "e2_pool_meta.hex").open("w") as fh:
        fh.write("%x\n" % len(run_order))
        fh.write("%x\n" % cfg_total)
        for l in range(4):
            fh.write("%x\n" % lane_totals[l])
        for case in run_order:
            fh.write("%x\n" % cfg_bases[case])
            fh.write("%x\n" % len(all_rows4[case]))  # prog_len = T (incl. EOP entry)
            for l in range(4):
                fh.write("%x\n" % lane_bases[l][case])

    with (DATA_ROOT / "e2_pool_map.txt").open("w") as fh:
        for pos, case in enumerate(run_order):
            fh.write("%d %s\n" % (pos, case))

    # self-check: pool segments must equal per-case encodings
    cfg_lines = (DATA_ROOT / "e2_pool_config5.memh").read_text().splitlines()
    lane_lines = [(DATA_ROOT / ("e2_pool_lane%d.memh" % l)).read_text().splitlines()
                  for l in range(4)]
    for case in layout_order:
        config, lanes = enc[case]
        seg = cfg_lines[cfg_bases[case]:cfg_bases[case] + len(config)]
        if [int(x, 16) for x in seg] != config:
            raise AssertionError("E2 pool config segment mismatch: %s" % case)
        for l in range(4):
            seg = lane_lines[l][lane_bases[l][case]:
                                lane_bases[l][case] + len(lanes[l])]
            if [int(x, 16) for x in seg] != lanes[l]:
                raise AssertionError("E2 pool lane %d segment mismatch: %s" % (l, case))

    return {
        "config_total": cfg_total,
        "lane_totals": lane_totals,
        "run_order": run_order,
        "programs": [
            {"pos": pos, "case": case, "cfg_base": cfg_bases[case],
             "len": len(all_rows4[case]),
             "lane_bases": [lane_bases[l][case] for l in range(4)]}
            for pos, case in enumerate(run_order)
        ],
    }


# ---------------------------------------------------------------------------
# E3 (2slot2lane): 5-bit pair codebook config + two shared lanes (4096 deep)
# ---------------------------------------------------------------------------

E3_LANE_DEPTH = 4096
E3_CONFIG_DEPTH = 8192
E3_EOP = 31  # in-band EOP code


def build_pair_codebook():
    """state -> code. states are (lane0_slot, lane1_slot) with entries in
    {None,0..4}; legal iff lane0 is None or lane1 is None or they differ.
    31 normal states (codes 0..30); code 31 is EOP.

    MUST mirror experiments/issue2_lane_study.py build_config_codebook().
    """
    choices = (None, 0, 1, 2, 3, 4)
    states = [(l0, l1) for l0 in choices for l1 in choices
              if l0 is None or l1 is None or l0 != l1]
    if len(states) != 31:
        raise AssertionError("pair codebook must have 31 normal states")
    return {state: code for code, state in enumerate(states)}


PAIR_FORWARD = build_pair_codebook()
PAIR_STATES = {code: state for state, code in PAIR_FORWARD.items()}


def encode_e3(rows):
    """rows -> (config[T] pair codes + EOP entry, lanes[2]).

    Two active slots -> (first, second); one active slot -> the shallower
    lane (tie -> lane0); empty cycle -> (None, None).
    """
    config = []
    lanes = [[], []]
    for row in rows:
        if row[5] == 1:
            config.append(E3_EOP)
            continue
        active = [s for s in range(5) if row[s] != 0]
        if len(active) > 2:
            raise AssertionError("E3: schedule exceeds two active slots")
        if len(active) == 2:
            assignment = (active[0], active[1])
        elif len(active) == 1:
            s = active[0]
            assignment = (s, None) if len(lanes[0]) <= len(lanes[1]) else (None, s)
        else:
            assignment = (None, None)
        for lane, slot in enumerate(assignment):
            if slot is not None:
                lanes[lane].append(row[slot])
        config.append(PAIR_FORWARD[assignment])
    return config, lanes


def decode_e3(config, lanes):
    """Software decode (self-check), mirrors the hardware pipeline."""
    rows = []
    pos = [0, 0]
    for code in config:
        if code == E3_EOP:
            rows.append([0, 0, 0, 0, 0, 1])
            continue
        a0, a1 = PAIR_STATES[code]
        row = [0, 0, 0, 0, 0]
        if a0 is not None:
            row[a0] = lanes[0][pos[0]]
            pos[0] += 1
        if a1 is not None:
            row[a1] = lanes[1][pos[1]]
            pos[1] += 1
        rows.append(row + [0])
    if pos[0] != len(lanes[0]) or pos[1] != len(lanes[1]):
        raise AssertionError("E3 decode: unconsumed lane events")
    return rows


def emit_pair_codebook():
    """Generate rtl/src/cfg_pair_codebook.v from the SAME enumeration as the
    encoder, so the RTL decoder can never drift from the software codebook.

    Output per code: {valid0, slot0[2:0], valid1, slot1[2:0]}; slot=None is
    emitted as valid=0, slot=0. Code 31 (EOP) decodes to all-invalid.
    """
    lines = []
    lines.append("`timescale 1ns/1ps")
    lines.append("`default_nettype none")
    lines.append("// -----------------------------------------------------------------------------")
    lines.append("// AUTO-GENERATED by rtl/tools/gen_rtl_streams.py -- DO NOT EDIT BY HAND.")
    lines.append("// Pair-codebook decoder shared by E3 (2slot2lane) and E4 (2slot4lane).")
    lines.append("// 5-bit code -> {valid0, slot0, valid1, slot1}; code 31 = EOP -> all invalid.")
    lines.append("// Enumeration mirrors experiments/issue2_lane_study.py build_config_codebook().")
    lines.append("// -----------------------------------------------------------------------------")
    lines.append("module cfg_pair_codebook (")
    lines.append("    input  wire [4:0] code,")
    lines.append("    output reg        valid0,")
    lines.append("    output reg  [2:0] slot0,")
    lines.append("    output reg        valid1,")
    lines.append("    output reg  [2:0] slot1")
    lines.append(");")
    lines.append("")
    lines.append("    always @(*) begin")
    lines.append("        case (code)")
    for code in range(32):
        state = PAIR_STATES.get(code, (None, None))  # 31 -> all invalid
        l0, l1 = state
        v0 = 0 if l0 is None else 1
        s0 = 0 if l0 is None else l0
        v1 = 0 if l1 is None else 1
        s1 = 0 if l1 is None else l1
        comment = ""
        if code == 31:
            comment = "  // EOP"
        lines.append(
            "            5'd%-2d: begin valid0 = 1'b%d; slot0 = 3'd%d; "
            "valid1 = 1'b%d; slot1 = 3'd%d; end%s"
            % (code, v0, s0, v1, s1, comment))
    lines.append("            default: begin valid0 = 1'b0; slot0 = 3'd0; "
                 "valid1 = 1'b0; slot1 = 3'd0; end")
    lines.append("        endcase")
    lines.append("    end")
    lines.append("")
    lines.append("endmodule")
    lines.append("`default_nettype wire")
    lines.append("")
    out = SRC_ROOT / "cfg_pair_codebook.v"
    out.write_text("\n".join(lines))
    return out


def write_case_e3(case, rows2):
    """Per-case E3 files + the max-2 golden (golden_issue2.txt)."""
    config, lanes = encode_e3(rows2)
    if decode_e3(config, lanes) != rows2:
        raise AssertionError("%s: E3 roundtrip mismatch" % case)
    case_dir = DATA_ROOT / case
    with (case_dir / "e3_config5.memh").open("w") as fh:
        for code in config:
            fh.write("%02x\n" % code)
    for l in range(2):
        with (case_dir / ("e3_lane%d.memh" % l)).open("w") as fh:
            for word in lanes[l]:
                fh.write("%09x\n" % word)
    golden = gen_golden(rows2)
    with (case_dir / "golden_issue2.txt").open("w") as fh:
        for grow in golden:
            fh.write(" ".join("%09x" % c for c in grow[:5]) + " %x\n" % grow[5])
    return {
        "config_entries": len(config),
        "lane_depths": [len(lanes[0]), len(lanes[1])],
    }


def gen_pool_e3(all_rows2):
    """E3 program pool: one config image (8192x5) + two lane images (4096x34).

    e3_pool_meta.hex - [N, cfg_total, lane_totals(2), then per program in RUN
                        order: cfg_base, prog_len, lane_base0, lane_base1]
    e3_pool_map.txt  - "<run_pos> <case>" per line
    """
    layout_order = list(CASES.keys())
    run_order = ["gelu_x64", "softmax_x64", "layernorm_x64"]

    enc = {}
    for case in layout_order:
        enc[case] = encode_e3(all_rows2[case])

    cfg_bases = {}
    base = 0
    for case in layout_order:
        cfg_bases[case] = base
        base += len(enc[case][0])
    cfg_total = base
    if cfg_total > E3_CONFIG_DEPTH:
        raise ValueError("E3 config pool %d exceeds %d" % (cfg_total, E3_CONFIG_DEPTH))

    lane_bases = {l: {} for l in range(2)}
    lane_totals = []
    for l in range(2):
        b = 0
        for case in layout_order:
            lane_bases[l][case] = b
            b += len(enc[case][1][l])
        lane_totals.append(b)
        if b > E3_LANE_DEPTH:
            raise ValueError("E3 lane %d pool %d exceeds %d" % (l, b, E3_LANE_DEPTH))

    with (DATA_ROOT / "e3_pool_config5.memh").open("w") as fh:
        for case in layout_order:
            for code in enc[case][0]:
                fh.write("%02x\n" % code)
    for l in range(2):
        with (DATA_ROOT / ("e3_pool_lane%d.memh" % l)).open("w") as fh:
            for case in layout_order:
                for word in enc[case][1][l]:
                    fh.write("%09x\n" % word)

    with (DATA_ROOT / "e3_pool_meta.hex").open("w") as fh:
        fh.write("%x\n" % len(run_order))
        fh.write("%x\n" % cfg_total)
        for l in range(2):
            fh.write("%x\n" % lane_totals[l])
        for case in run_order:
            fh.write("%x\n" % cfg_bases[case])
            fh.write("%x\n" % len(all_rows2[case]))
            for l in range(2):
                fh.write("%x\n" % lane_bases[l][case])

    with (DATA_ROOT / "e3_pool_map.txt").open("w") as fh:
        for pos, case in enumerate(run_order):
            fh.write("%d %s\n" % (pos, case))

    # self-check: pool segments must equal per-case encodings
    cfg_lines = (DATA_ROOT / "e3_pool_config5.memh").read_text().splitlines()
    lane_lines = [(DATA_ROOT / ("e3_pool_lane%d.memh" % l)).read_text().splitlines()
                  for l in range(2)]
    for case in layout_order:
        config, lanes = enc[case]
        seg = cfg_lines[cfg_bases[case]:cfg_bases[case] + len(config)]
        if [int(x, 16) for x in seg] != config:
            raise AssertionError("E3 pool config segment mismatch: %s" % case)
        for l in range(2):
            seg = lane_lines[l][lane_bases[l][case]:
                                lane_bases[l][case] + len(lanes[l])]
            if [int(x, 16) for x in seg] != lanes[l]:
                raise AssertionError("E3 pool lane %d segment mismatch: %s" % (l, case))

    return {
        "config_total": cfg_total,
        "lane_totals": lane_totals,
        "run_order": run_order,
        "programs": [
            {"pos": pos, "case": case, "cfg_base": cfg_bases[case],
             "len": len(all_rows2[case]),
             "lane_bases": [lane_bases[l][case] for l in range(2)]}
            for pos, case in enumerate(run_order)
        ],
    }


# ---------------------------------------------------------------------------
# E4 (2slot4lane): 6-bit {group, local5} config + four shared lanes (2048 deep)
# ---------------------------------------------------------------------------

E4_LANE_DEPTH = 2048
E4_CONFIG_DEPTH = 8192
E4_EOP = 63  # in-band EOP code (0b111111); code 31 is reserved/never emitted


def choose_general_lane(active_count, lane_counts):
    """Mirror four_lane_mapping_study.choose_general_lane (general_symmetric).

    Returns (group, physical_lanes). 2 events -> lane pair {0,1} or {2,3};
    1 event -> any of the 4 lanes (group = lane//2); 0 events -> (0, ()).
    Picks the option minimizing (max, sum of squares, pair-max-sum, group)
    of the projected lane counts.
    """
    candidates = []
    if active_count == 2:
        options = ((0, (0, 1)), (1, (2, 3)))
    elif active_count == 1:
        options = tuple((lane // 2, (lane,)) for lane in range(4))
    else:
        return 0, ()
    for group, lanes in options:
        projected = list(lane_counts)
        for lane in lanes:
            projected[lane] += 1
        score = (
            max(projected),
            sum(value * value for value in projected),
            max(projected[0], projected[1]) + max(projected[2], projected[3]),
            group,
        )
        candidates.append((score, group, lanes))
    _, group, lanes = min(candidates, key=lambda item: item[0])
    return group, lanes


def encode_e4(rows):
    """rows -> (config[T] {group,local} codes + EOP entry, lanes[4]).

    Lane-balance state resets per program (each program runs independently
    with its own descriptor in the RTL pool).
    """
    config = []
    lanes = [[], [], [], []]
    lane_counts = [0, 0, 0, 0]
    for row in rows:
        if row[5] == 1:
            config.append(E4_EOP)
            continue
        active = [s for s in range(5) if row[s] != 0]
        if len(active) > 2:
            raise AssertionError("E4: schedule exceeds two active slots")
        group, physical_lanes = choose_general_lane(len(active), lane_counts)
        local_assignment = [None, None]
        for index, slot in enumerate(active):
            lane = physical_lanes[index]
            local_assignment[lane % 2] = slot
            lanes[lane].append(row[slot])
            lane_counts[lane] += 1
        local_code = PAIR_FORWARD[tuple(local_assignment)]
        code = (group << 5) | local_code
        if code in (31, E4_EOP):
            raise AssertionError("E4: normal mapping used reserved code %d" % code)
        config.append(code)
    return config, lanes


def decode_e4(config, lanes):
    """Software decode (self-check), mirrors the hardware pipeline."""
    rows = []
    pos = [0, 0, 0, 0]
    for code in config:
        if code == E4_EOP:
            rows.append([0, 0, 0, 0, 0, 1])
            continue
        group = code >> 5
        a0, a1 = PAIR_STATES[code & 0x1F]
        row = [0, 0, 0, 0, 0]
        if a0 is not None:
            pl = 2 * group
            row[a0] = lanes[pl][pos[pl]]
            pos[pl] += 1
        if a1 is not None:
            pl = 2 * group + 1
            row[a1] = lanes[pl][pos[pl]]
            pos[pl] += 1
        rows.append(row + [0])
    if any(pos[l] != len(lanes[l]) for l in range(4)):
        raise AssertionError("E4 decode: unconsumed lane events")
    return rows


def write_case_e4(case, rows2):
    """Per-case E4 files. Golden is shared with E3 (golden_issue2.txt)."""
    config, lanes = encode_e4(rows2)
    if decode_e4(config, lanes) != rows2:
        raise AssertionError("%s: E4 roundtrip mismatch" % case)
    case_dir = DATA_ROOT / case
    with (case_dir / "e4_config6.memh").open("w") as fh:
        for code in config:
            fh.write("%02x\n" % code)
    for l in range(4):
        with (case_dir / ("e4_lane%d.memh" % l)).open("w") as fh:
            for word in lanes[l]:
                fh.write("%09x\n" % word)
    return {
        "config_entries": len(config),
        "lane_depths": [len(lanes[l]) for l in range(4)],
    }


def gen_pool_e4(all_rows2):
    """E4 program pool: one config image (8192x6) + four lane images (2048x34).

    e4_pool_meta.hex - [N, cfg_total, lane_totals(4), then per program in RUN
                        order: cfg_base, prog_len, lane_base0..3]
    e4_pool_map.txt  - "<run_pos> <case>" per line
    """
    layout_order = list(CASES.keys())
    run_order = ["gelu_x64", "softmax_x64", "layernorm_x64"]

    enc = {}
    for case in layout_order:
        enc[case] = encode_e4(all_rows2[case])

    cfg_bases = {}
    base = 0
    for case in layout_order:
        cfg_bases[case] = base
        base += len(enc[case][0])
    cfg_total = base
    if cfg_total > E4_CONFIG_DEPTH:
        raise ValueError("E4 config pool %d exceeds %d" % (cfg_total, E4_CONFIG_DEPTH))

    lane_bases = {l: {} for l in range(4)}
    lane_totals = []
    for l in range(4):
        b = 0
        for case in layout_order:
            lane_bases[l][case] = b
            b += len(enc[case][1][l])
        lane_totals.append(b)
        if b > E4_LANE_DEPTH:
            raise ValueError("E4 lane %d pool %d exceeds %d" % (l, b, E4_LANE_DEPTH))

    with (DATA_ROOT / "e4_pool_config6.memh").open("w") as fh:
        for case in layout_order:
            for code in enc[case][0]:
                fh.write("%02x\n" % code)
    for l in range(4):
        with (DATA_ROOT / ("e4_pool_lane%d.memh" % l)).open("w") as fh:
            for case in layout_order:
                for word in enc[case][1][l]:
                    fh.write("%09x\n" % word)

    with (DATA_ROOT / "e4_pool_meta.hex").open("w") as fh:
        fh.write("%x\n" % len(run_order))
        fh.write("%x\n" % cfg_total)
        for l in range(4):
            fh.write("%x\n" % lane_totals[l])
        for case in run_order:
            fh.write("%x\n" % cfg_bases[case])
            fh.write("%x\n" % len(all_rows2[case]))
            for l in range(4):
                fh.write("%x\n" % lane_bases[l][case])

    with (DATA_ROOT / "e4_pool_map.txt").open("w") as fh:
        for pos, case in enumerate(run_order):
            fh.write("%d %s\n" % (pos, case))

    # self-check: pool segments must equal per-case encodings
    cfg_lines = (DATA_ROOT / "e4_pool_config6.memh").read_text().splitlines()
    lane_lines = [(DATA_ROOT / ("e4_pool_lane%d.memh" % l)).read_text().splitlines()
                  for l in range(4)]
    for case in layout_order:
        config, lanes = enc[case]
        seg = cfg_lines[cfg_bases[case]:cfg_bases[case] + len(config)]
        if [int(x, 16) for x in seg] != config:
            raise AssertionError("E4 pool config segment mismatch: %s" % case)
        for l in range(4):
            seg = lane_lines[l][lane_bases[l][case]:
                                lane_bases[l][case] + len(lanes[l])]
            if [int(x, 16) for x in seg] != lanes[l]:
                raise AssertionError("E4 pool lane %d segment mismatch: %s" % (l, case))

    return {
        "config_total": cfg_total,
        "lane_totals": lane_totals,
        "run_order": run_order,
        "programs": [
            {"pos": pos, "case": case, "cfg_base": cfg_bases[case],
             "len": len(all_rows2[case]),
             "lane_bases": [lane_bases[l][case] for l in range(4)]}
            for pos, case in enumerate(run_order)
        ],
    }


def gen_pool(all_rows):
    """Build the E0 program-pool image: all programs loaded once into one
    8192x171 macro, laid out contiguously in CASES order; the run order is
    deliberately non-sequential in memory to exercise descriptor switching.

    Outputs (under rtl/data/):
      e0_pool_instr171.memh - pooled image (total_words lines)
      e0_pool_meta.hex      - [N, total_words, then per program in RUN order:
                               base, len] one hex value per line
      e0_pool_map.txt       - "<run_pos> <case>" per line (for the checker)
    """
    layout_order = list(CASES.keys())                      # memory layout order
    run_order = ["gelu_x64", "softmax_x64", "layernorm_x64"]  # switching order

    bases = {}
    base = 0
    for case in layout_order:
        bases[case] = base
        base += len(all_rows[case])
    total = base
    if total > MAX_DEPTH:
        raise ValueError("pool image %d words exceeds depth %d" % (total, MAX_DEPTH))

    # pooled image
    image_path = DATA_ROOT / "e0_pool_instr171.memh"
    with image_path.open("w") as fh:
        for case in layout_order:
            for row in all_rows[case]:
                fh.write("%043x\n" % encode_e0_word(row))

    # meta: N, total, then (base, len) per program in RUN order
    meta_path = DATA_ROOT / "e0_pool_meta.hex"
    with meta_path.open("w") as fh:
        fh.write("%x\n" % len(run_order))
        fh.write("%x\n" % total)
        for case in run_order:
            fh.write("%x\n%x\n" % (bases[case], len(all_rows[case])))

    # map: run position -> case
    map_path = DATA_ROOT / "e0_pool_map.txt"
    with map_path.open("w") as fh:
        for pos, case in enumerate(run_order):
            fh.write("%d %s\n" % (pos, case))

    # self-check: pooled image segments must equal the per-case images
    image_lines = image_path.read_text().splitlines()
    if len(image_lines) != total:
        raise AssertionError("pool image line count mismatch")
    for case in layout_order:
        for i, row in enumerate(all_rows[case]):
            word = int(image_lines[bases[case] + i], 16)
            if decode_e0_word(word) != row:
                raise AssertionError("pool image mismatch: %s row %d" % (case, i))

    return {
        "image": str(image_path.relative_to(ROOT)),
        "meta": str(meta_path.relative_to(ROOT)),
        "map": str(map_path.relative_to(ROOT)),
        "total_words": total,
        "layout_order": layout_order,
        "run_order": run_order,
        "programs": [
            {"pos": pos, "case": case, "base": bases[case], "len": len(all_rows[case])}
            for pos, case in enumerate(run_order)
        ],
    }


def main():
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "batch": 1,
        "priority_strategy": "index",
        "schedule_family": {"e0": "max5", "note": "E0/E1=max5, E2=max4, E3/E4=max2"},
        "cases": [],
    }
    all_rows = {}
    all_rows4 = {}
    all_rows2 = {}
    for case in CASES:
        mode, cycles, src = pick_schedule(case)
        rows = parse_schedule(src / "schedule.txt")
        validate_schedule(case, rows)
        entry = write_case(case, mode, rows)
        entry["source_schedule"] = str(src.relative_to(ROOT))
        entry["files"]["golden_raw_issue5"] = str(
            (DATA_ROOT / case / "golden_raw_issue5.txt").relative_to(ROOT))
        entry["e1"] = write_case_e1(case, rows)
        # E2: max-4 family schedule (same mode-selection rule, index priority)
        mode4, cycles4, src4 = pick_schedule(case, "issue4")
        rows4 = parse_schedule(src4 / "schedule.txt")
        validate_schedule(case, rows4)
        entry["e2"] = write_case_e2(case, rows4)
        entry["e2"]["source_schedule"] = str(src4.relative_to(ROOT))
        entry["e2"]["mode"] = mode4
        entry["e2"]["cycles"] = cycles4
        # E3: max-2 family schedule
        mode2, cycles2, src2 = pick_schedule(case, "issue2")
        rows2 = parse_schedule(src2 / "schedule.txt")
        validate_schedule(case, rows2)
        entry["e3"] = write_case_e3(case, rows2)
        entry["e3"]["source_schedule"] = str(src2.relative_to(ROOT))
        entry["e3"]["mode"] = mode2
        entry["e3"]["cycles"] = cycles2
        # E4: same max-2 family, grouped four-lane encoding
        entry["e4"] = write_case_e4(case, rows2)
        entry["e4"]["source_schedule"] = entry["e3"]["source_schedule"]
        entry["e4"]["mode"] = mode2
        entry["e4"]["cycles"] = cycles2
        manifest["cases"].append(entry)
        all_rows[case] = rows
        all_rows4[case] = rows4
        all_rows2[case] = rows2
        print("[gen] %s: T5=%d T4=%d T2=%d  e1_events=%s  e2_lanes=%s  e3_lanes=%s  e4_lanes=%s"
              % (case, cycles, cycles4, cycles2, entry["e1"]["slot_events"],
                 entry["e2"]["lane_depths"], entry["e3"]["lane_depths"],
                 entry["e4"]["lane_depths"]))

    cb_path = emit_pair_codebook()
    print("[gen] codebook -> %s" % cb_path.relative_to(ROOT))

    manifest["pool"] = gen_pool(all_rows)
    print("[gen] pool: total=%d words, run order %s"
          % (manifest["pool"]["total_words"], " -> ".join(manifest["pool"]["run_order"])))

    manifest["pool_e1"] = gen_pool_e1(all_rows)
    print("[gen] pool_e1: config=%d words, slot totals=%s"
          % (manifest["pool_e1"]["config_total"], manifest["pool_e1"]["slot_totals"]))

    manifest["pool_e2"] = gen_pool_e2(all_rows4)
    print("[gen] pool_e2: config=%d words, lane totals=%s"
          % (manifest["pool_e2"]["config_total"], manifest["pool_e2"]["lane_totals"]))

    manifest["pool_e3"] = gen_pool_e3(all_rows2)
    print("[gen] pool_e3: config=%d words, lane totals=%s"
          % (manifest["pool_e3"]["config_total"], manifest["pool_e3"]["lane_totals"]))

    manifest["pool_e4"] = gen_pool_e4(all_rows2)
    print("[gen] pool_e4: config=%d words, lane totals=%s"
          % (manifest["pool_e4"]["config_total"], manifest["pool_e4"]["lane_totals"]))

    manifest_path = DATA_ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print("[gen] manifest -> %s" % manifest_path.relative_to(ROOT))
    print("[gen] all self-checks passed")


if __name__ == "__main__":
    sys.exit(main())

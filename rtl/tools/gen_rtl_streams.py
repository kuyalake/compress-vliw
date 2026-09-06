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
DATA_ROOT = ROOT / "rtl" / "data"

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


def pick_schedule(case):
    """Among candidate modes (index priority), pick min cycles; tie -> lower mode."""
    spec = CASES[case]
    best = None
    for mode in spec["modes"]:
        d = ISSUE5_ROOT / ("%s_y%d_mode%d_index" % (case, spec["y"], mode))
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
    for case in CASES:
        mode, cycles, src = pick_schedule(case)
        rows = parse_schedule(src / "schedule.txt")
        validate_schedule(case, rows)
        entry = write_case(case, mode, rows)
        entry["source_schedule"] = str(src.relative_to(ROOT))
        entry["files"]["golden_raw_issue5"] = str(
            (DATA_ROOT / case / "golden_raw_issue5.txt").relative_to(ROOT))
        entry["e1"] = write_case_e1(case, rows)
        manifest["cases"].append(entry)
        all_rows[case] = rows
        print("[gen] %s: mode=%d T=%d  (%s)  e1_events=%s"
              % (case, mode, cycles, src.name, entry["e1"]["slot_events"]))

    manifest["pool"] = gen_pool(all_rows)
    print("[gen] pool: total=%d words, run order %s"
          % (manifest["pool"]["total_words"], " -> ".join(manifest["pool"]["run_order"])))

    manifest["pool_e1"] = gen_pool_e1(all_rows)
    print("[gen] pool_e1: config=%d words, slot totals=%s"
          % (manifest["pool_e1"]["config_total"], manifest["pool_e1"]["slot_totals"]))

    manifest_path = DATA_ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print("[gen] manifest -> %s" % manifest_path.relative_to(ROOT))
    print("[gen] all self-checks passed")


if __name__ == "__main__":
    sys.exit(main())

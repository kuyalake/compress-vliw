#!/usr/bin/env python3
"""Generate RTL data (memh + golden + meta + map) for the three model pools
(BERT / LLaMA / SD-UNet) x three schemes (E0 uncompressed / E1 Candidate A /
E2 4-slot), from the saved schedules of the model-pool study.

Layout per pool (rtl/data_model_pools/<pool>/):
  e0_instr171.memh, e0_meta.hex, e0_map.txt
  e1_config5.memh, e1_slot{0..4}.memh, e1_meta.hex, e1_map.txt
  e2_config5.memh, e2_lane{0..3}.memh, e2_meta.hex, e2_map.txt
  golden/<func>/golden.txt   (hold-semantics golden per program)

Pool = set of programs (the model's nonlinear functions), each run by
descriptor {base, len} switching (front-end reset between programs).

Run:  python3 experiments/gen_model_pool_rtl_data.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY_OUT = ROOT / "analysis_output_model_pool_2026-09-08"
SCHED = STUDY_OUT / "schedules"
DATA_ROOT = ROOT / "rtl" / "data_model_pools"

POOLS = {
    "BERT": [("softmax", 512), ("layernorm", 768), ("bias_gelu", 3072),
             ("tanh", 768)],
    "LLaMA": [("rmsnorm", 4096), ("softmax", 4096), ("swiglu", 11008)],
    "SD-UNet": [("groupnorm", 1280), ("silu", 1280), ("layernorm", 768),
                ("softmax", 1024), ("geglu", 3072)],
}

# OP field masks inside each 34-bit container (load, store, vector, scalar, sfu)
OP_MASKS = (0b11, 0b11, 0b1111, 0b1111, 0b1111)


def parse_schedule(path):
    """174-bit hex word -> rows [load, store, vector, scalar, sfu, eop]."""
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        p = int(line, 16)
        control = p & 0xF
        p >>= 4
        slots = []
        for _ in range(5):
            slots.append(p & ((1 << 34) - 1))
            p >>= 34
        rows.append(list(reversed(slots)) + [control & 1])
    return rows


def gen_golden(rows):
    """Hold semantics: invalid slot -> last valid container with OP zeroed."""
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


# ---- E0: uncompressed 171-bit ----
def e0_word(row):
    load, store, vector, scalar, sfu, eop = row
    return ((load << 137) | (store << 103) | (vector << 69) | (scalar << 35)
            | (sfu << 1) | eop)


# ---- E1: Candidate A (5-bit mask + 5 dedicated slot streams) ----
def encode_e1(rows):
    config = []
    streams = [[], [], [], [], []]
    for row in rows[:-1]:  # exclude EOP row
        mask = 0
        for s in range(5):
            if row[s] != 0:
                mask |= 1 << s
                streams[s].append(row[s])
        config.append(mask)
    return config, streams


# ---- E2: 4-slot (5-bit mask + phase striping onto 4 lanes) ----
def encode_e2(rows):
    config = []
    lanes = [[], [], [], []]
    phase = 0
    for row in rows:
        if row[5] == 1:
            config.append(31)
            continue
        active = [s for s in range(5) if row[s] != 0]
        if len(active) > 4:
            raise AssertionError("E2: schedule exceeds four active slots")
        mask = sum(1 << s for s in active)
        if mask == 31:
            raise AssertionError("E2: five-active mask collides with EOP")
        for rank, s in enumerate(active):
            lanes[(phase + rank) % 4].append(row[s])
        config.append(mask)
        phase = (phase + len(active)) % 4
    return config, lanes


def write_lines(path, values, fmt):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for v in values:
            fh.write((fmt % v) + "\n")


def main():
    results = json.loads((STUDY_OUT / "model_pool_compression_results.json").read_text())
    mode_of = {(w["function"], w["y"]): w["mode"] for w in results["work_items"]}

    # load schedules per work item
    rows5 = {}  # issue5 (E0/E1)
    rows4 = {}  # issue4 (E2)
    for (func, y), mode in mode_of.items():
        d5 = SCHED / ("%s_y%d_mode%d_issue5" % (func, y, mode)) / "schedule.txt"
        d4 = SCHED / ("%s_y%d_mode%d_issue4" % (func, y, mode)) / "schedule.txt"
        rows5[(func, y)] = parse_schedule(d5)
        rows4[(func, y)] = parse_schedule(d4)

    for pool, items in POOLS.items():
        pdir = DATA_ROOT / pool
        gdir = pdir / "golden"
        n = len(items)

        # ---------- E0 ----------
        image = []
        meta = [n]
        bases = {}
        base = 0
        for func, y in items:
            rows = rows5[(func, y)]
            bases[(func, y)] = base
            base += len(rows)
            for row in rows:
                image.append(e0_word(row))
        meta.append(base)  # total words
        for func, y in items:  # run order = pool order
            meta += [bases[(func, y)], len(rows5[(func, y)])]
        write_lines(pdir / "e0_instr171.memh", image, "%043x")
        write_lines(pdir / "e0_meta.hex", meta, "%x")
        write_lines(pdir / "e0_map.txt",
                    ["%d %s" % (i, f) for i, (f, y) in enumerate(items)],
                    "%s")
        # golden per program per schedule family:
        #   golden_issue5.txt from the max-5 schedule (for E0/E1),
        #   golden_issue4.txt from the max-4 schedule (for E2).
        for func, y in items:
            for fam, rows in (("issue5", rows5), ("issue4", rows4)):
                golden = gen_golden(rows[(func, y)])
                write_lines(gdir / func / ("golden_%s.txt" % fam),
                            [" ".join("%09x" % c for c in g[:5]) + " %x" % g[5]
                             for g in golden], "%s")

        # ---------- E1 ----------
        cfg_image = []
        slot_image = [[], [], [], [], []]
        cfg_bases = {}
        slot_bases = {(func, y): [] for func, y in items}
        cb = 0
        e1_cb = 0
        sb = [0] * 5
        for func, y in items:
            config, streams = encode_e1(rows5[(func, y)])
            cfg_bases[(func, y)] = cb
            cb += len(config)
            e1_cb += len(config)
            cfg_image += config
            for s in range(5):
                slot_bases[(func, y)].append(sb[s])
                sb[s] += len(streams[s])
                slot_image[s] += streams[s]
        meta = [n, cb] + sb
        for func, y in items:
            meta += [cfg_bases[(func, y)], len(rows5[(func, y)])] + \
                    slot_bases[(func, y)]
        write_lines(pdir / "e1_config5.memh", cfg_image, "%02x")
        for s in range(5):
            write_lines(pdir / ("e1_slot%d.memh" % s), slot_image[s], "%09x")
        write_lines(pdir / "e1_meta.hex", meta, "%x")
        write_lines(pdir / "e1_map.txt",
                    ["%d %s" % (i, f) for i, (f, y) in enumerate(items)], "%s")

        # ---------- E2 ----------
        cfg_image = []
        lane_image = [[], [], [], []]
        cfg_bases = {}
        lane_bases = {(func, y): [] for func, y in items}
        cb = 0
        lb = [0] * 4
        for func, y in items:
            config, lanes = encode_e2(rows4[(func, y)])
            cfg_bases[(func, y)] = cb
            cb += len(config)
            cfg_image += config
            for l in range(4):
                lane_bases[(func, y)].append(lb[l])
                lb[l] += len(lanes[l])
                lane_image[l] += lanes[l]
        meta = [n, cb] + lb
        for func, y in items:
            meta += [cfg_bases[(func, y)], len(rows4[(func, y)])] + \
                    lane_bases[(func, y)]
        write_lines(pdir / "e2_config5.memh", cfg_image, "%02x")
        for l in range(4):
            write_lines(pdir / ("e2_lane%d.memh" % l), lane_image[l], "%09x")
        write_lines(pdir / "e2_meta.hex", meta, "%x")
        write_lines(pdir / "e2_map.txt",
                    ["%d %s" % (i, f) for i, (f, y) in enumerate(items)], "%s")

        print("[gen] %s: E0 %d words | E1 cfg=%d slots=%s | E2 cfg=%d lanes=%s"
              % (pool, base, e1_cb, [len(slot_image[s]) for s in range(5)],
                 cb, [len(lane_image[l]) for l in range(4)]))

    print("[gen] done -> %s" % DATA_ROOT.relative_to(ROOT))


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Bit-exact roundtrip verification for the model-pool compression study.

Reads each work item's saved issue5/issue4 schedules, encodes them with the
Candidate A (mask + 5 dedicated slot streams) and 4-slot (mask + phase-striped
4 lanes) formats, decodes, and checks per-cycle per-bit equality with the
original schedule.

Run:  python3 experiments/verify_model_pool.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis_output_model_pool_2026-09-08"
SCHED = OUT / "schedules"


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


# ---- Candidate A ----
def encode_a(rows):
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


def decode_a(config, streams):
    rows = []
    pos = [0] * 5
    for mask in config:
        row = [0] * 5
        for s in range(5):
            if (mask >> s) & 1:
                row[s] = streams[s][pos[s]]
                pos[s] += 1
        rows.append(row + [0])
    rows.append([0, 0, 0, 0, 0, 1])
    return rows


# ---- 4-slot ----
def encode_4(rows):
    config = []
    lanes = [[], [], [], []]
    phase = 0
    for row in rows:
        if row[5] == 1:
            config.append(31)
            continue
        active = [s for s in range(5) if row[s] != 0]
        assert len(active) <= 4, "4-slot: schedule exceeds four active slots"
        mask = sum(1 << s for s in active)
        assert mask != 31, "4-slot: five-active mask collides with EOP"
        for rank, s in enumerate(active):
            lanes[(phase + rank) % 4].append(row[s])
        config.append(mask)
        phase = (phase + len(active)) % 4
    return config, lanes


def decode_4(config, lanes):
    rows = []
    pos = [0] * 4
    phase = 0
    for code in config:
        if code == 31:
            rows.append([0, 0, 0, 0, 0, 1])
            continue
        active = [s for s in range(5) if (code >> s) & 1]
        row = [0] * 5
        for rank, s in enumerate(active):
            lane = (phase + rank) % 4
            row[s] = lanes[lane][pos[lane]]
            pos[lane] += 1
        rows.append(row + [0])
        phase = (phase + len(active)) % 4
    return rows


def main():
    results = json.loads((OUT / "model_pool_compression_results.json").read_text())
    work = results["work_items"]
    all_ok = True
    for w in work:
        func, y, mode = w["function"], w["y"], w["mode"]
        for issue, tag in ((5, "A"), (4, "4slot")):
            path = SCHED / ("%s_y%d_mode%d_issue%d" % (func, y, mode, issue)) / "schedule.txt"
            rows = parse_schedule(path)
            if tag == "A":
                config, streams = encode_a(rows)
                dec = decode_a(config, streams)
            else:
                config, lanes = encode_4(rows)
                dec = decode_4(config, lanes)
            ok = (dec == rows)
            all_ok = all_ok and ok
            print("  %-10s y=%-6d %-6s issue%d  %s"
                  % (func, y, tag, issue, "OK" if ok else "MISMATCH"))
    print("ALL BIT-EXACT" if all_ok else "SOME MISMATCH")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

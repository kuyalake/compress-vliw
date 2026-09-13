#!/usr/bin/env python3
"""Generate E2 five-lane RTL data for the three model pools (plan 5).

Writes, per pool (BERT / SD-UNet / LLaMA) under rtl/data_model_pools/<pool>/:
  e2_5_config5.memh  - 5-bit mask per real execution cycle (implicit EOP)
  e2_5_lane0..4.memh - five 34-bit phase-striped payload lanes
  e2_5_meta.hex      - [N, cfg_total, lane_total0..4, then per program in
                        pool order: cfg_base, prog_len, lane_base0..4]
  e2_5_map.txt       - "<pos> <function>" per line (golden reuse:
                        golden/<function>/golden_issue5.txt)

The encoder is imported from experiments/e2_five_lane_model_pool_study
(single source of truth; that study already reproduces plan Table 5/6).
Golden references are NOT regenerated: the existing
rtl/data_model_pools/<pool>/golden/<func>/golden_issue5.txt are reused
(verified identical to a fresh max-5 hold-semantics golden).

Python >= 3.9.  No third-party packages.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # compress-vliw/
sys.path.insert(0, str(ROOT / "experiments"))
from e2_five_lane_model_pool_study_2026_09_13 import (  # noqa: E402
    POOLS, parse_schedule, validate_schedule, encode_e2_5, decode_e2_5,
    SCHED_ROOT, RESULTS_JSON,
)

OUT = ROOT / "rtl" / "data_model_pools"


def mode_of():
    j = json.loads(RESULTS_JSON.read_text())
    return {(w["function"], w["y"]): w["mode"] for w in j["work_items"]}


def main():
    mode_map = mode_of()
    # encode every distinct work item once
    enc = {}
    for items in POOLS.values():
        for func, y in items:
            if (func, y) in enc:
                continue
            mode = mode_map[(func, y)]
            d = SCHED_ROOT / ("%s_y%d_mode%d_issue5" % (func, y, mode))
            rows = parse_schedule(d / "schedule.txt")
            validate_schedule("%s_y%d" % (func, y), rows)
            config, lanes = encode_e2_5(rows)
            if decode_e2_5(config, lanes) != rows:
                raise AssertionError("E2-5 roundtrip mismatch: %s y%d"
                                     % (func, y))
            enc[(func, y)] = (config, lanes, len(rows))

    for pool_name, items in POOLS.items():
        pdir = OUT / pool_name
        pdir.mkdir(parents=True, exist_ok=True)

        cfg_total = 0
        lane_totals = [0] * 5
        meta_prog = []
        for func, y in items:
            config, lanes, cycles = enc[(func, y)]
            cfg_base = cfg_total
            cfg_total += len(config)
            lane_bases = []
            for l in range(5):
                lane_bases.append(lane_totals[l])
                lane_totals[l] += len(lanes[l])
            meta_prog.append((func, y, cfg_base, cycles, lane_bases))

        with (pdir / "e2_5_config5.memh").open("w") as fh:
            for func, y in items:
                for mask in enc[(func, y)][0]:
                    fh.write("%02x\n" % mask)
        for l in range(5):
            with (pdir / ("e2_5_lane%d.memh" % l)).open("w") as fh:
                for func, y in items:
                    for word in enc[(func, y)][1][l]:
                        fh.write("%09x\n" % word)

        with (pdir / "e2_5_meta.hex").open("w") as fh:
            fh.write("%x\n" % len(items))
            fh.write("%x\n" % cfg_total)
            for l in range(5):
                fh.write("%x\n" % lane_totals[l])
            for func, y, cfg_base, cycles, lane_bases in meta_prog:
                fh.write("%x\n" % cfg_base)
                fh.write("%x\n" % cycles)          # prog_len = T (incl. EOP)
                for l in range(5):
                    fh.write("%x\n" % lane_bases[l])

        with (pdir / "e2_5_map.txt").open("w") as fh:
            for pos, (func, y) in enumerate(items):
                fh.write("%d %s\n" % (pos, func))

        # self-check: pool segments must equal per-program encodings
        cfg_lines = (pdir / "e2_5_config5.memh").read_text().splitlines()
        lane_lines = [(pdir / ("e2_5_lane%d.memh" % l)).read_text().splitlines()
                      for l in range(5)]
        for func, y, cfg_base, cycles, lane_bases in meta_prog:
            config, lanes, _ = enc[(func, y)]
            seg = cfg_lines[cfg_base:cfg_base + len(config)]
            assert [int(x, 16) for x in seg] == config, \
                "config segment mismatch %s %s" % (pool_name, func)
            for l in range(5):
                seg = lane_lines[l][lane_bases[l]:lane_bases[l] + len(lanes[l])]
                assert [int(x, 16) for x in seg] == lanes[l], \
                    "lane %d segment mismatch %s %s" % (l, pool_name, func)
        print("[gen e2_5] %-8s config=%d lane_totals=%s"
              % (pool_name, cfg_total, lane_totals))

    print("[gen e2_5] all pool self-checks passed")


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Generate E2-3 / E2-2 RTL data for the three model pools.

Companion to rtl/tools/gen_e2_five_lane_streams.py (E2-5).  Same striping
scheme and pool layout, parameterised lane count:

  per pool (BERT / SD-UNet / LLaMA) under rtl/data_model_pools/<pool>/:
    e2_3_config5.memh        - 5-bit mask per real execution cycle (max-3)
    e2_3_lane0..2.memh       - three 34-bit phase-striped payload lanes
    e2_3_meta.hex            - [N, cfg_total, lane_total0..2, then per program
                                in pool order: cfg_base, prog_len, lane_base0..2]
    e2_3_map.txt             - "<pos> <function>" per line
    (same naming with the e2_2_ prefix for the max-2 / two-lane variant)

  golden (hold semantics) per program, regenerated from the NEW max-3 / max-2
  schedules (the max-5 golden_issue5.txt does NOT apply here):
    golden/<function>/golden_issue3.txt
    golden/<function>/golden_issue2.txt

The encoder is imported from experiments/e2_lane23_model_pool_study_2026_09_16
(single source of truth; that study already validated roundtrips and pool
capacities).  Schedules come from
analysis_output_model_pool_2026-09-08/schedules/<func>_y<y>_mode<m>_issue<w>/.

Run:  PYTHONPATH=".python-deps" python3 rtl/tools/gen_e2_lane23_streams.py
Python >= 3.9.  No third-party packages beyond the study imports.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # compress-vliw/
sys.path.insert(0, str(ROOT / "experiments"))
from e2_five_lane_model_pool_study_2026_09_13 import (  # noqa: E402
    POOLS, parse_schedule, validate_schedule, gen_golden,
    SCHED_ROOT, RESULTS_JSON,
)
from e2_lane23_model_pool_study_2026_09_16 import (  # noqa: E402
    encode_e2_n, decode_e2_n, schedule_path,
)

OUT = ROOT / "rtl" / "data_model_pools"
WIDTHS = (3, 2)                     # issue width == lane count


def mode_of():
    j = json.loads(RESULTS_JSON.read_text())
    return {(w["function"], w["y"]): w["mode"] for w in j["work_items"]}


def main():
    mode_map = mode_of()
    # encode every distinct work item once per issue width
    enc = {w: {} for w in WIDTHS}
    for w in WIDTHS:
        for items in POOLS.values():
            for func, y in items:
                if (func, y) in enc[w]:
                    continue
                mode = mode_map[(func, y)]
                rows = parse_schedule(schedule_path(func, y, mode, w)
                                      / "schedule.txt")
                validate_schedule("%s_y%d_issue%d" % (func, y, w), rows)
                config, lanes = encode_e2_n(rows, w)
                if decode_e2_n(config, lanes, w) != rows:
                    raise AssertionError("E2-%d roundtrip mismatch: %s y%d"
                                         % (w, func, y))
                enc[w][(func, y)] = (config, lanes, rows)

    for w in WIDTHS:
        tag = "e2_%d" % w
        for pool_name, items in POOLS.items():
            pdir = OUT / pool_name
            pdir.mkdir(parents=True, exist_ok=True)

            cfg_total = 0
            lane_totals = [0] * w
            meta_prog = []
            for func, y in items:
                config, lanes, rows = enc[w][(func, y)]
                cfg_base = cfg_total
                cfg_total += len(config)
                lane_bases = []
                for l in range(w):
                    lane_bases.append(lane_totals[l])
                    lane_totals[l] += len(lanes[l])
                meta_prog.append((func, y, cfg_base, len(rows), lane_bases))

            with (pdir / ("%s_config5.memh" % tag)).open("w") as fh:
                for func, y in items:
                    for mask in enc[w][(func, y)][0]:
                        fh.write("%02x\n" % mask)
            for l in range(w):
                with (pdir / ("%s_lane%d.memh" % (tag, l))).open("w") as fh:
                    for func, y in items:
                        for word in enc[w][(func, y)][1][l]:
                            fh.write("%09x\n" % word)

            with (pdir / ("%s_meta.hex" % tag)).open("w") as fh:
                fh.write("%x\n" % len(items))
                fh.write("%x\n" % cfg_total)
                for l in range(w):
                    fh.write("%x\n" % lane_totals[l])
                for func, y, cfg_base, cycles, lane_bases in meta_prog:
                    fh.write("%x\n" % cfg_base)
                    fh.write("%x\n" % cycles)      # prog_len = T (incl. EOP)
                    for l in range(w):
                        fh.write("%x\n" % lane_bases[l])

            with (pdir / ("%s_map.txt" % tag)).open("w") as fh:
                for pos, (func, y) in enumerate(items):
                    fh.write("%d %s\n" % (pos, func))

            # golden (hold semantics) from the NEW max-w schedule
            for func, y in items:
                golden = gen_golden(enc[w][(func, y)][2])
                gdir = pdir / "golden" / func
                gdir.mkdir(parents=True, exist_ok=True)
                with (gdir / ("golden_issue%d.txt" % w)).open("w") as fh:
                    for grow in golden:
                        fh.write(" ".join("%09x" % c for c in grow[:5])
                                 + " %x\n" % grow[5])

            # self-check: pool segments must equal per-program encodings
            cfg_lines = (pdir / ("%s_config5.memh" % tag)).read_text() \
                .splitlines()
            lane_lines = [(pdir / ("%s_lane%d.memh" % (tag, l))).read_text()
                          .splitlines() for l in range(w)]
            for func, y, cfg_base, cycles, lane_bases in meta_prog:
                config, lanes, _ = enc[w][(func, y)]
                seg = cfg_lines[cfg_base:cfg_base + len(config)]
                assert [int(x, 16) for x in seg] == config, \
                    "config segment mismatch %s %s issue%d" \
                    % (pool_name, func, w)
                for l in range(w):
                    seg = lane_lines[l][lane_bases[l]:
                                        lane_bases[l] + len(lanes[l])]
                    assert [int(x, 16) for x in seg] == lanes[l], \
                        "lane %d segment mismatch %s %s issue%d" \
                        % (l, pool_name, func, w)
            print("[gen %s] %-8s config=%d lane_totals=%s"
                  % (tag, pool_name, cfg_total, lane_totals))

    print("[gen] all pool self-checks passed (e2_3 + e2_2)")


if __name__ == "__main__":
    sys.exit(main())

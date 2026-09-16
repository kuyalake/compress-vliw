#!/usr/bin/env python3
"""E2 lane-sweep supplementary study: E2-3 (max-3) and E2-2 (max-2).

Companion to experiments/e2_five_lane_model_pool_study_2026_09_13.py (E2-5).
The E2 striping scheme is UNCHANGED (5-bit mask per cycle, phase-rotated
striping onto shared 34-bit physical lanes, implicit EOP via prog_len); the
target operation pool is UNCHANGED (the 12 programs of BERT / SD-UNet /
LLaMA).  The only change is the scheduler's max concurrent issue slots:
MAX_ISSUE_SLOTS=3 -> three shared lanes (mod-3 phase), and
MAX_ISSUE_SLOTS=2 -> two shared lanes (mod-2 phase).

Per the confirmed experiment setup:
  * each program keeps the mode selected at max-5 (control variable: only
    the issue-width limit changes), same convention as the 4-slot study;
  * schedules are run fresh at issue3/issue2 and stored next to the
    existing issue5 schedules under
    analysis_output_model_pool_2026-09-08/schedules/;

This script (software part):
  * runs the scheduler at issue3/issue2 for the 12 pool programs,
  * encodes E2-3 / E2-2 per program (phase resets to 0 at program start),
  * validates bit-exact encode->decode roundtrip per program,
  * checks payload totals are schedule-invariant (DAG is fixed),
  * runs the exhaustive mask x phase decode checks
    (E2-3: 26 legal masks x 3 phases = 78 states;
     E2-2: 16 legal masks x 2 phases = 32 states),
  * aggregates the three pools and reports per-pool capacity plus the
    unified-max physical capacity for EVERY issue width
    (E0 / E1-uniform / E2-w all on the same max-w schedule, w in {5,3,2}),
  * cross-checks the w=5 numbers against plan Table 5/6.

Outputs:
  analysis_output_e2_lane23_2026-09-16/e2_lane23_results.json

Run:  PYTHONPATH=".python-deps" python3 experiments/e2_lane23_model_pool_study_2026_09_16.py
Python >= 3.9.
"""

import contextlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # compress-vliw/
sys.path.insert(0, str(ROOT / "experiments"))

from e2_five_lane_model_pool_study_2026_09_13 import (  # noqa: E402
    POOLS, SLOT_BITS, parse_schedule, validate_schedule,
    pow2ceil, exhaustive_mask_phase_check,
    SCHED_ROOT, RESULTS_JSON, PLAN_TABLE5, PLAN_TABLE6,
)
from model_pool_compression_study import sched, SCHED_KW, X  # noqa: E402

OUT_ROOT = ROOT / "analysis_output_e2_lane23_2026-09-16"

ISSUE_WIDTHS = (5, 3, 2)        # 5 = existing E2-5 schedules (read from disk)
NLANES = {5: 5, 3: 3, 2: 2}


# ---------------------------------------------------------------------------
# scheduling (issue3 / issue2; issue5 already on disk)
# ---------------------------------------------------------------------------

def schedule_path(func, y, mode, issue):
    return SCHED_ROOT / ("%s_y%d_mode%d_issue%d" % (func, y, mode, issue))


def run_schedule(func, y, mode, issue):
    """Run the scheduler once at the given issue width (skips if present)."""
    out_dir = schedule_path(func, y, mode, issue)
    sched_txt = out_dir / "schedule.txt"
    if sched_txt.exists():
        rows = parse_schedule(sched_txt)
        return len(rows), rows, False
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "scheduler.log").open("w") as log:
        with contextlib.redirect_stdout(log):
            schedule, _, _ = sched.run_scheduler(
                FUNCTION=func, X=X, Y=y, mode=mode, MAX_ISSUE_SLOTS=issue,
                out_dir=str(out_dir), **SCHED_KW)
    rows = parse_schedule(sched_txt)
    return len(rows), rows, True


# ---------------------------------------------------------------------------
# E2-N codec: same striping scheme, parameterised lane count N
# ---------------------------------------------------------------------------

def encode_e2_n(rows, nlanes):
    """rows -> (config[T-1] masks, lanes[N]).  Identical scheme to E2-5 with
    the lane count generalised: rank r -> lane (phase+r) mod N;
    phase += popcount(mask) mod N.  Requires popcount <= N (guaranteed by the
    max-N schedule).  The all-NOP EOP row is dropped (implicit EOP)."""
    config = []
    lanes = [[] for _ in range(nlanes)]
    phase = 0
    for row in rows[:-1]:           # drop the trailing all-NOP EOP row
        active = [s for s in range(5) if row[s] != 0]
        if len(active) > nlanes:
            raise AssertionError("E2-%d: schedule exceeds %d active slots"
                                 % (nlanes, nlanes))
        mask = 0
        for s in active:
            mask |= 1 << s
        for rank, s in enumerate(active):
            lanes[(phase + rank) % nlanes].append(row[s])
        config.append(mask)
        phase = (phase + len(active)) % nlanes
    return config, lanes


def decode_e2_n(config, lanes, nlanes):
    """Software decode (self-check), mirrors the hardware pipeline."""
    rows = []
    pos = [0] * nlanes
    phase = 0
    for mask in config:
        active = [s for s in range(5) if (mask >> s) & 1]
        row = [0, 0, 0, 0, 0]
        for rank, s in enumerate(active):
            lane = (phase + rank) % nlanes
            row[s] = lanes[lane][pos[lane]]
            pos[lane] += 1
        rows.append(row + [0])
        phase = (phase + len(active)) % nlanes
    rows.append([0, 0, 0, 0, 0, 1])   # implicit EOP row
    if any(pos[l] != len(lanes[l]) for l in range(nlanes)):
        raise AssertionError("E2-%d decode: unconsumed lane events" % nlanes)
    return rows


def exhaustive_check(nlanes):
    """Legal-state exhaustive decode check.  For E2-N the legal masks are
    those with popcount <= N (max-N schedule), phase in 0..N-1:
      N=3: (1+5+10+10)=26 masks x 3 phases = 78 states
      N=2: (1+5+10)=16 masks x 2 phases = 32 states
    For every state verify: lane read count == popcount; at most one slot per
    lane per cycle; slot<->lane bijection; phase_next in range."""
    marker = lambda s: 0x100000000 + s   # distinct, fits 34 bit
    n_states = 0
    for mask in range(32):
        active = [s for s in range(5) if (mask >> s) & 1]
        k = len(active)
        if k > nlanes:
            continue                  # illegal under a max-N schedule
        for phase in range(nlanes):
            lanes = [[] for _ in range(nlanes)]
            for rank, s in enumerate(active):
                lanes[(phase + rank) % nlanes].append(marker(s))
            lane_pos = [0] * nlanes
            seen_lane = []
            row = [0] * 5
            for rank, s in enumerate(active):
                lane = (phase + rank) % nlanes
                seen_lane.append(lane)
                row[s] = lanes[lane][lane_pos[lane]]
                lane_pos[lane] += 1
            assert len(seen_lane) == k
            assert len(set(seen_lane)) == k, "two slots read same lane"
            for s in active:
                assert row[s] == marker(s), "slot %d wrong payload" % s
            assert 0 <= (phase + k) % nlanes <= nlanes - 1
            n_states += 1
    return n_states


# ---------------------------------------------------------------------------
# capacity helpers
# ---------------------------------------------------------------------------

def pool_capacity(enc, items, nlanes):
    """Aggregate one pool from per-program encodings (phase=0 per program)."""
    cfg_total = 0
    lane_totals = [0] * nlanes
    prog_meta = []
    for func, y in items:
        e = enc[(func, y)]
        cfg_base = cfg_total
        cfg_total += len(e["config"])
        lane_bases = []
        for l in range(nlanes):
            lane_bases.append(lane_totals[l])
            lane_totals[l] += len(e["lanes"][l])
        prog_meta.append(dict(prog="%s(y=%d)" % (func, y),
                              cfg_base=cfg_base, prog_len=e["cycles"],
                              lane_bases=lane_bases))
    return dict(n_programs=len(items), config_entries=cfg_total,
                payload_total=sum(lane_totals), lane_totals=lane_totals,
                longest_lane=max(lane_totals), programs=prog_meta)


def slot_event_totals(enc, items):
    st = [0] * 5
    for func, y in items:
        for row in enc[(func, y)]["rows"][:-1]:
            for s in range(5):
                if row[s] != 0:
                    st[s] += 1
    return st


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    wj = json.loads(RESULTS_JSON.read_text())
    mode_of = {(w["function"], w["y"]): w["mode"] for w in wj["work_items"]}
    work = sorted({(f, y) for items in POOLS.values() for f, y in items})

    # ---- [1/5] scheduling: issue3/issue2 fresh, issue5 from disk ----
    print("[1/5] scheduling 12 programs at max-3 / max-2 (mode = max-5 pick) ...")
    enc = {w: {} for w in ISSUE_WIDTHS}     # width -> (func,y) -> encoding
    for func, y in work:
        mode = mode_of[(func, y)]
        for w in ISSUE_WIDTHS:
            if w == 5:
                rows = parse_schedule(schedule_path(func, y, mode, 5)
                                      / "schedule.txt")
                fresh = False
            else:
                _, rows, fresh = run_schedule(func, y, mode, w)
            validate_schedule("%s_y%d_issue%d" % (func, y, w), rows)
            config, lanes = encode_e2_n(rows, NLANES[w])
            if decode_e2_n(config, lanes, NLANES[w]) != rows:
                raise AssertionError("E2-%d roundtrip mismatch: %s y%d"
                                     % (w, func, y))
            max_active = max(sum(1 for s in range(5) if r[s] != 0)
                             for r in rows[:-1])
            enc[w][(func, y)] = dict(config=config, lanes=lanes, rows=rows,
                                     cycles=len(rows), mode=mode,
                                     max_active=max_active)
            print("      %-10s y=%-6d mode=%d issue=%d  T=%-6d config=%-6d "
                  "lanes=%s max_active=%d%s"
                  % (func, y, mode, w, len(rows), len(config),
                     [len(l) for l in lanes], max_active,
                     " (new schedule)" if fresh else ""))

    # ---- payload totals must be schedule-invariant (DAG fixed) ----
    print("      checking payload totals are issue-width invariant ...")
    for func, y in work:
        ref = sum(len(l) for l in enc[5][(func, y)]["lanes"])
        for w in (3, 2):
            got = sum(len(l) for l in enc[w][(func, y)]["lanes"])
            if got != ref:
                raise AssertionError(
                    "payload total drift %s y%d: issue5=%d issue%d=%d"
                    % (func, y, ref, w, got))
    print("      payload totals identical across issue widths (as expected)")

    # ---- [2/5] exhaustive mask x phase checks ----
    print("[2/5] exhaustive decode checks ...")
    assert exhaustive_mask_phase_check()
    print("      E2-5: 160/160 states OK (sanity, original check)")
    for w in (3, 2):
        n = exhaustive_check(NLANES[w])
        print("      E2-%d: %d/%d states OK (legal masks x %d phases)"
              % (w, n, n, NLANES[w]))

    # ---- [3/5] pool aggregation per issue width ----
    print("[3/5] aggregating pools ...")
    report = {"issue_widths": {}, "capacity": {}, "plan_check_w5": {}}
    for w in ISSUE_WIDTHS:
        nlanes = NLANES[w]
        pools = {}
        for pool_name, items in POOLS.items():
            pools[pool_name] = pool_capacity(enc[w], items, nlanes)
            p = pools[pool_name]
            print("      w=%d %-8s: config=%d payload=%d lane_totals=%s "
                  "longest=%d cycles=%d"
                  % (w, pool_name, p["config_entries"], p["payload_total"],
                     p["lane_totals"], p["longest_lane"],
                     sum(enc[w][(f, y)]["cycles"] for f, y in items)))
        report["issue_widths"][w] = dict(nlanes=nlanes, pools=pools)

    # w=5 cross-check against plan Table 5 (must match the E2-5 study)
    for pool_name in POOLS:
        got = report["issue_widths"][5]["pools"][pool_name]
        want = PLAN_TABLE5[pool_name]
        ok = (got["config_entries"] == want["config"]
              and got["payload_total"] == want["payload"]
              and got["longest_lane"] == want["longest_lane"]
              and got["n_programs"] == want["nprog"])
        report["plan_check_w5"][pool_name] = ok
        print("      plan Table 5 w=5 %-8s: %s"
              % (pool_name, "MATCH" if ok else "MISMATCH"))
        if not ok:
            raise AssertionError("w=5 pool mismatch vs plan Table 5")

    # ---- [4/5] unified-max physical capacity per issue width ----
    print("[4/5] unified-max physical capacity (covers largest pool) ...")
    for w in ISSUE_WIDTHS:
        nlanes = NLANES[w]
        pools = report["issue_widths"][w]["pools"]
        max_cfg = max(pools[p]["config_entries"] for p in POOLS)
        max_lane = max(pools[p]["longest_lane"] for p in POOLS)
        max_cycles = max(sum(enc[w][(f, y)]["cycles"] for f, y in items)
                         for items in POOLS.values())
        slot_max = max(max(slot_event_totals(enc[w], items))
                       for items in POOLS.values())
        cfg_depth = pow2ceil(max_cfg)
        e0_depth = pow2ceil(max_cycles)
        e1_bank = pow2ceil(slot_max)
        e2_lane = pow2ceil(max_lane)
        cap = {
            "E0":         dict(bits=e0_depth * 171,
                               desc="1 x %d x 171" % e0_depth),
            "E1-uniform": dict(bits=cfg_depth * 5 + 5 * e1_bank * SLOT_BITS,
                               desc="1 x %d x 5 + 5 x %d x 34"
                                    % (cfg_depth, e1_bank)),
            "E2-%d" % w:  dict(bits=cfg_depth * 5
                                    + nlanes * e2_lane * SLOT_BITS,
                               desc="1 x %d x 5 + %d x %d x 34"
                                    % (cfg_depth, nlanes, e2_lane)),
        }
        report["capacity"][w] = dict(
            schemes=cap,
            meta=dict(cfg_depth=cfg_depth, e0_depth=e0_depth,
                      e1_bank_depth=e1_bank, e2_lane_depth=e2_lane,
                      max_cycles=max_cycles, max_cfg_entries=max_cfg,
                      max_longest_lane=max_lane, max_slot_total=slot_max))
        for k in ("E0", "E1-uniform", "E2-%d" % w):
            print("      w=%d %-11s %-30s = %9d bit"
                  % (w, k, cap[k]["desc"], cap[k]["bits"]))
    # w=5 cross-check against plan Table 6
    for k, ref in PLAN_TABLE6.items():
        got = report["capacity"][5]["schemes"][k]["bits"]
        if got != ref:
            raise AssertionError("w=5 capacity %s: got %d, plan %d"
                                 % (k, got, ref))
    print("      plan Table 6 w=5: MATCH (E0/E1-uniform/E2-5 all equal)")

    # ---- [5/5] per-program cycle table + summary ratios ----
    print("[5/5] per-program cycles (performance cost of issue limits) ...")
    prog_table = []
    for func, y in work:
        t5 = enc[5][(func, y)]["cycles"]
        t3 = enc[3][(func, y)]["cycles"]
        t2 = enc[2][(func, y)]["cycles"]
        prog_table.append(dict(func=func, y=y, mode=enc[5][(func, y)]["mode"],
                               T5=t5, T3=t3, T2=t2,
                               max_active5=enc[5][(func, y)]["max_active"]))
        print("      %-10s y=%-6d T5=%-6d T3=%-6d (%.1f%%) T2=%-6d (%.1f%%)"
              % (func, y, t5, t3, 100.0 * t3 / t5, t2, 100.0 * t2 / t5))
    report["programs"] = prog_table

    e25 = report["capacity"][5]["schemes"]["E2-5"]["bits"]
    for w in (3, 2):
        c = report["capacity"][w]["schemes"]
        e2w = c["E2-%d" % w]["bits"]
        print("      w=%d: E2-%d = %d bit = %.1f%% of E0(%d bit), "
              "%.1f%% of E1-uniform(%d bit); E2-%d vs E2-5 = %.1f%%"
              % (w, w, e2w, 100.0 * e2w / c["E0"]["bits"], c["E0"]["bits"],
                 100.0 * e2w / c["E1-uniform"]["bits"],
                 c["E1-uniform"]["bits"], w, 100.0 * e2w / e25))

    (OUT_ROOT / "e2_lane23_results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print("\n[done] results -> %s"
          % (OUT_ROOT / "e2_lane23_results.json").relative_to(ROOT))
    print("[done] all roundtrips + exhaustive + plan cross-checks passed")


if __name__ == "__main__":
    sys.exit(main())

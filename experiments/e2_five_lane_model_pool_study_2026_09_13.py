#!/usr/bin/env python3
"""E2 five-lane model-pool study.

Plan: plan/e2_five_lane_detailed_experiment_plan_2026-09-13.html

FRV-SFU-VLIW: 5 logical slots (LOAD/STORE/VECTOR/SCALAR/SFU), each a 34-bit
container; useful VLIW word = 5*34 + 1 EOP = 171 bit.  E2-5 keeps the original
max-5 schedule (five-slot concurrency allowed, mask 11111 is legal data) and
stripes valid payloads onto five shared physical 34-bit lanes with a running
phase; EOP is generated implicitly from prog_len (no in-band EOP code).

This script (software experiment, plan section 11 steps 1-4):
  * reads the existing max-5 schedules for the 12 pool programs,
  * encodes E2-5 per program (phase resets to 0 at each program start),
  * validates bit-exact encode->decode roundtrip per program,
  * runs the 32-mask x 5-phase = 160-state exhaustive decode check,
  * aggregates the three pools (BERT / SD-UNet / LLaMA) and reports the
    per-pool capacity (plan Table 5) and the unified-max physical capacity
    (plan Table 6),
  * writes per-pool Config/Lane/meta/map data files plus golden references.

Outputs:
  analysis_output_e2_five_lane_2026-09-13/e2_five_lane_results.json
  rtl/data/e2_5/<pool>/{e2_5_config5.memh, e2_5_lane0..4.memh,
                        e2_5_meta.hex, e2_5_map.txt, golden_issue5.txt per prog}

Python >= 3.9.  No third-party packages.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # compress-vliw/
SCHED_ROOT = ROOT / "analysis_output_model_pool_2026-09-08" / "schedules"
RESULTS_JSON = (ROOT / "analysis_output_model_pool_2026-09-08"
                / "model_pool_compression_results.json")
OUT_ROOT = ROOT / "analysis_output_e2_five_lane_2026-09-13"
DATA_ROOT = ROOT / "rtl" / "data" / "e2_5"

SLOT_BITS = 34
SLOT_NAMES = ("load", "store", "vector", "scalar", "sfu")
# OP field masks inside each 34-bit container (hold semantics)
OP_MASKS = (0b11, 0b11, 0b1111, 0b1111, 0b1111)

# pool -> [(function, y)], from model_pool_compression_study.py POOLS
POOLS = {
    "BERT":    [("softmax", 512), ("layernorm", 768), ("bias_gelu", 3072),
                ("tanh", 768)],
    "SD-UNet": [("groupnorm", 1280), ("silu", 1280), ("layernorm", 768),
                ("softmax", 1024), ("geglu", 3072)],
    "LLaMA":   [("rmsnorm", 4096), ("softmax", 4096), ("swiglu", 11008)],
}

# plan Table 5 (per-pool E2-5 capacity, phase=0 per program)
PLAN_TABLE5 = {
    "BERT":    dict(nprog=4, config=7663,  payload=7122,  longest_lane=1426),
    "SD-UNet": dict(nprog=5, config=11679, payload=13520, longest_lane=2705),
    "LLaMA":   dict(nprog=3, config=30701, payload=33104, longest_lane=6622),
}
# plan Table 6 (unified max physical config, covers the LLaMA pool)
PLAN_TABLE6 = {
    "E0":         5603328,   # 1 x 32768 x 171
    "E1-uniform": 2949120,   # 1 x 32768 x 5 + 5 x 16384 x 34
    "E2-5":       1556480,   # 1 x 32768 x 5 + 5 x 8192 x 34
}


# ---------------------------------------------------------------------------
# schedule reading (174-bit schedule.txt -> rows [load,store,vector,scalar,sfu,eop])
# ---------------------------------------------------------------------------

def parse_schedule(path):
    rows = []
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        packed = int(line, 16)
        if packed >> 174:
            raise ValueError("%s:%d exceeds 174 bits" % (path, lineno))
        control = packed & 0xF
        packed >>= 4
        slots_lsb = []
        for _ in range(5):
            slots_lsb.append(packed & ((1 << SLOT_BITS) - 1))
            packed >>= SLOT_BITS
        if packed:
            raise ValueError("%s:%d tail overflow" % (path, lineno))
        slots = list(reversed(slots_lsb))
        rows.append(slots + [control & 1])
    return rows


def validate_schedule(name, rows):
    if not rows:
        raise ValueError("%s: empty schedule" % name)
    for i, row in enumerate(rows):
        eop = row[5]
        if i == len(rows) - 1:
            if eop != 1 or any(row[:5]):
                raise ValueError("%s: last row must be all-NOP EOP" % name)
        elif eop != 0:
            raise ValueError("%s: row %d unexpected eop" % (name, i))


# ---------------------------------------------------------------------------
# E2-5 codec (plan section 4.3): five-lane phase striping, implicit EOP
# ---------------------------------------------------------------------------

def encode_e2_5(rows):
    """rows -> (config[T-1] masks, lanes[5]).

    Active slots ascending slot id; rank r -> lane (phase+r) mod 5;
    phase += popcount(mask) mod 5.  The all-NOP EOP row is dropped (implicit).
    mask 11111 (five active) is legal data.
    """
    config = []
    lanes = [[], [], [], [], []]
    phase = 0
    for row in rows[:-1]:           # drop the trailing all-NOP EOP row
        active = [s for s in range(5) if row[s] != 0]
        mask = 0
        for s in active:
            mask |= 1 << s
        for rank, s in enumerate(active):
            lanes[(phase + rank) % 5].append(row[s])
        config.append(mask)
        phase = (phase + len(active)) % 5
    return config, lanes


def decode_e2_5(config, lanes):
    """Software decode (self-check), mirrors the hardware pipeline."""
    rows = []
    pos = [0] * 5
    phase = 0
    for mask in config:
        active = [s for s in range(5) if (mask >> s) & 1]
        row = [0, 0, 0, 0, 0]
        for rank, s in enumerate(active):
            lane = (phase + rank) % 5
            row[s] = lanes[lane][pos[lane]]
            pos[lane] += 1
        rows.append(row + [0])
        phase = (phase + len(active)) % 5
    rows.append([0, 0, 0, 0, 0, 1])   # implicit EOP row
    if any(pos[l] != len(lanes[l]) for l in range(5)):
        raise AssertionError("E2-5 decode: unconsumed lane events")
    return rows


def exhaustive_mask_phase_check():
    """160-state check (plan 9.2): for every mask (32) x phase (5), decode a
    one-cycle 'instruction' with distinct marker payloads and verify the
    slot->lane mapping is a bijection consistent with the spec."""
    marker = lambda s: 0x100000000 + s   # distinct, fits 34 bit
    for mask in range(32):
        for phase in range(5):
            active = [s for s in range(5) if (mask >> s) & 1]
            k = len(active)
            # encode one cycle
            lanes = [[] for _ in range(5)]
            for rank, s in enumerate(active):
                lanes[(phase + rank) % 5].append(marker(s))
            # decode
            lane_pos = [0] * 5
            seen_lane = []
            row = [0] * 5
            for rank, s in enumerate(active):
                lane = (phase + rank) % 5
                seen_lane.append(lane)
                row[s] = lanes[lane][lane_pos[lane]]
                lane_pos[lane] += 1
            # checks: lane read count == popcount; lanes distinct; mapping exact
            assert len(seen_lane) == k
            assert len(set(seen_lane)) == k, "two slots read same lane"
            for s in active:
                assert row[s] == marker(s), "slot %d wrong payload" % s
            # phase update in range
            assert 0 <= (phase + k) % 5 <= 4
    return True


# ---------------------------------------------------------------------------
# golden (hold semantics) for later RTL verification
# ---------------------------------------------------------------------------

def gen_golden(rows):
    last = [0] * 5
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


# ---------------------------------------------------------------------------
# capacity helpers
# ---------------------------------------------------------------------------

def pow2ceil(n):
    return 1 << (n - 1).bit_length() if n > 1 else 1


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    DATA_ROOT.mkdir(parents=True, exist_ok=True)

    # work-item -> selected mode (from the existing model-pool results)
    wj = json.loads(RESULTS_JSON.read_text())
    mode_of = {(w["function"], w["y"]): w["mode"] for w in wj["work_items"]}

    # ---- per-program encode + roundtrip ----
    print("[1/4] encoding 12 programs (E2-5, max-5 schedule) ...")
    enc = {}            # (func,y) -> dict(config, lanes, rows, cycles)
    for func, y in sorted({(f, y) for items in POOLS.values() for f, y in items}):
        mode = mode_of[(func, y)]
        d = SCHED_ROOT / ("%s_y%d_mode%d_issue5" % (func, y, mode))
        rows = parse_schedule(d / "schedule.txt")
        validate_schedule("%s_y%d" % (func, y), rows)
        config, lanes = encode_e2_5(rows)
        if decode_e2_5(config, lanes) != rows:
            raise AssertionError("E2-5 roundtrip mismatch: %s y%d" % (func, y))
        enc[(func, y)] = dict(config=config, lanes=lanes, rows=rows,
                              cycles=len(rows), mode=mode)
        print("      %-10s y=%-6d mode=%d  T=%-6d config=%-6d lanes=%s"
              % (func, y, mode, len(rows), len(config),
                 [len(l) for l in lanes]))

    # ---- exhaustive mask x phase ----
    print("[2/4] 32-mask x 5-phase exhaustive decode check ...")
    assert exhaustive_mask_phase_check()
    print("      160/160 states OK")

    # ---- pool aggregation + capacity ----
    print("[3/4] aggregating pools ...")
    report = {"pools": {}, "capacity": {}, "plan_check": {}}
    for pool_name, items in POOLS.items():
        # layout order = POOLS order; per-program phase=0 (independent encode)
        cfg_total = 0
        lane_totals = [0] * 5
        prog_meta = []
        for func, y in items:
            e = enc[(func, y)]
            cfg_base = cfg_total
            cfg_total += len(e["config"])
            lane_bases = []
            for l in range(5):
                lane_bases.append(lane_totals[l])
                lane_totals[l] += len(e["lanes"][l])
            prog_meta.append(dict(prog="%s(y=%d)" % (func, y),
                                  cfg_base=cfg_base, prog_len=e["cycles"],
                                  lane_bases=lane_bases))
        payload_total = sum(lane_totals)
        longest_lane = max(lane_totals)
        report["pools"][pool_name] = dict(
            n_programs=len(items), config_entries=cfg_total,
            payload_total=payload_total, lane_totals=lane_totals,
            longest_lane=longest_lane, programs=prog_meta)
        print("      %-8s: progs=%d config=%d payload=%d lane_totals=%s longest=%d"
              % (pool_name, len(items), cfg_total, payload_total,
                 lane_totals, longest_lane))

    # ---- plan Table 5 cross-check ----
    print("[4/4] cross-checking plan Table 5 ...")
    for pool_name, items in POOLS.items():
        got = report["pools"][pool_name]
        want = PLAN_TABLE5[pool_name]
        ok = (got["config_entries"] == want["config"]
              and got["payload_total"] == want["payload"]
              and got["longest_lane"] == want["longest_lane"]
              and got["n_programs"] == want["nprog"])
        report["plan_check"][pool_name] = dict(
            match=ok,
            got=dict(config=got["config_entries"], payload=got["payload_total"],
                     longest_lane=got["longest_lane"]),
            want=want)
        print("      %-8s: %s" % (pool_name, "MATCH" if ok else "MISMATCH"),
              "got", report["plan_check"][pool_name]["got"], "want", want)

    # ---- unified-max physical capacity (plan Table 6) ----
    max_cfg = max(report["pools"][p]["config_entries"] for p in POOLS)
    max_lane = max(report["pools"][p]["longest_lane"] for p in POOLS)
    max_cycles = max(sum(enc[(f, y)]["cycles"] for (f, y) in items)
                     for items in POOLS.values())
    cfg_depth = pow2ceil(max_cfg)
    e0_depth = pow2ceil(max_cycles)
    # E1-uniform: per-slot bank depth = max over slots of pool slot-event total
    slot_totals_max = 0
    for pool_name, items in POOLS.items():
        st = [0] * 5
        for func, y in items:
            for row in enc[(func, y)]["rows"][:-1]:
                for s in range(5):
                    if row[s] != 0:
                        st[s] += 1
        slot_totals_max = max(slot_totals_max, max(st))
    e1_bank_depth = pow2ceil(slot_totals_max)
    e2_lane_depth = pow2ceil(max_lane)
    cap = {
        "E0":         dict(bits=e0_depth * 171,
                           desc="1 x %d x 171" % e0_depth),
        "E1-uniform": dict(bits=cfg_depth * 5 + 5 * e1_bank_depth * SLOT_BITS,
                           desc="1 x %d x 5 + 5 x %d x 34"
                                % (cfg_depth, e1_bank_depth)),
        "E2-5":       dict(bits=cfg_depth * 5 + 5 * e2_lane_depth * SLOT_BITS,
                           desc="1 x %d x 5 + 5 x %d x 34"
                                % (cfg_depth, e2_lane_depth)),
    }
    report["capacity"] = cap
    report["capacity_meta"] = dict(cfg_depth=cfg_depth, e0_depth=e0_depth,
                                   e1_bank_depth=e1_bank_depth,
                                   e2_lane_depth=e2_lane_depth,
                                   max_cycles=max_cycles)
    print("\n      unified-max physical capacity (covers largest pool):")
    for k in ("E0", "E1-uniform", "E2-5"):
        plan_ref = PLAN_TABLE6[k]
        got = cap[k]["bits"]
        print("      %-11s %-28s = %9d bit  (plan %9d, %s)"
              % (k, cap[k]["desc"], got, plan_ref,
                 "MATCH" if got == plan_ref else "diff"))
    e2 = cap["E2-5"]["bits"]
    print("      E2-5 vs E0 = %.1f%%, vs E1-uniform = %.1f%%"
          % (100.0 * e2 / cap["E0"]["bits"],
             100.0 * e2 / cap["E1-uniform"]["bits"]))

    # ---- write pool data files ----
    print("\n[gen] writing per-pool data files under %s ..." % DATA_ROOT)
    for pool_name, items in POOLS.items():
        pdir = DATA_ROOT / pool_name.lower().replace("-", "_")
        pdir.mkdir(parents=True, exist_ok=True)
        # config + lane images (layout order = POOLS order)
        with (pdir / "e2_5_config5.memh").open("w") as fh:
            for func, y in items:
                for mask in enc[(func, y)]["config"]:
                    fh.write("%02x\n" % mask)
        for l in range(5):
            with (pdir / ("e2_5_lane%d.memh" % l)).open("w") as fh:
                for func, y in items:
                    for word in enc[(func, y)]["lanes"][l]:
                        fh.write("%09x\n" % word)
        # meta: N, cfg_total, lane_totals(5), then per program in POOLS order:
        #       cfg_base, prog_len, lane_base0..4
        pm = report["pools"][pool_name]
        with (pdir / "e2_5_meta.hex").open("w") as fh:
            fh.write("%x\n" % len(items))
            fh.write("%x\n" % pm["config_entries"])
            for l in range(5):
                fh.write("%x\n" % pm["lane_totals"][l])
            for prog in pm["programs"]:
                fh.write("%x\n" % prog["cfg_base"])
                fh.write("%x\n" % prog["prog_len"])
                for l in range(5):
                    fh.write("%x\n" % prog["lane_bases"][l])
        with (pdir / "e2_5_map.txt").open("w") as fh:
            for pos, (func, y) in enumerate(items):
                fh.write("%d %s_y%d\n" % (pos, func, y))
        # golden (hold semantics) per program
        for func, y in items:
            golden = gen_golden(enc[(func, y)]["rows"])
            with (pdir / ("golden_%s_y%d.txt" % (func, y))).open("w") as fh:
                for grow in golden:
                    fh.write(" ".join("%09x" % c for c in grow[:5])
                             + " %x\n" % grow[5])
        print("      %-8s -> %s" % (pool_name, pdir.relative_to(ROOT)))

    # ---- pool-image self-check (segments must equal per-program encodings) ----
    for pool_name, items in POOLS.items():
        pdir = DATA_ROOT / pool_name.lower().replace("-", "_")
        cfg_lines = (pdir / "e2_5_config5.memh").read_text().splitlines()
        lane_lines = [(pdir / ("e2_5_lane%d.memh" % l)).read_text().splitlines()
                      for l in range(5)]
        pm = report["pools"][pool_name]
        for prog, (func, y) in zip(pm["programs"], items):
            e = enc[(func, y)]
            seg = cfg_lines[prog["cfg_base"]:
                            prog["cfg_base"] + len(e["config"])]
            assert [int(x, 16) for x in seg] == e["config"], \
                "config segment mismatch %s %s" % (pool_name, func)
            for l in range(5):
                seg = lane_lines[l][prog["lane_bases"][l]:
                                    prog["lane_bases"][l] + len(e["lanes"][l])]
                assert [int(x, 16) for x in seg] == e["lanes"][l], \
                    "lane %d segment mismatch %s %s" % (l, pool_name, func)

    (OUT_ROOT / "e2_five_lane_results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print("\n[done] results -> %s" % (OUT_ROOT / "e2_five_lane_results.json")
          .relative_to(ROOT))
    print("[done] all roundtrips + pool self-checks passed")


if __name__ == "__main__":
    sys.exit(main())

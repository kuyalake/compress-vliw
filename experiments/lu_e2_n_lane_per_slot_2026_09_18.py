#!/usr/bin/env python3
"""
E2-N per slot (user's "每个 slot 均匀分成 N 等分 lane"), exact stream mechanism
consistent with the repo's E2 (per-lane independent streams, rolling phase, NO padding):

  group g (width W_g, field width w_g, n_g fields) -> N lanes of width W_g/N.
  Cycle i: k_i valid fields (ascending id) -> lane (phase + rank) mod N;
  the field's w_g bits are appended to that lane's bitstream; phase += k_i mod N.
  Per-cycle per-lane delivery <= ceil(k_i/N)*w_g <= W_g/N = one word: feasible for any N.
  Lane depth (words) = ceil(lane_bits / (W_g/N)); pool depth = max over lanes.

wea raw 32b/cyc; mask M4 48b/cyc (op 16 shared with sel1, wea 32 = sel2 mask,
addr mask derived from sel1 values).
"""
import os, sys, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lu_e2_striping_study_2026_09_18 import load_matrix, MATS, LU

def p2(n):
    return 1 << max(0, (n - 1).bit_length())

def p2_tiled2(n):
    if n <= 1:
        return max(1, n)
    a = n.bit_length() - 1
    base = 1 << a
    return base if base == n else base + p2(n - base)

GROUPS = [("op", "op_v", 16, 5), ("sel1", "s1_v", 48, 5), ("sel2", "s2_v", 32, 4), ("addr", "ad_v", 32, 11)]

def simulate_lane_bits(per_cycle_counts, N):
    """field-granular round-robin; returns per-lane total bits (in fields)."""
    lanes = [0] * N
    phase = 0
    for k in per_cycle_counts:
        for r in range(k):
            lanes[(phase + r) % N] += 1
        phase = (phase + k) % N
    return lanes

out = {}
for mat in MATS:
    C, cycles, _ = load_matrix(mat)
    for N in (4, 8):
        pools = {}
        for g, key, nf, w in GROUPS:
            W = nf * w
            lw = W // N                      # lane width in bits
            fpw = lw // w                    # fields per lane word
            pc = [sum(cy[key]) for cy in cycles]
            lanes = simulate_lane_bits(pc, N)          # per-lane field counts
            depths = [math.ceil(lc / fpw) for lc in lanes]
            pools[g] = dict(N=N, lane_w=lw, depth=max(depths), depths=depths,
                            total_bits=sum(pc) * w)
        for conv, f in (("logical", lambda x: x), ("strict", p2), ("tiled2", p2_tiled2)):
            e0 = 832 * f(C)
            pay = sum(p["N"] * p["lane_w"] * f(p["depth"]) for p in pools.values())
            tot = pay + (48 + 32) * f(C)
            out.setdefault(mat, {})[f"E2-{N}lane_{conv}"] = dict(E0=e0, total=tot, ratio=e0 / tot)
            print(f"{mat:<18} E2-{N}lane {conv:<8} E0={e0/1e6:>7.2f}M total={tot/1e6:>7.2f}M ratio={e0/tot:.3f}x")
        # bank organization detail
        print(f"  [{mat}] N={N} bank org: " +
              "  ".join(f"{g}: {N}x{pools[g]['lane_w']}b x {pools[g]['depth']}" for g, _, _, _ in GROUPS))

fp = os.path.join(LU, "e2_mask_run", "lu_e2_n_lane_per_slot_results.json")
with open(fp, "w") as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False)
print(f"\nJSON written: {fp}")

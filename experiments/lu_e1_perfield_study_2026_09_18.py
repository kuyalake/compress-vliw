#!/usr/bin/env python3
"""
CORRECTED E1 for the LU VLIW: per-field vertical compression within each of the
4 non-wea slots (sel1/sel2/op/addr); wea stored raw.

  payload = sum over fields of count_f * w_f          (per-field FIFO compaction)
  mask    = M4 shared: op 16b + wea 32b = 48b/cycle
            (sel1 mask derived from op via pattern table; sel2 mask == wea;
             addr mask = union of valid sel1 values)
          or M1 explicit: op16+sel1 48+sel2 32+addr 32 = 128b/cycle (sel2 redundant w/ wea)

Depth organization:
  exact   : per-field depth = count_f            (logical bound; 128 distinct-depth banks)
  uniform : per-group depth = max count_f in group (realistic per-group bank construction)
Depth quantization on uniform: logical / strict pow2 / tiled2.

Compared against corrected E2 (exact per-lane streams, no padding) from
lu_e2_exact_lane_study_2026_09_18.py.
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

print(f"{'matrix':<18}{'conv':<9}{'E0':>9}{'E1pf-exact-M4':>14}{'E1pf-unif-M4':>13}{'E2-M4':>9}   ratioE1exact/ratioE1unif/ratioE2")
out = {}
for mat in MATS:
    C, cycles, _ = load_matrix(mat)
    per_group = {}
    for g, key, nf, w in GROUPS:
        counts = [sum(cy[key][f] for cy in cycles) for f in range(nf)]
        per_group[g] = dict(nf=nf, w=w, total=sum(counts), mx=max(counts), counts=counts)

    for conv, f in (("logical", lambda x: x), ("strict", p2), ("tiled2", p2_tiled2)):
        e0 = 832 * f(C)
        # E1 per-field, exact depths (logical only meaningful)
        e1_exact = sum(g["total"] * g["w"] for g in per_group.values()) + (48 + 32) * f(C)  # +wea raw 32b/cyc
        # E1 per-field, uniform depth per group = max count
        e1_unif = sum(g["nf"] * g["w"] * f(g["mx"]) for g in per_group.values()) + (48 + 32) * f(C)  # +wea raw
        # E2-M4 (corrected, exact lane sim): N lanes, depth = max lane count = ceil(total/N) (verified)
        e2 = 0
        for g, key, nf, w in GROUPS:
            pc = [sum(cy[key]) for cy in cycles]
            N = max(pc)
            depth = math.ceil(sum(pc) / N)  # exact lane sim confirmed == max lane count
            e2 += N * w * f(depth)
        e2 += (48 + 32) * f(C)  # mask 48b + wea raw 32b per cycle
        out.setdefault(mat, {})[conv] = dict(E0=e0, E1pf_exact_M4=e1_exact, E1pf_unif_M4=e1_unif, E2_M4=e2)
        print(f"{mat:<18}{conv:<9}{e0/1e6:>8.2f}M{e1_exact/1e6:>13.2f}M{e1_unif/1e6:>12.2f}M{e2/1e6:>8.2f}M   "
              f"{e0/e1_exact:.3f} / {e0/e1_unif:.3f} / {e0/e2:.3f}")

# group max-vs-mean detail (why uniform-depth E1 loses to E2)
print("\nfield-count imbalance per group (max / mean) — E1-uniform depth penalty vs E2 shared-lane depth:")
for mat in MATS:
    C, cycles, _ = load_matrix(mat)
    line = f"  {mat:<18}"
    for g, key, nf, w in GROUPS:
        counts = [sum(cy[key][f] for cy in cycles) for f in range(nf)]
        line += f" {g}: {max(counts)}/{sum(counts)//nf} = {max(counts)*nf/sum(counts):.2f} |"
    print(line)

fp = os.path.join(LU, "e2_mask_run", "lu_e1_perfield_results.json")
with open(fp, "w") as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False)
print(f"\nJSON written: {fp}")

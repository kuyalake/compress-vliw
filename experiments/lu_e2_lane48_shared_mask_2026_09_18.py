#!/usr/bin/env python3
"""
LANE4/LANE8 with SHARED masks (user's insight, same-cycle rule):
  - op lane l and sel1 lane l share ONE mask bit (op[j]!=0 <=> PE j has >=1 valid sel1 field;
    exact equality, verified: all 22 op patterns use >=1 operand)
  - sel2 lane mask derived from wea by OR-reduction (sel2[b] valid <=> wea[b]==1), 0 extra bits
  - addr lane mask: explicit L bits  (variant A)
    or derived from sel1 values union (variant B, adds decode dependency chain)
Metadata per cycle:
  LANE4-A: 4 (op/sel1 shared) + 4 (addr) + 32 (wea raw) = 40 b/cyc
  LANE4-B: 4 + 32 = 36 b/cyc
  LANE8-A: 8 + 8 + 32 = 48 b/cyc
  LANE8-B: 8 + 32 = 40 b/cyc
"""
import os, sys, json
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

GROUPS = [("sel1", "s1_v", 48, 5), ("sel2", "s2_v", 32, 4),
          ("op", "op_v", 16, 5), ("addr", "ad_v", 32, 11)]

def lane_split(nf, L):
    per = nf // L
    return [list(range(l * per, (l + 1) * per)) for l in range(L)]

out = {}
for mat in MATS:
    C, cycles, _ = load_matrix(mat)
    # sanity: verify op[j]!=0 <=> any sel1 field of PE j valid, and sel2[b] valid <=> wea[b]
    for cy in cycles:
        for j in range(16):
            assert (cy["op_v"][j] == 1) == any(cy["s1_v"][3*j:3*j+3]), "op<->sel1 mask sharing broken"
        for b in range(32):
            assert cy["s2_v"][b] == cy["we"][b], "sel2<->wea mask sharing broken"

    for L in (4, 8):
        lanes = []
        for g, key, nf, w in GROUPS:
            per_field = [[cy[key][f] for cy in cycles] for f in range(nf)]
            for li, members in enumerate(lane_split(nf, L)):
                lw = len(members) * w
                vc = sum(1 for i in range(C) if any(per_field[f][i] for f in members))
                lanes.append((g, li, lw, vc))
        for conv, f in (("logical", lambda x: x), ("strict", p2), ("tiled2", p2_tiled2)):
            e0 = 832 * f(C)
            pay = sum(lw * f(vc) for _, _, lw, vc in lanes)
            for variant, meta_bits in (("A", 2 * L + 32), ("B", L + 32)):
                tot = pay + meta_bits * f(C)
                out.setdefault(mat, {}).setdefault(f"L{L}", {})[f"{variant}_{conv}"] = dict(
                    E0=e0, total=tot, ratio=e0 / tot, meta_per_cycle=meta_bits)
                print(f"{mat:<18} L={L} variant={variant} {conv:<8} E0={e0/1e6:>7.2f}M "
                      f"total={tot/1e6:>7.2f}M ratio={e0/tot:.3f}x (meta {meta_bits}b/cyc)")

fp = os.path.join(LU, "e2_mask_run", "lu_e2_lane48_shared_mask_results.json")
with open(fp, "w") as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False)
print(f"\nJSON written: {fp}")
print("\nSanity checks passed: op[j]!=0 <=> any(sel1[3j..3j+2] valid); sel2[b] valid <=> wea[b]==1 (all cycles, all matrices)")

#!/usr/bin/env python3
"""
LU VLIW: per-slot uniform split into 4 or 8 equal lanes (block-drop),
under TWO validity rules:
  Rule-S (same-cycle): sel1[i] valid <=> op[i] active (with operand pattern);
                       sel2[i] valid <=> wea[i]==1
  Rule-N (next-cycle, user's rule): sel1[i] valid <=> op[i+1] active (pattern);
                       sel2[i] valid <=> wea[i+1]==1
Rule-N validity = Rule-S validity shifted by one cycle (last cycle all-invalid).

Splits (contiguous fields):
  4-way: sel1 4x60b(12f) sel2 4x32b(8f) op 4x20b(4f) addr 4x88b(8f); mask 16b/cyc
  8-way: sel1 8x30b(6f)  sel2 8x16b(4f) op 8x10b(2f) addr 8x44b(4f); mask 32b/cyc
wea stored raw 32b/cycle in all cases.
Depth conventions: logical / strict pow2 / tiled2.
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

def build_validity(cycles, C, rule):
    """per-field validity per group; Rule-N shifts sel1/sel2 validity by +1 cycle."""
    V = {}
    for g, key, nf, w in GROUPS:
        V[g] = [[cy[key][f] for cy in cycles] for f in range(nf)]
    if rule == "N":
        for g in ("sel1", "sel2"):
            V[g] = [[cy[g == "sel1" and "s1_v" or "s2_v"][f] for cy in cycles[1:]] + [0]
                    for f in range(len(V[g]))]
    return V

def lane_split(nf, L):
    per = nf // L
    return [list(range(l * per, (l + 1) * per)) for l in range(L)]

out = {}
for mat in MATS:
    C, cycles, _ = load_matrix(mat)
    for rule in ("S", "N"):
        V = build_validity(cycles, C, rule)
        for L in (4, 8):
            lanes = []
            for g, key, nf, w in GROUPS:
                for li, members in enumerate(lane_split(nf, L)):
                    lw = len(members) * w
                    vc = sum(1 for i in range(C) if any(V[g][f][i] for f in members))
                    lanes.append((g, li, lw, vc))
            nmask = L * 4
            for conv, f in (("logical", lambda x: x), ("strict", p2), ("tiled2", p2_tiled2)):
                e0 = 832 * f(C)
                pay = sum(lw * f(vc) for _, _, lw, vc in lanes)
                tot = pay + (nmask + 32) * f(C)
                out.setdefault(mat, {}).setdefault(f"rule{rule}", {})[f"L{L}_{conv}"] = dict(
                    E0=e0, total=tot, ratio=e0 / tot)
                print(f"{mat:<18} rule={rule} L={L} {conv:<8} E0={e0/1e6:>7.2f}M "
                      f"total={tot/1e6:>7.2f}M ratio={e0/tot:.3f}x")

fp = os.path.join(LU, "e2_mask_run", "lu_e2_lane48_nextrule_results.json")
with open(fp, "w") as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False)
print(f"\nJSON written: {fp}")

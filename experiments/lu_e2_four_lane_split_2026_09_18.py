#!/usr/bin/env python3
"""
LU VLIW: each slot group uniformly split into 4 equal-width lanes (block-drop scheme).

  sel1 (48x5b=240b) -> 4 lanes x 60b (12 fields each, contiguous)
  sel2 (32x4b=128b) -> 4 lanes x 32b (8 fields each)
  op   (16x5b=80b)  -> 4 lanes x 20b (4 PEs each)
  addr (32x11b=352b)-> 4 lanes x 88b (8 banks each)
  wea  (32b)        -> stored raw, not compressed
  mask              -> 16 bits/cycle (4 groups x 4 lanes)

Lane valid <=> any member field valid that cycle; dropped lanes refill defaults
(bit-exact, since idle fields are don't-care fills / explicit idle codes).

Depth quantization per lane bank: logical (exact) / strict pow2 / tiled2.
Also reports interleaved (round-robin) field->lane assignment as a variant.
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

# (group, n_fields, field_width) in fixed order
GROUPS = [("sel1", 48, 5), ("sel2", 32, 4), ("op", 16, 5), ("addr", 32, 11)]
KEYS = {"sel1": "s1_v", "sel2": "s2_v", "op": "op_v", "addr": "ad_v"}

def lane_assignment(nf, mode):
    """returns list of 4 lists of field indices."""
    if mode == "contiguous":
        per = nf // 4
        return [list(range(l * per, (l + 1) * per)) for l in range(4)]
    else:  # interleaved round-robin
        return [[f for f in range(nf) if f % 4 == l] for l in range(4)]

def run(mat, mode):
    C, cycles, _ = load_matrix(mat)
    lanes = []  # (group, lane_idx, width, valid_cycles)
    for g, nf, w in GROUPS:
        key = KEYS[g]
        per_field = [[cy[key][f] for cy in cycles] for f in range(nf)]
        for li, members in enumerate(lane_assignment(nf, mode)):
            lw = len(members) * w
            vc = sum(1 for i in range(C) if any(per_field[f][i] for f in members))
            lanes.append((g, li, lw, vc))
    return C, lanes

def totals(f, C, lanes):
    payload = sum(lw * f(vc) for _, _, lw, vc in lanes)
    return payload + 16 * f(C) + 32 * f(C)  # mask 16b + wea raw 32b per cycle

print(f"{'matrix':<18}{'mode':<12}{'conv':<8}{'E0':>9}{'LANE4':>9}  ratio   payload+meta breakdown")
all_out = {}
for mat in MATS:
    for mode in ("contiguous", "interleaved"):
        C, lanes = run(mat, mode)
        for conv, f in (("logical", lambda x: x), ("strict", p2), ("tiled2", p2_tiled2)):
            e0 = 832 * f(C)
            tot = totals(f, C, lanes)
            pay = sum(lw * f(vc) for _, _, lw, vc in lanes)
            all_out.setdefault(mat, {}).setdefault(mode, {})[conv] = dict(
                E0=e0, total=tot, payload=pay, meta=tot - pay, ratio=e0 / tot,
                lanes=[(g, li, lw, vc, f(vc)) for g, li, lw, vc in lanes])
            print(f"{mat:<18}{mode:<12}{conv:<8}{e0/1e6:>8.2f}M{tot/1e6:>8.2f}M  {e0/tot:.3f}x  "
                  f"payload={pay/1e6:.2f}M meta={ (tot-pay)/1e6:.2f}M")
    # per-lane valid-cycle detail (contiguous)
    C, lanes = run(mat, "contiguous")
    print(f"  [{mat}] contiguous lane valid-cycles (of C={C}):")
    for g, nf, w in GROUPS:
        row = [f"{vc}({lw}b)" for gg, li, lw, vc in lanes if gg == g]
        print(f"    {g:<5} " + "  ".join(row))

out = os.path.join(LU, "e2_mask_run", "lu_e2_four_lane_split_results.json")
with open(out, "w") as fp:
    json.dump(all_out, fp, indent=1, ensure_ascii=False)
print(f"\nJSON written: {out}")

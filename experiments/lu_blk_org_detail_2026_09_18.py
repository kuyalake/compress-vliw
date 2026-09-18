#!/usr/bin/env python3
"""BLK (hardware-aligned blocks) storage organization detail.

48 blocks:
  PE block j   (j=0..15): {op[j], sel1[3j], sel1[3j+1], sel1[3j+2]} = 5+15 = 20b
                          valid <=> op_j != 0
  bank block b (b=0..31): {addr[b], sel2[b], wea[b]} = 11+4+1 = 16b
                          valid <=> addr_b != 2047 or wea_b == 1
mask stream: 48b/cycle (16 PE-block bits + 32 bank-block bits).
Each block = own bank, own read pointer, depth = its valid-cycle count.
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

out = {}
for mat in MATS:
    C, cycles, _ = load_matrix(mat)
    pe_depth = [sum(1 for cy in cycles if cy["op_v"][j]) for j in range(16)]
    bk_depth = [sum(1 for cy in cycles if cy["ad_v"][b] or cy["we"][b]) for b in range(32)]
    for conv, f in (("logical", lambda x: x), ("strict", p2), ("tiled2", p2_tiled2)):
        e0 = 832 * f(C)
        pay = sum(20 * f(d) for d in pe_depth) + sum(16 * f(d) for d in bk_depth)
        tot = pay + 48 * f(C)
        out.setdefault(mat, {})[conv] = dict(E0=e0, total=tot, ratio=e0 / tot)
        if conv == "strict":
            print(f"{mat:<18} BLK strict: total={tot/1e6:.2f}M ratio={e0/tot:.3f}x")
    print(f"== {mat} (C={C}) ==")
    print(f"  PE  blocks (20b): valid-cycles min={min(pe_depth)} max={max(pe_depth)} "
          f"mean={sum(pe_depth)/16:.0f} -> pow2 depths {sorted(set(p2(d) for d in pe_depth))}")
    print(f"    per-PE: {pe_depth}")
    print(f"  bank blocks (16b): min={min(bk_depth)} max={max(bk_depth)} mean={sum(bk_depth)/32:.0f} "
          f"-> pow2 depths {sorted(set(p2(d) for d in bk_depth))}")
    print(f"    per-bank: {bk_depth}")

fp = os.path.join(LU, "e2_mask_run", "lu_blk_org_detail.json")
with open(fp, "w") as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False)
print(f"\nJSON written: {fp}")

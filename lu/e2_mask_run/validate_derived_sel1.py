#!/usr/bin/env python3
"""Bit-exact validation: pattern-derived sel1 mask vs actual mask.txt on regenerated runs.
Also measures addr value locality (broadcast/run potential) on the ORIGINAL traces.
"""
import os

LU = "/Users/maghu/Desktop/work at school/compress/compress-vliw/lu"
RUNS = ["oscil", "oscil_op2", "rajat", "add20", "bomhof"]
BASE = os.path.join(LU, "e2_mask_run")

OP_PATTERN = {
    1: (0,1,1), 2: (0,1,0), 3: (0,0,1), 4: (1,1,1), 5: (0,1,0),
    6: (1,0,1), 7: (0,1,1), 8: (1,0,0), 9: (0,1,0), 10: (0,0,1),
    11: (1,0,0), 12: (0,1,1), 13: (0,1,0), 14: (0,0,1), 15: (0,1,1),
    17: (0,0,1), 19: (0,1,0), 20: (0,1,0), 21: (0,0,1), 22: (0,0,1), 23: (0,0,1),
}

print("=== 1) sel1 mask: pattern-derived vs actual (regenerated runs) ===")
for run in RUNS:
    d = os.path.join(BASE, run)
    if not os.path.exists(os.path.join(d, "mask.txt")):
        continue
    total, mismatch = 0, 0
    with open(os.path.join(d, "mask.txt")) as fm, open(os.path.join(d, "op.txt")) as fo:
        for lm, lo in zip(fm, fo):
            lm, lo = lm.strip(), lo.strip()
            if not lm or not lo:
                continue
            m_sel1 = lm.split("_")[1]          # 48 chars, idx=47..0
            ops = [int(x, 2) for x in lo.split("_")]  # j=15..0
            for p in range(16):
                j = 15 - p
                o = ops[p]
                pat = OP_PATTERN.get(o, (0, 0, 0))
                for k in range(3):  # k=0 rd, 1 rt, 2 rs
                    idx = 3 * j + k
                    derived = pat[k] if o != 0 else 0
                    actual = int(m_sel1[47 - idx])
                    total += 1
                    if derived != actual:
                        mismatch += 1
    print(f"  {run:<10} fields={total:>9}  mismatches={mismatch}  "
          f"({'EXACT' if mismatch == 0 else f'{mismatch/total:.4%}'})")

print("\n=== 2) addr value locality on ORIGINAL traces ===")
for mat in ["2624bomhof_1", "1041rajat04", "2395add20", "430oscil_dcop_11"]:
    d = os.path.join(LU, mat)
    with open(os.path.join(d, "addr.txt")) as f:
        rows = [[int(x, 2) for x in l.strip().split("_")] for l in f if l.strip()]
    C = len(rows)
    valid = 0
    eq_prev = 0          # valid addr equal to previous valid addr (bank order, same cycle)
    distinct_sum = 0     # distinct addr values per cycle
    for r in rows:
        vals = [a for a in r if a != 2047]
        valid += len(vals)
        distinct_sum += len(set(vals))
        for a, b in zip(vals, vals[1:]):
            if a == b:
                eq_prev += 1
    print(f"  {mat:<18} C={C:>6} valid_addr={valid:>9} "
          f"eq_prev={eq_prev/valid:6.1%}  distinct/cycle={distinct_sum/C:5.2f} "
          f"(valid/cycle={valid/C:5.2f})")

print("\n=== 3) op value histogram on ORIGINAL traces (top ops) ===")
import collections
for mat in ["2624bomhof_1", "1041rajat04"]:
    d = os.path.join(LU, mat)
    h = collections.Counter()
    with open(os.path.join(d, "op.txt")) as f:
        for l in f:
            for x in l.strip().split("_"):
                h[int(x, 2)] += 1
    top = ", ".join(f"op{o}:{c}" for o, c in h.most_common(6))
    print(f"  {mat:<18} {top}")

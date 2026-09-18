#!/usr/bin/env python3
"""Infer (rd,rt,rs) validity patterns for ops missing from the regenerated-trace table
(ops 2, 3, 23), using ONLY the original instruction files.

Constraints per occurrence of op X at (cycle i, PE j):
  - operand k marked INVALID => sel1[3j+k] == (3j+k) % 32   (default fill value)
  - operand k marked VALID   => addr[ sel1[3j+k] ] != 2047  (its bank must be read)
Global per cycle: union of banks of all valid sel1 fields == {b : addr[b] != 2047}.
"""
import os, itertools, collections

LU = "/Users/maghu/Desktop/work at school/compress/compress-vliw/lu"
MATS = ["2624bomhof_1", "1041rajat04", "2395add20", "430oscil_dcop_11"]

KNOWN = {1: (0,1,1), 4: (1,1,1), 5: (0,1,0), 6: (1,0,1), 7: (0,1,1), 8: (1,0,0),
         9: (0,1,0), 10: (0,0,1), 11: (1,0,0), 12: (0,1,1), 13: (0,1,0),
         14: (0,0,1), 15: (0,1,1), 17: (0,0,1), 19: (0,1,0), 20: (0,1,0),
         21: (0,0,1), 22: (0,0,1)}
TARGETS = [2, 3, 23]

def load(mat):
    d = os.path.join(LU, mat)
    def rd(fn):
        with open(os.path.join(d, fn)) as f:
            return [l.strip() for l in f if l.strip()]
    op   = [list(reversed([int(x,2) for x in l.split("_")])) for l in rd("op.txt")]
    sel1 = [list(reversed([int(x,2) for x in l.split("_")])) for l in rd("sel1.txt")]
    addr = [list(reversed([int(x,2) for x in l.split("_")])) for l in rd("addr.txt")]
    return op, sel1, addr

# candidate patterns per target op, filtered by per-occurrence field constraints
cand = {t: set(itertools.product([0,1], repeat=3)) for t in TARGETS}
occ_count = collections.Counter()

for mat in MATS:
    op, sel1, addr = load(mat)
    for i in range(len(op)):
        ad_v = [a != 2047 for a in addr[i]]
        for j in range(16):
            o = op[i][j]
            if o not in TARGETS:
                continue
            occ_count[o] += 1
            vals = [sel1[i][3*j], sel1[i][3*j+1], sel1[i][3*j+2]]  # rd, rt, rs
            ok = set()
            for pat in cand[o]:
                good = True
                for k in range(3):
                    idx = 3*j + k
                    if pat[k] == 0:  # invalid => must equal default fill
                        if vals[k] != idx % 32:
                            good = False; break
                    else:            # valid => bank must be read
                        if not ad_v[vals[k]]:
                            good = False; break
                if good:
                    ok.add(pat)
            cand[o] &= ok

print("occurrences:", dict(occ_count))
for t in TARGETS:
    print(f"op {t}: surviving candidates (rd,rt,rs) = {sorted(cand[t])}")

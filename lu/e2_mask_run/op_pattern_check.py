#!/usr/bin/env python3
"""Check whether sel1 operand-validity pattern is a pure function of op code.

mask.txt line format: m_op(16b) _ m_sel1(48b) _ m_addr(32b)
  m_op[p]    (p=0..15, left to right)  -> PE j = 15-p
  m_sel1[p]  (p=0..47, left to right)  -> field idx = 47-p ; idx=3j+2 rs, 3j+1 rt, 3j rd
op.txt line: 16 fields of 5b, printed j=15..0, so field p (left->right) -> PE j = 15-p
"""
import os, sys, collections

RUNS = ["oscil", "oscil_op2", "rajat", "add20", "bomhof"]
BASE = os.path.dirname(os.path.abspath(__file__))

# op -> set of (rd_valid, rt_valid, rs_valid) patterns ; also count
patterns = collections.defaultdict(collections.Counter)
# op -> set of ops seen with op!=0
op_hist = collections.Counter()

for run in RUNS:
    d = os.path.join(BASE, run)
    if not (os.path.exists(os.path.join(d, "mask.txt")) and os.path.exists(os.path.join(d, "op.txt"))):
        continue
    with open(os.path.join(d, "mask.txt")) as fm, open(os.path.join(d, "op.txt")) as fo:
        for lm, lo in zip(fm, fo):
            lm, lo = lm.strip(), lo.strip()
            if not lm or not lo:
                continue
            m_op, m_sel1, m_addr = lm.split("_")
            ops = lo.split("_")
            assert len(m_op) == 16 and len(m_sel1) == 48 and len(ops) == 16
            for p in range(16):
                j = 15 - p
                op = int(ops[p], 2)
                op_hist[op] += 1
                if op == 0:
                    continue
                # mask bits for PE j: idx 3j (rd), 3j+1 (rt), 3j+2 (rs)
                rd_v = m_sel1[47 - 3 * j]
                rt_v = m_sel1[47 - (3 * j + 1)]
                rs_v = m_sel1[47 - (3 * j + 2)]
                patterns[op][(rd_v, rt_v, rs_v)] += 1

print(f"{'op':>3} {'count':>8}  patterns (rd,rt,rs):count")
pure = True
for op in sorted(patterns):
    tot = sum(patterns[op].values())
    ps = ", ".join(f"{''.join(k)}:{c}" for k, c in patterns[op].most_common())
    flag = "" if len(patterns[op]) == 1 else "  <-- MULTIPLE"
    if len(patterns[op]) > 1:
        pure = False
    print(f"{op:>3} {tot:>8}  {ps}{flag}")
print()
print("PURE FUNCTION" if pure else "NOT A PURE FUNCTION OF op")
print("ops seen:", sorted(op_hist))

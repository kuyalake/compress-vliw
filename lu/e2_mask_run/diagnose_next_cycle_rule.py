#!/usr/bin/env python3
"""Diagnose sel1/sel2 value placement vs validity rule.

Rule-S (same-cycle, my old rule): sel1[3j+k][i] valid <=> op_j[i]!=0 & pattern bit k
Rule-N (user's rule, next-cycle): sel1[3j+k][i] valid <=> op_j[i+1]!=0 & pattern bit k
                                   sel2[b][i] valid <=> wea[b][i+1]==1

Checks per matrix:
 1. addr-union consistency of Rule-N: union of Rule-N-valid sel1 values at row i
    == {b : addr[b][i] != 2047} ?
 2. value placement: among Rule-N-valid positions, fraction with non-default value;
    among Rule-S-valid positions, fraction with non-default value.
 3. sel2: when wea[b][i+1]=1, is sel2[b][i] non-default? when wea[b][i]=1?
"""
import os, sys
sys.path.insert(0, "/Users/maghu/Desktop/work at school/compress/compress-vliw/experiments")
from lu_e2_striping_study_2026_09_18 import load_matrix, OP_PATTERN, MATS, LU

def load_raw(mat):
    d = os.path.join(LU, mat)
    def rd(fn):
        with open(os.path.join(d, fn)) as f:
            return [l.strip() for l in f if l.strip()]
    op   = [list(reversed([int(x, 2) for x in l.split("_")])) for l in rd("op.txt")]
    sel1 = [list(reversed([int(x, 2) for x in l.split("_")])) for l in rd("sel1.txt")]
    sel2 = [list(reversed([int(x, 2) for x in l.split("_")])) for l in rd("sel2.txt")]
    wea  = [[int(c) for c in l.replace("_", "")][::-1] for l in rd("wea.txt")]
    addr = [list(reversed([int(x, 2) for x in l.split("_")])) for l in rd("addr.txt")]
    return op, sel1, sel2, wea, addr

for mat in MATS:
    op, sel1, sel2, wea, addr = load_raw(mat)
    C = len(op)

    # --- Rule-N addr-union check
    bad_n = 0
    for i in range(C):
        nxt = op[i + 1] if i + 1 < C else [0] * 16
        banks = set()
        for j in range(16):
            o = nxt[j]
            if o == 0 or o not in OP_PATTERN:
                continue
            rd_v, rt_v, rs_v = OP_PATTERN[o]
            for k, pv in ((0, rd_v), (1, rt_v), (2, rs_v)):
                if pv:
                    banks.add(sel1[i][3 * j + k])
        ref = {b for b in range(32) if addr[i][b] != 2047}
        if banks != ref:
            bad_n += 1
    # --- Rule-S addr-union check (for reference; known 0)
    bad_s = 0
    for i in range(C):
        banks = set()
        for j in range(16):
            o = op[i][j]
            if o == 0 or o not in OP_PATTERN:
                continue
            rd_v, rt_v, rs_v = OP_PATTERN[o]
            for k, pv in ((0, rd_v), (1, rt_v), (2, rs_v)):
                if pv:
                    banks.add(sel1[i][3 * j + k])
        ref = {b for b in range(32) if addr[i][b] != 2047}
        if banks != ref:
            bad_s += 1

    # --- value placement: non-default fraction
    def nondef_sel1(idx, v):
        return v != idx % 32
    n_valid = s_valid = n_nondef = s_nondef = 0
    for i in range(C):
        nxt = op[i + 1] if i + 1 < C else [0] * 16
        for j in range(16):
            on, os_ = nxt[j], op[i][j]
            pn = OP_PATTERN.get(on)
            ps = OP_PATTERN.get(os_)
            for k in range(3):
                idx = 3 * j + k
                v = sel1[i][idx]
                if on and pn and pn[k]:
                    n_valid += 1
                    n_nondef += nondef_sel1(idx, v)
                if os_ and ps and ps[k]:
                    s_valid += 1
                    s_nondef += nondef_sel1(idx, v)
    # --- sel2 placement
    def nondef_sel2(b, v):
        return v != b // 2
    s2_n = s2_s = s2_n_nd = s2_s_nd = 0
    for i in range(C):
        nxtw = wea[i + 1] if i + 1 < C else [0] * 32
        for b in range(32):
            v = sel2[i][b]
            if nxtw[b]:
                s2_n += 1
                s2_n_nd += nondef_sel2(b, v)
            if wea[i][b]:
                s2_s += 1
                s2_s_nd += nondef_sel2(b, v)

    print(f"== {mat} (C={C}) ==")
    print(f"  addr-union mismatch cycles: Rule-N(next)={bad_n}  Rule-S(same)={bad_s}")
    print(f"  sel1 non-default value rate: Rule-N-valid {n_nondef}/{n_valid} = {n_nondef/max(n_valid,1):.1%}  "
          f"Rule-S-valid {s_nondef}/{s_valid} = {s_nondef/max(s_valid,1):.1%}")
    print(f"  sel2 non-default value rate: next-wea-valid {s2_n_nd}/{s2_n} = {s2_n_nd/max(s2_n,1):.1%}  "
          f"same-wea-valid {s2_s_nd}/{s2_s} = {s2_s_nd/max(s2_s,1):.1%}")

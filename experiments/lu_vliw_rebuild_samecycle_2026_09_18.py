#!/usr/bin/env python3
"""
Rebuild LU VLIW instruction files under the SAME-CYCLE validity rule (Rule-S):
identify don't-care fields and canonicalize them to default fills; keep valid values.

Rules (per cycle i, same cycle):
  op[j]      : valid iff op != 0; invalid canonical = 00000
  sel1[3j+k] : valid iff op_j != 0 and operand k in OP_PATTERN[op]; invalid = idx%32
  sel2[b]    : valid iff wea_clean[b]=1; invalid = b/2
  addr[b]    : valid iff != 2047; invalid = 2047
  wea[b]     : REGENERATED from op + sel1/sel2 consistency (removes the inst[i][16]
               out-of-bounds ghost bits produced by the writeInst loop bug):
                 op in {1,3,22,23}  -> write bank = rs%32 = sel1[3j+2] value
                 op in {4,6,8,11}   -> write bank = rd%32 = sel1[3j]   value
                 op in {19,20}      -> write bank = b where sel2[b]==j and wea[b]==1
Outputs rebuilt files to lu/rebuilt_vliw/<matrix>/ and reports diffs vs original.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lu_e2_striping_study_2026_09_18 import load_matrix, OP_PATTERN, MATS, LU

OUT = os.path.join(LU, "rebuilt_vliw")

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

def fmt5(v): return format(v, "05b")
def fmt4(v): return format(v, "04b")
def fmt11(v): return format(v, "011b")

report = {}
for mat in MATS:
    op, sel1, sel2, wea, addr = load_raw(mat)
    C = len(op)
    dirty = dict(sel1=0, sel2=0, addr=0, op=0)
    ghost_bits = 0
    missing_wea = 0

    R_op, R_s1, R_s2, R_wea, R_addr = [], [], [], [], []
    for i in range(C):
        # --- regenerate clean wea from op + sel1/sel2
        wea_new = [0] * 32
        for j in range(16):
            o = op[i][j]
            if o in (1, 3, 22, 23):
                wea_new[sel1[i][3 * j + 2]] = 1          # rs % 32
            elif o in (4, 6, 8, 11):
                wea_new[sel1[i][3 * j]] = 1              # rd % 32
            elif o in (19, 20):
                # rs not present in sel1; recover bank via sel2 reverse lookup
                cands = [b for b in range(32) if wea[i][b] == 1 and sel2[i][b] == j]
                if cands:
                    wea_new[cands[0]] = 1
        # --- diff wea
        for b in range(32):
            if wea_new[b] != wea[i][b]:
                if wea[i][b] == 1:
                    ghost_bits += 1      # original had a spurious 1
                else:
                    missing_wea += 1     # original missed a real write
        # --- rebuild fields
        new_op = []
        new_s1 = [0] * 48
        new_s2 = [0] * 32
        new_ad = [0] * 32
        for j in range(16):
            o = op[i][j]
            new_op.append(o)
            pat = OP_PATTERN.get(o, (0, 0, 0)) if o != 0 else (0, 0, 0)
            for k in range(3):
                idx = 3 * j + k
                valid = (o != 0) and pat[k] == 1
                if valid:
                    new_s1[idx] = sel1[i][idx]
                else:
                    new_s1[idx] = idx % 32
                    if sel1[i][idx] != idx % 32:
                        dirty["sel1"] += 1
        for b in range(32):
            if wea_new[b]:
                new_s2[b] = sel2[i][b]
            else:
                new_s2[b] = b // 2
                if sel2[i][b] != b // 2:
                    dirty["sel2"] += 1
            if addr[i][b] != 2047:
                new_ad[b] = addr[i][b]
            else:
                new_ad[b] = 2047
        R_op.append(new_op)
        R_s1.append(new_s1)
        R_s2.append(new_s2)
        R_wea.append(wea_new)
        R_addr.append(new_ad)

    # --- write rebuilt files (original field order: high index first)
    mdir = os.path.join(OUT, mat)
    os.makedirs(mdir, exist_ok=True)
    def w(fn, lines):
        with open(os.path.join(mdir, fn), "w") as f:
            f.write("\n".join(lines) + "\n")
    w("op.txt",   ["_".join(fmt5(R_op[i][j]) for j in range(15, -1, -1)) for i in range(C)])
    w("sel1.txt", ["_".join(fmt5(R_s1[i][x]) for x in range(47, -1, -1)) for i in range(C)])
    w("sel2.txt", ["_".join(fmt4(R_s2[i][b]) for b in range(31, -1, -1)) for i in range(C)])
    w("addr.txt", ["_".join(fmt11(R_addr[i][b]) for b in range(31, -1, -1)) for i in range(C)])
    # wea format: 32 bits grouped by 4 with '_', b=31..0
    w("wea.txt",  ["_".join("".join(str(R_wea[i][b]) for b in range(hi, hi - 4, -1))
                            for hi in (31, 27, 23, 19, 15, 11, 7, 3)) for i in range(C)])
    with open(os.path.join(mdir, "count.txt"), "w") as f:
        f.write(format(C, "016b") + "\n")

    report[mat] = dict(C=C, dirty=dirty, ghost_wea_bits=ghost_bits, missing_wea_bits=missing_wea)
    print(f"{mat:<18} C={C}  dirty(non-default@invalid): {dirty}  "
          f"wea ghost bits removed: {ghost_bits}, wea bits added: {missing_wea}")

fp = os.path.join(OUT, "rebuild_report.json")
with open(fp, "w") as f:
    json.dump(report, f, indent=1, ensure_ascii=False)
print(f"\nRebuilt files at {OUT}/<matrix>/ ; report: {fp}")

#!/usr/bin/env python3
"""
LU-decomposition VLIW (832-bit, per-beat static issue): E2 striping vs vertical compression.

Instruction layout per cycle (832 bits total):
  op   : 16 x 5b   (PE operation; 0 = NOP)
  sel1 : 48 x 5b   (bank-port select for PE operands; idx 3j=rd, 3j+1=rt, 3j+2=rs)
  sel2 : 32 x 4b   (PE-output select for bank write port b)
  wea  : 32 x 1b   (write enable per bank port) == sel2 validity mask
  addr : 32 x 11b  (read address per bank port; 2047 = idle)

Validity rules (from version10/mymethod.cpp writeInst):
  op[j]      valid  <=>  op != 0
  sel1[field] valid <=>  operand used; operand-usage pattern is a PURE FUNCTION of op
             (verified on regenerated traces, see op_pattern_check.py)
  sel2[b]    valid  <=>  wea[b] == 1
  addr[b]    valid  <=>  addr != 2047
  wea        always stored (it *is* the sel2 mask)

Schemes compared (storage in bits, metadata included):
  E0    : raw 832b x C
  E1c   : coarse vertical - 5 group banks (240/128/80/32/352b), depth = active cycles of group, 5b mask/cycle
  E1f   : fine vertical   - per-field banks (128 fields), mask 128b/cycle (incl. wea as sel2 mask)
  E2g   : per-group striping, 4 lane pools (op5b, sel1 5b, sel2 4b, addr 11b), rolling phase + row padding
  E2g5  : per-group striping, 3 pools (op+sel1 share 5b pool of 64 fields, sel2 4b, addr 11b)
  E2p   : whole-word pack-then-stripe, bit-level packing into W-bit rows (W = N*w lane)
  SLICE : naive equal slicing of raw 832b word (no repacking) - lane droppable iff all its fields idle
Metadata variants: M1 = explicit masks 128b/cycle ; M2 = op raw 80b + wea 32b + addr-mask 32b = 144b/cycle
"""

import os, json, math, collections

LU = "/Users/maghu/Desktop/work at school/compress/compress-vliw/lu"
MATS = ["2624bomhof_1", "1041rajat04", "2395add20", "430oscil_dcop_11"]

# op -> (rd_valid, rt_valid, rs_valid), from regenerated self-consistent traces
# (ops 2, 3, 23 inferred from original traces via default-fill/read-bank constraints,
#  see lu/e2_mask_run/infer_op_patterns.py; op 23 taken as op 22 analog = rs only)
OP_PATTERN = {
    1: (0, 1, 1), 2: (0, 1, 0), 3: (0, 0, 1), 4: (1, 1, 1), 5: (0, 1, 0),
    6: (1, 0, 1), 7: (0, 1, 1), 8: (1, 0, 0), 9: (0, 1, 0), 10: (0, 0, 1),
    11: (1, 0, 0), 12: (0, 1, 1), 13: (0, 1, 0), 14: (0, 0, 1), 15: (0, 1, 1),
    17: (0, 0, 1), 19: (0, 1, 0), 20: (0, 1, 0), 21: (0, 0, 1), 22: (0, 0, 1),
    23: (0, 0, 1),
}

def load_matrix(mat):
    d = os.path.join(LU, mat)
    def rd(fn):
        with open(os.path.join(d, fn)) as f:
            return [l.strip() for l in f if l.strip()]
    op   = [[int(x, 2) for x in l.split("_")] for l in rd("op.txt")]      # 16, order j=15..0
    sel1 = [[int(x, 2) for x in l.split("_")] for l in rd("sel1.txt")]    # 48, idx=47..0
    sel2 = [[int(x, 2) for x in l.split("_")] for l in rd("sel2.txt")]    # 32, b=31..0
    wea_s = [l.replace("_", "") for l in rd("wea.txt")]                    # 32 chars, b=31..0
    addr = [[int(x, 2) for x in l.split("_")] for l in rd("addr.txt")]    # 32, b=31..0
    C = len(op)
    assert all(len(r) == 16 for r in op) and all(len(r) == 48 for r in sel1)
    assert all(len(r) == 32 for r in sel2) and all(len(r) == 32 for r in addr)
    assert all(len(s) == 32 for s in wea_s) and len(sel1) == C and len(addr) == C

    # Build per-cycle validity. Internally use natural index order (PE j=0..15, bank b=0..31).
    # File order is reversed (j=15..0 / idx=47..0 / b=31..0); reverse back.
    cycles = []
    unknown_ops = set()
    for i in range(C):
        ops = list(reversed(op[i]))           # j=0..15
        s1  = list(reversed(sel1[i]))         # idx=0..47
        s2  = list(reversed(sel2[i]))         # b=0..31
        we  = [int(c) for c in reversed(wea_s[i])]  # b=0..31
        ad  = list(reversed(addr[i]))         # b=0..31
        op_v   = [1 if o != 0 else 0 for o in ops]
        s1_v   = [0] * 48
        for j in range(16):
            if ops[j] == 0:
                continue
            if ops[j] not in OP_PATTERN:
                unknown_ops.add(ops[j])
                continue
            rd_v, rt_v, rs_v = OP_PATTERN[ops[j]]
            s1_v[3*j]   = rd_v
            s1_v[3*j+1] = rt_v
            s1_v[3*j+2] = rs_v
        s2_v = we[:]                            # sel2 valid <=> wea==1
        ad_v = [1 if a != 2047 else 0 for a in ad]
        cycles.append(dict(ops=ops, s1=s1, s2=s2, we=we, ad=ad,
                           op_v=op_v, s1_v=s1_v, s2_v=s2_v, ad_v=ad_v))
    return C, cycles, unknown_ops

def validate(cycles, mat):
    """union of valid sel1 values (banks read) must equal addr-valid bank set."""
    bad = 0
    for i, cy in enumerate(cycles):
        banks = set()
        for idx in range(48):
            if cy["s1_v"][idx]:
                banks.add(cy["s1"][idx])
        ref = {b for b in range(32) if cy["ad_v"][b]}
        if banks != ref:
            bad += 1
            if bad <= 3:
                print(f"    [{mat}] cycle {i}: derived read banks != addr mask; "
                      f"extra={sorted(banks-ref)} missing={sorted(ref-banks)}")
    return bad

def rolling_pack(counts, N):
    """Rolling-phase striping into N lanes/row. Pad to next row when a cycle's
    payload would cross a row boundary. Returns (rows, capacity_in_slots)."""
    p, rows = 0, 0
    for k in counts:
        if k == 0:
            continue
        assert k <= N, f"per-cycle count {k} exceeds lane count {N}"
        if p + k > N:
            rows += 1
            p = 0
        p += k
        if p == N:
            rows += 1
            p = 0
    if p > 0:
        rows += 1
    return rows, rows * N

def stats_for_group(cycles, key, nfields):
    tot = sum(sum(cy[key]) for cy in cycles)
    per_cycle = [sum(cy[key]) for cy in cycles]
    mx = max(per_cycle)
    mean = tot / len(cycles)
    per_field = [sum(cy[key][f] for cy in cycles) for f in range(nfields)]
    fmax, fmin = max(per_field), min(per_field)
    return dict(total=tot, max_conc=mx, mean_conc=mean,
                field_max=fmax, field_min=fmin,
                imbalance=(fmax / (tot / nfields)) if tot else 0.0,
                per_cycle=per_cycle, per_field=per_field)

def analyze(mat):
    C, cycles, unknown = load_matrix(mat)
    r = dict(matrix=mat, cycles=C)
    if unknown:
        r["unknown_ops"] = sorted(unknown)
    bad = validate(cycles, mat)
    r["addr_validation_mismatch_cycles"] = bad

    g_op  = stats_for_group(cycles, "op_v", 16)
    g_s1  = stats_for_group(cycles, "s1_v", 48)
    g_s2  = stats_for_group(cycles, "s2_v", 32)
    g_ad  = stats_for_group(cycles, "ad_v", 32)
    r["groups"] = dict(op=g_op, sel1=g_s1, sel2=g_s2, addr=g_ad)
    idle_cycles = sum(1 for cy in cycles if not (any(cy["op_v"]) or any(cy["we"])))
    r["fully_idle_cycles"] = idle_cycles

    W = dict(op=5, sel1=5, sel2=4, wea=1, addr=11)
    GW = dict(op=80, sel1=240, sel2=128, wea=32, addr=352)

    # ---- E0
    e0 = 832 * C
    r["E0"] = e0

    # ---- E1c: 5 group banks, depth = cycles with any activity in group
    def active_cycles(key):
        return sum(1 for cy in cycles if any(cy[key]))
    d_op, d_s1, d_s2, d_ad = (active_cycles("op_v"), active_cycles("s1_v"),
                              active_cycles("s2_v"), active_cycles("ad_v"))
    d_wea = sum(1 for cy in cycles if any(cy["we"]))
    e1c_payload = d_op*80 + d_s1*240 + d_s2*128 + d_wea*32 + d_ad*352
    e1c = e1c_payload + 5*C
    r["E1c"] = dict(total=e1c, payload=e1c_payload, mask=5*C,
                    depths=dict(op=d_op, sel1=d_s1, sel2=d_s2, wea=d_wea, addr=d_ad))

    # ---- E1f: per-field banks; mask = 16(op)+48(sel1)+32(addr) + wea raw 32 = 128b/cycle
    e1f_payload = (g_op["total"]*5 + g_s1["total"]*5 + g_s2["total"]*4 + g_ad["total"]*11)
    mask_m1 = 128 * C
    e1f = e1f_payload + mask_m1
    r["E1f"] = dict(total=e1f, payload=e1f_payload, mask=mask_m1)

    # ---- E2g: 4 pools
    def pool(stat, width, N=None):
        N = N or stat["max_conc"]
        rows, cap = rolling_pack(stat["per_cycle"], N)
        return dict(N=N, rows=rows, width=width, bits=rows*N*width,
                    util=stat["total"]/cap if cap else 1.0)
    pools = dict(op=pool(g_op, 5), sel1=pool(g_s1, 5),
                 sel2=pool(g_s2, 4), addr=pool(g_ad, 11))
    e2g_payload = sum(p["bits"] for p in pools.values())
    e2g = e2g_payload + mask_m1
    r["E2g"] = dict(total=e2g, payload=e2g_payload, mask=mask_m1, pools=pools)

    # ---- E2g5: op+sel1 share one 5b pool (64 fields)
    pc5 = [a + b for a, b in zip(g_op["per_cycle"], g_s1["per_cycle"])]
    stat5 = dict(total=g_op["total"] + g_s1["total"], max_conc=max(pc5), per_cycle=pc5)
    pools5 = dict(opsel1=pool(stat5, 5), sel2=pools["sel2"], addr=pools["addr"])
    e2g5_payload = sum(p["bits"] for p in pools5.values())
    e2g5 = e2g5_payload + mask_m1
    r["E2g5"] = dict(total=e2g5, payload=e2g5_payload, mask=mask_m1, pools=pools5)

    # ---- E2p: bit-level pack of all valid payloads, row width W = N*w
    L = [g_op["per_cycle"][i]*5 + g_s1["per_cycle"][i]*5 +
         g_s2["per_cycle"][i]*4 + g_ad["per_cycle"][i]*11 for i in range(C)]
    Lmax = max(L)
    e2p_variants = {}
    for w in (16, 32, 64):
        N = math.ceil(Lmax / w)
        Wrow = N * w
        rows, cap = rolling_pack(L, Wrow)
        payload = rows * Wrow
        e2p_variants[f"w{w}"] = dict(lanes=N, row_bits=Wrow, rows=rows,
                                     payload=payload, total=payload + mask_m1,
                                     util=sum(L)/cap if cap else 1.0)
    r["E2p"] = dict(Lmax=Lmax, Lmean=sum(L)/C, variants=e2p_variants, mask=mask_m1)

    # ---- M2 metadata variant for E2g5/E2p: op raw + wea raw + addr mask = 144b/cycle
    mask_m2 = 144 * C
    # under M2, op payloads are stored raw (80b/cycle) and removed from pools
    pc_s1only = g_s1["per_cycle"]
    pools_m2 = dict(sel1=pool(g_s1, 5), sel2=pools["sel2"], addr=pools["addr"])
    e2g5_m2_payload = 80*C + sum(p["bits"] for p in pools_m2.values())
    r["E2g5_M2"] = dict(total=e2g5_m2_payload + mask_m2, payload=e2g5_m2_payload, mask=mask_m2)
    Lm2 = [g_s1["per_cycle"][i]*5 + g_s2["per_cycle"][i]*4 + g_ad["per_cycle"][i]*11 for i in range(C)]
    Lmax2 = max(Lm2)
    N2 = math.ceil(Lmax2 / 32)
    rows2, cap2 = rolling_pack(Lm2, N2*32)
    r["E2p_M2"] = dict(total=80*C + rows2*N2*32 + mask_m2,
                       payload=80*C + rows2*N2*32, mask=mask_m2, lanes=N2, rows=rows2)

    # ---- SLICE: naive equal slicing of raw 832b (no repack)
    # field bit ranges in the 832b word (layout order: sel1|sel2|op|wea|addr)
    ranges = []  # (start, end, group_key, field_idx)
    pos = 0
    for key, nf, w in (("s1_v", 48, 5), ("s2_v", 32, 4), ("op_v", 16, 5),
                       ("we", 32, 1), ("ad_v", 32, 11)):
        for f in range(nf):
            ranges.append((pos, pos + w, key, f))
            pos += w
    assert pos == 832
    slice_res = {}
    for nl in (13, 26, 52):
        wl = 832 // nl  # 64, 32, 16
        drop = 0
        for cy in cycles:
            for l in range(nl):
                lo, hi = l*wl, (l+1)*wl
                if all(not cy[k][f] for (s, e, k, f) in ranges if s < hi and e > lo):
                    drop += 1
        kept_bits = (nl * C - drop) * wl
        slice_res[f"{nl}x{wl}"] = dict(droppable_per_cycle=drop / C,
                                       frac=drop / (nl * C),
                                       total=kept_bits + nl * C)  # + lane mask
    r["SLICE"] = slice_res

    # ---- M4 metadata: op mask 16b + wea 32b = 48b/cycle
    # (sel1 mask derived from op mask + op payloads via OP_PATTERN;
    #  addr mask derived from sel1 values; sel2 mask == wea)
    mask_m4 = 48 * C
    r["M4_bits_per_cycle"] = 48
    r["E1f_M4"] = e1f_payload + mask_m4
    # E2g with dual-bank row interleave => no row-boundary padding (lower bound):
    # capacity per pool = N * ceil(total/N) * w
    e2g_np_payload = 0
    for g, wdt in (("op", 5), ("sel1", 5), ("sel2", 4), ("addr", 11)):
        s = r["groups"][g]
        e2g_np_payload += s["max_conc"] * math.ceil(s["total"] / s["max_conc"]) * wdt
    r["E2g_nopad_M4"] = dict(total=e2g_np_payload + mask_m4, payload=e2g_np_payload, mask=mask_m4)
    e2g_m4 = e2g_payload + mask_m4
    r["E2g_M4"] = dict(total=e2g_m4, payload=e2g_payload, mask=mask_m4)
    return r

def fmt(bits):
    return f"{bits/1e6:.3f} Mb" if bits >= 1e6 else f"{bits/1e3:.1f} Kb"

def main():
    results = []
    for m in MATS:
        print(f"== {m} ==")
        results.append(analyze(m))
    print("\n" + "="*120)
    hdr = f"{'matrix':<18}{'C':>7} | {'E0':>9} | {'E1c':>9} | {'E1f':>9} | {'E2g':>9} | {'E2g5':>9} | {'E2p32':>9} | {'E2g5_M2':>9} | {'E2p_M2':>9}"
    print(hdr); print("-"*len(hdr))
    for r in results:
        print(f"{r['matrix']:<18}{r['cycles']:>7} | {fmt(r['E0']):>9} | {fmt(r['E1c']['total']):>9} | "
              f"{fmt(r['E1f']['total']):>9} | {fmt(r['E2g']['total']):>9} | {fmt(r['E2g5']['total']):>9} | "
              f"{fmt(r['E2p']['variants']['w32']['total']):>9} | {fmt(r['E2g5_M2']['total']):>9} | {fmt(r['E2p_M2']['total']):>9}")
    print("\ncompression ratio vs E0 (higher=better):")
    for r in results:
        e0 = r["E0"]
        print(f"  {r['matrix']:<18} E1c {e0/r['E1c']['total']:.2f}x | E1f {e0/r['E1f']['total']:.2f}x | "
              f"E2g {e0/r['E2g']['total']:.2f}x | E2p32 {e0/r['E2p']['variants']['w32']['total']:.2f}x | "
              f"E1f_M4 {e0/r['E1f_M4']:.2f}x | E2g_M4 {e0/r['E2g_M4']['total']:.2f}x | "
              f"E2g_nopad_M4 {e0/r['E2g_nopad_M4']['total']:.2f}x")
    print("\nM4-metadata totals (mask=48b/cycle) and SLICE totals:")
    for r in results:
        print(f"  {r['matrix']:<18} E1f_M4={fmt(r['E1f_M4']):>9} E2g_M4={fmt(r['E2g_M4']['total']):>9} "
              f"E2g_nopad_M4={fmt(r['E2g_nopad_M4']['total']):>9} "
              f"SLICE26x32={fmt(r['SLICE']['26x32']['total']):>9} SLICE13x64={fmt(r['SLICE']['13x64']['total']):>9}")
    print("\ngroup activity / concurrency:")
    for r in results:
        print(f"  {r['matrix']:<18} C={r['cycles']}, idle={r['fully_idle_cycles']}, "
              f"addr_mismatch={r['addr_validation_mismatch_cycles']}")
        for g in ("op", "sel1", "sel2", "addr"):
            s = r["groups"][g]
            print(f"    {g:<5} total={s['total']:>8} max_conc={s['max_conc']:>3} "
                  f"mean_conc={s['mean_conc']:>6.2f} field_max={s['field_max']:>7} "
                  f"field_min={s['field_min']:>7} imbalance={s['imbalance']:.2f}")
    print("\nE2g pool detail (N lanes x rows x width):")
    for r in results:
        for g, p in r["E2g"]["pools"].items():
            print(f"  {r['matrix']:<18} {g:<5} N={p['N']:>3} rows={p['rows']:>6} w={p['width']} "
                  f"bits={p['bits']:>9} util={p['util']:.3f}")
    print("\nE2p detail:")
    for r in results:
        e = r["E2p"]
        print(f"  {r['matrix']:<18} Lmax={e['Lmax']} Lmean={e['Lmean']:.1f}")
        for k, v in e["variants"].items():
            print(f"    {k}: {v['lanes']} lanes x {v['rows']} rows x row={v['row_bits']}b "
                  f"payload={v['payload']} util={v['util']:.3f}")
    print("\nSLICE (naive equal slicing, no repack) droppable-lane fraction:")
    for r in results:
        for k, v in r["SLICE"].items():
            print(f"  {r['matrix']:<18} {k}: {v['droppable_per_cycle']:.2f} lanes/cycle ({v['frac']*100:.2f}%)")

    out = os.path.join(LU, "e2_mask_run", "lu_e2_striping_results.json")
    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items() if k not in ("per_cycle", "per_field")}
        return o
    with open(out, "w") as f:
        json.dump([strip(r) for r in results], f, indent=1, ensure_ascii=False)
    print(f"\nJSON written: {out}")

if __name__ == "__main__":
    main()

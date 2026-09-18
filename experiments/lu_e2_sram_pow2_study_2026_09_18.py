#!/usr/bin/env python3
"""
LU VLIW: actual SRAM-bit comparison of E0 / E1 / E2 with depths padded to powers of 2.

Schemes:
  E0        : 832b x pow2(C)
  E1u       : 5 slot banks, UNIFORM depth = pow2(max group active cycles)  [FRV-E1 analog]
  E1c       : 5 slot banks, per-group depth = pow2(group active cycles), mask 5b/cyc
  E2        : user's scheme - wea raw + 4 striped pools (op 16x5b, sel1 48x5b, sel2 16x4b,
              addr 32x11b), rolling-phase rows (single-row/cycle, with padding),
              explicit mask M1 128b/cyc
  E2+       : same pools but dual-bank row interleave (no padding: rows = ceil(total/N))
              + derived mask M4 48b/cyc
Two depth-quantization conventions:
  strict    : depth = next power of 2
  tiled2    : depth = 2^a + 2^b (minimal sum of at most two pow2 tiles >= needed)
All numbers in bits; ratios vs E0 under the SAME convention.
"""
import os, sys, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lu_e2_striping_study_2026_09_18 import load_matrix, MATS, LU, rolling_pack

def p2(n):
    return 1 << max(0, (n - 1).bit_length())

def p2_tiled2(n):
    if n <= 1:
        return max(1, n)
    a = n.bit_length() - 1
    base = 1 << a
    if base == n:
        return n
    return base + p2(n - base)

def mb(bits):
    return bits / 1e6

results = {}
for mat in MATS:
    C, cycles, _ = load_matrix(mat)

    # group activity (E1 depths)
    def active(key):
        return sum(1 for cy in cycles if any(cy[key]))
    d = dict(op=active("op_v"), sel1=active("s1_v"), sel2=active("s2_v"),
             wea=sum(1 for cy in cycles if any(cy["we"])), addr=active("ad_v"))

    # E2 pool stats
    groups = {}
    for key, nf, w in (("op_v", 16, 5), ("s1_v", 48, 5), ("s2_v", 32, 4), ("ad_v", 32, 11)):
        per_cycle = [sum(cy[key]) for cy in cycles]
        total = sum(per_cycle)
        N = max(per_cycle)
        rows_pad, _ = rolling_pack(per_cycle, N)
        rows_nopad = math.ceil(total / N)
        groups[key] = dict(w=w, N=N, total=total, rows_pad=rows_pad, rows_nopad=rows_nopad)

    for conv, f in (("strict", p2), ("tiled2", p2_tiled2)):
        e0 = 832 * f(C)
        # E1 uniform
        dmax = max(d.values())
        e1u = 832 * f(dmax) + 5 * f(C)
        # E1 per-group
        e1c = (240 * f(d["sel1"]) + 128 * f(d["sel2"]) + 80 * f(d["op"]) +
               32 * f(d["wea"]) + 352 * f(d["addr"])) + 5 * f(C)
        # E2 (M1): pools with padding rows + wea raw + mask 128b
        e2 = sum(g["N"] * g["w"] * f(g["rows_pad"]) for g in groups.values()) \
             + 32 * f(C) + 128 * f(C)
        # E2+ (M4 + nopad): pools with nopad rows + wea raw + mask 48b
        e2p = sum(g["N"] * g["w"] * f(g["rows_nopad"]) for g in groups.values()) \
              + 32 * f(C) + 48 * f(C)
        results.setdefault(mat, {})[conv] = dict(
            C=C, E0=e0, E1u=e1u, E1c=e1c, E2=e2, E2p=e2p,
            ratios=dict(E1u=e0 / e1u, E1c=e0 / e1c, E2=e0 / e2, E2p=e0 / e2p))
        results[mat][f"depths_{conv}"] = dict(
            C=f(C), op=d["op"], sel1=d["sel1"], sel2=d["sel2"], wea=d["wea"], addr=d["addr"],
            pools={k: (g["N"], g["w"], f(g["rows_pad"]), f(g["rows_nopad"])) for k, g in groups.items()})

for conv in ("strict", "tiled2"):
    print(f"\n===== depth convention: {conv} =====")
    hdr = f"{'matrix':<18}{'C':>7} | {'E0':>8} | {'E1u':>8} | {'E1c':>8} | {'E2(M1)':>8} | {'E2+(M4nopad)':>12} | ratios E1u/E1c/E2/E2+"
    print(hdr)
    for mat in MATS:
        r = results[mat][conv]
        rr = r["ratios"]
        print(f"{mat:<18}{r['C']:>7} | {mb(r['E0']):>7.2f}M | {mb(r['E1u']):>7.2f}M | {mb(r['E1c']):>7.2f}M | "
              f"{mb(r['E2']):>7.2f}M | {mb(r['E2p']):>10.2f}M | "
              f"{rr['E1u']:.2f} / {rr['E1c']:.2f} / {rr['E2']:.2f} / {rr['E2p']:.2f}")

print("\n===== depth details =====")
for mat in MATS:
    print(f"{mat}: C={results[mat]['strict']['C']} pow2(C)={results[mat]['depths_strict']['C']}")
    print(f"  E1 group active cycles: op={results[mat]['depths_strict']['op']} sel1={results[mat]['depths_strict']['sel1']} "
          f"sel2={results[mat]['depths_strict']['sel2']} wea={results[mat]['depths_strict']['wea']} addr={results[mat]['depths_strict']['addr']}")
    for k, v in results[mat]['depths_strict']['pools'].items():
        print(f"  pool {k:<5} N={v[0]:>3} w={v[1]:>2}  rows_pad->strict {v[2]:>6}  rows_nopad->strict {v[3]:>6}")

# ================= unified program pool over the 4 matrices =================
# Collect per-matrix bank requirements: list of (width, depth_needed) per scheme.
per_mat = {}
for mat in MATS:
    C, cycles, _ = load_matrix(mat)
    def active(key):
        return sum(1 for cy in cycles if any(cy[key]))
    d = dict(op=active("op_v"), sel1=active("s1_v"), sel2=active("s2_v"),
             wea=sum(1 for cy in cycles if any(cy["we"])), addr=active("ad_v"))
    pools = {}
    for key, nf, w in (("op_v", 16, 5), ("s1_v", 48, 5), ("s2_v", 32, 4), ("ad_v", 32, 11)):
        per_cycle = [sum(cy[key]) for cy in cycles]
        total = sum(per_cycle)
        N = max(per_cycle)
        rows_pad, _ = rolling_pack(per_cycle, N)
        pools[key] = dict(w=w, N=N, rows_pad=rows_pad, rows_nopad=math.ceil(total / N))
    per_mat[mat] = dict(C=C, d=d, pools=pools)

def pool_total(f, mode):
    """mode: 'max' (replaceable, unified sizing) or 'sum' (simultaneously resident)."""
    def agg(vals):
        return max(vals) if mode == "max" else sum(vals)
    out = {}
    # E0: (832, C)
    out["E0"] = 832 * f(agg([m["C"] for m in per_mat.values()]))
    # E1u: uniform depth = agg of max group active
    e1u_depth = agg([max(m["d"].values()) for m in per_mat.values()])
    out["E1u"] = 832 * f(e1u_depth) + 5 * f(agg([m["C"] for m in per_mat.values()]))
    # E1c: per-group
    e1c = 0
    for gkey, w in (("sel1", 240), ("sel2", 128), ("op", 80), ("wea", 32), ("addr", 352)):
        e1c += w * f(agg([m["d"][gkey] for m in per_mat.values()]))
    out["E1c"] = e1c + 5 * f(agg([m["C"] for m in per_mat.values()]))
    # E2 (M1): pools (N=max over mats) + wea + mask 128
    e2 = 0
    for pkey in ("op_v", "s1_v", "s2_v", "ad_v"):
        N = max(m["pools"][pkey]["N"] for m in per_mat.values())
        w = per_mat[MATS[0]]["pools"][pkey]["w"]
        e2 += N * w * f(agg([m["pools"][pkey]["rows_pad"] for m in per_mat.values()]))
    e2 += 32 * f(agg([m["C"] for m in per_mat.values()])) + 128 * f(agg([m["C"] for m in per_mat.values()]))
    out["E2"] = e2
    # E2+ (M4 + nopad)
    e2p = 0
    for pkey in ("op_v", "s1_v", "s2_v", "ad_v"):
        N = max(m["pools"][pkey]["N"] for m in per_mat.values())
        w = per_mat[MATS[0]]["pools"][pkey]["w"]
        e2p += N * w * f(agg([m["pools"][pkey]["rows_nopad"] for m in per_mat.values()]))
    e2p += 32 * f(agg([m["C"] for m in per_mat.values()])) + 48 * f(agg([m["C"] for m in per_mat.values()]))
    out["E2p"] = e2p
    return out

print("\n===== unified pool (4 matrices) =====")
for conv, f in (("strict", p2), ("tiled2", p2_tiled2)):
    for mode, label in (("max", "分时驻留(深度取max)"), ("sum", "同时驻留(深度取sum)")):
        r = pool_total(f, mode)
        print(f"[{conv} / {label}] E0={mb(r['E0']):.2f}M  E1u={mb(r['E1u']):.2f}M({r['E0']/r['E1u']:.2f}x)  "
              f"E1c={mb(r['E1c']):.2f}M({r['E0']/r['E1c']:.2f}x)  E2={mb(r['E2']):.2f}M({r['E0']/r['E2']:.2f}x)  "
              f"E2+={mb(r['E2p']):.2f}M({r['E0']/r['E2p']:.2f}x)")
    results.setdefault("pool", {})[conv] = {m: pool_total(f, m) for m in ("max", "sum")}

out = os.path.join(LU, "e2_mask_run", "lu_e2_sram_pow2_results.json")
with open(out, "w") as fp:
    json.dump(results, fp, indent=1, ensure_ascii=False)
print(f"\nJSON written: {out}")

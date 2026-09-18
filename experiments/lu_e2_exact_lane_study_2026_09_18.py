#!/usr/bin/env python3
"""
LU VLIW E2 striping - CORRECTED model matching the repo's real E2 mechanism
(see experiments/e2_five_lane_model_pool_study_2026_09_13.py encode_e2_5/decode_e2_5):

  Per pool: N independent lane banks, each with its own read pointer.
  Cycle i with k_i valid fields: fields (ascending id) -> lane (phase+rank) mod N,
  target lane appends one entry; phase = (phase + k_i) mod N.
  NO rows, NO padding. Pool depth = max per-lane append count (exact simulation).

Schemes:
  E0        : 832b x C
  E1c       : 5 slot banks (240/128/80/32/352b), depth = group active cycles, mask 5b/cyc
  E2-M1     : 4 pools (op 16x5b, sel1 48x5b, sel2 16x4b, addr 32x11b) + wea raw 32b/cyc
              + explicit mask 128b/cyc (op16+sel1 48+addr32+wea32)
  E2-M4     : same pools + derived mask 48b/cyc (op mask 16b + wea 32b;
              sel1 mask derived from op via pattern table, addr mask = union of sel1 values)
Depth quantization: logical (exact) / strict pow2 / tiled2 (2^a+2^b).
Pool semantics: per-matrix, unified-replaceable (max), unified-resident (sum).
"""
import os, sys, math, json
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

def lane_depths(per_cycle_counts, N):
    """Exact simulation of phase-rolling append; returns (max_lane_count, counts)."""
    lanes = [0] * N
    phase = 0
    for k in per_cycle_counts:
        for r in range(k):
            lanes[(phase + r) % N] += 1
        phase = (phase + k) % N
    return max(lanes), lanes

POOLS = [("op", "op_v", 16, 5), ("sel1", "s1_v", 48, 5), ("sel2", "s2_v", 32, 4), ("addr", "ad_v", 32, 11)]

per_mat = {}
for mat in MATS:
    C, cycles, _ = load_matrix(mat)
    d = dict(op=sum(1 for cy in cycles if any(cy["op_v"])),
             sel1=sum(1 for cy in cycles if any(cy["s1_v"])),
             sel2=sum(1 for cy in cycles if any(cy["s2_v"])),
             wea=sum(1 for cy in cycles if any(cy["we"])),
             addr=sum(1 for cy in cycles if any(cy["ad_v"])))
    pools = {}
    for name, key, nf, w in POOLS:
        pc = [sum(cy[key]) for cy in cycles]
        N = max(pc)
        depth, counts = lane_depths(pc, N)
        pools[name] = dict(N=N, w=w, total=sum(pc), depth=depth,
                           ideal=math.ceil(sum(pc) / N),
                           lane_min=min(counts), lane_max=max(counts))
    per_mat[mat] = dict(C=C, d=d, pools=pools)
    imb = {n: (p["depth"], p["ideal"]) for n, p in pools.items()}
    print(f"== {mat} (C={C}) ==  pool depth vs ceil(total/N): " +
          "  ".join(f"{n}:{v[0]}/{v[1]}" for n, v in imb.items()))

def scheme_bits(f, mats):
    """Total SRAM bits for the set of matrices under depth rule f.
    mats: list of matrix names included (each loaded separately => depth=max;
    for simultaneous residency pass mode='sum')."""
    raise NotImplementedError

def totals(f, mode):
    """mode: 'max' = replaceable (depth = max over matrices), 'sum' = resident (depth = sum)."""
    def agg(vals):
        return max(vals) if mode == "max" else sum(vals)
    out = {}
    Cagg = agg([m["C"] for m in per_mat.values()])
    out["E0"] = 832 * f(Cagg)
    dmax = agg([max(m["d"].values()) for m in per_mat.values()])
    out["E1u"] = 832 * f(dmax) + 5 * f(Cagg)
    e1c = 0
    for g, w in (("sel1", 240), ("sel2", 128), ("op", 80), ("wea", 32), ("addr", 352)):
        e1c += w * f(agg([m["d"][g] for m in per_mat.values()]))
    out["E1c"] = e1c + 5 * f(Cagg)
    e2 = e2m4 = 0
    for name, _, _, w in POOLS:
        N = max(m["pools"][name]["N"] for m in per_mat.values())
        dep = agg([m["pools"][name]["depth"] for m in per_mat.values()])
        e2 += N * w * f(dep)
        e2m4 += N * w * f(dep)
    out["E2_M1"] = e2 + 32 * f(Cagg) + 128 * f(Cagg)
    out["E2_M4"] = e2m4 + 32 * f(Cagg) + 48 * f(Cagg)
    return out

print("\n===== CORRECTED E2 (no padding) - per matrix =====")
hdr = f"{'matrix':<18}{'C':>7} | {'conv':<7} | {'E0':>8} | {'E1c':>8} | {'E2-M1':>8} | {'E2-M4':>8} | ratios E1c/E2-M1/E2-M4"
print(hdr)
final = {}
for mat in MATS:
    final[mat] = {}
    for conv, f in (("logical", lambda x: x), ("strict", p2), ("tiled2", p2_tiled2)):
        save = per_mat
        one = {mat: per_mat[mat]}
        per_mat = one
        r = totals(f, "max")
        per_mat = save
        final[mat][conv] = r
        print(f"{mat:<18}{r and per_mat[mat]['C']:>7} | {conv:<7} | {r['E0']/1e6:>7.2f}M | {r['E1c']/1e6:>7.2f}M | "
              f"{r['E2_M1']/1e6:>7.2f}M | {r['E2_M4']/1e6:>7.2f}M | "
              f"{r['E0']/r['E1c']:.2f} / {r['E0']/r['E2_M1']:.2f} / {r['E0']/r['E2_M4']:.2f}")

print("\n===== CORRECTED E2 - unified 4-matrix pool =====")
for conv, f in (("strict", p2), ("tiled2", p2_tiled2)):
    for mode, label in (("max", "分时驻留max"), ("sum", "同时驻留sum")):
        r = totals(f, mode)
        final.setdefault("pool", {}).setdefault(conv, {})[mode] = r
        print(f"[{conv}/{label}] E0={r['E0']/1e6:.2f}M E1c={r['E1c']/1e6:.2f}M({r['E0']/r['E1c']:.2f}x) "
              f"E2-M1={r['E2_M1']/1e6:.2f}M({r['E0']/r['E2_M1']:.2f}x) E2-M4={r['E2_M4']/1e6:.2f}M({r['E0']/r['E2_M4']:.2f}x)")

out = os.path.join(LU, "e2_mask_run", "lu_e2_exact_lane_results.json")
with open(out, "w") as fp:
    json.dump(final, fp, indent=1, ensure_ascii=False)
print(f"\nJSON written: {out}")

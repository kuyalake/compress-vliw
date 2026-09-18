#!/usr/bin/env python3
"""
LU VLIW 832-bit word: "cut the whole instruction into equal blocks" study.

Three blockings, all with per-cycle block-drop mask (block stored <=> any member field valid;
dropped blocks refill position-dependent defaults: op=0, wea=0, sel1=idx%32, sel2=b/2, addr=2047):

  A. NATURAL SLICE : equal slices of the raw 832b word in file-concatenation layout
                     (sel1|sel2|op|wea|addr), no reordering.
  B. HW-ALIGNED    : 16 PE blocks x 20b (op_j + 3x sel1) + 32 bank blocks x 16b
                     (addr_b + sel2_b + wea_b) = 832b, blocks aligned to hardware structure.
  C. OPT-BLOCK     : equal W-bit blocks after a *static bit permutation* (zero-cost wires in
                     hardware) that clusters fields by validity-pattern correlation.
                     Greedy agglomerative merge maximizing per-cycle joint-idle overlap,
                     cluster content width capped at W.

References: E0 = 832*C ; E1f = per-field vertical (128 banks, logical lower bound, M1 mask 128b/cyc).

Field inventory (136 fields, 832 bits):
  sel1: 48 x 5b | sel2: 32 x 4b | op: 16 x 5b | wea: 32 x 1b | addr: 32 x 11b
"""
import os, sys, math, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/Users/maghu/Desktop/work at school/compress/compress-vliw/.python-deps")
import numpy as np

from lu_e2_striping_study_2026_09_18 import load_matrix, MATS, LU

# field list: (name, width) in fixed order; validity vector built per matrix
FIELDS = (
    [("sel1", 5)] * 48 + [("sel2", 4)] * 32 + [("op", 5)] * 16 +
    [("wea", 1)] * 32 + [("addr", 11)] * 32
)
NF = len(FIELDS)          # 136
WIDTHS = np.array([w for _, w in FIELDS], dtype=np.int64)
assert WIDTHS.sum() == 832

def validity_matrix(cycles):
    """C x 136 bool matrix, column order = FIELDS."""
    C = len(cycles)
    V = np.zeros((C, NF), dtype=bool)
    for i, cy in enumerate(cycles):
        V[i, 0:48]    = cy["s1_v"]
        V[i, 48:80]   = cy["s2_v"]
        V[i, 80:96]   = cy["op_v"]
        V[i, 96:128]  = cy["we"]
        V[i, 128:160] = cy["ad_v"]
    return V

def scheme_storage(block_valid_counts, block_caps, C):
    """bits = sum(valid_cycles_B * cap_B) + n_blocks * C (block mask)."""
    nb = len(block_valid_counts)
    return int(sum(int(v) * int(c) for v, c in zip(block_valid_counts, block_caps)) + nb * C)

# ---------- A: natural-layout equal slices ----------
def natural_slice(V, C, blk_w):
    nb = 832 // blk_w
    # bit ranges of fields in layout order sel1|sel2|op|wea|addr
    ranges = []
    pos = 0
    for fi, w in enumerate(WIDTHS):
        ranges.append((pos, pos + w, fi))
        pos += w
    counts, caps = [], []
    for l in range(nb):
        lo, hi = l * blk_w, (l + 1) * blk_w
        members = [fi for (s, e, fi) in ranges if s < hi and e > lo]
        v = V[:, members].any(axis=1)
        counts.append(int(v.sum()))
        caps.append(blk_w)
    return counts, caps

# ---------- B: hardware-aligned blocks ----------
def hw_aligned(V, C):
    # field indices: sel1 0..47 (idx 3j rd, 3j+1 rt, 3j+2 rs), sel2 48..79 (b),
    # op 80..95 (j), wea 96..127 (b), addr 128..159 (b)
    counts, caps = [], []
    for j in range(16):  # PE block: op_j + sel1[3j..3j+2] = 5+15 = 20b
        members = [80 + j, 3 * j, 3 * j + 1, 3 * j + 2]
        v = V[:, members].any(axis=1)
        counts.append(int(v.sum())); caps.append(20)
    for b in range(32):  # bank block: addr_b + sel2_b + wea_b = 11+4+1 = 16b
        members = [128 + b, 48 + b, 96 + b]
        v = V[:, members].any(axis=1)
        counts.append(int(v.sum())); caps.append(16)
    return counts, caps

# ---------- C: optimized static blocking ----------
def opt_blocks(V, C, blk_w, target_nb):
    """Greedy agglomerative: merge the pair (content width <= blk_w) with max
    joint-valid overlap |vi AND vj| (minimizes merged block's valid cycles).
    Overlaps computed on packed bits (avoids BLAS float matmul issues)."""
    n = NF
    P = np.packbits(V, axis=0)          # (W8, n) uint8

    def popcnt(v):
        return int(np.bitwise_count(v).sum())

    vecs = {i: P[:, i].copy() for i in range(n)}   # packed validity per cluster
    widths = {i: int(w) for i, w in enumerate(WIDTHS)}
    members = {i: [i] for i in range(n)}
    alive = list(range(n))

    def overlap(a, b):
        return popcnt(np.bitwise_and(vecs[a], vecs[b]))

    G = np.zeros((n, n), dtype=np.int64)
    for x in range(n):
        for y in range(x + 1, n):
            G[x, y] = G[y, x] = overlap(x, y)
    G[np.arange(n), np.arange(n)] = -1

    while len(alive) > target_nb:
        Wa = np.array([widths[i] for i in alive])
        Ga = G[np.ix_(alive, alive)]
        ok = (Wa[:, None] + Wa[None, :]) <= blk_w
        Ga = np.where(ok, Ga, -1)
        idx = int(np.argmax(Ga))
        bi, bj = idx // Ga.shape[1], idx % Ga.shape[1]
        if Ga[bi, bj] < 0:
            break  # no capacity-feasible merge left
        i, j = alive[bi], alive[bj]
        vecs[i] = np.bitwise_or(vecs[i], vecs[j])
        widths[i] += widths[j]
        members[i] += members[j]
        for k in alive:
            if k == i:
                continue
            G[i, k] = G[k, i] = overlap(i, k)
        G[i, i] = -1
        G[j, :] = -1
        G[:, j] = -1
        alive.remove(j)

    counts = [popcnt(vecs[i]) for i in alive]
    caps = [blk_w] * len(alive)
    return counts, caps, [members[i] for i in alive], [widths[i] for i in alive]

def main():
    all_res = {}
    for mat in MATS:
        C, cycles, unknown = load_matrix(mat)
        assert not unknown
        V = validity_matrix(cycles)
        e0 = 832 * C
        res = {"cycles": C, "E0": e0}

        # A: natural slices
        for bw in (104, 64, 32, 16):
            counts, caps = natural_slice(V, C, bw)
            st = scheme_storage(counts, caps, C)
            res[f"A_natural_{832//bw}x{bw}"] = dict(
                blocks=832 // bw, storage=st, ratio=e0 / st,
                drop_per_cycle=(832 // bw) - sum(counts) / C)

        # B: hw-aligned
        counts, caps = hw_aligned(V, C)
        st = scheme_storage(counts, caps, C)
        res["B_hw_aligned"] = dict(blocks=len(counts), storage=st, ratio=e0 / st,
                                   drop_per_cycle=len(counts) - sum(counts) / C)

        # reference: E1f per-field vertical (M1 mask 128b/cycle)
        e1f = int((V.sum(axis=0) * WIDTHS).sum()) + 128 * C
        res["E1f_ref"] = dict(blocks=136, storage=e1f, ratio=e0 / e1f,
                              drop_per_cycle=0)

        # C: optimized equal blocks
        for bw in (104, 64, 32, 16):
            target = math.ceil(832 / bw)
            counts, caps, members, cwidths = opt_blocks(V, C, bw, target)
            st = scheme_storage(counts, caps, C)
            res[f"C_opt_{len(counts)}x{bw}"] = dict(
                blocks=len(counts), storage=st, ratio=e0 / st,
                drop_per_cycle=len(counts) - sum(counts) / C,
                content_widths=sorted(cwidths, reverse=True)[:8])
            if bw == 32:
                # summarize composition of clusters
                comp = []
                for m in members:
                    kinds = {}
                    for fi in m:
                        k = FIELDS[fi][0]
                        kinds[k] = kinds.get(k, 0) + 1
                    comp.append(kinds)
                res[f"C_opt_{len(counts)}x{bw}"]["composition_sample"] = comp[:6]
        all_res[mat] = res
        print(f"== {mat} (C={C}) ==")
        for k, v in res.items():
            if k in ("cycles", "E0"):
                continue
            print(f"  {k:<18} blocks={v['blocks']:>3} drop/cyc={v['drop_per_cycle']:>6.2f} "
                  f"storage={v['storage']/1e6:>8.3f} Mb  ratio={v['ratio']:.3f}x")

    out = os.path.join(LU, "e2_mask_run", "lu_e2_block_slicing_results.json")
    with open(out, "w") as f:
        json.dump(all_res, f, indent=1, ensure_ascii=False, default=str)
    print(f"\nJSON written: {out}")

if __name__ == "__main__":
    main()

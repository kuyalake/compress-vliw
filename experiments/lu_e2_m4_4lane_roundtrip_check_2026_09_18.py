#!/usr/bin/env python3
"""
FACT CHECK: does the E2-M4 scheme with N=4 equal-width lanes per slot still decode
correctly in hardware, including the derived-mask chain?

Hardware-faithful software model:
  ENCODE (offline): per pool (op/sel1/sel2/addr), N=4 lanes, lane width = slot width / 4
    (op 20b=4f, sel1 60b=12f, sel2 32b=8f, addr 88b=8f per word).
    Cycle i: k valid fields (ascending id) -> lane (phase+r) mod 4, appended to that
    lane's bitstream (fields packed continuously into words, last word zero-padded);
    phase = (phase + k) mod 4.
  DECODE (per cycle, zero-stall):
    - read op mask (16b) + wea (32b) from streams
    - op pool: extract popcount(op mask) fields via round-robin from lane buffers
    - derive sel1 mask from op values via OP_PATTERN (pure function)
    - sel1 pool extract; derive addr mask = union of sel1 values
    - sel2 mask = wea; sel2 pool extract
    - rebuild 832b word (defaults for invalid fields) and compare BIT-EXACT vs original
    Buffer model per lane: 2-word skid buffer, at most 1 word read per lane per cycle,
    read issued at end of cycle when buffer < 1 word (1-cycle SRAM latency, arrives next
    cycle); assert buffer never underflows at consumption time.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lu_e2_striping_study_2026_09_18 import load_matrix, OP_PATTERN, MATS, LU

N = 4
POOLS = [  # name, vkey, n_fields, field_w, default_fn
    ("op",   "op_v", 16, 5,  lambda idx: 0),
    ("sel1", "s1_v", 48, 5,  lambda idx: idx % 32),
    ("sel2", "s2_v", 32, 4,  lambda idx: idx // 2),
    ("addr", "ad_v", 32, 11, lambda idx: 2047),
]
VALKEY = {"op": "ops", "sel1": "s1", "sel2": "s2", "addr": "ad"}

def encode(cycles, C):
    """returns pools: name -> list of 4 lanes, each a list of words (ints)."""
    pools = {}
    for name, vk, nf, w, dflt in POOLS:
        lw = (nf * w) // N
        fpw = lw // w
        lanes = [[] for _ in range(N)]   # per-lane field values
        phase = 0
        for i in range(C):
            cy = cycles[i]
            valid = [f for f in range(nf) if cy[vk][f]]
            for r, f in enumerate(valid):
                lanes[(phase + r) % N].append(cy[VALKEY[name]][f])
            phase = (phase + len(valid)) % N
        # pack fields into words
        lane_words = []
        for fl in lanes:
            words = []
            for i in range(0, len(fl), fpw):
                chunk = fl[i:i + fpw]
                word = 0
                for j, v in enumerate(chunk):
                    word |= v << (j * w)
                words.append(word)
            lane_words.append(words)
        pools[name] = dict(words=lane_words, fpw=fpw, w=w, lw=lw,
                           depth=max(len(x) for x in lane_words))
    return pools

def decode_and_check(cycles, C, pools, mat):
    """Hardware-faithful decode; returns (bit_exact, underflows, max_buffer_words)."""
    underflows = 0
    max_buf = [0]
    # per-pool decode state
    st = {}
    for name, _, _, _, _ in POOLS:
        p = pools[name]
        st[name] = dict(phase=0,
                        buf=[[] for _ in range(N)],       # per-lane pending fields
                        ptr=[0] * N)                      # per-lane next word index
    # prefill 2 words per lane (reset sequence)
    for name, _, _, _, _ in POOLS:
        p = pools[name]
        for l in range(N):
            for _ in range(2):
                if st[name]["ptr"][l] < len(p["words"][l]):
                    word = p["words"][l][st[name]["ptr"][l]]
                    st[name]["ptr"][l] += 1
                    st[name]["buf"][l].extend((word >> (j * p["w"])) & ((1 << p["w"]) - 1)
                                              for j in range(p["fpw"]))

    def extract(name, mask_bits, i):
        """extract popcount fields for cycle i following round-robin; returns {field: value}."""
        p = pools[name]
        s = st[name]
        valid_fields = [f for f, b in enumerate(mask_bits) if b]
        k = len(valid_fields)
        out = {}
        # per-lane consumption this cycle
        need = [0] * N
        for r in range(k):
            need[(s["phase"] + r) % N] += 1
        # underflow check at consumption time
        for l in range(N):
            if need[l] > len(s["buf"][l]):
                underflows += 1
                return None
        for r in range(k):
            l = (s["phase"] + r) % N
            out[valid_fields[r]] = s["buf"][l].pop(0)
        s["phase"] = (s["phase"] + k) % N
        # end-of-cycle refill decision (arrives next cycle): if buffer < 1 word, read 1 word
        for l in range(N):
            if len(s["buf"][l]) < p["fpw"] and s["ptr"][l] < len(p["words"][l]):
                word = p["words"][l][s["ptr"][l]]
                s["ptr"][l] += 1
                s["buf"][l].extend((word >> (j * p["w"])) & ((1 << p["w"]) - 1)
                                   for j in range(p["fpw"]))
            max_buf[0] = max(max_buf[0], len(s["buf"][l]) // max(1, p["fpw"]))
        return out

    for i in range(C):
        cy = cycles[i]
        op_mask = cy["op_v"]                       # 16b stream
        wea = cy["we"]                             # 32b stream
        # 1) op pool
        got = extract("op", op_mask, i)
        if got is None:
            return False, underflows, max_buf[0]
        ops = [got.get(j, 0) for j in range(16)]
        # 2) derive sel1 mask from op values (pattern table)
        s1_mask = [0] * 48
        for j in range(16):
            o = ops[j]
            if o != 0:
                pat = OP_PATTERN[o]
                for k in range(3):
                    s1_mask[3 * j + k] = pat[k]
        got = extract("sel1", s1_mask, i)
        if got is None:
            return False, underflows, max_buf[0]
        s1 = [got.get(idx, (idx % 32)) for idx in range(48)]
        # 3) derive addr mask = union of valid sel1 values
        ad_mask = [0] * 32
        for idx in range(48):
            if s1_mask[idx]:
                ad_mask[s1[idx]] = 1
        got = extract("addr", ad_mask, i)
        if got is None:
            return False, underflows, max_buf[0]
        ad = [got.get(b, 2047) for b in range(32)]
        # 4) sel2 mask = wea
        got = extract("sel2", wea, i)
        if got is None:
            return False, underflows, max_buf[0]
        s2 = [got.get(b, b // 2) for b in range(32)]
        # 5) compare bit-exact vs original
        if (ops != cy["ops"] or s1 != cy["s1"] or s2 != cy["s2"] or ad != cy["ad"]):
            # find first mismatch for debug
            for nm, a, b in (("op", ops, cy["ops"]), ("sel1", s1, cy["s1"]),
                             ("sel2", s2, cy["s2"]), ("addr", ad, cy["ad"])):
                if a != b:
                    print(f"    [{mat}] cycle {i} MISMATCH in {nm}")
                    break
            return False, underflows, max_buf[0]
    return True, underflows, max_buf[0]

print("E2-M4 with N=4 equal lanes per slot: end-to-end hardware-faithful round-trip")
for mat in MATS:
    C, cycles, _ = load_matrix(mat)
    pools = encode(cycles, C)
    ok, uf, mb = decode_and_check(cycles, C, pools, mat)
    depths = {n: pools[n]["depth"] for n, _, _, _, _ in POOLS}
    print(f"  {mat:<18} bit-exact={ok}  buffer-underflows={uf}  "
          f"pool depths={depths}")

#!/usr/bin/env python3
"""Per-model program-pool compression study (BERT / LLaMA / SD-UNet).

Adds DAG constructors for functions NOT in the base scheduler
(Bias+GELU, RMSNorm, SwiGLU, SiLU, GeGLU, GroupNorm), then runs the three
storage schemes (uncompressed / Candidate A / 4-slot) on each model's
nonlinear-function pool and reports cycle count + bank depth + macro types.

Pools (architecture-faithful, X=64, PRIORITY_STRATEGY=index, model-real Y):
  BERT   (512/768/3072): softmax, layernorm, bias_gelu, tanh
  LLaMA  (4096/11008)  : rmsnorm, softmax, swiglu
  SD-UNet (rep. dims)  : groupnorm, silu, layernorm, softmax, geglu

Schemes:
  uncompressed: MAX_ISSUE_SLOTS=5, 174-bit word per cycle
  Candidate A : MAX_ISSUE_SLOTS=5, 5-bit mask + 5 dedicated 34-bit slot banks
  4-slot      : MAX_ISSUE_SLOTS=4, 5-bit mask + phase striping onto 4 lanes

Run:  PYTHONPATH=".python-deps" python3 experiments/model_pool_compression_study.py
"""

import contextlib
import importlib.util
import io
import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]  # compress-vliw/
SCHED_PATH = ROOT / "schedule_v19_issue2_priority_174.py"
OUT_ROOT = ROOT / "analysis_output_model_pool_2026-09-08"

X = 64
NUM_VE = 256
SCHED_KW = dict(NUM_VE=256, VGPR_CAP=256, SGPR_CAP=256, MASK_FIFO=8,
                add_rqo_option0=32, add_rqo_option1=16, add_rqo_option2=16,
                PRIORITY_STRATEGY="index")

# ---------------------------------------------------------------------------
# scheduler loading + monkey-patched dispatch for the new functions
# ---------------------------------------------------------------------------


def load_scheduler():
    spec = importlib.util.spec_from_file_location("scheduler", SCHED_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


sched = load_scheduler()
DAGNode = sched.DAGNode
Operation = sched.Operation


def _segments(Y, NUM_VE):
    K = math.ceil(Y / NUM_VE)
    lens = [NUM_VE] * K
    if Y % NUM_VE != 0:
        lens[-1] = Y - NUM_VE * (K - 1)
    return K, lens


class _B:
    """DAG builder following the scheduler's DAGNode/Operation conventions."""

    def __init__(self):
        self.nodes = {0: DAGNode(0, Operation(None, None, "root"), 0, -1, -1, 0)}
        self.idx = 1

    def const(self, gpr):
        n = self.idx
        self.nodes[n] = DAGNode(n, Operation(None, None, "const"), 0, 0, -1, 1,
                                gpr_addr=gpr)
        self.nodes[0].child_list.append(n)
        self.idx += 1
        return n

    def gload(self, length, seg_id):
        """Global parameter load (once, into a fixed VGPR region)."""
        n = self.idx
        self.nodes[n] = DAGNode(n, Operation(None, None, "load"), 0, 1, None,
                                length, segment_id=seg_id, vector_id=None,
                                wait_to_load=True)
        self.nodes[0].child_list.append(n)
        self.idx += 1
        return n

    def n(self, op, dtype, length, seg_id=None, vec_id=None, s0=None, s1=None,
          wtl=False):
        n = self.idx
        gid = vec_id if vec_id is not None else -1
        self.nodes[n] = DAGNode(n, Operation(s0, s1, op), 0, dtype, gid, length,
                                segment_id=seg_id, vector_id=vec_id,
                                wait_to_load=wtl)
        if s0 is not None:
            self.nodes[s0].child_list.append(n)
        if s1 is not None:
            self.nodes[s1].child_list.append(n)
        self.idx += 1
        return n

    def tree_reduce(self, op, id_list, vec_id):
        current = list(id_list)
        while len(current) > 1:
            nxt = []
            for i in range(0, len(current), 2):
                if i + 1 < len(current):
                    nxt.append(self.n(op, 0, 1, vec_id=vec_id,
                                      s0=current[i], s1=current[i + 1]))
                else:
                    nxt.append(current[i])
            current = nxt
        return current[0]


def _empty_mapping():
    return pd.DataFrame({"Vector Index": [], "Segment ID": [], "Length": [],
                         "Load Node": [], "Store Node": []})


# --- element-wise / fused-activation constructors (long-vector, segmented) ---

def construct_silu(X=64, Y=1024, NUM_VE=256):
    """SiLU: x * sigmoid(x)."""
    b = _B()
    K, lens = _segments(Y, NUM_VE)
    mapping = []
    for v in range(X):
        for k in range(K):
            L = lens[k]
            n_load = b.n("load", 1, L, seg_id=k, vec_id=v, wtl=True)
            b.nodes[0].child_list.append(n_load)
            n_sig = b.n("sigmoid", 1, L, seg_id=k, vec_id=v, s0=n_load)
            n_out = b.n("mul", 1, L, seg_id=k, vec_id=v, s0=n_load, s1=n_sig)
            b.n("store", 1, L, seg_id=k, vec_id=v, s0=n_out)
            mapping.append({"Vector Index": v, "Segment ID": k, "Length": L,
                            "Load Node": n_load, "Store Node": n_out})
    return b.nodes, pd.DataFrame(mapping), 0


def construct_geglu(X=64, Y=1024, NUM_VE=256):
    """GeGLU: up * gelu(gate)."""
    b = _B()
    K, lens = _segments(Y, NUM_VE)
    mapping = []
    for v in range(X):
        for k in range(K):
            L = lens[k]
            n_gate = b.n("load", 1, L, seg_id=k, vec_id=v, wtl=True)
            b.nodes[0].child_list.append(n_gate)
            n_up = b.n("load", 1, L, seg_id=k, vec_id=v, wtl=True)
            b.nodes[0].child_list.append(n_up)
            n_gelu = b.n("gelu", 1, L, seg_id=k, vec_id=v, s0=n_gate)
            n_out = b.n("mul", 1, L, seg_id=k, vec_id=v, s0=n_up, s1=n_gelu)
            b.n("store", 1, L, seg_id=k, vec_id=v, s0=n_out)
            mapping.append({"Vector Index": v, "Segment ID": k, "Length": L,
                            "Load Node": n_gate, "Store Node": n_out})
    return b.nodes, pd.DataFrame(mapping), 0


def construct_swiglu(X=64, Y=1024, NUM_VE=256):
    """SwiGLU: up * (gate * sigmoid(gate))."""
    b = _B()
    K, lens = _segments(Y, NUM_VE)
    mapping = []
    for v in range(X):
        for k in range(K):
            L = lens[k]
            n_gate = b.n("load", 1, L, seg_id=k, vec_id=v, wtl=True)
            b.nodes[0].child_list.append(n_gate)
            n_up = b.n("load", 1, L, seg_id=k, vec_id=v, wtl=True)
            b.nodes[0].child_list.append(n_up)
            n_sig = b.n("sigmoid", 1, L, seg_id=k, vec_id=v, s0=n_gate)
            n_silu = b.n("mul", 1, L, seg_id=k, vec_id=v, s0=n_gate, s1=n_sig)
            n_out = b.n("mul", 1, L, seg_id=k, vec_id=v, s0=n_up, s1=n_silu)
            b.n("store", 1, L, seg_id=k, vec_id=v, s0=n_out)
            mapping.append({"Vector Index": v, "Segment ID": k, "Length": L,
                            "Load Node": n_gate, "Store Node": n_out})
    return b.nodes, pd.DataFrame(mapping), 0


def construct_bias_gelu(X=64, Y=1024, NUM_VE=256):
    """Bias+GELU: gelu(x + bias). bias is a global per-segment parameter."""
    b = _B()
    K, lens = _segments(Y, NUM_VE)
    bias_loads = [b.gload(lens[k], k) for k in range(K)]
    mapping = []
    for v in range(X):
        for k in range(K):
            L = lens[k]
            n_load = b.n("load", 1, L, seg_id=k, vec_id=v, wtl=True)
            b.nodes[0].child_list.append(n_load)
            n_add = b.n("add", 1, L, seg_id=k, vec_id=v, s0=n_load,
                        s1=bias_loads[k])
            n_gelu = b.n("gelu", 1, L, seg_id=k, vec_id=v, s0=n_add)
            n_st = b.n("store", 1, L, seg_id=k, vec_id=v, s0=n_gelu)
            mapping.append({"Vector Index": v, "Segment ID": k, "Length": L,
                            "Load Node": n_load, "Store Node": n_st})
    return b.nodes, pd.DataFrame(mapping), K  # K global bias loads


# --- reduction constructors (RMSNorm / GroupNorm) ---

def construct_rmsnorm(X=64, Y=1024, NUM_VE=256):
    """RMSNorm: x / sqrt(mean(x^2)+eps) * gamma  (no mean centering, no beta)."""
    b = _B()
    eps = b.const(4)
    inv_n = b.const(6)
    sqrt2 = b.const(5)
    K, lens = _segments(Y, NUM_VE)
    gamma_loads = [b.gload(lens[k], k) for k in range(K)]
    mapping = []
    for v in range(X):
        sq_sums = []
        seg_loads = []
        for k in range(K):
            L = lens[k]
            n_load = b.n("load", 1, L, seg_id=k, vec_id=v, wtl=True)
            b.nodes[0].child_list.append(n_load)
            seg_loads.append(n_load)
            n_sq = b.n("square_fp16_fp16_bf16", 1, L, seg_id=k, vec_id=v, s0=n_load)
            n_sum = b.n("reduce_sum_bf16", 0, 1, seg_id=k, vec_id=v, s0=n_sq)
            sq_sums.append(n_sum)
        total = b.tree_reduce("add_bf16", sq_sums, v)
        n_var = b.n("mul_bf16_fp16_fp16", 0, 1, vec_id=v, s0=total, s1=inv_n)
        n_eps = b.n("add", 0, 1, vec_id=v, s0=n_var, s1=eps)
        n_sqrt = b.n("sqrt", 0, 1, vec_id=v, s0=n_eps)
        n_corr = b.n("mul", 0, 1, vec_id=v, s0=n_sqrt, s1=sqrt2)
        b.nodes[n_corr].mask = 1
        n_inv = b.n("inv", 0, 1, vec_id=v, s0=n_corr)
        for k in range(K):
            L = lens[k]
            n_norm = b.n("mul", 1, L, seg_id=k, vec_id=v, s0=seg_loads[k],
                         s1=n_inv)
            n_scaled = b.n("mul", 1, L, seg_id=k, vec_id=v, s0=n_norm,
                           s1=gamma_loads[k])
            n_st = b.n("store", 1, L, seg_id=k, vec_id=v, s0=n_scaled)
            mapping.append({"Vector Index": v, "Segment ID": k, "Length": L,
                            "Load Node": seg_loads[k], "Store Node": n_st})
    return b.nodes, pd.DataFrame(mapping), K  # K global gamma loads


def construct_groupnorm(X=64, Y=1024, NUM_VE=256):
    """GroupNorm: per-vector LayerNorm-style normalize (mean+var) + gamma/beta.

    Each vector is one channel-group; Y is the per-group normalization length.
    """
    b = _B()
    eps = b.const(4)
    sqrt2 = b.const(5)
    inv_n = b.const(6)
    K, lens = _segments(Y, NUM_VE)
    gamma_loads = [b.gload(lens[k], k) for k in range(K)]
    beta_loads = [b.gload(lens[k], k) for k in range(K)]
    mapping = []
    for v in range(X):
        sum_nodes = []
        seg_loads = []
        seg_subs = []
        for k in range(K):
            L = lens[k]
            n_load = b.n("load", 1, L, seg_id=k, vec_id=v, wtl=True)
            b.nodes[0].child_list.append(n_load)
            seg_loads.append(n_load)
            sum_nodes.append(b.n("reduce_sum", 0, 1, seg_id=k, vec_id=v,
                                 s0=n_load))
        n_mu = b.n("mul", 0, 1, vec_id=v,
                   s0=b.tree_reduce("add", sum_nodes, v), s1=inv_n)
        sq_sums = []
        for k in range(K):
            L = lens[k]
            n_sub = b.n("sub", 1, L, seg_id=k, vec_id=v, s0=seg_loads[k],
                        s1=n_mu)
            seg_subs.append(n_sub)
            n_sq = b.n("square_fp16_fp16_bf16", 1, L, seg_id=k, vec_id=v,
                       s0=n_sub)
            sq_sums.append(b.n("reduce_sum_bf16", 0, 1, seg_id=k, vec_id=v,
                               s0=n_sq))
        n_var = b.n("mul_bf16_fp16_fp16", 0, 1, vec_id=v,
                    s0=b.tree_reduce("add_bf16", sq_sums, v), s1=inv_n)
        n_eps = b.n("add", 0, 1, vec_id=v, s0=n_var, s1=eps)
        n_sqrt = b.n("sqrt", 0, 1, vec_id=v, s0=n_eps)
        n_corr = b.n("mul", 0, 1, vec_id=v, s0=n_sqrt, s1=sqrt2)
        b.nodes[n_corr].mask = 1
        n_inv = b.n("inv", 0, 1, vec_id=v, s0=n_corr)
        for k in range(K):
            L = lens[k]
            n_norm = b.n("mul", 1, L, seg_id=k, vec_id=v, s0=seg_subs[k],
                         s1=n_inv)
            n_scaled = b.n("mul", 1, L, seg_id=k, vec_id=v, s0=n_norm,
                           s1=gamma_loads[k])
            n_shift = b.n("add", 1, L, seg_id=k, vec_id=v, s0=n_scaled,
                          s1=beta_loads[k])
            n_st = b.n("store", 1, L, seg_id=k, vec_id=v, s0=n_shift)
            mapping.append({"Vector Index": v, "Segment ID": k, "Length": L,
                            "Load Node": seg_loads[k], "Store Node": n_st})
    return b.nodes, pd.DataFrame(mapping), 2 * K  # gamma+beta global loads


# dispatch: new functions first, else fall back to the base scheduler
_orig_construct_dag = sched.construct_dag
_NEW = {
    "silu": construct_silu,
    "geglu": construct_geglu,
    "swiglu": construct_swiglu,
    "bias_gelu": construct_bias_gelu,
    "rmsnorm": construct_rmsnorm,
    "groupnorm": construct_groupnorm,
}


def _dispatch(function, X, Y, NUM_VE):
    f = function.lower()
    if f in _NEW:
        return _NEW[f](X=X, Y=Y, NUM_VE=NUM_VE)
    return _orig_construct_dag(function=function, X=X, Y=Y, NUM_VE=NUM_VE)


sched.construct_dag = _dispatch

# ---------------------------------------------------------------------------
# scheme encoders (rows = [load, store, vector, scalar, sfu, eop])
# ---------------------------------------------------------------------------


def next_pow2(n):
    return 1 << (n - 1).bit_length() if n > 1 else 1


def slot_event_counts(rows):
    """Per-slot number of valid (non-zero) events over the functional rows."""
    counts = [0, 0, 0, 0, 0]
    for row in rows[:-1]:  # exclude the EOP row
        for s in range(5):
            if row[s] != 0:
                counts[s] += 1
    return counts


def encode_4slot(rows):
    """5-bit mask + phase striping onto 4 lanes; returns per-lane event counts."""
    lanes = [[], [], [], []]
    phase = 0
    for row in rows:
        if row[5] == 1:
            continue
        active = [s for s in range(5) if row[s] != 0]
        if len(active) > 4:
            raise AssertionError("4-slot: schedule exceeds four active slots")
        for rank, s in enumerate(active):
            lanes[(phase + rank) % 4].append(row[s])
        phase = (phase + len(active)) % 4
    return [len(l) for l in lanes]


# ---------------------------------------------------------------------------
# experiment driver
# ---------------------------------------------------------------------------

# pool definition: model -> list of (function, Y)
POOLS = {
    "BERT": [("softmax", 512), ("layernorm", 768), ("bias_gelu", 3072),
             ("tanh", 768)],
    "LLaMA": [("rmsnorm", 4096), ("softmax", 4096), ("swiglu", 11008)],
    "SD-UNet": [("groupnorm", 1280), ("silu", 1280), ("layernorm", 768),
                ("softmax", 1024), ("geglu", 3072)],
}

# distinct (function, Y) work items (layerNorm/768 shared by BERT & SD-UNet)
WORK = {}
for model, items in POOLS.items():
    for func, y in items:
        WORK.setdefault((func, y), None)


def run_one(func, y, mode, max_issue):
    """Run the scheduler; returns (cycles, rows)."""
    out_dir = OUT_ROOT / "schedules" / ("%s_y%d_mode%d_issue%d" % (func, y, mode, max_issue))
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "scheduler.log").open("w") as log:
        with contextlib.redirect_stdout(log):
            schedule, _, _ = sched.run_scheduler(
                FUNCTION=func, X=X, Y=y, mode=mode, MAX_ISSUE_SLOTS=max_issue,
                out_dir=str(out_dir), **SCHED_KW)
    rows = [r[:5] + [r[6]] for r in schedule]  # drop reserved -> [5 slots, eop]
    return len(schedule), rows


def pick_mode(func, y):
    """Among candidate modes 0/1/2 at max-5, pick min cycles; tie -> lower mode."""
    best = None
    for mode in (0, 1, 2):
        try:
            cycles, _ = run_one(func, y, mode, 5)
        except Exception as exc:  # illegal mode for this function
            print("      [skip] %s y%d mode%d: %s" % (func, y, mode, exc))
            continue
        if best is None or cycles < best[0]:
            best = (cycles, mode)
    if best is None:
        raise RuntimeError("no legal mode for %s y%d" % (func, y))
    return best[1], best[0]  # mode, cycles


def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    print("[1/3] scheduling %d distinct (function, Y) work items ..." % len(WORK))

    # per work item: max-5 and max-4 schedules + event counts
    results = {}
    for (func, y) in sorted(WORK):
        mode, cyc5 = pick_mode(func, y)
        t5, rows5 = run_one(func, y, mode, 5)
        t4, rows4 = run_one(func, y, mode, 4)
        results[(func, y)] = {
            "function": func, "y": y, "mode": mode,
            "cycles_issue5": t5, "cycles_issue4": t4,
            "slot_events": slot_event_counts(rows5),   # for Candidate A
            "lane_events": encode_4slot(rows4),        # for 4-slot
        }
        print("      %-10s y=%-6d mode=%d  T5=%d T4=%d  slots=%s  lanes=%s"
              % (func, y, mode, t5, t4, results[(func, y)]["slot_events"],
                 results[(func, y)]["lane_events"]))

    print("[2/3] aggregating pools ...")
    pool_report = {}
    for model, items in POOLS.items():
        # cycles
        cyc_unc = sum(results[(f, y)]["cycles_issue5"] for f, y in items)
        cyc_a = cyc_unc
        cyc_4 = sum(results[(f, y)]["cycles_issue4"] for f, y in items)
        # Candidate A: merge each slot's events, pad all 5 banks to pow2(max)
        slot_totals = [0] * 5
        for f, y in items:
            for s in range(5):
                slot_totals[s] += results[(f, y)]["slot_events"][s]
        a_pay_depth = next_pow2(max(slot_totals))
        a_cfg_depth = next_pow2(cyc_a)
        # 4-slot: merge each lane's events, pad all 4 lanes to pow2(max)
        lane_totals = [0] * 4
        for f, y in items:
            for l in range(4):
                lane_totals[l] += results[(f, y)]["lane_events"][l]
        s4_pay_depth = next_pow2(max(lane_totals))
        s4_cfg_depth = next_pow2(cyc_4)
        # uncompressed: 174-bit word per cycle
        unc_depth = next_pow2(cyc_unc)
        pool_report[model] = {
            "functions": ["%s(y=%d)" % (f, y) for f, y in items],
            "cycles": {"uncompressed": cyc_unc, "candidate_a": cyc_a,
                       "four_slot": cyc_4},
            "uncompressed": {"word_bits": 174, "depth": unc_depth,
                             "macro_types": 1,
                             "alloc_bits": 174 * unc_depth},
            "candidate_a": {"config": {"bits": 5, "depth": a_cfg_depth},
                            "payload": {"bits": 34, "banks": 5,
                                        "depth": a_pay_depth,
                                        "bank_events": slot_totals},
                            "macro_types": 2,
                            "alloc_bits": 5 * a_cfg_depth + 5 * 34 * a_pay_depth},
            "four_slot": {"config": {"bits": 5, "depth": s4_cfg_depth},
                          "payload": {"bits": 34, "banks": 4,
                                      "depth": s4_pay_depth,
                                      "bank_events": lane_totals},
                          "macro_types": 2,
                          "alloc_bits": 5 * s4_cfg_depth + 4 * 34 * s4_pay_depth},
        }
        print("      %-8s cycles unc/A/4slot = %d/%d/%d  |  A pay depth=%d  4slot pay depth=%d"
              % (model, cyc_unc, cyc_a, cyc_4, a_pay_depth, s4_pay_depth))

    print("[3/3] writing outputs ...")
    out_json = OUT_ROOT / "model_pool_compression_results.json"
    out_json.write_text(json.dumps({"settings": {
        "X": X, "NUM_VE": NUM_VE, "priority": "index",
        "issue5_schemes": ["uncompressed", "candidate_a"],
        "issue4_schemes": ["four_slot"],
        "pools": {m: POOLS[m] for m in POOLS},
    }, "work_items": [results[k] for k in sorted(results)],
        "pools": pool_report}, indent=2, ensure_ascii=False) + "\n")
    print("      results -> %s" % out_json.relative_to(ROOT))
    print("done.")


if __name__ == "__main__":
    sys.exit(main())

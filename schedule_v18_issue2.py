"""
schedule_v2 is modified on schedule_v1
it adds a mask-fifo (depth = 8) to acclerate the sqrt operations issue to avoid
unnecessary waiting due to the mask usage
schedule_v3 is modified on schedule_v2
it changes the gpr depth from 1024 to 256
the addr width changes from 10bit to 8bit
schedule_v4 is modified on schedule_v3 based on the hardware latency
seperate const nodes to imm table from sgpr
schedule_v5 is modifeid on schedule_v4 
beta and gamma are handled as vectors in vgpr, that should be loaded at the beginning
historical schedule_v5 VLIW width: 184 bits
schedule_v6 is modified on schedule_v4
remove the explicit *log2(e) for exp
change the time parameter for exp and sfu
schedule_v7 is modified on schedule_v6
debug for read conflict in 'store' slot
schedule_v8 is modified on schedule_v7
add output performance.txt and activation function
schedule_v9 is modified on schedule_v8
debug for num_ve = 128
schedule_v10 is modified on schedule_v9
change the memory address for the "store" nodes
schedule_v11 is modified on schedule_v10
it allows SFU to borrow half of FPUs in the vector module when "borrow = 1"
support bf16
schedule_v12 is modified on schedule_v11
it sets two reuse mode:
borrow = 00: no use
borrow = 01: reuse by half (100 fpu -> 20 ax2+bx+c)
borrow = 10: resue by all  (160 fpu -> 32 ax2+bx+c)
schedule_v13 is modified on schedule_v12
debug for ve and sfu conflict on fpu
add ve_usage: 0=used fully by ve; 1=idle; 2=used partially by ve; 3=used partially by SFU; 4=used fully by ve&SFU
update resouce checking and updating functions
schedule_v13_update is modified on schedule_v13
debug for sin/cos/ln scheduling tested
schedule_v16 is modified on schedule_v13_update 
for the full SFU borrow : mode = 0/1/2
ve_usage: 0=used fully by ve; 1=idle; 2=used partially by ve; 3=used partially by SFU; 4=used by ve&SFU
schedule_v17 is modified on schedule_v16
to support more workloads and debug on scalar output
schedule_v17_mem12 is modified on schedule_v17
one memory address selects one 256-element × 16-bit vector row
it reduces the on-chip SRAM memory address from 28 bits to 12 bits
LOAD/STORE slots become 26 bits and the complete VLIW becomes 152 bits
schedule_v18_issue2 is modified on schedule_v17_mem12
it limits each cycle to at most two active functional slots
"""
import pandas as pd
import math
import os

MEM_ADDR_BITS = 12
MEM_ADDR_MAX = (1 << MEM_ADDR_BITS) - 1
MEM_VECTOR_ELEMENTS = 256
MEM_ELEMENT_BITS = 16
MEM_ROW_BITS = MEM_VECTOR_ELEMENTS * MEM_ELEMENT_BITS
LOAD_STORE_SLOT_BITS = 26
VLIW_BITS = 152

class Operation:
    def __init__(self, src0=None, src1=None, op_type=None):
        self.src0 = src0
        self.src1 = src1
        self.op_type = op_type

class DAGNode:
    def __init__(self, index, op, layer, data_type, group_id, vector_len,
                 segment_id=None, vector_id=None, gpr_addr=None, wait_to_load=False):
        self.index = index
        self.op = op
        self.layer = layer
        self.type = data_type  # 0 = scalar, 1 = vector, -1 = special
        self.group_id = group_id
        self.vector_len = vector_len
        self.segment_id = segment_id
        self.vector_id = vector_id
        self.child_list = []
        self.gpr_addr = gpr_addr
        self.wait_to_load = wait_to_load
        self.mask = 0  # 默认无掩码操作

        # 以下为调度相关字段，调度器会用到
        self.issued = False        # 是否已发射
        self.ready_time = 0        # 当前节点最早可以被发射的时刻
        self.importance = 0        # 节点重要性，用于排序调度优先级


def construct_logsumexp(X=32, Y=1024, NUM_VE=256):
    if Y > NUM_VE:
        return construct_logsumexp_long_vector_no_fusion(X, Y, NUM_VE)
    else:
        return construct_logsumexp_short_vector_no_fusion(X, Y)


def construct_logsumexp_short_vector_no_fusion(X=32, Y=32):
    nodes = {}
    mapping = []
    idx = 0

    # root
    nodes[idx] = DAGNode(
        idx, Operation(None, None, 'root'),
        0, -1, -1, 0, wait_to_load=False
    )
    idx += 1

    for x in range(X):
        def add_node(op_type, layer, dtype, length, src0=None, src1=None, wait_to_load=False):
            nonlocal idx
            node = DAGNode(
                idx, Operation(src0, src1, op_type),
                layer, dtype, x, length,
                vector_id=x, wait_to_load=wait_to_load
            )
            if src0 is not None:
                nodes[src0].child_list.append(idx)
            if src1 is not None:
                nodes[src1].child_list.append(idx)
            nodes[idx] = node
            idx += 1
            return idx - 1

        n1 = add_node('load', 1, 1, Y, wait_to_load=True)
        nodes[0].child_list.append(n1)

        n2 = add_node('reduce_max', 2, 0, 1, src0=n1)
        n3 = add_node('sub', 3, 1, Y, src0=n1, src1=n2)
        n4 = add_node('exp', 4, 1, Y, src0=n3)
        n5 = add_node('reduce_sum', 5, 0, 1, src0=n4)
        n6 = add_node('ln', 6, 0, 1, src0=n5)
        n7 = add_node('add', 7, 0, 1, src0=n2, src1=n6)
        n8 = add_node('store', 8, 0, 1, src0=n7)

        mapping.append({
            "Vector Index": x,
            "Group ID": x,
            "Group Offset": 0,
            "Virtual Node ID": n1,
            "Store Node": n8
        })

    return nodes, pd.DataFrame(mapping), 0


def construct_logsumexp_long_vector_no_fusion(X=32, Y=1024, NUM_VE=256):
    nodes = {}
    mapping = []
    idx = 0

    # root
    nodes[idx] = DAGNode(
        idx, Operation(None, None, 'root'),
        0, -1, -1, 0, wait_to_load=False
    )
    idx += 1

    def build_tree_reduce(op_type, id_list, start_layer, vec_id):
        nonlocal idx
        current = id_list[:]
        layer = start_layer
        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                if i + 1 < len(current):
                    n0, n1 = current[i], current[i + 1]
                    node = DAGNode(
                        idx, Operation(n0, n1, op_type),
                        layer, 0, vec_id, 1,
                        vector_id=vec_id, wait_to_load=False
                    )
                    nodes[n0].child_list.append(idx)
                    nodes[n1].child_list.append(idx)
                    nodes[idx] = node
                    next_level.append(idx)
                    idx += 1
                else:
                    next_level.append(current[i])
            current = next_level
            layer += 1
        return current[0]

    for vec_id in range(X):
        K = math.ceil(Y / NUM_VE)
        segment_lens = [NUM_VE] * K
        if Y % NUM_VE != 0:
            segment_lens[-1] = Y - NUM_VE * (K - 1)

        segment_load_nodes = []
        segment_local_max_nodes = []
        segment_shift_nodes = []
        segment_exp_nodes = []
        segment_sum_nodes = []

        def add_node(op_type, layer, dtype, length, seg_id=None, src0=None, src1=None, wait_to_load=False):
            nonlocal idx
            node = DAGNode(
                idx, Operation(src0, src1, op_type),
                layer, dtype, vec_id, length,
                segment_id=seg_id, vector_id=vec_id, wait_to_load=wait_to_load
            )
            if src0 is not None:
                nodes[src0].child_list.append(idx)
            if src1 is not None:
                nodes[src1].child_list.append(idx)
            nodes[idx] = node
            idx += 1
            return idx - 1

        # Step 1: load + local reduce_max
        for k in range(K):
            seg_len = segment_lens[k]
            n_load = add_node('load', 1, 1, seg_len, seg_id=k, wait_to_load=True)
            nodes[0].child_list.append(n_load)
            n_local_max = add_node('reduce_max', 2, 0, 1, seg_id=k, src0=n_load)

            segment_load_nodes.append(n_load)
            segment_local_max_nodes.append(n_local_max)

        # Step 2: global max
        g_max_id = build_tree_reduce('max', segment_local_max_nodes, 3, vec_id)

        # Step 3: shifted vector + exp + local sum
        for k in range(K):
            seg_len = segment_lens[k]
            n_shift = add_node('sub', 4, 1, seg_len, seg_id=k, src0=segment_load_nodes[k], src1=g_max_id)
            n_exp = add_node('exp', 5, 1, seg_len, seg_id=k, src0=n_shift)
            n_sum = add_node('reduce_sum', 6, 0, 1, seg_id=k, src0=n_exp)

            segment_shift_nodes.append(n_shift)
            segment_exp_nodes.append(n_exp)
            segment_sum_nodes.append(n_sum)

        # Step 4: global sum
        g_sum_id = build_tree_reduce('add', segment_sum_nodes, 7, vec_id)

        # Step 5: ln(sum)
        g_ln_id = add_node('ln', 8, 0, 1, src0=g_sum_id)

        # Step 6: final add: max + ln(sum)
        g_out_id = add_node('add', 9, 0, 1, src0=g_max_id, src1=g_ln_id)

        # Step 7: scalar store
        n_store = add_node('store', 10, 0, 1, src0=g_out_id)

        mapping.append({
            "Vector Index": vec_id,
            "Num Segments": K,
            "Length": Y,
            "Global Max Node": g_max_id,
            "Global Sum Node": g_sum_id,
            "Ln Node": g_ln_id,
            "Store Node": n_store
        })

    return nodes, pd.DataFrame(mapping), 0


def construct_elu(X=32, Y=1024, NUM_VE=256):
    if Y > NUM_VE:
        return construct_elu_long_vector_no_fusion(X, Y, NUM_VE)
    else:
        return construct_elu_short_vector_no_fusion(X, Y)


def construct_elu_short_vector_no_fusion(X=32, Y=32):
    nodes = {}
    mapping = []
    idx = 0

    # root
    nodes[idx] = DAGNode(
        idx, Operation(None, None, 'root'),
        0, -1, -1, 0, wait_to_load=False
    )
    idx += 1

    # scalar const 0.0 in SGPR
    const_zero_idx = idx
    nodes[idx] = DAGNode(
        idx, Operation(None, None, 'const'),
        0, 0, -1, 1, gpr_addr=8, wait_to_load=False
    )
    nodes[0].child_list.append(idx)
    idx += 1

    # scalar const 1.0 in SGPR
    const_one_idx = idx
    nodes[idx] = DAGNode(
        idx, Operation(None, None, 'const'),
        0, 0, -1, 1, gpr_addr=7, wait_to_load=False
    )
    nodes[0].child_list.append(idx)
    idx += 1

    for x in range(X):
        def add_node(op_type, layer, dtype, length, src0=None, src1=None, wait_to_load=False):
            nonlocal idx
            node = DAGNode(
                idx, Operation(src0, src1, op_type),
                layer, dtype, x, length,
                vector_id=x, wait_to_load=wait_to_load
            )
            if src0 is not None:
                nodes[src0].child_list.append(idx)
            if src1 is not None:
                nodes[src1].child_list.append(idx)
            nodes[idx] = node
            idx += 1
            return idx - 1

        n1 = add_node('load', 1, 1, Y, wait_to_load=True)
        nodes[0].child_list.append(n1)

        n2 = add_node('max', 2, 1, Y, src0=n1, src1=const_zero_idx)   # max(x, 0)
        n3 = add_node('min', 2, 1, Y, src0=n1, src1=const_zero_idx)   # min(x, 0)
        n4 = add_node('exp', 3, 1, Y, src0=n3)                        # exp(min(x,0))
        n5 = add_node('add', 4, 1, Y, src0=n2, src1=n4)               # max(x,0)+exp(min(x,0))
        n6 = add_node('sub', 5, 1, Y, src0=n5, src1=const_one_idx)    # ... - 1
        n7 = add_node('store', 6, 1, Y, src0=n6)

        mapping.append({
            "Vector Index": x,
            "Group ID": x,
            "Group Offset": 0,
            "Virtual Node ID": n1,
            "Store Node": n7
        })

    return nodes, pd.DataFrame(mapping), 0


def construct_elu_long_vector_no_fusion(X=32, Y=1024, NUM_VE=256):
    nodes = {}
    mapping = []
    idx = 0

    # root
    nodes[idx] = DAGNode(
        idx, Operation(None, None, 'root'),
        0, -1, -1, 0, wait_to_load=False
    )
    idx += 1

    # scalar const 0.0 in SGPR
    const_zero_idx = idx
    nodes[idx] = DAGNode(
        idx, Operation(None, None, 'const'),
        0, 0, -1, 1, gpr_addr=8, wait_to_load=False
    )
    nodes[0].child_list.append(idx)
    idx += 1

    # scalar const 1.0 in SGPR
    const_one_idx = idx
    nodes[idx] = DAGNode(
        idx, Operation(None, None, 'const'),
        0, 0, -1, 1, gpr_addr=7, wait_to_load=False
    )
    nodes[0].child_list.append(idx)
    idx += 1

    for vec_id in range(X):
        K = math.ceil(Y / NUM_VE)
        segment_lens = [NUM_VE] * K
        if Y % NUM_VE != 0:
            segment_lens[-1] = Y - NUM_VE * (K - 1)

        def add_node(op_type, layer, dtype, length, seg_id=None, src0=None, src1=None, wait_to_load=False):
            nonlocal idx
            node = DAGNode(
                idx, Operation(src0, src1, op_type),
                layer, dtype, vec_id, length,
                segment_id=seg_id, vector_id=vec_id, wait_to_load=wait_to_load
            )
            if src0 is not None:
                nodes[src0].child_list.append(idx)
            if src1 is not None:
                nodes[src1].child_list.append(idx)
            nodes[idx] = node
            idx += 1
            return idx - 1

        for k in range(K):
            seg_len = segment_lens[k]

            n_load = add_node('load', 1, 1, seg_len, seg_id=k, wait_to_load=True)
            nodes[0].child_list.append(n_load)

            n_max = add_node('max', 2, 1, seg_len, seg_id=k, src0=n_load, src1=const_zero_idx)
            n_min = add_node('min', 2, 1, seg_len, seg_id=k, src0=n_load, src1=const_zero_idx)
            n_exp = add_node('exp', 3, 1, seg_len, seg_id=k, src0=n_min)
            n_add = add_node('add', 4, 1, seg_len, seg_id=k, src0=n_max, src1=n_exp)
            n_sub = add_node('sub', 5, 1, seg_len, seg_id=k, src0=n_add, src1=const_one_idx)
            n_store = add_node('store', 6, 1, seg_len, seg_id=k, src0=n_sub)

            mapping.append({
                "Vector Index": vec_id,
                "Segment ID": k,
                "Start Index": k * NUM_VE,
                "Length": seg_len,
                "Load Node": n_load,
                "Exp Node": n_exp,
                "Store Node": n_store
            })

    return nodes, pd.DataFrame(mapping), 0

def construct_softplus(X=32, Y=1024, NUM_VE=256):
    if Y > NUM_VE:
        return construct_softplus_long_vector_no_fusion(X, Y, NUM_VE)
    else:
        return construct_softplus_short_vector_no_fusion(X, Y)


def construct_softplus_short_vector_no_fusion(X=32, Y=32):
    nodes = {}
    mapping = []
    idx = 0

    # root
    nodes[idx] = DAGNode(
        idx, Operation(None, None, 'root'),
        0, -1, -1, 0, wait_to_load=False
    )
    idx += 1

    # scalar const 1.0 in SGPR
    const_one_idx = idx
    nodes[idx] = DAGNode(
        idx, Operation(None, None, 'const'),
        0, 0, -1, 1, gpr_addr=7, wait_to_load=False
    )
    nodes[0].child_list.append(idx)
    idx += 1

    for x in range(X):
        def add_node(op_type, layer, dtype, length, src0=None, src1=None, wait_to_load=False):
            nonlocal idx
            node = DAGNode(
                idx, Operation(src0, src1, op_type),
                layer, dtype, x, length,
                vector_id=x, wait_to_load=wait_to_load
            )
            if src0 is not None:
                nodes[src0].child_list.append(idx)
            if src1 is not None:
                nodes[src1].child_list.append(idx)
            nodes[idx] = node
            idx += 1
            return idx - 1

        n1 = add_node('load', 1, 1, Y, wait_to_load=True)
        nodes[0].child_list.append(n1)
        n2 = add_node('exp', 2, 1, Y, src0=n1)
        n3 = add_node('add', 3, 1, Y, src0=n2, src1=const_one_idx)
        n4 = add_node('ln', 4, 1, Y, src0=n3)
        n5 = add_node('store', 5, 1, Y, src0=n4)

        mapping.append({
            "Vector Index": x,
            "Group ID": x,
            "Group Offset": 0,
            "Virtual Node ID": n1,
            "Store Node": n5
        })

    return nodes, pd.DataFrame(mapping), 0


def construct_softplus_long_vector_no_fusion(X=32, Y=1024, NUM_VE=256):
    nodes = {}
    mapping = []
    idx = 0

    # root
    nodes[idx] = DAGNode(
        idx, Operation(None, None, 'root'),
        0, -1, -1, 0, wait_to_load=False
    )
    idx += 1

    # scalar const 1.0 in SGPR
    const_one_idx = idx
    nodes[idx] = DAGNode(
        idx, Operation(None, None, 'const'),
        0, 0, -1, 1, gpr_addr=7, wait_to_load=False
    )
    nodes[0].child_list.append(idx)
    idx += 1

    for vec_id in range(X):
        K = math.ceil(Y / NUM_VE)
        segment_lens = [NUM_VE] * K
        if Y % NUM_VE != 0:
            segment_lens[-1] = Y - NUM_VE * (K - 1)

        def add_node(op_type, layer, dtype, length, seg_id=None, src0=None, src1=None, wait_to_load=False):
            nonlocal idx
            node = DAGNode(
                idx, Operation(src0, src1, op_type),
                layer, dtype, vec_id, length,
                segment_id=seg_id, vector_id=vec_id, wait_to_load=wait_to_load
            )
            if src0 is not None:
                nodes[src0].child_list.append(idx)
            if src1 is not None:
                nodes[src1].child_list.append(idx)
            nodes[idx] = node
            idx += 1
            return idx - 1

        for k in range(K):
            seg_len = segment_lens[k]
            n_load = add_node('load', 1, 1, seg_len, seg_id=k, wait_to_load=True)
            nodes[0].child_list.append(n_load)

            n_exp = add_node('exp', 2, 1, seg_len, seg_id=k, src0=n_load)
            n_add = add_node('add', 3, 1, seg_len, seg_id=k, src0=n_exp, src1=const_one_idx)
            n_ln = add_node('ln', 4, 1, seg_len, seg_id=k, src0=n_add)
            n_store = add_node('store', 5, 1, seg_len, seg_id=k, src0=n_ln)

            mapping.append({
                "Vector Index": vec_id,
                "Segment ID": k,
                "Start Index": k * NUM_VE,
                "Length": seg_len,
                "Load Node": n_load,
                "Exp Node": n_exp,
                "Ln Node": n_ln,
                "Store Node": n_store
            })

    return nodes, pd.DataFrame(mapping), 0

def construct_logsoftmax(X=32, Y=1024, NUM_VE=256):
    if Y > NUM_VE:
        return construct_logsoftmax_long_vector_no_fusion(X, Y, NUM_VE)
    else:
        return construct_logsoftmax_short_vector_no_fusion(X, Y)


def construct_logsoftmax_short_vector_no_fusion(X=32, Y=32):
    nodes = {}
    mapping = []
    idx = 0

    # Node 0: root
    nodes[idx] = DAGNode(
        idx, Operation(None, None, 'root'),
        0, -1, -1, 0, wait_to_load=False
    )
    idx += 1

    for x in range(X):
        def add_node(op_type, layer, dtype, length, src0=None, src1=None, wait_to_load=False):
            nonlocal idx
            node = DAGNode(
                idx, Operation(src0, src1, op_type),
                layer, dtype, x, length,
                vector_id=x, wait_to_load=wait_to_load
            )
            if src0 is not None:
                nodes[src0].child_list.append(idx)
            if src1 is not None:
                nodes[src1].child_list.append(idx)
            nodes[idx] = node
            idx += 1
            return idx - 1

        n1 = add_node('load', 1, 1, Y, wait_to_load=True)
        nodes[0].child_list.append(n1)

        n2 = add_node('reduce_max', 2, 0, 1, src0=n1)
        n3 = add_node('sub', 3, 1, Y, src0=n1, src1=n2)      # y = x - max(x)
        n4 = add_node('exp', 4, 1, Y, src0=n3)               # z = exp(y)
        n5 = add_node('reduce_sum', 5, 0, 1, src0=n4)        # s = sum(z)
        n6 = add_node('ln', 6, 0, 1, src0=n5)                # l = ln(s)
        n7 = add_node('sub', 7, 1, Y, src0=n3, src1=n6)      # out = y - l
        n8 = add_node('store', 8, 1, Y, src0=n7)

        mapping.append({
            "Vector Index": x,
            "Group ID": x,
            "Group Offset": 0,
            "Virtual Node ID": n1,
            "Store Node": n8
        })

    return nodes, pd.DataFrame(mapping), 0


def construct_logsoftmax_long_vector_no_fusion(X=32, Y=1024, NUM_VE=256):
    nodes = {}
    mapping = []
    idx = 0

    # Node 0: root
    nodes[idx] = DAGNode(
        idx, Operation(None, None, 'root'),
        0, -1, -1, 0, wait_to_load=False
    )
    idx += 1

    def build_tree_reduce(op_type, id_list, start_layer, vec_id):
        nonlocal idx
        current = id_list[:]
        layer = start_layer
        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                if i + 1 < len(current):
                    n0, n1 = current[i], current[i + 1]
                    node = DAGNode(
                        idx, Operation(n0, n1, op_type),
                        layer, 0, vec_id, 1,
                        vector_id=vec_id, wait_to_load=False
                    )
                    nodes[n0].child_list.append(idx)
                    nodes[n1].child_list.append(idx)
                    nodes[idx] = node
                    next_level.append(idx)
                    idx += 1
                else:
                    next_level.append(current[i])
            current = next_level
            layer += 1
        return current[0]

    for vec_id in range(X):
        K = math.ceil(Y / NUM_VE)
        segment_lens = [NUM_VE] * K
        if Y % NUM_VE != 0:
            segment_lens[-1] = Y - NUM_VE * (K - 1)

        segment_load_nodes = []
        segment_local_max_nodes = []
        segment_shift_nodes = []
        segment_exp_nodes = []
        segment_sum_nodes = []

        def add_node(op_type, layer, dtype, length, seg_id=None, src0=None, src1=None, wait_to_load=False):
            nonlocal idx
            node = DAGNode(
                idx, Operation(src0, src1, op_type),
                layer, dtype, vec_id, length,
                segment_id=seg_id, vector_id=vec_id, wait_to_load=wait_to_load
            )
            if src0 is not None:
                nodes[src0].child_list.append(idx)
            if src1 is not None:
                nodes[src1].child_list.append(idx)
            nodes[idx] = node
            idx += 1
            return idx - 1

        # Step 1: load + local reduce_max
        for k in range(K):
            seg_len = segment_lens[k]
            n_load = add_node('load', 1, 1, seg_len, seg_id=k, wait_to_load=True)
            nodes[0].child_list.append(n_load)
            n_local_max = add_node('reduce_max', 2, 0, 1, seg_id=k, src0=n_load)

            segment_load_nodes.append(n_load)
            segment_local_max_nodes.append(n_local_max)

        # Step 2: global max
        g_max_id = build_tree_reduce('max', segment_local_max_nodes, 3, vec_id)

        # Step 3: y = x - global_max ; z = exp(y) ; local sum
        for k in range(K):
            seg_len = segment_lens[k]
            n_shift = add_node('sub', 4, 1, seg_len, seg_id=k, src0=segment_load_nodes[k], src1=g_max_id)
            n_exp = add_node('exp', 5, 1, seg_len, seg_id=k, src0=n_shift)
            n_sum = add_node('reduce_sum', 6, 0, 1, seg_id=k, src0=n_exp)

            segment_shift_nodes.append(n_shift)
            segment_exp_nodes.append(n_exp)
            segment_sum_nodes.append(n_sum)

        # Step 4: global sum
        g_sum_id = build_tree_reduce('add', segment_sum_nodes, 7, vec_id)

        # Step 5: ln(sum(exp(...)))
        g_ln_id = add_node('ln', 8, 0, 1, src0=g_sum_id)

        # Step 6: out = y - ln_sum ; store
        for k in range(K):
            seg_len = segment_lens[k]
            n_out = add_node('sub', 9, 1, seg_len, seg_id=k, src0=segment_shift_nodes[k], src1=g_ln_id)
            n_store = add_node('store', 10, 1, seg_len, seg_id=k, src0=n_out)

            mapping.append({
                "Vector Index": vec_id,
                "Segment ID": k,
                "Start Index": k * NUM_VE,
                "Length": seg_len,
                "Load Node": segment_load_nodes[k],
                "Shift Node": segment_shift_nodes[k],
                "Exp Node": segment_exp_nodes[k],
                "Ln Node": g_ln_id,
                "Store Node": n_store
            })

    return nodes, pd.DataFrame(mapping), 0        

def construct_softmax(X=32, Y=32, NUM_VE=256):
    if Y>NUM_VE:
        return construct_softmax_long_vector_no_fusion(X, Y, NUM_VE)
    else:
        return construct_softmax_short_vector_no_fusion(X, Y)

def construct_softmax_short_vector_no_fusion(X=32, Y=32):
    nodes = {}
    mapping = []
    idx = 0

    # Node 0: root
    nodes[idx] = DAGNode(idx, Operation(None, None, 'root'), 0, -1, -1, 0, wait_to_load=False)
    idx += 1

    # Node 1: log2(e)，假定为 SGPR 地址 1 的常量，不需要加载
    #nodes[idx] = DAGNode(idx, Operation(None, None, 'const'), 0, 0, -1, 1, gpr_addr=1, wait_to_load=False)
    #nodes[0].child_list.append(idx)
    #log2e_node = idx
    #idx += 1

    for x in range(X):
        def add_node(op_type, layer, dtype, length, src0=None, src1=None, wait_to_load=False):
            nonlocal idx
            node = DAGNode(idx, Operation(src0, src1, op_type), layer, dtype, x, length, vector_id=x, wait_to_load=wait_to_load)
            if src0 is not None:
                nodes[src0].child_list.append(idx)
            if src1 is not None:
                nodes[src1].child_list.append(idx)
            nodes[idx] = node
            idx += 1
            return idx - 1

        n1 = add_node('load', 1, 1, Y, wait_to_load=True)
        nodes[0].child_list.append(n1)
        n2 = add_node('reduce_max', 2, 0, 1, n1)
        n3 = add_node('sub', 3, 1, Y, n1, n2)
        # n3_5 = add_node('mul', 4, 1, Y, n3, log2e_node)  # 使用 log2(e) 常量
        n4 = add_node('exp', 4, 1, Y, n3)
        n5 = add_node('reduce_sum', 5, 0, 1, n4)
        n6 = add_node('inv', 6, 0, 1, n5)
        n7 = add_node('mul', 7, 1, Y, n4, n6)
        add_node('store', 8, 1, Y, n7)

        mapping.append({
            "Vector Index": x,
            "Group ID": x,
            "Group Offset": 0,
            "Virtual Node ID": n1
        })

    return nodes, pd.DataFrame(mapping), 0

def construct_softmax_long_vector_no_fusion(X=32, Y=1024, NUM_VE=256):
    nodes = {}
    mapping = []
    idx = 0

    # Node 0: root
    nodes[idx] = DAGNode(idx, Operation(None, None, 'root'), 0, -1, -1, 0, wait_to_load=False)
    idx += 1

    # Node 1: log2(e)，常量节点，SGPR地址1
    # nodes[idx] = DAGNode(idx, Operation(None, None, 'const'), 0, 0, -1, 1, gpr_addr=1, wait_to_load=False)
    # nodes[0].child_list.append(idx)
    # log2e_node = idx
    # idx += 1

    for vec_id in range(X):
        K = math.ceil(Y / NUM_VE)
        segment_lens = [NUM_VE] * K
        if Y % NUM_VE != 0:
            segment_lens[-1] = Y - NUM_VE * (K - 1)

        segment_load_nodes = []
        segment_exp_nodes = []
        segment_sum_nodes = []

        def add_node(op_type, layer, dtype, length, seg_id=None, src0=None, src1=None, wait_to_load=False):
            nonlocal idx
            node = DAGNode(idx, Operation(src0, src1, op_type), layer, dtype, vec_id, length,
                           segment_id=seg_id, vector_id=vec_id, wait_to_load=wait_to_load)
            if src0 is not None:
                nodes[src0].child_list.append(idx)
            if src1 is not None:
                nodes[src1].child_list.append(idx)
            nodes[idx] = node
            idx += 1
            return idx - 1

        for k in range(K):
            seg_len = segment_lens[k]
            n_load = add_node('load', 1, 1, seg_len, seg_id=k, wait_to_load=True)
            nodes[0].child_list.append(n_load)
            n_max = add_node('reduce_max', 2, 0, 1, seg_id=k, src0=n_load)
            segment_load_nodes.append(n_load)
            segment_exp_nodes.append((n_load, n_max))

        # 层次化全局 reduce_max
        def build_tree_reduce(op_type, id_list, start_layer):
            nonlocal idx
            current = id_list[:]
            while len(current) > 1:
                next_level = []
                for i in range(0, len(current), 2):
                    if i + 1 < len(current):
                        n0, n1 = current[i], current[i+1]
                        new_node = DAGNode(idx, Operation(n0, n1, op_type), start_layer, 0, vec_id, 1)
                        nodes[n0].child_list.append(idx)
                        nodes[n1].child_list.append(idx)
                        nodes[idx] = new_node
                        next_level.append(idx)
                        idx += 1
                    else:
                        next_level.append(current[i])
                current = next_level
                start_layer += 1
            return current[0]

        max_ids = [m for _, m in segment_exp_nodes]
        g_max_id = build_tree_reduce('max', max_ids, 3)

        for k, (n_load, _) in enumerate(segment_exp_nodes):
            seg_len = segment_lens[k]
            n_sub = add_node('sub', 4, 1, seg_len, seg_id=k, src0=n_load, src1=g_max_id)
            # n_mul = add_node('mul', 5, 1, seg_len, seg_id=k, src0=n_sub, src1=log2e_node)
            n_exp = add_node('exp', 5, 1, seg_len, seg_id=k, src0=n_sub)
            n_sum = add_node('reduce_sum', 6, 0, 1, seg_id=k, src0=n_exp)
            segment_exp_nodes[k] = n_exp
            segment_sum_nodes.append(n_sum)

        # 层次化全局 reduce_sum
        g_sum_id = build_tree_reduce('add', segment_sum_nodes, 7)

        # inv(g_sum)
        g_inv_id = add_node('inv', 8, 0, 1, src0=g_sum_id)

        for k, exp_id in enumerate(segment_exp_nodes):
            seg_len = segment_lens[k]
            n_mul = add_node('mul', 9, 1, seg_len, seg_id=k, src0=exp_id, src1=g_inv_id)
            n_store = add_node('store', 10, 1, seg_len, seg_id=k, src0=n_mul)

            mapping.append({
                "Vector Index": vec_id,
                "Segment ID": k,
                "Start Index": k * NUM_VE,
                "Length": seg_len,
                "Load Node": segment_load_nodes[k],
                "Store Node": n_store
            })

    return nodes, pd.DataFrame(mapping), 0


def construct_activation(X=32, Y=32, NUM_VE=256, act_func="gelu"):
    if Y > NUM_VE:
        return construct_activation_long_vector_no_fusion(X, Y, NUM_VE, act_func)
    else:
        return construct_activation_short_vector_no_fusion(X, Y, act_func)

def construct_activation_short_vector_no_fusion(X=32, Y=32, act_func="gelu"):
    nodes = {}
    mapping = []
    idx = 0

    # Node 0: root
    nodes[idx] = DAGNode(idx, Operation(None, None, 'root'), 0, -1, -1, 0, wait_to_load=False)
    idx += 1

    for x in range(X):
        def add_node(op_type, layer, dtype, length, src0=None, src1=None, wait_to_load=False):
            nonlocal idx
            node = DAGNode(idx, Operation(src0, src1, op_type), layer, dtype, x, length,
                           vector_id=x, wait_to_load=wait_to_load)
            if src0 is not None:
                nodes[src0].child_list.append(idx)
            if src1 is not None:
                nodes[src1].child_list.append(idx)
            nodes[idx] = node
            idx += 1
            return idx - 1

        n1 = add_node('load', 1, 1, Y, wait_to_load=True)
        nodes[0].child_list.append(n1)
        n2 = add_node(act_func, 2, 1, Y, src0=n1)
        n3 = add_node('store', 3, 1, Y, src0=n2)

        mapping.append({
            "Vector Index": x,
            "Group ID": x,
            "Group Offset": 0,
            "Virtual Node ID": n1
        })

    return nodes, pd.DataFrame(mapping), 0

def construct_activation_long_vector_no_fusion(X=32, Y=1024, NUM_VE=256, act_func="gelu"):
    nodes = {}
    mapping = []
    idx = 0

    # Node 0: root
    nodes[idx] = DAGNode(idx, Operation(None, None, 'root'), 0, -1, -1, 0, wait_to_load=False)
    idx += 1

    for vec_id in range(X):
        K = math.ceil(Y / NUM_VE)
        segment_lens = [NUM_VE] * K
        if Y % NUM_VE != 0:
            segment_lens[-1] = Y - NUM_VE * (K - 1)

        def add_node(op_type, layer, dtype, length, seg_id=None, src0=None, src1=None, wait_to_load=False):
            nonlocal idx
            node = DAGNode(idx, Operation(src0, src1, op_type), layer, dtype, vec_id, length,
                           segment_id=seg_id, vector_id=vec_id, wait_to_load=wait_to_load)
            if src0 is not None:
                nodes[src0].child_list.append(idx)
            if src1 is not None:
                nodes[src1].child_list.append(idx)
            nodes[idx] = node
            idx += 1
            return idx - 1

        for k in range(K):
            seg_len = segment_lens[k]
            n_load = add_node('load', 1, 1, seg_len, seg_id=k, wait_to_load=True)
            nodes[0].child_list.append(n_load)
            n_act = add_node(act_func, 2, 1, seg_len, seg_id=k, src0=n_load)
            n_store = add_node('store', 3, 1, seg_len, seg_id=k, src0=n_act)

            mapping.append({
                "Vector Index": vec_id,
                "Segment ID": k,
                "Start Index": k * NUM_VE,
                "Length": seg_len,
                "Load Node": n_load,
                "Store Node": n_store
            })

    return nodes, pd.DataFrame(mapping), 0

def construct_layernorm(X=32, Y=32, NUM_VE=256):
    if Y>NUM_VE:
        return construct_layernorm_long_vector_no_fusion(X, Y, NUM_VE)
    else:
        return construct_layernorm_short_vector_no_fusion(X, Y)

def construct_layernorm_short_vector_no_fusion(X=32, Y=32):
    nodes = {}
    mapping = []
    idx = 0

    # Node 0: root
    nodes[idx] = DAGNode(idx, Operation(None, None, 'root'), 0, -1, -1, 0, wait_to_load=False)
    idx += 1

    # 标量常量
    constants = {
        "epsilon": {"gpr": 4, "type": 0, "len": 1},
        "sqrt2":  {"gpr": 5, "type": 0, "len": 1},
        "inv_n":  {"gpr": 6, "type": 0, "len": 1},
    }
    const_nodes = {}
    for name, info in constants.items():
        nodes[idx] = DAGNode(
            idx, Operation(None, None, 'const'),
            0, info["type"], -1, info["len"],
            gpr_addr=info["gpr"], wait_to_load=False)
        nodes[0].child_list.append(idx)
        const_nodes[name] = idx
        idx += 1

    # 全局gamma和beta（向量load节点，只生成一次）
    n_gamma = idx
    nodes[n_gamma] = DAGNode(
        n_gamma, Operation(None, None, 'load'), 1, 1, group_id = -1, vector_len=Y, vector_id = -1, wait_to_load=True)
    nodes[0].child_list.append(n_gamma)
    idx += 1

    n_beta = idx
    nodes[n_beta] = DAGNode(
        n_beta, Operation(None, None, 'load'), 1, 1, group_id = -1, vector_len=Y, vector_id = -1, wait_to_load=True)
    nodes[0].child_list.append(n_beta)
    idx += 1

    for x in range(X):
        def add_node(op_type, layer, dtype, length, src0=None, src1=None, wait_to_load=False, mask=0, vector_id=x):
            nonlocal idx
            node = DAGNode(idx, Operation(src0, src1, op_type), layer, dtype, x, length,
                           vector_id=vector_id, wait_to_load=wait_to_load)
            node.mask = mask
            if src0 is not None:
                nodes[src0].child_list.append(idx)
            if src1 is not None:
                nodes[src1].child_list.append(idx)
            nodes[idx] = node
            idx += 1
            return idx - 1

        # Step 1: load v1
        n1 = add_node("load", 1, 1, Y, wait_to_load=True)
        nodes[0].child_list.append(n1)

        # Step 2: reduce_sum(v1)
        n2 = add_node("reduce_sum", 2, 0, 1, src0=n1)

        # Step 3: mu = sum / n
        n3 = add_node("mul", 3, 0, 1, src0=n2, src1=const_nodes["inv_n"])

        # Step 4: v1 - mu
        n4 = add_node("sub", 4, 1, Y, src0=n1, src1=n3)

        # Step 5: (v1 - mu)^2
        n5 = add_node("square_fp16_fp16_bf16", 5, 1, Y, src0=n4)

        # Step 6: reduce_sum((v1 - mu)^2)
        n6 = add_node("reduce_sum_bf16", 6, 0, 1, src0=n5)

        # Step 7: sigma^2 = sum / n
        n7 = add_node("mul_bf16_fp16_fp16", 7, 0, 1, src0=n6, src1=const_nodes["inv_n"])

        # Step 8: sigma^2 + epsilon
        n8 = add_node("add", 8, 0, 1, src0=n7, src1=const_nodes["epsilon"])

        # Step 9: sqrt(sigma^2 + epsilon)
        n9 = add_node("sqrt", 9, 0, 1, src0=n8)

        # Step 9.5: sqrt(...) * sqrt(2), with mask
        n9_5 = add_node("mul", 10, 0, 1, src0=n9, src1=const_nodes["sqrt2"], mask=1)

        # Step 10: inv(sqrt)
        n10 = add_node("inv", 11, 0, 1, src0=n9_5)

        # Step 11: (v1 - mu) / sqrt
        n11 = add_node("mul", 12, 1, Y, src0=n4, src1=n10)

        # Step 12: gamma * normed，直接引用全局n_gamma
        n12 = add_node("mul", 13, 1, Y, src0=n11, src1=n_gamma)

        # Step 13: + beta，直接引用全局n_beta
        n13 = add_node("add", 14, 1, Y, src0=n12, src1=n_beta)

        # Step 14: store
        n14 = add_node("store", 15, 1, Y, src0=n13)

        mapping.append({
            "Vector Index": x,
            "Group ID": x,
            "Group Offset": 0,
            "Virtual Node ID": n1
        })

    return nodes, pd.DataFrame(mapping), 2

def construct_layernorm_long_vector_no_fusion(X=32, Y=1024, NUM_VE=256):
    nodes = {}
    mapping = []
    idx = 0

    # Node 0: root
    nodes[idx] = DAGNode(idx, Operation(None, None, 'root'), 0, -1, -1, 0)
    idx += 1

    # Scalar constants in SGPR
    constants = {
        "epsilon": 4,
        "sqrt2": 5,
        "inv_n": 6
    }
    const_nodes = {}
    for name, gpr in constants.items():
        nodes[idx] = DAGNode(idx, Operation(None, None, 'const'), 0, 0, -1, 1, gpr_addr=gpr)
        nodes[0].child_list.append(idx)
        const_nodes[name] = idx
        idx += 1

    vgpr_index_start = idx

    # Global gamma/beta per-segment loads (generated once)
    K = (Y + NUM_VE - 1) // NUM_VE
    gamma_load_nodes = []
    beta_load_nodes = []
    segment_lens = [NUM_VE] * K
    if Y % NUM_VE != 0:
        segment_lens[-1] = Y % NUM_VE

    for k in range(K):
        seg_len = segment_lens[k]
        n_gamma = idx
        nodes[n_gamma] = DAGNode(n_gamma, Operation(None, None, 'load'), 0, 1, None, seg_len,
                                 segment_id=k, vector_id=None, wait_to_load=True)
        nodes[0].child_list.append(n_gamma)
        gamma_load_nodes.append(n_gamma)
        idx += 1

        n_beta = idx
        nodes[n_beta] = DAGNode(n_beta, Operation(None, None, 'load'), 0, 1, None, seg_len,
                                segment_id=k, vector_id=None, wait_to_load=True)
        nodes[0].child_list.append(n_beta)
        beta_load_nodes.append(n_beta)
        idx += 1

    vgpr_start_addr = idx - vgpr_index_start

    def build_tree_reduce(op_type, id_list, start_layer, vec_id):
        nonlocal idx
        current = id_list[:]
        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                if i + 1 < len(current):
                    n0, n1 = current[i], current[i + 1]
                    node = DAGNode(idx, Operation(n0, n1, op_type), start_layer, 0, vec_id, 1)
                    nodes[n0].child_list.append(idx)
                    nodes[n1].child_list.append(idx)
                    nodes[idx] = node
                    next_level.append(idx)
                    idx += 1
                else:
                    next_level.append(current[i])
            current = next_level
            start_layer += 1
        return current[0]

    for vec_id in range(X):
        seg_load_nodes = []
        seg_sub_nodes = []
        seg_sq_nodes = []
        seg_sq_sum_nodes = []

        def add_node(op_type, layer, dtype, length, seg_id=None, src0=None, src1=None, wait_to_load=False, mask=0, vector_id=vec_id):
            nonlocal idx
            node = DAGNode(idx, Operation(src0, src1, op_type), layer, dtype, vec_id, length,
                           segment_id=seg_id, vector_id=vector_id, wait_to_load=wait_to_load)
            node.mask = mask
            if src0 is not None:
                nodes[src0].child_list.append(idx)
            if src1 is not None:
                nodes[src1].child_list.append(idx)
            nodes[idx] = node
            idx += 1
            return idx - 1

        # 1) Segment loads and partial sums for mean
        sum_nodes = []
        for k in range(K):
            seg_len = segment_lens[k]
            n_load = add_node("load", 1, 1, seg_len, seg_id=k, wait_to_load=True)
            nodes[0].child_list.append(n_load)
            n_sum = add_node("reduce_sum", 2, 0, 1, seg_id=k, src0=n_load)  # mean path stays in default precision
            seg_load_nodes.append(n_load)
            sum_nodes.append(n_sum)

        # μ = reduce_sum(v1) / n  (mean tree uses "add" as before)
        n_mu = add_node("mul", 3, 0, 1,
                        src0=build_tree_reduce("add", sum_nodes, 2, vec_id),
                        src1=const_nodes["inv_n"])

        # 2) Centering, square (bf16), and segment-wise square-sum (bf16)
        for k, n_load in enumerate(seg_load_nodes):
            seg_len = segment_lens[k]
            n_sub = add_node("sub", 4, 1, seg_len, seg_id=k, src0=n_load, src1=n_mu)
            # ---- CHANGED: square -> square_bf16 ----
            n_sq = add_node("square_fp16_fp16_bf16", 5, 1, seg_len, seg_id=k, src0=n_sub)
            # ---- CHANGED: reduce_sum -> reduce_sum_bf16 (on squared values) ----
            n_sq_sum = add_node("reduce_sum_bf16", 6, 0, 1, seg_id=k, src0=n_sq)
            seg_sub_nodes.append(n_sub)
            seg_sq_nodes.append(n_sq)
            seg_sq_sum_nodes.append(n_sq_sum)

        # 3) Variance path: sum of squared residuals uses bf16 add tree, then mul_bf16 by inv_n
        # ---- CHANGED: "add" -> "add_bf16" for the square-sum tree ----
        tree_sq_sum = build_tree_reduce("add_bf16", seg_sq_sum_nodes, 6, vec_id)
        # ---- CHANGED: mul -> mul_bf16 for variance ----
        n_var = add_node("mul_bf16_fp16_fp16", 7, 0, 1, src0=tree_sq_sum, src1=const_nodes["inv_n"])

        # 4) Normalization coefficient
        n_add_eps = add_node("add", 8, 0, 1, src0=n_var, src1=const_nodes["epsilon"])
        n_sqrt = add_node("sqrt", 9, 0, 1, src0=n_add_eps)
        n_mul_sqrt2 = add_node("mul", 10, 0, 1, src0=n_sqrt, src1=const_nodes["sqrt2"], mask=1)
        n_inv = add_node("inv", 11, 0, 1, src0=n_mul_sqrt2)

        # 5) Per-segment normalization and affine transform with global gamma/beta segments
        for k, n_sub in enumerate(seg_sub_nodes):
            seg_len = segment_lens[k]
            n_norm = add_node("mul", 12, 1, seg_len, seg_id=k, src0=n_sub, src1=n_inv)
            n_scaled = add_node("mul", 13, 1, seg_len, seg_id=k, src0=n_norm, src1=gamma_load_nodes[k])
            n_shifted = add_node("add", 14, 1, seg_len, seg_id=k, src0=n_scaled, src1=beta_load_nodes[k])
            n_store = add_node("store", 15, 1, seg_len, seg_id=k, src0=n_shifted)

            mapping.append({
                "Vector Index": vec_id,
                "Segment ID": k,
                "Start Index": k * NUM_VE,
                "Length": seg_len,
                "Load Node": seg_load_nodes[k],
                "Store Node": n_store
            })

    return nodes, pd.DataFrame(mapping), vgpr_start_addr


def construct_dag(function="softmax", X=32, Y=32, NUM_VE=256):
    f = function.lower()
    if f == "softmax":
        return construct_softmax(X=X, Y=Y, NUM_VE=NUM_VE)
    elif f == "logsoftmax":
        return construct_logsoftmax(X=X, Y=Y, NUM_VE=NUM_VE)
    elif f == "logsumexp":
        return construct_logsumexp(X=X, Y=Y, NUM_VE=NUM_VE)
    elif f == "layernorm":
        return construct_layernorm(X=X, Y=Y, NUM_VE=NUM_VE)
    elif f == "softplus":
        return construct_softplus(X=X, Y=Y, NUM_VE=NUM_VE)
    elif f == "elu":
        return construct_elu(X=X, Y=Y, NUM_VE=NUM_VE)
    else:
        return construct_activation(X=X, Y=Y, NUM_VE=NUM_VE, act_func=function)





def relabel_dag_layers(dag_nodes):
    """
    遍历 DAG 并根据依赖关系修正每个节点的 layer 值，使其表示从根节点出发的最短路径层级。
    """
    from collections import deque

    # 初始化所有节点的入度和依赖图
    indegree = {idx: 0 for idx in dag_nodes}
    reverse_edges = {idx: [] for idx in dag_nodes}
    for idx, node in dag_nodes.items():
        for child in node.child_list:
            indegree[child] += 1
            reverse_edges[idx].append(child)

    # 拓扑排序（从 root 开始）
    queue = deque()
    if 0 in dag_nodes:
        dag_nodes[0].layer = 0
        queue.append(0)

    while queue:
        current = queue.popleft()
        current_layer = dag_nodes[current].layer
        for child in reverse_edges.get(current, []):
            indegree[child] -= 1
            # 更新子节点层数为当前层数 + 1 的最大值
            dag_nodes[child].layer = max(dag_nodes[child].layer, current_layer + 1)
            if indegree[child] == 0:
                queue.append(child)

def assign_register_and_memory_addresses(dag_nodes, sgpr_start_addr=0, vgpr_start_addr=0, mem_start_addr=0,
                                         sgpr_cap=1024, vgpr_cap=1024):
    """
    为 DAG 中的节点分配 SGPR、VGPR 和 Memory 地址。
    v17: 保证所有 load/store（无论标量/向量）都有 memory 地址。
    """
    sgpr_addr = sgpr_start_addr
    vgpr_addr = vgpr_start_addr
    mem_addr = mem_start_addr
    store_addr = mem_start_addr

    parameter_addr = 0

    # Step 1: 预处理 load 节点，分配 memory 地址
    for node in dag_nodes.values():
        if node.op.op_type == "load":
            node.op.src0 = mem_addr
            mem_addr += 1

    # Step 2: 分配 GPR 地址 + store 的 memory 地址
    for node in dag_nodes.values():
        if node.op.op_type in ["const", "root"] and node.gpr_addr is not None:
            continue

        # 所有 store 节点都需要 memory 地址，不区分 scalar/vector
        if node.op.op_type == "store":
            node.op.src1 = store_addr
            store_addr += 1
            continue

        if node.type == 0:
            node.gpr_addr = (sgpr_addr - sgpr_start_addr) % (sgpr_cap - sgpr_start_addr) + sgpr_start_addr
            sgpr_addr += 1

        elif node.type == 1:
            if node.op.op_type == "load":
                if node.group_id is None or node.group_id == -1:
                    # parameter
                    node.gpr_addr = parameter_addr
                    parameter_addr += 1
                else:
                    # normal
                    node.gpr_addr = (vgpr_addr - vgpr_start_addr) % (vgpr_cap - vgpr_start_addr) + vgpr_start_addr
                    vgpr_addr += 1
            else:
                node.gpr_addr = (vgpr_addr - vgpr_start_addr) % (vgpr_cap - vgpr_start_addr) + vgpr_start_addr
                vgpr_addr += 1
"""
def assign_register_and_memory_addresses(dag_nodes, sgpr_start_addr=0, vgpr_start_addr=0, mem_start_addr=0,
                                         sgpr_cap=1024, vgpr_cap=1024):
    
    为 DAG 中的节点分配 SGPR、VGPR 和 Memory 地址。
    v10中保证同一个向量的store和load的memory地址相同。
    
    sgpr_addr = sgpr_start_addr
    vgpr_addr = vgpr_start_addr
    mem_addr = mem_start_addr
    store_addr = vgpr_start_addr

    parameter_addr = 0

    # Step 1: 预处理 load 和store 节点，分配 memory 地址
    for node in dag_nodes.values():
        if node.op.op_type == "load":
            node.op.src0 = mem_addr
            mem_addr += 1

    # Step 2: 分配 GPR 地址
    for node in dag_nodes.values():
        if node.op.op_type in ["const", "root"] and node.gpr_addr is not None:
            continue

        if node.type == 0:
            node.gpr_addr = (sgpr_addr - sgpr_start_addr) % (sgpr_cap - sgpr_start_addr) + sgpr_start_addr
            sgpr_addr += 1

        elif node.type == 1:
            if node.op.op_type == "load":
                if node.group_id == None or node.group_id == -1:
                    # parameter
                    node.gpr_addr = parameter_addr
                    parameter_addr += 1
                else:
                    # normal
                    node.gpr_addr = (vgpr_addr - vgpr_start_addr) % (vgpr_cap - vgpr_start_addr) + vgpr_start_addr
                    vgpr_addr += 1
            elif node.op.op_type == "store":
                node.op.src1 = store_addr
                store_addr += 1
            else:
                node.gpr_addr = (vgpr_addr - vgpr_start_addr) % (vgpr_cap - vgpr_start_addr) + vgpr_start_addr
                vgpr_addr += 1
"""
def count_sgpr_vgpr_usage(dag_nodes, group_id=0):
    sgpr_count = 0
    vgpr_count  = 0

    for node in dag_nodes.values():
        if node.group_id != group_id:
            continue
        if node.gpr_addr is not None:
            if node.type == 0:
                sgpr_count += 1
            elif node.type == 1:
                vgpr_count += 1

    print("Group ID = {} 使用的 SGPR 数量 = {}, VGPR 数量 = {}".format(group_id, sgpr_count, vgpr_count))
    return sgpr_count, vgpr_count

def calculate_max_active_state(sgpr_count, vgpr_count, y, num_ve,
                               sgpr_start_addr=0, vgpr_start_addr=0,
                               vgpr_cap=1024, sgpr_cap=1024):
    """
    For current DAG construction, sgpr_count/vgpr_count already represent
    the register demand of one complete logical vector state (including all segments
    of a long vector). Therefore do NOT multiply by ceil(y / num_ve) again.
    """
    if sgpr_count <= 0:
        max_active_sgpr = sgpr_cap - sgpr_start_addr
    else:
        max_active_sgpr = math.floor((sgpr_cap - sgpr_start_addr) / sgpr_count)

    if vgpr_count <= 0:
        max_active_vgpr = vgpr_cap - vgpr_start_addr
    else:
        max_active_vgpr = math.floor((vgpr_cap - vgpr_start_addr) / vgpr_count)

    max_active_state = min(max_active_sgpr, max_active_vgpr)

    print("最大活跃 SGPR 数量 = {}".format(max_active_sgpr))
    print("最大活跃 VGPR 数量 = {}".format(max_active_vgpr))
    print("最大活跃状态数量 = {}".format(max_active_state))

    return max_active_state
"""
def calculate_max_active_state(sgpr_count, vgpr_count, y, num_ve, sgpr_start_addr=0, vgpr_start_addr=0, vgpr_cap=1024,
                                         sgpr_cap=1024):
    max_active_sgpr = math.floor((sgpr_cap - sgpr_start_addr) / sgpr_count)
    max_active_vgpr = math.floor((vgpr_cap - vgpr_start_addr) / vgpr_count)
    
    if max_active_sgpr > max_active_vgpr:
        max_active_state = max_active_vgpr
    else:
        max_active_state = max_active_sgpr
    
    i = math.ceil(y / num_ve)

    max_active_sgpr *= i
    max_active_vgpr *= i
    max_active_state *= i

    print(f"最大活跃 SGPR 数量 = {max_active_sgpr}")
    print(f"最大活跃 VGPR 数量 = {max_active_vgpr}")
    print(f"最大活跃状态数量 = {max_active_state}")

    return max_active_state
"""

def validate_mem_addr(mem_addr):
    if not 0 <= mem_addr <= MEM_ADDR_MAX:
        raise ValueError(
            f"mem_addr={mem_addr} exceeds the {MEM_ADDR_BITS}-bit on-chip SRAM "
            f"address range 0..{MEM_ADDR_MAX}"
        )

def encode_load_slot(mem_fmt, mem_addr, gpr_fmt, gpr_addr, optype):
    validate_mem_addr(mem_addr)
    return ((mem_fmt & 0b11) << 24) | ((mem_addr & MEM_ADDR_MAX) << 12) | ((gpr_fmt & 0b11) << 10) | ((gpr_addr & 0xFF) << 2) | (optype & 0b11)

def encode_store_slot(mem_fmt, mem_addr, gpr_fmt, gpr_addr, optype):
    validate_mem_addr(mem_addr)
    return ((mem_fmt & 0b11) << 24) | ((mem_addr & MEM_ADDR_MAX) << 12) | ((gpr_fmt & 0b11) << 10) | ((gpr_addr & 0xFF) << 2) | (optype & 0b11)

def encode_vector_slot(half, imm, connect, dst, src1, src0, mask, optype):
    return ((half & 0b11) << 32) | ((imm & 0b1) << 31) | ((connect & 0b11) << 29) | ((dst & 0xFF) << 21) | ((src1 & 0xFF) << 13) | ((src0 & 0xFF) << 5) | ((mask & 1) << 4) | (optype & 0xF)

def encode_scalar_slot(imm, connect, dst, src1, src0, mask, optype):
    return ((imm & 0b1) << 30) | ((connect & 0b1) << 29) | ((dst & 0xFF) << 21) | ((src1 & 0xFF) << 13) | ((src0 & 0xFF) << 5) | ((mask & 1) << 4) | (optype & 0xF)

def encode_sfu_slot(borrow, dst, src, is_vector, rounds, optype):
    return ((borrow & 0b11) << 29) | ((dst & 0xFF) << 21) | ((src & 0xFF) << 13) | ((is_vector & 0x1) << 12) | ((rounds & 0xFF) << 4) | (optype & 0b1111)


VECTOR_OPCODES = {
    "nop":         0,
    "mul":         1,
    "add":         2,
    "sub":         3,
    "max":         4,
    "min":         5,
    "cmp_eq":      6,
    "cmp_geq":     7,
    "cmp_leq":     8,
    "shl":         9,
    "shr":         10,
    "reduce_sum":  11,
    "reduce_max":  12,
    "reduce_sum_bf16": 13,          #1101
    "mul_fp16_fp16_bf16": 14,       #1110  可支持square_fp16_fp16_bf16
    "mul_bf16_fp16_fp16": 15,       #1111
}


SCALAR_OPCODES = {
    "nop":         0,
    "mul":         1,
    "add":         2,
    "sub":         3,
    "max":         4,
    "min":         5,
    "cmp_eq":      6,
    "cmp_geq":     7,
    "cmp_leq":     8,
    "shl":         9,
    "shr":         10,
    "add_bf16":    11,              #1011 bf16+bf16->bf16
    "mul_fp16_fp16_bf16": 14,       #1110  可支持square_fp16_fp16_bf16
    "mul_bf16_fp16_fp16": 15,       #1111
}

SFU_OPCODES = {
    "nop":     0,
    "exp":     1,
    "sqrt":    2,
    "inv":     3,      # 表示 1/x
    "gelu":    4,
    "sigmoid": 5,
    "tanh":    6,
    "sin":     7,
    "cos":     8,
    "ln":      9,
}

class MaskTracker:
    def __init__(self, mask_fifo):
        self.scalar = mask_fifo
        self.vector = mask_fifo
        self.mask_fifo = mask_fifo  # 保存下来，避免重复传参

    def check(self, op, is_vector):
        if op == "sqrt":
            if is_vector and self.vector > 0:
                return 1
            elif not is_vector and self.scalar > 0:
                return 1
            else: return 0
            #return self.vector if is_vector else self.scalar
        return 1

    def update(self, op, is_vector, mask):
        if op == "sqrt":
            if is_vector:
                self.vector -= 1
            else:
                self.scalar -= 1
        elif op == "mul" and mask:
            if is_vector:
                self.vector += 1
                if self.vector > self.mask_fifo:
                    print("ERROR: Vector mask fifo overflow!")
            else:
                self.scalar += 1
                if self.scalar > self.mask_fifo:
                    print("ERROR: Scalar mask fifo overflow!")




def schedule_dag_nodes(dag_nodes, max_active_state, num_ve=256, mask_fifo=8, mode=0,
                       add_rqo_option0=32, add_rqo_option1=16, add_rqo_option2=16,
                       max_issue_slots=2):
    """
    调度 DAG 中的节点，生成指令时间表。
    返回 schedule（每个cycle一个五元组）和 EOP 插入后的完整表。
    """

    if not 1 <= max_issue_slots <= 5:
        raise ValueError("max_issue_slots must be in the range 1..5")

    # 初始化
    Tmax = 100000
    for node in dag_nodes.values():
        node.issued = False
        node.ready_time = -1

    # 初始：root 和 const 已完成
    for node in dag_nodes.values():
        if node.op.op_type in ["const", "root"]:
            node.issued = True
            node.ready_time = 0

    # 资源表
    ve_usage = [1] * (Tmax+50) # 0代表ve全部占用，1代表空闲，2代表被VE占用一部分，3代表被SFU占用一部分，4代表被ve和SFU同时占用
    scalar_usage = [1] * (Tmax+50)
    sfu_usage = [-1] * (Tmax+50)
    sfu_s_usage = [-1] * (Tmax+50)
    sgpr_read_bank = [[-1]*(Tmax+50) for _ in range(4)]
    vgpr_read_bank = [[-1]*(Tmax+50) for _ in range(4)]
    sgpr_write_bank = [[-1]*(Tmax+50) for _ in range(4)]
    vgpr_write_bank = [[-1]*(Tmax+50) for _ in range(4)]
    mask_tracker = MaskTracker(mask_fifo)

    slot_tags = ['load', 'store', 'vector', 'scalar', 'sfu']
    schedule = []

    def bank(addr):
        return addr & 0b11 if addr is not None else -1


    def check_read(t, src0_addr, src1_addr, src0_is_vector, src1_is_vector, src0_is_gpr, src1_is_gpr):
        tt = t + 1  # actual read happens 1 cycles later

        # case 1: both operands are GPR
        if src0_is_gpr and src1_is_gpr:
            if src0_is_vector and src1_is_vector:
                banks = vgpr_read_bank
            elif not src0_is_vector and not src1_is_vector:
                banks = sgpr_read_bank
            else:
                b0 = bank(src0_addr)
                b1 = bank(src1_addr)
                if src0_is_vector:
                    return vgpr_read_bank[b0][tt] in [-1, src0_addr] and sgpr_read_bank[b1][tt] in [-1, src1_addr], 0
                else:
                    return sgpr_read_bank[b0][tt] in [-1, src0_addr] and vgpr_read_bank[b1][tt] in [-1, src1_addr], 0

            b0 = bank(src0_addr)
            b1 = bank(src1_addr)
            if b0 == b1:
                # same bank: try t and t+1
                return banks[b0][tt] in [-1, src0_addr] and banks[b0][tt+1] in [-1, src1_addr], 1
            else:
                return banks[b0][tt] in [-1, src0_addr] and banks[b1][tt] in [-1, src1_addr], 0

        # case 2: only src0 is GPR (e.g. store or src1 is imm)
        elif src0_is_gpr:
            banks = vgpr_read_bank if src0_is_vector else sgpr_read_bank
            b0 = bank(src0_addr)
            return banks[b0][tt] in [-1, src0_addr], 0

        # case 3: only src1 is GPR (e.g. load)
        elif src1_is_gpr:
            banks = vgpr_read_bank if src1_is_vector else sgpr_read_bank
            b1 = bank(src1_addr)
            return banks[b1][tt] in [-1, src1_addr], 0

        # default case (should not happen)
        return True, 0



    def update_read(t, src0_addr, src1_addr, src0_is_vector, src1_is_vector, src0_is_gpr, src1_is_gpr, access_penalty):
        tt = t + 1  # actual read starts here

        if src0_is_gpr:
            banks0 = vgpr_read_bank if src0_is_vector else sgpr_read_bank
            b0 = bank(src0_addr)
            banks0[b0][tt] = src0_addr

        if src1_is_gpr:
            banks1 = vgpr_read_bank if src1_is_vector else sgpr_read_bank
            b1 = bank(src1_addr)
            if access_penalty == 0:
                banks1[b1][tt] = src1_addr
            else:
                banks1[b1][tt+1] = src1_addr


    def check_write(t, dst_addr, dst_is_gpr, dst_is_vector, latency, access_penalty):
        if not dst_is_gpr:
            return 1
        else:
            b = bank(dst_addr)
            if dst_is_vector:
                return vgpr_write_bank[b][t+latency+access_penalty] in [-1]
            else:
                return sgpr_write_bank[b][t+latency+access_penalty] in [-1]
    
    def update_write(t, dst_addr, dst_is_gpr, dst_is_vector, latency, access_penalty):
        if dst_is_gpr:
            banks = vgpr_write_bank if dst_is_vector else sgpr_write_bank
            b = bank(dst_addr)
            banks[b][t+latency+access_penalty] = dst_addr

    def check_resource(t, slot_type, access_penalty, mode):
        # return ok, half
        if slot_type == "ve" and mode == 0:
            # 需要两拍
            tt = t + 3 + access_penalty
            usage_a = ve_usage[tt]
            usage_b = ve_usage[tt+1]

            tt_start = tt - 9
            if (tt_start < 0):
                tt_start = 0
            
            allow_full = 1
            for i in range(tt_start, tt):
                if ve_usage[i] == 3 or ve_usage[i] == 4: # 检测是否会有sfu重构冲突
                    allow_full = 0

            if allow_full == 1:
                if usage_a == 1:
                    return 1, 0
                elif usage_a == 3 and (usage_b == 1 or usage_b == 3):
                    return 1, 1
                else: return 0,0
            else:
                if usage_a == 3 and (usage_b == 1 or usage_b == 3):
                    return 1, 1
                else: return 0,0

        elif slot_type == "ve" and mode == 1:
            # 需要4拍
            tt = t + 3 + access_penalty
            usage_a = ve_usage[tt]
            usage_b = ve_usage[tt+1]
            usage_c = ve_usage[tt+2]
            usage_d = ve_usage[tt+3]

            tt_start = tt - 9
            if (tt_start < 0):
                tt_start = 0
            
            allow_full = 1
            for i in range(tt_start, tt):
                if ve_usage[i] == 3 or ve_usage[i] == 4: # 检测是否会有sfu重构冲突
                    allow_full = 0

            if allow_full == 1:
                if usage_a == 1:
                    return 1, 0
                elif usage_a == 3 and (usage_b == 1 or usage_b == 3) and (usage_c == 1 or usage_c == 3) and (usage_d == 1 or usage_d == 3):
                    return 1, 2
                else: return 0, 0
            else:
                if usage_a == 3 and (usage_b == 1 or usage_b == 3) and (usage_c == 1 or usage_c == 3) and (usage_d == 1 or usage_d == 3):
                    return 1, 2
                else: return 0, 0
        
        elif slot_type == "ve" and mode == 2:
            # VE需要要么暂停要么1拍做完
            tt = t + 3 + access_penalty
            usage_a = ve_usage[tt]

            tt_start = tt - 9
            if (tt_start < 0):
                tt_start = 0
            
            allow_full = 1
            for i in range(tt_start, tt):
                if ve_usage[i] == 3: # 检测是否会有sfu重构冲突，不存在=4的情况
                    allow_full = 0
            
            if allow_full == 1:
                if usage_a == 1:
                    return 1, 0
                else: return 0, 0
            else:
                return 0, 0
                
        elif slot_type == "scalar":
            tt = t + 3 + access_penalty
            if scalar_usage[tt] in [1]:
                return 1, 0
            else:
                return 0, 0
        else:
            return 1, 0

    def check_sfu_history_scalar(t, op):

        tt = t + 3
        
        if op == "exp":
            if sfu_s_usage[tt] not in [-1]:
                return 0
            for k in range(3):
                if tt - 1 - k >= 0 and sfu_s_usage[tt - 1 - k] in [8]:
                    # cos stall
                    return 0 
                
        elif (SFU_OPCODES[op] >= 2 and SFU_OPCODES[op] <= 6):
            if sfu_s_usage[tt] not in [-1]:
                return 0
            for k in range(5):
                if tt - 1 - k >= 0 and sfu_s_usage[tt - 1 - k] in [1,7]:
                    # exp/sin stall
                    return 0 
            for k in range(3):
                if tt - 1 - k >= 0 and sfu_s_usage[tt - 1 - k] in [9]:
                    # ln stall
                    return 0 
            for k in range(8):
                if tt - 1 - k >= 0 and sfu_s_usage[tt - 1 - k] in [8]:
                    # cos stall
                    return 0 
            
        elif SFU_OPCODES[op] == 9:
            if sfu_s_usage[tt] not in [-1]:
                return 0
            for k in range(5):
                if tt - 1 - k >= 0 and sfu_s_usage[tt - 1 - k] in [1,7]:
                    # exp/sin stall
                    return 0 
            for k in range(8):
                if tt - 1 - k >= 0 and sfu_s_usage[tt - 1 - k] in [8]:
                    # cos stall
                    return 0 
            
        elif SFU_OPCODES[op] == 7:
            if sfu_s_usage[tt] not in [-1]:
                return 0
            for k in range(3):
                if tt - 1 - k >= 0 and sfu_s_usage[tt - 1 - k] in [8]:
                    # cos stall
                    return 0 
        
        elif SFU_OPCODES[op] == 8:
            if sfu_s_usage[tt] not in [-1]:
                return 0
        
        else: return 0

        return 1

    def check_sfu_history(t, op, rounds):
        # rounds数目已考虑到borrow情况
        tt = t + 4

        if op == "exp":
            for k in range(rounds):
                if sfu_usage[tt+k] not in [-1]:
                    return 0
            for k in range(3):
                if tt - 1 - k >= 0 and sfu_usage[tt - 1 - k] in [8]:
                    # cos stall
                    return 0 
        
        elif (SFU_OPCODES[op] >= 2 and SFU_OPCODES[op] <= 6):
            for k in range(5):
                if tt - 1 - k >= 0 and sfu_usage[tt - 1 - k] in [1,7]:
                    # exp/sin stall
                    return 0 
            for k in range(3):
                if tt - 1 - k >= 0 and sfu_usage[tt - 1 - k] in [9]:
                    # ln stall
                    return 0 
            for k in range(8):
                if tt - 1 - k >= 0 and sfu_usage[tt - 1 - k] in [8]:
                    # cos stall
                    return 0 
            for k in range(rounds):
                if sfu_usage[tt+k] not in [-1]:
                    return 0
        
        elif SFU_OPCODES[op] == 9 :
            for k in range(5):
                if tt - 1 - k >= 0 and sfu_usage[tt - 1 - k] in [1,7]:
                    # exp/sin stall
                    return 0 
            for k in range(8):
                if tt - 1 - k >= 0 and sfu_usage[tt - 1 - k] in [8]:
                    # cos stall
                    return 0 
            for k in range(rounds):
                if sfu_usage[tt+k] not in [-1]:
                    return 0
                
        elif SFU_OPCODES[op] == 7:
            for k in range(3):
                if tt - 1 - k >= 0 and sfu_usage[tt - 1 - k] in [8]:
                    # cos stall
                    return 0 
            for k in range(rounds):
                if sfu_usage[tt+k] not in [-1]:
                    return 0
                
        elif SFU_OPCODES[op] == 8:
            for k in range(rounds):
                if sfu_usage[tt+k] not in [-1]:
                    return 0
                
        else: return 0
        
        return 1
    
    
    def check_ve_from_sfu(t, op, rounds):
        if op == "exp":
            tt_ve = t + 3 + exp_prep
        elif (SFU_OPCODES[op] >= 2 and SFU_OPCODES[op] <= 6) :
            tt_ve = t + 3 + sfu_prep
        elif (SFU_OPCODES[op] == 7):
            tt_ve = t + 3 + sin_prep
        elif (SFU_OPCODES[op] == 8):
            tt_ve = t + 3 + cos_prep
        elif (SFU_OPCODES[op] == 9):
            tt_ve = t + 3 + ln_prep
        
        for k in range(rounds):
            if (ve_usage[tt_ve + k] == 0 or ve_usage[tt_ve + k] == 3 or ve_usage[tt_ve + k] == 4):
                return 0
        
        return 1
                
    
    def update_resource(t, slot_type, access_penalty, rounds, mode, half, op):
        if slot_type == "ve" and half == 0:
            tt = t + 3 + access_penalty
            ve_usage[tt] = 0

        elif slot_type == "ve" and half == 1:
            tt = t + 3 + access_penalty
            if ve_usage[tt] == 1:
                ve_usage[tt] = 2
            elif ve_usage[tt] == 3:
                ve_usage[tt] = 4
                
            if ve_usage[tt+1] == 1:
                ve_usage[tt+1] = 2
            elif ve_usage[tt+1] == 3:
                ve_usage[tt+1] = 4

        elif slot_type == "ve" and half == 2:
            tt = t + 3 + access_penalty
            if ve_usage[tt] == 1:
                ve_usage[tt] = 2
            elif ve_usage[tt] == 3:
                ve_usage[tt] = 4
                
            if ve_usage[tt+1] == 1:
                ve_usage[tt+1] = 2
            elif ve_usage[tt+1] == 3:
                ve_usage[tt+1] = 4

            if ve_usage[tt+2] == 1:
                ve_usage[tt+2] = 2
            elif ve_usage[tt+2] == 3:
                ve_usage[tt+2] = 4

            if ve_usage[tt+3] == 1:
                ve_usage[tt+3] = 2
            elif ve_usage[tt+3] == 3:
                ve_usage[tt+3] = 4
            
        elif slot_type == "scalar":
            tt = t + 3 + access_penalty
            scalar_usage[tt] = 0

        elif slot_type == "sfu" and rounds > 0:
            if op == "exp":
                tt_ve = t + 3 + exp_prep
            elif (SFU_OPCODES[op] >= 2 and SFU_OPCODES[op] <= 6) :
                tt_ve = t + 3 + sfu_prep
            elif (SFU_OPCODES[op] == 7):
                tt_ve = t + 3 + sin_prep
            elif (SFU_OPCODES[op] == 8):
                tt_ve = t + 3 + cos_prep 
            elif (SFU_OPCODES[op] == 9):
                tt_ve = t + 3 + ln_prep    

            tt = t + 4
            for k in range(rounds):
                # 更新sfu
                sfu_usage[tt + k] = SFU_OPCODES[op]
                # 更新ve
                if (mode == 0 or mode == 1):
                    if (ve_usage[tt_ve + k] == 1):
                        ve_usage[tt_ve + k] = 3
                    elif (ve_usage[tt_ve + k] == 2):
                        ve_usage[tt_ve + k] = 4
                elif (mode == 2):
                    if (ve_usage[tt_ve + k] == 1):
                        ve_usage[tt_ve + k] = 3
        
        elif slot_type == "sfu" and rounds == 0:
            # 标准版SFU算子更新
            tt = t + 3
            sfu_s_usage[tt] = SFU_OPCODES[op]
                
                        
                        


    load_wb = 3 # load操作写回延时，已检查
    scalar_wb = 7 # scalar操作写回延时
    ve_wb = 7
    ve_reduce_sum_wb = 12
    ve_reduce_max_wb = 7
    sfu_wb = 16+3
    exp_wb = 21+3
    ln_wb = 19+3
    sin_wb = 21+3
    cos_wb = 24+3

    exp_prep = 1+7 # 数据输入SFU到二阶多项式开始计算延迟 (+3=11)
    sfu_prep = 1+2 # 数据输入SFU到二阶多项式开始计算延迟 (+3=6)
    ln_prep = 1+2
    sin_prep = 1+7
    cos_prep = 1+10


    load_latency = 3 # load操作数据准备延时，已检查
    scalar_latency = 7 # scalar操作数据准备延时
    ve_latency = 7
    ve_reduce_sum_latency = 12
    ve_reduce_max_latency = 7
    sfu_latency = 16+3
    exp_latency = 21+3
    ln_latency = 19+3
    sin_latency = 21+3
    cos_latency = 24+3

    half_penalty = {0:0, 1:1, 2:3} # mode0/1/2轮数=1/2/4

    NodeList = list(node for node in dag_nodes.values() if node.op.op_type not in ["const", "root"])
    
    t = 0
    active_state = 0
    mask_list = []

    # Track logical active vectors instead of counting every load/store node
    active_vector_keys = set()
    store_nodes_per_vector = {}

    for node in dag_nodes.values():
        if node.op.op_type == "store" and node.group_id is not None and node.group_id != -1:
            key = node.group_id
            store_nodes_per_vector[key] = store_nodes_per_vector.get(key, 0) + 1
    
    while NodeList:

        slot_used = {k: False for k in slot_tags}
        slot_data = {k: 0 for k in slot_tags}

        for node in mask_list:
            # 检查src0是否ready
            pred_ids = [node.op.src0]
            pred_ids = [p for p in pred_ids if p is not None and isinstance(p, int) and p in dag_nodes]
            pred_issued = all(dag_nodes[p].issued and t >= dag_nodes[p].ready_time for p in pred_ids)
            if not pred_issued: break
            # 因为mask_list中的node必须顺序发射，所以不再判定后续的node

            # 只会出现*sqrt(2)的mask mul操作
            op = node.op.op_type
            is_vector = (node.type == 1)
            gpr_addr = node.gpr_addr
            src0_node = dag_nodes.get(node.op.src0, None)
            src1_node = dag_nodes.get(node.op.src1, None)
            src0_is_vector = src0_node.type if src0_node else -1
            src1_is_vector = src1_node.type if src1_node else -1
            src0_addr = src0_node.gpr_addr if src0_node else -1
            src1_addr = src1_node.gpr_addr if src1_node else -1

            if is_vector:
                # src0 is vector, src1 is scalar
                can_read, penalty = check_read(t, src0_addr, src1_addr, 1, 0, 1, 0)
                if not can_read: break
                # can_write = check_write(t, gpr_addr, 1, is_vector, ve_wb, penalty)
                # if not can_write: break
                can_use, half = check_resource(t, "ve", penalty, mode)
                if not can_use: break
                can_write = check_write(t + half_penalty[half], gpr_addr, 1, is_vector, ve_wb, penalty)
                if not can_write: break

                slot_data["vector"] = encode_vector_slot(half, 0, 1, 2, gpr_addr, src1_addr, src0_addr, node.mask, VECTOR_OPCODES[op])
                mask_tracker.update(op, is_vector, node.mask)
                update_read(t, src0_addr, src1_addr, 1, 0, 1, 0, penalty)
                update_write(t + half_penalty[half], gpr_addr, 1, is_vector, ve_wb, penalty)
                update_resource(t, "ve", penalty, 1, mode, half, op)
                node.issued = True
                node.ready_time = t + ve_latency + penalty + half_penalty[half]
                slot_used["vector"] = True
                NodeList.remove(node)
                print("t={}, issue ve node {} with op {} src0={} src1={} dst={} latency={} penalty={} half={}".format(t, node.index, op, src0_addr, src1_addr, gpr_addr, ve_latency, penalty, half))
                mask_list.remove(node)
                break
            else:
                can_read, penalty = check_read(t, src0_addr, src1_addr, 0, 0, 1, 0)
                if not can_read: break
                can_write = check_write(t, gpr_addr, 1, 0, scalar_wb, penalty)
                if not can_write: break
                can_use, half = check_resource(t, "scalar", penalty, mode)
                if not can_use: break
                slot_data["scalar"] = encode_scalar_slot(1, 0, gpr_addr, src1_addr, src0_addr, node.mask, SCALAR_OPCODES[op])
                mask_tracker.update(op, is_vector, node.mask)
                update_read(t, src0_addr, src1_addr, 0, 0, 1, 0, penalty)
                update_write(t, gpr_addr, 1, 0, scalar_wb, penalty)
                update_resource(t, "scalar", penalty, 1, mode, half, op)
                node.issued = True
                node.ready_time = t + scalar_latency + penalty
                slot_used["scalar"] = True
                NodeList.remove(node)
                print("t={}, issue scalar node {} with op {} src0={} src1={} dst={} latency={} penalty={}".format(t, node.index, op, src0_addr, src1_addr, gpr_addr, scalar_latency, penalty))
                mask_list.remove(node)
                break


        waiting = []    

        for node in list(NodeList):
            if node.op.op_type == 'load':
                pred_issued = 1
            elif node.op.op_type == 'store':
                pred_id = node.op.src0
                pred_issued = dag_nodes[pred_id].issued and t >= dag_nodes[pred_id].ready_time
            else:
                pred_ids = [node.op.src0, node.op.src1]
                pred_ids = [p for p in pred_ids if p is not None and isinstance(p, int) and p in dag_nodes]
                pred_issued = all(dag_nodes[p].issued and t >= dag_nodes[p].ready_time for p in pred_ids)
            
            if pred_issued:
                waiting.append(node)    
        
        waiting.sort(key=lambda n: -n.importance)

        # 在每轮调度开始打印
        #print("=== 时间 t = {} ===".format(t))
        #print("Waiting 节点:")
        #for node in waiting:
        #    print("  Node {}: op={}, \tsrc0={}, \tsrc1={}, \timportance={}".format(node.index, node.op.op_type, node.op.src0, node.op.src1, node.importance))

        # print("NodeList 中剩余节点:")
        # for node in NodeList:
        #     print("  Node {}: op={}, src0={}, src1={}".format(node.index, node.op.op_type, node.op.src0, node.op.src1))

        #print("=====================")

        for node in waiting:
            if sum(slot_used.values()) >= max_issue_slots:
                break

            op = node.op.op_type
            ve_len = node.vector_len
            is_vector = (node.type == 1)
            gpr_addr = node.gpr_addr

            src0_node = dag_nodes.get(node.op.src0, None)
            src1_node = dag_nodes.get(node.op.src1, None)
            if src1_node == None:
                imm = 0 # 不是常数
            else:
                imm = src1_node.op.op_type == "const" # 判断src1是否是常数

            src0_is_vector = src0_node.type if src0_node else -1
            src1_is_vector = src1_node.type if src1_node else -1

            src0_addr = src0_node.gpr_addr if src0_node else -1
            src1_addr = src1_node.gpr_addr if src1_node else -1


            if op == "load" and not slot_used["load"]:
                vector_key = node.group_id

                # Only the first load of one logical vector consumes one active state
                need_new_active_slot = (
                    vector_key is not None and
                    vector_key != -1 and
                    vector_key not in active_vector_keys
                )

                if need_new_active_slot and active_state >= max_active_state:
                    continue

                ok = check_write(t, gpr_addr, 1, is_vector, load_wb, 0)
                if ok:
                    slot_data["load"] = encode_load_slot(0, node.op.src0, 0, gpr_addr, 3 if is_vector else 2)
                    update_write(t, gpr_addr, 1, is_vector, load_wb, 0)
                    node.issued = True
                    node.ready_time = t + load_latency
                    slot_used["load"] = True
                    NodeList.remove(node)
                    print("t={}, issue load node {} gpr={} mem={} latency={}".format(t, node.index, gpr_addr, node.op.src0, load_latency))

                    if need_new_active_slot:
                        active_vector_keys.add(vector_key)
                        active_state += 1
            
            elif op == "store" and not slot_used["store"]:
                ok, access_penalty = check_read(t, src0_node.gpr_addr, 0, is_vector, 0, 1, 0)
                if ok:
                    slot_data["store"] = encode_store_slot(0, node.op.src1, 0, (dag_nodes[node.op.src0]).gpr_addr, 3 if is_vector else 2)
                    update_read(t, src0_node.gpr_addr, 0, is_vector, 0, 1, 0, 0)
                    node.issued = True
                    node.ready_time = t
                    slot_used["store"] = True
                    NodeList.remove(node)
                    print("t={}, issue store node {} mem={} latency={}".format(t, node.index, node.op.src1, 0))

                    vector_key = node.group_id
                    if vector_key is not None and vector_key != -1:
                        if vector_key in store_nodes_per_vector:
                            store_nodes_per_vector[vector_key] -= 1
                            if store_nodes_per_vector[vector_key] == 0:
                                del store_nodes_per_vector[vector_key]
                                if vector_key in active_vector_keys:
                                    active_vector_keys.remove(vector_key)
                                    active_state -= 1

            elif (op in SCALAR_OPCODES or op == 'square') and not src0_is_vector and not src1_is_vector and not slot_used["scalar"]:
                if op == 'square':
                    # only src0
                    can_read, penalty = check_read(t, src0_addr, 0, 0, 0, 1, 0)
                    if not can_read: continue
                    can_write = check_write(t, gpr_addr, 1, 0, scalar_wb, penalty)
                    if not can_write: continue
                    can_use, half = check_resource(t, "scalar", penalty, mode)
                    if not can_use: continue
                    slot_data["scalar"] = encode_scalar_slot(0, 1, gpr_addr, 0, src0_addr, node.mask, SCALAR_OPCODES["mul"])
                    update_read(t, src0_addr, 0, 0, 0, 1, 0, penalty)
                    update_write(t, gpr_addr, 1, 0, scalar_wb, penalty)
                    update_resource(t, "scalar", penalty, 1, mode, half, op)
                    node.issued = True
                    node.ready_time = t + scalar_latency + penalty
                    slot_used["scalar"] = True
                    NodeList.remove(node)
                else:
                    can_read, penalty = check_read(t, src0_addr, src1_addr, 0, 0, 1, imm == 0)
                    if not can_read: continue
                    can_write = check_write(t, gpr_addr, 1, 0, scalar_wb, penalty)
                    if not can_write: continue
                    can_use, half = check_resource(t, "scalar", penalty, mode)
                    if not can_use: continue
                    slot_data["scalar"] = encode_scalar_slot(imm, 0, gpr_addr, src1_addr, src0_addr, node.mask, SCALAR_OPCODES[op])
                    mask_tracker.update(op, is_vector, node.mask)
                    update_read(t, src0_addr, src1_addr, 0, 0, 1, imm == 0, penalty)
                    update_write(t, gpr_addr, 1, 0, scalar_wb, penalty)
                    update_resource(t, "scalar", penalty, 1, mode, half, op)
                    node.issued = True
                    node.ready_time = t + scalar_latency + penalty
                    slot_used["scalar"] = True
                    NodeList.remove(node)
                print("t={}, issue scalar node {} with op {} src0={} src1={} dst={} latency={} penalty={}".format(t, node.index, op, src0_addr, src1_addr, gpr_addr, scalar_latency, penalty))
            
            elif (op in VECTOR_OPCODES or op == 'square' or op == 'square_fp16_fp16_bf16') and not (not src0_is_vector and not src1_is_vector) and not slot_used["vector"]:
                if op == 'square':
                    # only src0
                    can_read, penalty = check_read(t, src0_addr, 0, 1, 0, 1, 0)
                    if not can_read: continue
                    can_use, half = check_resource(t, "ve", penalty, mode)
                    if not can_use: continue
                    can_write = check_write(t + half_penalty[half], gpr_addr, 1, 1, ve_wb, penalty)
                    if not can_write: continue
                
                    slot_data["vector"] = encode_vector_slot(half, 0, 1, gpr_addr, 0, src0_addr, node.mask, VECTOR_OPCODES["mul"])
                    update_read(t, src0_addr, 0, 1, 0, 1, 0, penalty)
                    update_write(t + half_penalty[half], gpr_addr, 1, 1, ve_wb, penalty)
                    update_resource(t, "ve", penalty, 1, mode, half, op)
                    node.issued = True
                    node.ready_time = t + ve_latency + penalty + half_penalty[half]
                    slot_used["vector"] = True
                    NodeList.remove(node)
                    print("t={}, issue ve node {} with op {} src0={} src1={} dst={} latency={} penalty={} half={}".format(t, node.index, op, src0_addr, src1_addr, gpr_addr, ve_latency, penalty, half))
                
                elif op == 'square_fp16_fp16_bf16':
                    # only src0
                    can_read, penalty = check_read(t, src0_addr, 0, 1, 0, 1, 0)
                    if not can_read: continue
                    can_use, half = check_resource(t, "ve", penalty, mode)
                    if not can_use: continue
                    can_write = check_write(t + half_penalty[half], gpr_addr, 1, 1, ve_wb, penalty)
                    if not can_write: continue
                
                    slot_data["vector"] = encode_vector_slot(half, 0, 1, gpr_addr, 0, src0_addr, node.mask, VECTOR_OPCODES["mul_fp16_fp16_bf16"])
                    update_read(t, src0_addr, 0, 1, 0, 1, 0, penalty)
                    update_write(t + half_penalty[half], gpr_addr, 1, 1, ve_wb, penalty)
                    update_resource(t, "ve", penalty, 1, mode, half, op)
                    node.issued = True
                    node.ready_time = t + ve_latency + penalty + half_penalty[half]
                    slot_used["vector"] = True
                    NodeList.remove(node)
                    print("t={}, issue ve node {} with op {} src0={} src1={} dst={} latency={} penalty={} half={}".format(t, node.index, op, src0_addr, src1_addr, gpr_addr, ve_latency, penalty, half))
                
                elif op == 'reduce_sum' or op == 'reduce_max' or op == 'reduce_sum_bf16':
                    if op == 'reduce_sum' or op == 'reduce_sum_bf16':
                        wb = ve_reduce_sum_wb
                        latency = ve_reduce_sum_latency
                    else:
                        wb = ve_reduce_max_wb
                        latency = ve_reduce_max_latency
                    # only src0
                    can_read, penalty = check_read(t, src0_addr, 0, 1, 0, 1, 0)
                    if not can_read: continue
                    can_write = check_write(t, gpr_addr, 1, 0, wb, penalty)
                    if not can_write: continue
                    # 全流水的归约操作的资源检查由slot_used["vector"]确定，无需再检查
                    # can_use = check_resource(t, "ve", penalty, 1)
                    # if not can_use: continue
                    slot_data["vector"] = encode_vector_slot(0, 0, 1, gpr_addr, 0, src0_addr, node.mask, VECTOR_OPCODES[op])
                    update_read(t, src0_addr, 0, 1, 0, 1, 0, penalty)
                    update_write(t, gpr_addr, 1, 0, wb, penalty)
                    # update_resource(t, "ve", penalty, 1)
                    node.issued = True
                    node.ready_time = t + latency + penalty
                    slot_used["vector"] = True
                    NodeList.remove(node)
                    print("t={}, issue ve node {} with op {} src0={} src1={} dst={} latency={} penalty={}".format(t, node.index, op, src0_addr, src1_addr, gpr_addr, latency, penalty))
                elif src1_is_vector and src0_is_vector:
                    can_read, penalty = check_read(t, src0_addr, src1_addr, 1, 1, 1, 1)
                    if not can_read: continue
                    can_use, half = check_resource(t, "ve", penalty, mode)
                    if not can_use: continue
                    can_write = check_write(t + half_penalty[half], gpr_addr, 1, is_vector, ve_wb, penalty)
                    if not can_write: continue
                    
                    slot_data["vector"] = encode_vector_slot(half, 0, 0, gpr_addr, src1_addr, src0_addr, node.mask, VECTOR_OPCODES[op])
                    update_read(t, src0_addr, src1_addr, 1, 1, 1, 1, penalty)
                    update_write(t + half_penalty[half], gpr_addr, 1, is_vector, ve_wb, penalty)
                    update_resource(t, "ve", penalty, 1, mode, half, op)
                    node.issued = True
                    node.ready_time = t + ve_latency + penalty + half_penalty[half]
                    slot_used["vector"] = True
                    NodeList.remove(node)
                    print("t={}, issue ve node {} with op {} src0={} src1={} dst={} latency={} penalty={} half={}".format(t, node.index, op, src0_addr, src1_addr, gpr_addr, ve_latency, penalty, half))
                else:
                    # src0 is vector, src1 is scalar
                    can_read, penalty = check_read(t, src0_addr, src1_addr, 1, 0, 1, imm == 0)
                    if not can_read: continue
                    can_use, half = check_resource(t, "ve", penalty, mode)
                    if not can_use: continue
                    can_write = check_write(t + half_penalty[half], gpr_addr, 1, is_vector, ve_wb, penalty)
                    if not can_write: continue

                    slot_data["vector"] = encode_vector_slot(half, imm, 2, gpr_addr, src1_addr, src0_addr, node.mask, VECTOR_OPCODES[op])
                    mask_tracker.update(op, is_vector, node.mask)
                    update_read(t, src0_addr, src1_addr, 1, 0, 1, imm == 0, penalty)
                    update_write(t + half_penalty[half], gpr_addr, 1, is_vector, ve_wb, penalty)
                    update_resource(t, "ve", penalty, 1, mode, half, op)
                    node.issued = True
                    node.ready_time = t + ve_latency + penalty + half_penalty[half]
                    slot_used["vector"] = True
                    NodeList.remove(node)
                    print("t={}, issue ve node {} with op {} src0={} src1={} dst={} latency={} penalty={} half={}".format(t, node.index, op, src0_addr, src1_addr, gpr_addr, ve_latency, penalty, half))

            elif op in SFU_OPCODES and not slot_used["sfu"]:
                """
                if is_vector:
                    sfu_borrow = mode
                else:
                    sfu_borrow = 0

                if sfu_borrow == 1:
                    rounds = math.ceil(ve_len / (num_sfu + add_sfu_option1)) if is_vector else 1
                elif sfu_borrow == 2:
                    rounds = math.ceil(ve_len / (num_sfu + add_sfu_option2)) if is_vector else 1
                else:
                    rounds = math.ceil(ve_len / num_sfu) if is_vector else 1
                """

                if is_vector: 
                # 向量全部走简化版SFU算子。
                    if mode == 0:
                        rounds = math.ceil(ve_len / add_rqo_option0)
                    elif mode == 1:
                        rounds = math.ceil(ve_len / (add_rqo_option0 + add_rqo_option1))
                    else:
                        # mode == 2
                        rounds = math.ceil(ve_len / (add_rqo_option0 + add_rqo_option1 + add_rqo_option2))

                    can_read, penalty = check_read(t, src0_addr, 0, is_vector, 0, 1, 0)
                    if not can_read: continue

                    can_use_sfu = check_sfu_history(t, op, rounds)
                    if not can_use_sfu: continue

                    can_use_ve = check_ve_from_sfu(t, op, rounds)
                    if not can_use_ve: continue
                
                    if op == "exp":
                        can_write = check_write(t, gpr_addr, 1, is_vector, exp_wb + rounds, penalty)
                    elif op == "ln":
                        can_write = check_write(t, gpr_addr, 1, is_vector, ln_wb + rounds, penalty)
                    elif op == "sin":
                        can_write = check_write(t, gpr_addr, 1, is_vector, sin_wb + rounds, penalty)
                    elif op == "cos":
                        can_write = check_write(t, gpr_addr, 1, is_vector, cos_wb + rounds, penalty)
                    else:
                        can_write = check_write(t, gpr_addr, 1, is_vector, sfu_wb + rounds, penalty)
                    if not can_write: continue
                

                    can_write_mask = mask_tracker.check(op, is_vector)
                    if not can_write_mask: continue
                
                    slot_data["sfu"] = encode_sfu_slot(mode, gpr_addr, src0_addr, is_vector, rounds, SFU_OPCODES[op])
                    mask_tracker.update(op, is_vector, 0)
                    if op == "sqrt":
                        assert len(node.child_list) > 0 and node.child_list[0] is not None
                        mask_list.append(dag_nodes[node.child_list[0]])
                    update_read(t, src0_addr, 0, is_vector, 0, 1, 0, penalty)
                    update_resource(t, "sfu", penalty, rounds, mode, 0, op)
                    if op == 'exp':
                        update_write(t, gpr_addr, 1, is_vector, exp_wb + rounds, penalty)
                        node.ready_time = t + exp_latency + rounds + penalty
                        latency = exp_latency
                    elif op == 'ln':
                        update_write(t, gpr_addr, 1, is_vector, ln_wb + rounds, penalty)
                        node.ready_time = t + ln_latency + rounds + penalty
                        latency = ln_latency
                    elif op == 'sin':
                        update_write(t, gpr_addr, 1, is_vector, sin_wb + rounds, penalty)
                        node.ready_time = t + sin_latency + rounds + penalty
                        latency = sin_latency
                    elif op == 'cos':
                        update_write(t, gpr_addr, 1, is_vector, cos_wb + rounds, penalty)
                        node.ready_time = t + cos_latency + rounds + penalty
                        latency = cos_latency
                    else:
                        update_write(t, gpr_addr, 1, is_vector, sfu_wb + rounds, penalty)
                        node.ready_time = t + sfu_latency + rounds + penalty
                        latency = sfu_latency
                    node.issued = True
                    slot_used["sfu"] = True
                    NodeList.remove(node)
                    print("t={}, issue sfu node {} with op {} src0={} src1={} dst={} latency={} rounds={} penalty={} borrow={}".format(t, node.index, op, src0_addr, src1_addr, gpr_addr, latency + rounds, rounds, penalty, mode))

                else:
                    # 标量走标准SFU算子
                    can_read, penalty = check_read(t, src0_addr, 0, is_vector, 0, 1, 0)
                    if not can_read: continue

                    can_use_sfu = check_sfu_history_scalar(t, op)
                    if not can_use_sfu: continue

                    if op == "exp":
                        can_write = check_write(t, gpr_addr, 1, is_vector, exp_wb, penalty)
                    elif op == "ln":
                        can_write = check_write(t, gpr_addr, 1, is_vector, ln_wb, penalty)
                    elif op == "sin":
                        can_write = check_write(t, gpr_addr, 1, is_vector, sin_wb, penalty)
                    elif op == "cos":
                        can_write = check_write(t, gpr_addr, 1, is_vector, cos_wb, penalty)
                    else:
                        can_write = check_write(t, gpr_addr, 1, is_vector, sfu_wb, penalty)
                    if not can_write: continue

                    can_write_mask = mask_tracker.check(op, is_vector)
                    if not can_write_mask: continue

                    slot_data["sfu"] = encode_sfu_slot(mode, gpr_addr, src0_addr, is_vector, 0, SFU_OPCODES[op])
                    mask_tracker.update(op, is_vector, 0)
                    if op == "sqrt":
                        assert len(node.child_list) > 0 and node.child_list[0] is not None
                        mask_list.append(dag_nodes[node.child_list[0]])
                    update_read(t, src0_addr, 0, is_vector, 0, 1, 0, penalty)
                    update_resource(t, "sfu", penalty, 0, mode, 0, op)
                    if op == 'exp':
                        update_write(t, gpr_addr, 1, is_vector, exp_wb, penalty)
                        node.ready_time = t + exp_latency + penalty
                        latency = exp_latency
                    elif op == 'ln':
                        update_write(t, gpr_addr, 1, is_vector, ln_wb, penalty)
                        node.ready_time = t + ln_latency + penalty
                        latency = ln_latency
                    elif op == 'sin':
                        update_write(t, gpr_addr, 1, is_vector, sin_wb, penalty)
                        node.ready_time = t + sin_latency + penalty
                        latency = sin_latency
                    elif op == 'cos':
                        update_write(t, gpr_addr, 1, is_vector, cos_wb, penalty)
                        node.ready_time = t + cos_latency + penalty
                        latency = cos_latency
                    else:
                        update_write(t, gpr_addr, 1, is_vector, sfu_wb, penalty)
                        node.ready_time = t + sfu_latency + penalty
                        latency = sfu_latency
                    node.issued = True
                    slot_used["sfu"] = True
                    NodeList.remove(node)
                    print("t={}, issue sfu node {} with op {} src0={} src1={} dst={} latency={} rounds={} penalty={} borrow={}".format(t, node.index, op, src0_addr, src1_addr, gpr_addr, latency, 0, penalty, mode))


        # 未分配槽填充 NOP
        assert sum(slot_used.values()) <= max_issue_slots
        schedule.append([
            slot_data["load"],
            slot_data["store"],
            slot_data["vector"],
            slot_data["scalar"],
            slot_data["sfu"],  
            000, #reserved       3 bit   
            0  # EOP
        ])
        t += 1

    schedule.append([0,0,0,0,0,0,1])
    
    return schedule, ve_usage, scalar_usage, sfu_usage

# ======================== 外部调用入口函数 ========================
def run_scheduler(
    FUNCTION="softmax",
    X=32,
    Y=32,
    mode=2,
    NUM_VE=256,
    VGPR_CAP=256,
    SGPR_CAP=256,
    MASK_FIFO=8,
    add_rqo_option0=32,
    add_rqo_option1=16,
    add_rqo_option2=16,
    MAX_ISSUE_SLOTS=2,
    out_dir="./out/"     # 输出目录可外部指定
):
    """
    调度器外部调用入口函数
    参数说明：
    - FUNCTION: 调度函数类型，支持 "softmax" / "layernorm" / 激活函数名（如"gelu"）
    - X/Y: 向量维度参数
    - NUM_VE: VE数量
    - VGPR_CAP/SGPR_CAP: VGPR/SGPR容量（深度）
    - MASK_FIFO: mask-fifo深度
    - MAX_ISSUE_SLOTS: 每周期最多发射的功能槽数量
    - out_dir: 输出文件保存目录
    返回值：
    - schedule: 调度结果列表（每个周期的指令槽数据）
    - performance: 性能统计字典
    - total_cycles: 总调度周期数
    """
    # 1. 创建输出目录
    os.makedirs(out_dir, exist_ok=True)

    # 2. 构建依赖图
    dag_nodes, mapping_df, vgpr_start_addr = construct_dag(function=FUNCTION, X=X, Y=Y, NUM_VE=NUM_VE)
    relabel_dag_layers(dag_nodes)

    total_nodes = len(dag_nodes)
    print(f"Total DAG nodes: {total_nodes}")
    print(f"vgpr_start_addr = {vgpr_start_addr}")

    # 3. 分配寄存器/内存地址
    assign_register_and_memory_addresses(
        dag_nodes,
        vgpr_start_addr=vgpr_start_addr,
        sgpr_cap=SGPR_CAP,
        vgpr_cap=VGPR_CAP
    )

    # 4. 统计寄存器使用 & 计算最大活跃状态
    sgpr_count, vgpr_count = count_sgpr_vgpr_usage(dag_nodes)
    if FUNCTION.lower() not in ["softmax", "logsoftmax", "layernorm", "logsumexp"]:
        sgpr_count = 1
    print(f"sgpr_count = {sgpr_count}\tvgpr_count = {vgpr_count}")
    
    max_active_state = calculate_max_active_state(
        sgpr_count, vgpr_count,
        y=Y, num_ve=NUM_VE,
        sgpr_start_addr=0, vgpr_start_addr=vgpr_start_addr,
        sgpr_cap=SGPR_CAP, vgpr_cap=VGPR_CAP
    )

    # 5. 设置节点调度优先级
    for node in dag_nodes.values():
        vector_id = node.vector_id if node.vector_id is not None else 0
        segment_id = node.segment_id if node.segment_id is not None else 0
        node.importance = -node.index

    # 6. 输出DAG和mapping表格
    dag_df = pd.DataFrame([
        {
            "Node": node.index,
            "Operation": node.op.op_type,
            "src0": node.op.src0 if node.op.src0 is not None else "",
            "src1": node.op.src1 if node.op.src1 is not None else "",
            "Layer": node.layer,
            "Vector ID": node.vector_id if hasattr(node, "vector_id") else "",
            "Segment ID": node.segment_id if node.segment_id is not None else "",
            "Group ID": node.group_id,
            "Vector Len": node.vector_len,
            "Type": "Vector" if node.type == 1 else ("Scalar" if node.type == 0 else "None"),
            "Children": ", ".join(str(c) for c in node.child_list),
            "Wait_to_load": node.wait_to_load,
            "mask": node.mask,
            "GPR Addr": node.gpr_addr if node.gpr_addr is not None else "",
            "Mem Addr": node.op.src0 if node.op.op_type == "load" else (node.op.src1 if node.op.op_type == "store" else ""),
            "importance": node.importance
        }
        for node in dag_nodes.values()
    ])
    dag_df.to_csv(os.path.join(out_dir, "dag.csv"), index=False)
    mapping_df.to_csv(os.path.join(out_dir, "mapping_table.csv"), index=False)

    # 7. 执行调度
    schedule, ve_usage, scalar_usage, sfu_usage = schedule_dag_nodes(
        dag_nodes, max_active_state,
        num_ve=NUM_VE,
        mask_fifo=MASK_FIFO, mode=mode,
        add_rqo_option0=add_rqo_option0, add_rqo_option1=add_rqo_option1,
        add_rqo_option2=add_rqo_option2, max_issue_slots=MAX_ISSUE_SLOTS
    )

    # 8. 输出调度结果文件
    # 8.1 schedule.txt (152-bit VLIW, stored in 38 hexadecimal digits)
    with open(os.path.join(out_dir, "schedule.txt"), "w") as f:
        for row in schedule:
            slot_widths = [LOAD_STORE_SLOT_BITS, LOAD_STORE_SLOT_BITS, 34, 31, 31, 3, 1]
            bin_row = "".join(format(x, f"0{w}b") for x, w in zip(row, slot_widths))
            assert len(bin_row) == VLIW_BITS
            hex_str = hex(int(bin_row, 2))[2:].zfill((VLIW_BITS + 3) // 4)
            f.write(hex_str + "\n")

    # 8.2 各槽位的csv/txt文件
    slot_fields = {
        "slot_load.csv":     (["mem_fmt", "mem_addr", "gpr_fmt", "gpr_addr", "optype"], [2, MEM_ADDR_BITS, 2, 8, 2]),
        "slot_store.csv":    (["mem_fmt", "mem_addr", "gpr_fmt", "gpr_addr", "optype"], [2, MEM_ADDR_BITS, 2, 8, 2]),
        "slot_vector.csv":   (["half", "imm", "connect", "dst", "src1", "src0", "mask", "optype"], [2, 1, 2, 8, 8, 8, 1, 4]),
        "slot_scalar.csv":   (["imm", "connect", "dst", "src1", "src0", "mask", "optype"], [1, 1, 8, 8, 8, 1, 4]),
        "slot_sfu.csv":      (["borrow", "dst", "src", "is_vector", "rounds", "optype"], [2, 8, 8, 1, 8, 4]),
    }        
    for i, (fname, (field_names, bit_widths)) in enumerate(slot_fields.items()):
        csv_path = os.path.join(out_dir, fname)
        txt_path = os.path.join(out_dir, fname.replace(".csv", ".txt"))
        with open(csv_path, "w") as f_csv, open(txt_path, "w") as f_txt:
            f_csv.write("t," + ",".join(field_names) + "\n")
            for t, row in enumerate(schedule):
                value = row[i]
                bin_str = format(value, f"0{sum(bit_widths)}b")
                parts = []
                offset = 0
                for w in bit_widths:
                    parts.append(bin_str[offset:offset + w])
                    offset += w
                f_csv.write(f"{t},{','.join(parts)}\n")
                f_txt.write(hex(int(bin_str, 2))[2:].zfill((sum(bit_widths) + 3) // 4) + "\n")

    # 8.3 control.txt
    with open(os.path.join(out_dir, "control.txt"), "w") as f:
        for row in schedule:
            value = (row[5] << 1) | row[6]
            bin_str = format(value, "04b")
            f.write(hex(int(bin_str, 2))[2:].zfill(2) + "\n")

    # 9. 统计性能并输出performance.txt
    total_cycles = len(schedule)
    total_exec_cycles = total_cycles + 3
    inst_names = ['load', 'store', 've', 'scalar', 'sfu']
    inst_counts = {name: 0 for name in inst_names}
    # 预先计算活跃状态，方便后续统计利用率
    ve_active_count = 0
    sfu_active_count = 0
    for i, row in enumerate(schedule[:-1]):
        # 1. 统计各发射槽指令数
        if row[0]: inst_counts['load'] += 1
        if row[1]: inst_counts['store'] += 1
        if row[2]: inst_counts['ve'] += 1
        if row[3]: inst_counts['scalar'] += 1
        if row[4]: inst_counts['sfu'] += 1
        
        # 2. 统计 VE 活跃：
        # 使用当前周期索引 i 访问 usage 数组。
        # 注意：如果你的 usage 长度和 schedule 一致，直接用 i；
        # 如果考虑流水线延迟需要偏移，请确保 i+offset < len(ve_usage)
        if i+3 < len(ve_usage) and (ve_usage[i+3] != 1 or row[2]):
            ve_active_count += 1
            
        # 3. 统计 SFU 活跃：
        if i+4 < len(sfu_usage) and (sfu_usage[i+4] != -1 or row[4]):
            sfu_active_count += 1
    
    # 计算最大并发度
    max_concurrent = max(sum(1 for x in row[:5] if x) for row in schedule[:-1])
    
    # 统计 Scalar 活跃 (保持原样)
    scalar_active = sum(1 for i in range(total_cycles) if scalar_usage[i] == 0)
    
    # 计算利用率
    # 注意：如果 total_cycles 为 0 可能会报错，实际建议加个判断
    ve_util = ve_active_count / total_exec_cycles 
    scalar_util = scalar_active / total_exec_cycles
    sfu_util = sfu_active_count / total_exec_cycles 

    ve_active = sum(1 for i in range(total_cycles) if ve_usage[i] != 1)
    sfu_active = sum(1 for i in range(total_cycles) if sfu_usage[i] != -1)


    performance = {
        "total_cycles": total_cycles,
        "total_exec_cycles": total_exec_cycles,
        "inst_counts": inst_counts,
        "max_concurrent": max_concurrent,
        "ve_active": ve_active,
        "ve_utilization": ve_util,
        "scalar_active": scalar_active,
        "scalar_utilization": scalar_util,
        "sfu_active": sfu_active,
        "sfu_utilization": sfu_util
    }

    with open(os.path.join(out_dir, "performance.txt"), "w") as f:
        f.write("调度性能统计 (performance summary)\n")
        f.write(f"总周期数: {total_cycles}\n")
        f.write(f"总执行周期（总周期数+3）: {total_exec_cycles}\n")
        f.write("各类指令数:\n")
        for name in inst_names:
            f.write(f"  {name}: {inst_counts[name]}\n")
        f.write(f"最高并发数（单周期内最多的指令槽数）: {max_concurrent}\n")
        f.write("指令槽发射周期数:\n")
        f.write(f"  ve:     {inst_counts['ve']} / {total_cycles} = {(inst_counts['ve']/total_cycles):.3f}\n")
        f.write(f"  scalar: {inst_counts['scalar']} / {total_cycles} = {(inst_counts['scalar']/total_cycles):.3f}\n")
        f.write(f"  sfu:    {inst_counts['sfu']} / {total_cycles} = {(inst_counts['sfu']/total_cycles):.3f}\n")

        f.write("资源利用率：\n")
        f.write(f"ve: {ve_util:.3f}\n")
        f.write(f"scalar: {scalar_util:.3f}\n")
        f.write(f"sfu: {sfu_util:.3f}\n")


    # 10. 输出ve/sfu使用情况csv
    t_max = len(schedule) - 1
    ve_df = pd.DataFrame({
        "t": list(range(t_max)),
        "value": [ve_usage[t] for t in range(t_max)]
    })
    ve_df.to_csv(os.path.join(out_dir, "ve_usage.csv"), index=False)

    sfu_df = pd.DataFrame({
        "t": list(range(t_max)),
        "value": [sfu_usage[t] for t in range(t_max)]
    })
    sfu_df.to_csv(os.path.join(out_dir, "sfu_usage.csv"), index=False)

    print(f"调度完成，周期数 = {total_cycles}")
    print(f"统计已完成，结果已输出到 {out_dir}performance.txt")
    print(f"Saved VE usage to: {os.path.join(out_dir, 've_usage.csv')}")
    print(f"Saved SFU usage to: {os.path.join(out_dir, 'sfu_usage.csv')}")

    # 返回核心结果，方便外部调用后进一步处理
    return schedule, performance, total_exec_cycles

# ======================== 测试调用示例 ========================
if __name__ == "__main__":
    # workload修改
    schedule, perf, cycles = run_scheduler(
        FUNCTION="softmax",
        X=256,
        Y=256,
        mode=2,  # 0/1/2
        NUM_VE=256,
        VGPR_CAP=256,
        SGPR_CAP=256,
        MASK_FIFO=8,
        add_rqo_option0=32,
        add_rqo_option1=16,
        add_rqo_option2=16,
        MAX_ISSUE_SLOTS=2,
        out_dir="./out_v18_issue2/"
    )
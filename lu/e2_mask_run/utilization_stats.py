#!/usr/bin/env python3
"""Instruction validity/efficiency statistics for the 4 LU traces."""
import os, sys
sys.path.insert(0, "/Users/maghu/Desktop/work at school/compress/compress-vliw/experiments")
from lu_e2_striping_study_2026_09_18 import load_matrix, MATS

IDEAL = {"2624bomhof_1": 29027, "1041rajat04": 2738, "2395add20": 4022, "430oscil_dcop_11": 196}

for mat in MATS:
    C, cycles, _ = load_matrix(mat)
    pe = [sum(cy["op_v"]) for cy in cycles]        # active PEs per cycle (0..16)
    ad = [sum(cy["ad_v"]) for cy in cycles]        # valid addr per cycle (0..32)
    we = [sum(cy["we"]) for cy in cycles]          # writes per cycle (0..32)

    full_idle = sum(1 for cy in cycles if not any(cy["op_v"]))
    pe_slots = sum(pe)
    print(f"\n== {mat}  C={C} ==")
    print(f"  完全空闲拍(16个PE全op=0): {full_idle}/{C} = {full_idle/C:.1%}")
    print(f"  PE 槽位有效率: {pe_slots}/{16*C} = {pe_slots/(16*C):.1%}  (平均每拍 {pe_slots/C:.1f}/16 个PE活跃)")
    print(f"  addr 端口有效率: {sum(ad)}/{32*C} = {sum(ad)/(32*C):.1%}  (平均每拍 {sum(ad)/C:.1f}/32)")
    print(f"  写端口(wea)有效率: {sum(we)}/{32*C} = {sum(we)/(32*C):.1%}  (平均每拍 {sum(we)/C:.1f}/32)")
    print(f"  理论最小周期(div+ms)/16 = {IDEAL[mat]}, 实际 {C}, 调度效率 = {IDEAL[mat]/C:.1%}")

    # histogram of active PEs per cycle
    buckets = [0]*5  # 0, 1-4, 5-8, 9-12, 13-16
    for v in pe:
        if v == 0: buckets[0] += 1
        elif v <= 4: buckets[1] += 1
        elif v <= 8: buckets[2] += 1
        elif v <= 12: buckets[3] += 1
        else: buckets[4] += 1
    labels = ["0", "1-4", "5-8", "9-12", "13-16"]
    print("  每拍活跃PE数分布: " + "  ".join(f"{l}:{b/C:.0%}" for l, b in zip(labels, buckets)))

    # phase analysis: 10 equal windows
    W = 10
    print("  分阶段PE活跃率(10等分窗口):")
    line = "    "
    for w in range(W):
        seg = pe[w*C//W:(w+1)*C//W]
        line += f"W{w}:{sum(seg)/(16*len(seg)):.0%} "
    print(line)
    line = "    "
    for w in range(W):
        seg = ad[w*C//W:(w+1)*C//W]
        line += f"W{w}:{sum(seg)/(32*len(seg)):.0%} "
    print("  分阶段addr活跃率:")
    print(line)

#!/usr/bin/env bash
# BERT-pool lane-sweep regression under the UNIFORM 2048x34 payload primitive
# (fairness fix, 2026-09-16): every scheme's payload storage is built from
# 2048x34 macros with per-tile CEN gating, so a payload read costs the same
# energy in E1 / E2-2 / E2-3 / E2-4 (and E2-5, which uses native 2048x34).
#
#   scheme  top                                  payload construction
#   E1      exp1_candidate_a_pool_top_bert       5x sram_2048x34_tiled#2 (4096/bank)
#   E2-4    exp2_adaptive_4slot_pool_top_bert    4x sram_2048x34_wrapper (native)
#   E2-3    exp2_three_lane_pool_top_bert        3x sram_2048x34_tiled#2 (4096/lane)
#   E2-2    exp2_two_lane_pool_top_bert          2x sram_2048x34_tiled#2 (4096/lane)
#
# Real TSMC 28nm macro models; iverilog functional run; per-scheme bit-exact
# check (E1 -> golden_issue5.txt, E2-4 -> golden_issue4.txt,
# E2-3 -> golden_issue3.txt, E2-2 -> golden_issue2.txt); each scheme runs in
# forward AND reverse program order (out-of-order descriptor switching).
#
# Usage:  bash rtl/sim/run_bert_lane_fair.sh [e1|e2_4|e2_3|e2_2|all]
set -euo pipefail

RTL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_DIR="$(dirname "$RTL_DIR")"
WHICH="${1:-all}"

# --- pick a working iverilog/vvp (see setup_iverilog_nospace.sh) -----------
IV="${IVERILOG:-iverilog}"
VVP="${VVP:-vvp}"
if ! command -v "$IV" >/dev/null 2>&1 || \
   ! ( printf 'module t;initial $finish;endmodule' > /tmp/.ivl_probe.v && \
       "$IV" -o /tmp/.ivl_probe.vvp /tmp/.ivl_probe.v >/dev/null 2>&1 ); then
    [ -x /tmp/ivl/libexec/iverilog ] || bash "$RTL_DIR/sim/setup_iverilog_nospace.sh"
    IV=/tmp/ivl/libexec/iverilog
    VVP=/tmp/ivl/libexec/vvp
fi
rm -f /tmp/.ivl_probe.v /tmp/.ivl_probe.vvp

M_8192x5=(  "$RTL_DIR/src/ts1n28hpcphvtb8192x5m8swbasod_180a_ffg0p88v0p99v0c.v" )
M_2048x34=( "$RTL_DIR/src/ts1n28hpcphvtb2048x34m8swbasod_180a_ffg0p88v0p99v0c.v" )

SRCS_CFG=( "$RTL_DIR/src/sram_8192x5_wrapper.v" "${M_8192x5[@]}" )
SRCS_PAY=( "$RTL_DIR/src/sram_2048x34_tiled.v" "$RTL_DIR/src/sram_2048x34_wrapper.v"
           "${M_2048x34[@]}" )

run_one() {  # tag  tb_module  top_file  tb_file  golden_name  map_file  rev
    local tag="$1" tbm="$2" top="$3" tb="$4" golden="$5" map="$6" rev="$7"
    local suffix=""; [ "$rev" = "1" ] && suffix="_rev"
    "$IV" -g2012 -P "${tbm}.REV=$rev" -o "/tmp/bfair_${tag}_${rev}.vvp" \
        "$RTL_DIR/sim/$tb" "$RTL_DIR/src/$top" \
        "${SRCS_CFG[@]}" "${SRCS_PAY[@]}" "$RTL_DIR/src/sram_8192x5_tiled.v"
    ( cd "$REPO_DIR" && "$VVP" "/tmp/bfair_${tag}_${rev}.vvp" 2>&1 | grep -E "\[tb\]" || true )
    python3 "$RTL_DIR/tools/check_rtl_output.py" --pool \
        --rtl "$REPO_DIR/rtl_out_${tag}_BERT${suffix}.txt" \
        --map "$RTL_DIR/data_model_pools/BERT/${map}" \
        --data "$RTL_DIR/data_model_pools/BERT/golden" --golden-name "$golden"
    rm -f "$REPO_DIR/rtl_out_${tag}_BERT${suffix}.txt"
    rm -f "/tmp/bfair_${tag}_${rev}.vvp"
}

run_scheme() {  # tag  tb_module  top_file  tb_file  golden_name  map_file
    run_one "$1" "$2" "$3" "$4" "$5" "$6" 0
    run_one "$1" "$2" "$3" "$4" "$5" "$6" 1
}

case "$WHICH" in
    e1)
        run_scheme e1   tb_exp1_candidate_a_pool_bert \
            exp1_candidate_a_pool_top_bert.v tb_exp1_candidate_a_pool_bert.v \
            golden_issue5.txt e1_map.txt ;;
    e2_4)
        run_scheme e2   tb_exp2_pool_bert \
            exp2_adaptive_4slot_pool_top_bert.v tb_exp2_pool_bert.v \
            golden_issue4.txt e2_map.txt ;;
    e2_3)
        run_scheme e2_3 tb_exp2_three_lane_pool_bert \
            exp2_three_lane_pool_top_bert.v tb_exp2_three_lane_pool_bert.v \
            golden_issue3.txt e2_3_map.txt ;;
    e2_2)
        run_scheme e2_2 tb_exp2_two_lane_pool_bert \
            exp2_two_lane_pool_top_bert.v tb_exp2_two_lane_pool_bert.v \
            golden_issue2.txt e2_2_map.txt ;;
    all)
        run_scheme e1   tb_exp1_candidate_a_pool_bert \
            exp1_candidate_a_pool_top_bert.v tb_exp1_candidate_a_pool_bert.v \
            golden_issue5.txt e1_map.txt
        run_scheme e2   tb_exp2_pool_bert \
            exp2_adaptive_4slot_pool_top_bert.v tb_exp2_pool_bert.v \
            golden_issue4.txt e2_map.txt
        run_scheme e2_3 tb_exp2_three_lane_pool_bert \
            exp2_three_lane_pool_top_bert.v tb_exp2_three_lane_pool_bert.v \
            golden_issue3.txt e2_3_map.txt
        run_scheme e2_2 tb_exp2_two_lane_pool_bert \
            exp2_two_lane_pool_top_bert.v tb_exp2_two_lane_pool_bert.v \
            golden_issue2.txt e2_2_map.txt ;;
    *) echo "usage: $0 [e1|e2_4|e2_3|e2_2|all]" >&2; exit 1 ;;
esac

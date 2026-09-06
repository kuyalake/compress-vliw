#!/usr/bin/env bash
# E1 regression: program-pool mode, HOLD_EN=1, real TSMC 28nm macro models.
# Usage:  bash rtl/sim/run_e1.sh
#         IVERILOG=/path/to/iverilog VVP=/path/to/vvp bash rtl/sim/run_e1.sh
set -euo pipefail

RTL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
IV="${IVERILOG:-iverilog}"
VVP="${VVP:-vvp}"
MODELS=(
    "$RTL_DIR/src/ts1n28hpcphvtb8192x5m8swbasod_180a_ffg0p88v0p99v0c.v"
    "$RTL_DIR/src/ts1n28hpcphvtb2048x34m8swbasod_180a_ffg0p88v0p99v0c.v"
)

simv="/tmp/exp1_pool.vvp"
"$IV" -g2012 -o "$simv" \
    "$RTL_DIR/sim/tb_exp1_candidate_a.v" \
    "$RTL_DIR/src/exp1_candidate_a_top.v" \
    "$RTL_DIR/src/sram_8192x5_wrapper.v" \
    "$RTL_DIR/src/sram_2048x34_wrapper.v" "${MODELS[@]}"

pool_out_dir="$RTL_DIR/out/pool"
mkdir -p "$pool_out_dir"
"$VVP" "$simv" "+DATA=$RTL_DIR/data" \
    "+OUT=$pool_out_dir/rtl_out_e1_pool.txt" 2>&1 | grep -E "\[tb\]|ERROR" || true
python3 "$RTL_DIR/tools/check_rtl_output.py" --pool \
    --rtl "$pool_out_dir/rtl_out_e1_pool.txt" \
    --map "$RTL_DIR/data/e1_pool_map.txt" --data "$RTL_DIR/data"

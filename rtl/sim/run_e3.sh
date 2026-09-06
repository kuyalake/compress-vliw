#!/usr/bin/env bash
# E3 regression: program-pool mode, hold-only, real TSMC 28nm macro models.
# Usage:  bash rtl/sim/run_e3.sh
#         IVERILOG=/path/to/iverilog VVP=/path/to/vvp bash rtl/sim/run_e3.sh
set -euo pipefail

RTL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
IV="${IVERILOG:-iverilog}"
VVP="${VVP:-vvp}"
MODELS=(
    "$RTL_DIR/src/ts1n28hpcphvtb8192x5m8swbasod_180a_ffg0p88v0p99v0c.v"
    "$RTL_DIR/src/ts1n28hpcphvtb4096x34m8swbasod_180a_ffg0p88v0p99v0c.v"
)

simv="/tmp/exp3_pool.vvp"
"$IV" -g2012 -o "$simv" \
    "$RTL_DIR/sim/tb_exp3_2slot2lane.v" \
    "$RTL_DIR/src/exp3_2slot2lane_top.v" \
    "$RTL_DIR/src/cfg_pair_codebook.v" \
    "$RTL_DIR/src/sram_8192x5_wrapper.v" \
    "$RTL_DIR/src/sram_4096x34_wrapper.v" "${MODELS[@]}"

pool_out_dir="$RTL_DIR/out/pool"
mkdir -p "$pool_out_dir"
"$VVP" "$simv" "+DATA=$RTL_DIR/data" \
    "+OUT=$pool_out_dir/rtl_out_e3_pool.txt" 2>&1 | grep -E "\[tb\]|ERROR" || true
python3 "$RTL_DIR/tools/check_rtl_output.py" --pool \
    --rtl "$pool_out_dir/rtl_out_e3_pool.txt" \
    --map "$RTL_DIR/data/e3_pool_map.txt" --data "$RTL_DIR/data" \
    --golden-name golden_issue2.txt

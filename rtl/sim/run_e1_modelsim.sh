#!/usr/bin/env bash
# E1 regression under ModelSim/Questa: program-pool mode, HOLD_EN=1.
# Requires vlib/vlog/vsim and python3 on PATH.
# Usage:  bash rtl/sim/run_e1_modelsim.sh
set -euo pipefail

RTL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$RTL_DIR/out/modelsim_build_e1"
MODELS=(
    "$RTL_DIR/src/ts1n28hpcphvtb8192x5m8swbasod_180a_ffg0p88v0p99v0c.v"
    "$RTL_DIR/src/ts1n28hpcphvtb2048x34m8swbasod_180a_ffg0p88v0p99v0c.v"
)

mkdir -p "$BUILD"
cd "$BUILD"
vlib work

vlog +define+UNIT_DELAY \
    "${MODELS[@]}" \
    "$RTL_DIR/src/sram_8192x5_wrapper.v" \
    "$RTL_DIR/src/sram_2048x34_wrapper.v" \
    "$RTL_DIR/src/exp1_candidate_a_top.v" \
    "$RTL_DIR/sim/tb_exp1_candidate_a.v"

pool_out_dir="$RTL_DIR/out/pool"
mkdir -p "$pool_out_dir"
vsim -c work.tb_exp1_candidate_a \
    "+DATA=$RTL_DIR/data" \
    "+OUT=$pool_out_dir/rtl_out_e1_pool.txt" \
    -do "run -all; quit -f"
python3 "$RTL_DIR/tools/check_rtl_output.py" --pool \
    --rtl "$pool_out_dir/rtl_out_e1_pool.txt" \
    --map "$RTL_DIR/data/e1_pool_map.txt" --data "$RTL_DIR/data"

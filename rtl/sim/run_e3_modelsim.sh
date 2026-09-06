#!/usr/bin/env bash
# E3 regression under ModelSim/Questa: program-pool mode, hold-only.
# Requires vlib/vlog/vsim and python3 on PATH.
# Usage:  bash rtl/sim/run_e3_modelsim.sh
set -euo pipefail

RTL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$RTL_DIR/out/modelsim_build_e3"
MODELS=(
    "$RTL_DIR/src/ts1n28hpcphvtb8192x5m8swbasod_180a_ffg0p88v0p99v0c.v"
    "$RTL_DIR/src/ts1n28hpcphvtb4096x34m8swbasod_180a_ffg0p88v0p99v0c.v"
)

mkdir -p "$BUILD"
cd "$BUILD"
vlib work

vlog +define+UNIT_DELAY \
    "${MODELS[@]}" \
    "$RTL_DIR/src/sram_8192x5_wrapper.v" \
    "$RTL_DIR/src/sram_4096x34_wrapper.v" \
    "$RTL_DIR/src/cfg_pair_codebook.v" \
    "$RTL_DIR/src/exp3_2slot2lane_top.v" \
    "$RTL_DIR/sim/tb_exp3_2slot2lane.v"

pool_out_dir="$RTL_DIR/out/pool"
mkdir -p "$pool_out_dir"
vsim -c work.tb_exp3_2slot2lane \
    "+DATA=$RTL_DIR/data" \
    "+OUT=$pool_out_dir/rtl_out_e3_pool.txt" \
    -do "run -all; quit -f"
python3 "$RTL_DIR/tools/check_rtl_output.py" --pool \
    --rtl "$pool_out_dir/rtl_out_e3_pool.txt" \
    --map "$RTL_DIR/data/e3_pool_map.txt" --data "$RTL_DIR/data" \
    --golden-name golden_issue2.txt

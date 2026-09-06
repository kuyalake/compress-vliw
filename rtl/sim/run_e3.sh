#!/usr/bin/env bash
# E3 regression: program-pool mode, hold-only, real TSMC 28nm macro models.
# Drives the simple tb (tb_exp3_simple.v) from the repo root.
# Usage:  bash rtl/sim/run_e3.sh
#         IVERILOG=/path/to/iverilog VVP=/path/to/vvp bash rtl/sim/run_e3.sh
set -euo pipefail

RTL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_DIR="$(dirname "$RTL_DIR")"
IV="${IVERILOG:-iverilog}"
VVP="${VVP:-vvp}"
MODELS=(
    "$RTL_DIR/src/ts1n28hpcphvtb8192x5m8swbasod_180a_ffg0p88v0p99v0c.v"
    "$RTL_DIR/src/ts1n28hpcphvtb4096x34m8swbasod_180a_ffg0p88v0p99v0c.v"
)

simv="/tmp/exp3_simple.vvp"
"$IV" -g2012 -o "$simv" \
    "$RTL_DIR/sim/tb_exp3_simple.v" \
    "$RTL_DIR/src/exp3_2slot2lane_top.v" \
    "$RTL_DIR/src/cfg_pair_codebook.v" \
    "$RTL_DIR/src/sram_8192x5_wrapper.v" \
    "$RTL_DIR/src/sram_4096x34_wrapper.v" "${MODELS[@]}"

cd "$REPO_DIR"
"$VVP" "$simv" 2>&1 | grep -E "\[tb\]" || true
python3 "$RTL_DIR/tools/check_rtl_output.py" --pool \
    --rtl "$REPO_DIR/rtl_out_e3.txt" \
    --map "$RTL_DIR/data/e3_pool_map.txt" --data "$RTL_DIR/data" \
    --golden-name golden_issue2.txt
rm -f "$REPO_DIR/rtl_out_e3.txt"

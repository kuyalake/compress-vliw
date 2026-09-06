#!/usr/bin/env bash
# E0 regression: program-pool mode, hold-only, real TSMC 28nm macro models.
# Drives the simple tb (tb_exp0_simple.v) from the repo root.
# Usage:  bash rtl/sim/run_e0.sh
#         IVERILOG=/path/to/iverilog VVP=/path/to/vvp bash rtl/sim/run_e0.sh
set -euo pipefail

RTL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_DIR="$(dirname "$RTL_DIR")"
IV="${IVERILOG:-iverilog}"
VVP="${VVP:-vvp}"
MODELS=(
    "$RTL_DIR/src/ts1n28hpcphvtb8192x144m4swbasod_180a_ffg0p88v0p99v0c.v"
    "$RTL_DIR/src/ts1n28hpcphvtb8192x27m4swbasod_180a_ffg0p88v0p99v0c.v"
)

simv="/tmp/exp0_simple.vvp"
"$IV" -g2012 -o "$simv" \
    "$RTL_DIR/sim/tb_exp0_simple.v" \
    "$RTL_DIR/src/exp0_uncompressed_top.v" \
    "$RTL_DIR/src/sram_8192x171_wrapper.v" "${MODELS[@]}"

cd "$REPO_DIR"
"$VVP" "$simv" 2>&1 | grep -E "\[tb\]" || true
python3 "$RTL_DIR/tools/check_rtl_output.py" --pool \
    --rtl "$REPO_DIR/rtl_out_e0.txt" \
    --map "$RTL_DIR/data/e0_pool_map.txt" --data "$RTL_DIR/data"
rm -f "$REPO_DIR/rtl_out_e0.txt"

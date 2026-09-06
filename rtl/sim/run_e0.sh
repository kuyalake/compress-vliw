#!/usr/bin/env bash
# E0 regression: 3 cases x HOLD_EN={1,0}, real TSMC 28nm macro models.
# Usage:  bash rtl/sim/run_e0.sh
#         IVERILOG=/path/to/iverilog VVP=/path/to/vvp bash rtl/sim/run_e0.sh
set -euo pipefail

RTL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
IV="${IVERILOG:-iverilog}"
VVP="${VVP:-vvp}"
CASES=(softmax_x64 layernorm_x64 gelu_x64)
MODELS=(
    "$RTL_DIR/src/ts1n28hpcphvtb8192x144m4swbasod_180a_ffg0p88v0p99v0c.v"
    "$RTL_DIR/src/ts1n28hpcphvtb8192x27m4swbasod_180a_ffg0p88v0p99v0c.v"
)

for hold in 1 0; do
    simv="/tmp/exp0_hold${hold}.vvp"
    "$IV" -g2012 -P "tb_exp0_uncompressed.HOLD_EN=$hold" -o "$simv" \
        "$RTL_DIR/sim/tb_exp0_uncompressed.v" \
        "$RTL_DIR/src/exp0_uncompressed_top.v" \
        "$RTL_DIR/src/sram_8192x171_wrapper.v" "${MODELS[@]}"
    for case in "${CASES[@]}"; do
        mkdir -p "$RTL_DIR/out/$case"
        if [ "$hold" = "1" ]; then
            golden="$RTL_DIR/data/$case/golden_issue5.txt"; tag=e0
        else
            golden="$RTL_DIR/data/$case/golden_raw_issue5.txt"; tag=e0_raw
        fi
        "$VVP" "$simv" "+DATA=$RTL_DIR/data/$case" \
            "+OUT=$RTL_DIR/out/$case/rtl_out_${tag}.txt" 2>&1 | grep -E "\[tb\]" || true
        python3 "$RTL_DIR/tools/check_rtl_output.py" \
            --rtl "$RTL_DIR/out/$case/rtl_out_${tag}.txt" \
            --golden "$golden" --case "${case}(HOLD_EN=$hold)"
    done

    # ---- program-pool run: one image loaded once, descriptor switching ----
    pool_out_dir="$RTL_DIR/out/pool"
    mkdir -p "$pool_out_dir"
    if [ "$hold" = "1" ]; then rawflag=""; else rawflag="--raw"; fi
    "$VVP" "$simv" +POOL=1 "+DATA=$RTL_DIR/data" \
        "+OUT=$pool_out_dir/rtl_out_e0_pool_hold${hold}.txt" 2>&1 | grep -E "\[tb\]" || true
    python3 "$RTL_DIR/tools/check_rtl_output.py" --pool \
        --rtl "$pool_out_dir/rtl_out_e0_pool_hold${hold}.txt" \
        --map "$RTL_DIR/data/e0_pool_map.txt" --data "$RTL_DIR/data" $rawflag
done

#!/usr/bin/env bash
# E2 three-lane per-pool regression (supplementary lane-sweep experiment to
# E2-5; max-3 schedule, mod-3 phase striping, implicit EOP).
# Each pool has its own top + tb (per-pool macro caliber):
#   BERT    : exp2_three_lane_pool_top_bert    + sram_8192x5_wrapper + 3x sram_4096x34_wrapper
#   SD-UNet : exp2_three_lane_pool_top_sd_unet + sram_8192x5_tiled#2 + 3x sram_4096x34_tiled#2
#   LLaMA   : exp2_three_lane_pool_top_llama   + sram_32768x5_wrapper + 3x sram_16384x34_wrapper
# Real TSMC 28nm macro models; iverilog functional run; per-pool bit-exact
# check vs golden_issue3.txt (hold semantics of the max-3 schedule); each
# pool run in forward AND reverse order (out-of-order descriptor switching).
#
# Usage:  bash rtl/sim/run_e2_three_lane_pool.sh [bert|sd_unet|llama|all]
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
M_32768x5=( "$RTL_DIR/src/ts1n28hpcphvtb32768x5m16swbasod_180a_ffg0p88v0p99v0c.v" )
M_4096x34=( "$RTL_DIR/src/ts1n28hpcphvtb4096x34m8swbasod_180a_ffg0p88v0p99v0c.v" )
M_16384x34=( "$RTL_DIR/src/ts1n28hpcphvtb16384x34m8swbasod_180a_ffg0p88v0p99v0c.v" )

run_one() {  # suffix  pool_name  rev(0/1)
    local sfx="$1" pname="$2" rev="$3"
    local top="$RTL_DIR/src/exp2_three_lane_pool_top_${sfx}.v"
    local tb="$RTL_DIR/sim/tb_exp2_three_lane_pool_${sfx}.v"
    local srcs
    case "$sfx" in
        bert)
            srcs=( "$RTL_DIR/src/sram_8192x5_wrapper.v" "$RTL_DIR/src/sram_4096x34_wrapper.v"
                   "${M_8192x5[@]}" "${M_4096x34[@]}" ) ;;
        sd_unet)
            srcs=( "$RTL_DIR/src/sram_8192x5_tiled.v" "$RTL_DIR/src/sram_8192x5_wrapper.v"
                   "$RTL_DIR/src/sram_4096x34_tiled.v" "$RTL_DIR/src/sram_4096x34_wrapper.v"
                   "${M_8192x5[@]}" "${M_4096x34[@]}" ) ;;
        llama)
            srcs=( "$RTL_DIR/src/sram_32768x5_wrapper.v" "$RTL_DIR/src/sram_16384x34_wrapper.v"
                   "${M_32768x5[@]}" "${M_16384x34[@]}" ) ;;
        *) echo "unknown pool $sfx" >&2; exit 1 ;;
    esac
    local suffix=""; [ "$rev" = "1" ] && suffix="_rev"
    "$IV" -g2012 -P "tb_exp2_three_lane_pool_${sfx}.REV=$rev" -o "/tmp/e23_${sfx}_${rev}.vvp" \
        "$tb" "$top" "${srcs[@]}"
    ( cd "$REPO_DIR" && "$VVP" "/tmp/e23_${sfx}_${rev}.vvp" 2>&1 | grep -E "\[tb\]" || true )
    python3 "$RTL_DIR/tools/check_rtl_output.py" --pool \
        --rtl "$REPO_DIR/rtl_out_e2_3_${pname}${suffix}.txt" \
        --map "$RTL_DIR/data_model_pools/${pname}/e2_3_map.txt" \
        --data "$RTL_DIR/data_model_pools/${pname}/golden" --golden-name golden_issue3.txt
    rm -f "$REPO_DIR/rtl_out_e2_3_${pname}${suffix}.txt"
    rm -f "/tmp/e23_${sfx}_${rev}.vvp"
}

run_pool() {  # suffix pool_name
    run_one "$1" "$2" 0
    run_one "$1" "$2" 1
}

case "$WHICH" in
    bert)    run_pool bert    BERT ;;
    sd_unet) run_pool sd_unet SD-UNet ;;
    llama)   run_pool llama   LLaMA ;;
    all)     run_pool bert BERT; run_pool sd_unet SD-UNet; run_pool llama LLaMA ;;
    *) echo "usage: $0 [bert|sd_unet|llama|all]" >&2; exit 1 ;;
esac

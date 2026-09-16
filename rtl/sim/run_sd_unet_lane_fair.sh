#!/usr/bin/env bash
# SD-UNet-pool lane-sweep regression under the UNIFORM construction
# (fairness, 2026-09-16): every scheme uses config = sram_8192x5_tiled#2 and
# payload at the 4096x34 granule (native, or gated tiles where depth > 4096),
# so both a config read and a payload read cost the same energy in every
# scheme.  E2-4 uses implicit EOP like all other schemes (no in-band 11111).
# Each scheme has its own dedicated top + tb (no generic tops):
#
#   scheme  top                                       payload construction
#   E1      exp1_candidate_a_pool_top_sd_unet         5x sram_4096x34_tiled#2 (8192/bank)
#   E2-5    exp2_five_lane_pool_top_sd_unet           5x sram_4096x34_wrapper (native)
#   E2-4    exp2_adaptive_4slot_pool_top_sd_unet      4x sram_4096x34_wrapper (native)
#   E2-3    exp2_three_lane_pool_top_sd_unet          3x sram_4096x34_tiled#2 (8192/lane)
#   E2-2    exp2_two_lane_pool_top_sd_unet            2x sram_4096x34_tiled#2 (8192/lane)
#
# Real TSMC 28nm macro models; iverilog functional run; per-scheme bit-exact
# check (E1/E2-5 -> golden_issue5.txt, E2-4 -> golden_issue4.txt,
# E2-3 -> golden_issue3.txt, E2-2 -> golden_issue2.txt); each scheme runs in
# forward AND reverse program order (out-of-order descriptor switching).
#
# Usage:  bash rtl/sim/run_sd_unet_lane_fair.sh [e1|e2_5|e2_4|e2_3|e2_2|all]
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
M_4096x34=( "$RTL_DIR/src/ts1n28hpcphvtb4096x34m8swbasod_180a_ffg0p88v0p99v0c.v" )

SRCS=( "$RTL_DIR/src/sram_8192x5_tiled.v" "$RTL_DIR/src/sram_8192x5_wrapper.v"
       "$RTL_DIR/src/sram_4096x34_tiled.v" "$RTL_DIR/src/sram_4096x34_wrapper.v"
       "${M_8192x5[@]}" "${M_4096x34[@]}" )

run_one() {  # tag  tb_module  top_file  tb_file  golden_name  map_file  rev
    local tag="$1" tbm="$2" top="$3" tb="$4" golden="$5" map="$6" rev="$7"
    local suffix=""; [ "$rev" = "1" ] && suffix="_rev"
    "$IV" -g2012 -P "${tbm}.REV=$rev" -o "/tmp/sfair_${tag}_${rev}.vvp" \
        "$RTL_DIR/sim/$tb" "$RTL_DIR/src/$top" "${SRCS[@]}"
    ( cd "$REPO_DIR" && "$VVP" "/tmp/sfair_${tag}_${rev}.vvp" 2>&1 | grep -E "\[tb\]" || true )
    python3 "$RTL_DIR/tools/check_rtl_output.py" --pool \
        --rtl "$REPO_DIR/rtl_out_${tag}_SD-UNet${suffix}.txt" \
        --map "$RTL_DIR/data_model_pools/SD-UNet/${map}" \
        --data "$RTL_DIR/data_model_pools/SD-UNet/golden" --golden-name "$golden"
    rm -f "$REPO_DIR/rtl_out_${tag}_SD-UNet${suffix}.txt"
    rm -f "/tmp/sfair_${tag}_${rev}.vvp"
}

run_scheme() {  # tag  tb_module  top_file  tb_file  golden_name  map_file
    run_one "$1" "$2" "$3" "$4" "$5" "$6" 0
    run_one "$1" "$2" "$3" "$4" "$5" "$6" 1
}

case "$WHICH" in
    e1)
        run_scheme e1   tb_exp1_candidate_a_pool_sd_unet \
            exp1_candidate_a_pool_top_sd_unet.v tb_exp1_candidate_a_pool_sd_unet.v \
            golden_issue5.txt e1_map.txt ;;
    e2_5)
        run_scheme e2_5 tb_exp2_five_lane_pool_sd_unet \
            exp2_five_lane_pool_top_sd_unet.v tb_exp2_five_lane_pool_sd_unet.v \
            golden_issue5.txt e2_5_map.txt ;;
    e2_4)
        run_scheme e2   tb_exp2_pool_sd_unet \
            exp2_adaptive_4slot_pool_top_sd_unet.v tb_exp2_pool_sd_unet.v \
            golden_issue4.txt e2_map.txt ;;
    e2_3)
        run_scheme e2_3 tb_exp2_three_lane_pool_sd_unet \
            exp2_three_lane_pool_top_sd_unet.v tb_exp2_three_lane_pool_sd_unet.v \
            golden_issue3.txt e2_3_map.txt ;;
    e2_2)
        run_scheme e2_2 tb_exp2_two_lane_pool_sd_unet \
            exp2_two_lane_pool_top_sd_unet.v tb_exp2_two_lane_pool_sd_unet.v \
            golden_issue2.txt e2_2_map.txt ;;
    all)
        run_scheme e1   tb_exp1_candidate_a_pool_sd_unet \
            exp1_candidate_a_pool_top_sd_unet.v tb_exp1_candidate_a_pool_sd_unet.v \
            golden_issue5.txt e1_map.txt
        run_scheme e2_5 tb_exp2_five_lane_pool_sd_unet \
            exp2_five_lane_pool_top_sd_unet.v tb_exp2_five_lane_pool_sd_unet.v \
            golden_issue5.txt e2_5_map.txt
        run_scheme e2   tb_exp2_pool_sd_unet \
            exp2_adaptive_4slot_pool_top_sd_unet.v tb_exp2_pool_sd_unet.v \
            golden_issue4.txt e2_map.txt
        run_scheme e2_3 tb_exp2_three_lane_pool_sd_unet \
            exp2_three_lane_pool_top_sd_unet.v tb_exp2_three_lane_pool_sd_unet.v \
            golden_issue3.txt e2_3_map.txt
        run_scheme e2_2 tb_exp2_two_lane_pool_sd_unet \
            exp2_two_lane_pool_top_sd_unet.v tb_exp2_two_lane_pool_sd_unet.v \
            golden_issue2.txt e2_2_map.txt ;;
    *) echo "usage: $0 [e1|e2_5|e2_4|e2_3|e2_2|all]" >&2; exit 1 ;;
esac

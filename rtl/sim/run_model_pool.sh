#!/usr/bin/env bash
# Model-pool regression: 3 pools (BERT/SD-UNet/LLaMA) x 3 schemes (E0/E1/E2).
# Real TSMC 28nm macros, 1 GHz. Runs the pool tbs (tb_expN_pool.v) and checks
# with the pool checker (golden_issue5.txt for E0/E1, golden_issue4.txt for E2).
#
# Build matrix (compile-time -P params / -D defines):
#   pool    POOL_ID  E0 TILES   E1 TILES_CFG/PAY  E2 TILES_CFG/PAY  MC defines
#   BERT    0        1          1/1               1/1               (none)
#   SD-UNet 1        2          2/2               2/2               (none)
#   LLaMA   2        4          MC                MC                -DCFG_MC -DPAY_MC
#
# Usage:  bash rtl/sim/run_model_pool.sh [e0|e1|e2|all]   (default all)
#         IVERILOG=/path/iverilog VVP=/path/vvp bash rtl/sim/run_model_pool.sh
set -euo pipefail

RTL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_DIR="$(dirname "$RTL_DIR")"
IV="${IVERILOG:-iverilog}"
VVP="${VVP:-vvp}"
WHICH="${1:-all}"

M_171=( "$RTL_DIR/src/ts1n28hpcphvtb8192x144m4swbasod_180a_ffg0p88v0p99v0c.v"
        "$RTL_DIR/src/ts1n28hpcphvtb8192x27m4swbasod_180a_ffg0p88v0p99v0c.v" )
M_5=(   "$RTL_DIR/src/ts1n28hpcphvtb8192x5m8swbasod_180a_ffg0p88v0p99v0c.v" )
M_34=(  "$RTL_DIR/src/ts1n28hpcphvtb4096x34m8swbasod_180a_ffg0p88v0p99v0c.v" )
M_MC5=( "$RTL_DIR/src/ts1n28hpcphvtb32768x5m16swbasod_180a_ffg0p88v0p99v0c.v" )
M_MC34=( "$RTL_DIR/src/ts1n28hpcphvtb16384x34m8swbasod_180a_ffg0p88v0p99v0c.v" )

POOLS=( "BERT" "SD-UNet" "LLaMA" )

run_e0() {  # pid tiles name
    "$IV" -g2012 -P tb_exp0_pool.POOL_ID=$1 -P tb_exp0_pool.TILES=$2 -o /tmp/e0p_$1.vvp \
        "$RTL_DIR/sim/tb_exp0_pool.v" "$RTL_DIR/src/exp0_uncompressed_pool_top.v" \
        "$RTL_DIR/src/sram_8192x171_tiled.v" "$RTL_DIR/src/sram_8192x171_wrapper.v" "${M_171[@]}"
    ( cd "$REPO_DIR" && "$VVP" /tmp/e0p_$1.vvp 2>&1 | grep -E "\[tb\]" || true )
    python3 "$RTL_DIR/tools/check_rtl_output.py" --pool \
        --rtl "$REPO_DIR/rtl_out_e0_$3.txt" \
        --map "$RTL_DIR/data_model_pools/$3/e0_map.txt" \
        --data "$RTL_DIR/data_model_pools/$3/golden" --golden-name golden_issue5.txt
    rm -f "$REPO_DIR/rtl_out_e0_$3.txt"
}

run_e1() {  # pid tcfg tpay name mcflag
    local srcs
    if [ -n "$5" ]; then
        srcs=( "$RTL_DIR/src/sram_32768x5_wrapper.v" "$RTL_DIR/src/sram_16384x34_wrapper.v" "${M_MC5[@]}" "${M_MC34[@]}" )
    else
        srcs=( "$RTL_DIR/src/sram_8192x5_tiled.v" "$RTL_DIR/src/sram_8192x5_wrapper.v"
               "$RTL_DIR/src/sram_4096x34_tiled.v" "$RTL_DIR/src/sram_4096x34_wrapper.v"
               "${M_5[@]}" "${M_34[@]}" )
    fi
    "$IV" -g2012 $5 -P tb_exp1_pool.POOL_ID=$1 -P tb_exp1_pool.TILES_CFG=$2 -P tb_exp1_pool.TILES_PAY=$3 \
        -o /tmp/e1p_$1.vvp "$RTL_DIR/sim/tb_exp1_pool.v" "$RTL_DIR/src/exp1_candidate_a_pool_top.v" "${srcs[@]}"
    ( cd "$REPO_DIR" && "$VVP" /tmp/e1p_$1.vvp 2>&1 | grep -E "\[tb\]" || true )
    python3 "$RTL_DIR/tools/check_rtl_output.py" --pool \
        --rtl "$REPO_DIR/rtl_out_e1_$4.txt" \
        --map "$RTL_DIR/data_model_pools/$4/e1_map.txt" \
        --data "$RTL_DIR/data_model_pools/$4/golden" --golden-name golden_issue5.txt
    rm -f "$REPO_DIR/rtl_out_e1_$4.txt"
}

run_e2() {  # pid tcfg tpay name mcflag
    local srcs
    if [ -n "$5" ]; then
        srcs=( "$RTL_DIR/src/sram_32768x5_wrapper.v" "$RTL_DIR/src/sram_16384x34_wrapper.v" "${M_MC5[@]}" "${M_MC34[@]}" )
    else
        srcs=( "$RTL_DIR/src/sram_8192x5_tiled.v" "$RTL_DIR/src/sram_8192x5_wrapper.v"
               "$RTL_DIR/src/sram_4096x34_tiled.v" "$RTL_DIR/src/sram_4096x34_wrapper.v"
               "${M_5[@]}" "${M_34[@]}" )
    fi
    "$IV" -g2012 $5 -P tb_exp2_pool.POOL_ID=$1 -P tb_exp2_pool.TILES_CFG=$2 -P tb_exp2_pool.TILES_PAY=$3 \
        -o /tmp/e2p_$1.vvp "$RTL_DIR/sim/tb_exp2_pool.v" "$RTL_DIR/src/exp2_adaptive_4slot_pool_top.v" "${srcs[@]}"
    ( cd "$REPO_DIR" && "$VVP" /tmp/e2p_$1.vvp 2>&1 | grep -E "\[tb\]" || true )
    python3 "$RTL_DIR/tools/check_rtl_output.py" --pool \
        --rtl "$REPO_DIR/rtl_out_e2_$4.txt" \
        --map "$RTL_DIR/data_model_pools/$4/e2_map.txt" \
        --data "$RTL_DIR/data_model_pools/$4/golden" --golden-name golden_issue4.txt
    rm -f "$REPO_DIR/rtl_out_e2_$4.txt"
}

if [ "$WHICH" = "e0" ] || [ "$WHICH" = "all" ]; then
    run_e0 0 1 BERT; run_e0 1 2 SD-UNet; run_e0 2 4 LLaMA
fi
if [ "$WHICH" = "e1" ] || [ "$WHICH" = "all" ]; then
    run_e1 0 1 1 BERT ""; run_e1 1 2 2 SD-UNet ""; run_e1 2 0 0 LLaMA "-DCFG_MC -DPAY_MC"
fi
if [ "$WHICH" = "e2" ] || [ "$WHICH" = "all" ]; then
    run_e2 0 1 1 BERT ""; run_e2 1 2 2 SD-UNet ""; run_e2 2 0 0 LLaMA "-DCFG_MC -DPAY_MC"
fi
echo "=== model-pool regression ($WHICH) done ==="

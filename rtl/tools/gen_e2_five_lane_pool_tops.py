#!/usr/bin/env python3
"""Generate the per-pool E2 five-lane tops and testbenches.

The plan (e2_five_lane_detailed_experiment_plan_2026-09-13, Table 5) uses a
per-pool macro caliber for the per-pool PPA data points; the repo convention
is a self-contained top + tb per pool (cf. exp2_adaptive_4slot_pool_top_bert.v
/ tb_exp2_pool_bert.v).  To avoid hand-duplication drift, the three tops and
three tbs are MECHANICALLY derived here from the verified generic
exp2_five_lane_pool_top.v / tb_exp2_five_lane_pool.v by substituting only the
pool-specific parts (module name, address widths, SRAM macros, data dir).

Per-pool macro caliber (plan Table 5):
  BERT    : config 8192x5 (sram_8192x5_wrapper),        payload 5x 2048x34 (sram_2048x34_wrapper)
  SD-UNet : config 16384x5 (sram_8192x5_tiled #2),      payload 5x 4096x34 (sram_4096x34_wrapper)
  LLaMA   : config 32768x5 (sram_32768x5_wrapper),      payload 5x 8192x34 (sram_4096x34_tiled #2)

Run: python3 rtl/tools/gen_e2_five_lane_pool_tops.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "rtl" / "src"
SIM = ROOT / "rtl" / "sim"

GENERIC_TOP = SRC / "exp2_five_lane_pool_top.v"
GENERIC_TB = SIM / "tb_exp2_five_lane_pool.v"

# pool -> (suffix, CFG_AW, config_macro_inst, PAY_AW, payload_macro_inst,
#          tb CFG_DEPTH, tb LANE_DEPTH, pool_dir, pool_name)
CFG_WRAPPER = {
    "bert":    "sram_8192x5_wrapper",
    "sd_unet": "sram_8192x5_tiled",
    "llama":   "sram_32768x5_wrapper",
}
PAY_WRAPPER = {
    "bert":    "sram_2048x34_wrapper",
    "sd_unet": "sram_4096x34_wrapper",
    "llama":   "sram_4096x34_tiled",
}
POOLS = {
    "bert":    dict(CFG_AW=13, PAY_AW=11, CFG_DEPTH=8192,  LANE_DEPTH=2048,
                    pool_dir="BERT",    pool_name="BERT"),
    "sd_unet": dict(CFG_AW=14, PAY_AW=12, CFG_DEPTH=16384, LANE_DEPTH=4096,
                    pool_dir="SD-UNet", pool_name="SD-UNet"),
    "llama":   dict(CFG_AW=15, PAY_AW=13, CFG_DEPTH=32768, LANE_DEPTH=8192,
                    pool_dir="LLaMA",   pool_name="LLaMA"),
}


def gen_top(suffix, spec):
    t = GENERIC_TOP.read_text()
    cfg_aw, pay_aw = spec["CFG_AW"], spec["PAY_AW"]
    cfg_mac = CFG_WRAPPER[suffix]
    pay_mac = PAY_WRAPPER[suffix]

    # module name
    t = t.replace("module exp2_five_lane_pool_top (",
                  "module exp2_five_lane_pool_top_%s (" % suffix)
    # header comment: note the pool
    t = t.replace(
        "// E2 five-lane (model-pool): five shared payload lanes for the deep program\n"
        "// pools (BERT / SD-UNet / LLaMA), original max-5 schedule (five-slot",
        "// E2 five-lane (model-pool): five shared payload lanes for the %s pool,\n"
        "// original max-5 schedule (five-slot" % spec["pool_name"])

    # config address width
    t = t.replace(
        "    wire [14:0] cfg_addr  = load_en ? load_addr : cfg_pc;",
        "    wire [%d:0] cfg_addr  = load_en ? load_addr[%d:0] : cfg_pc[%d:0];"
        % (cfg_aw - 1, cfg_aw - 1, cfg_aw - 1))
    # lane address widths (5 lanes)
    for l in range(5):
        t = t.replace(
            "    wire [12:0] lane%d_addr = load_en ? load_addr[12:0] : ptr%d[12:0];"
            % (l, l),
            "    wire [%d:0] lane%d_addr = load_en ? load_addr[%d:0] : ptr%d[%d:0];"
            % (pay_aw - 1, l, pay_aw - 1, l, pay_aw - 1))

    # config macro
    if cfg_mac == "sram_8192x5_tiled":
        cfg_inst = ("    sram_8192x5_tiled #(.TILES(2)) u_cfg (\n"
                    "        .clk(clk), .cen(cfg_cen), .wen(cfg_wen), .addr(cfg_addr),\n"
                    "        .wdata(cfg_wdata), .wmask(cfg_wmask), .rdata(cfg_rdata)\n"
                    "    );")
    else:
        cfg_inst = ("    %s u_cfg (\n"
                    "        .clk(clk), .cen(cfg_cen), .wen(cfg_wen), .addr(cfg_addr),\n"
                    "        .wdata(cfg_wdata), .wmask(cfg_wmask), .rdata(cfg_rdata)\n"
                    "    );" % cfg_mac)
    t = t.replace(
        "    sram_32768x5_wrapper u_cfg (\n"
        "        .clk(clk), .cen(cfg_cen), .wen(cfg_wen), .addr(cfg_addr),\n"
        "        .wdata(cfg_wdata), .wmask(cfg_wmask), .rdata(cfg_rdata)\n"
        "    );",
        cfg_inst)

    # payload lane macros (5x)
    for l in range(5):
        if pay_mac == "sram_4096x34_tiled":
            old = ("    sram_4096x34_tiled #(.TILES(2)) u_lane%d (\n"
                   "        .clk(clk), .cen(lane%d_cen), .wen(lane%d_wen), .addr(lane%d_addr),\n"
                   "        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane%d_rdata));"
                   % (l, l, l, l, l))
            new = ("    sram_4096x34_tiled #(.TILES(2)) u_lane%d (\n"
                   "        .clk(clk), .cen(lane%d_cen), .wen(lane%d_wen), .addr(lane%d_addr),\n"
                   "        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane%d_rdata));"
                   % (l, l, l, l, l))
        else:
            old = ("    sram_4096x34_tiled #(.TILES(2)) u_lane%d (\n"
                   "        .clk(clk), .cen(lane%d_cen), .wen(lane%d_wen), .addr(lane%d_addr),\n"
                   "        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane%d_rdata));"
                   % (l, l, l, l, l))
            new = ("    %s u_lane%d (\n"
                   "        .clk(clk), .cen(lane%d_cen), .wen(lane%d_wen), .addr(lane%d_addr),\n"
                   "        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane%d_rdata));"
                   % (pay_mac, l, l, l, l, l))
        if old not in t:
            raise AssertionError("lane %d macro block not found" % l)
        t = t.replace(old, new)

    out = SRC / ("exp2_five_lane_pool_top_%s.v" % suffix)
    out.write_text(t)
    return out


def gen_tb(suffix, spec):
    t = GENERIC_TB.read_text()
    # module name
    t = t.replace("module tb_exp2_five_lane_pool;",
                  "module tb_exp2_five_lane_pool_%s;" % suffix)
    # drop the POOL_ID/REV parameters -> hardcode; keep REV as a plain param
    t = t.replace(
        "    parameter POOL_ID = 0;   // 0=BERT, 1=SD-UNet, 2=LLaMA\n"
        "    parameter REV     = 0;   // 1 = run programs in reverse storage order\n"
        "                             //     (out-of-order descriptor switching, plan 9.4)",
        "    parameter REV     = 0;   // 1 = run programs in reverse storage order\n"
        "                             //     (out-of-order descriptor switching, plan 9.4)")
    # memory depths
    t = t.replace("    localparam integer CFG_DEPTH     = 32768;",
                  "    localparam integer CFG_DEPTH     = %d;" % spec["CFG_DEPTH"])
    t = t.replace("    localparam integer LANE_DEPTH    = 8192;",
                  "    localparam integer LANE_DEPTH    = %d;" % spec["LANE_DEPTH"])
    # pool_dir case -> fixed
    t = t.replace(
        "        case (POOL_ID)\n"
        "            0: pool_dir = \"rtl/data_model_pools/BERT\";\n"
        "            1: pool_dir = \"rtl/data_model_pools/SD-UNet\";\n"
        "            2: pool_dir = \"rtl/data_model_pools/LLaMA\";\n"
        "            default: pool_dir = \"rtl/data_model_pools/BERT\";\n"
        "        endcase",
        "        pool_dir = \"rtl/data_model_pools/%s\";" % spec["pool_dir"])
    # output file case -> fixed
    t = t.replace(
        "        case (POOL_ID)\n"
        "            0: out_fd = $fopen(REV ? \"rtl_out_e2_5_BERT_rev.txt\"  : \"rtl_out_e2_5_BERT.txt\", \"w\");\n"
        "            1: out_fd = $fopen(REV ? \"rtl_out_e2_5_SD-UNet_rev.txt\" : \"rtl_out_e2_5_SD-UNet.txt\", \"w\");\n"
        "            2: out_fd = $fopen(REV ? \"rtl_out_e2_5_LLaMA_rev.txt\"  : \"rtl_out_e2_5_LLaMA.txt\", \"w\");\n"
        "            default: out_fd = $fopen(\"rtl_out_e2_5.txt\", \"w\");\n"
        "        endcase",
        "        out_fd = $fopen(REV ? \"rtl_out_e2_5_%s_rev.txt\" : \"rtl_out_e2_5_%s.txt\", \"w\");"
        % (spec["pool_dir"], spec["pool_dir"]))
    # DUT instantiation: module name + drop POOL_ID param
    t = t.replace("    exp2_five_lane_pool_top dut (",
                  "    exp2_five_lane_pool_top_%s dut (" % suffix)
    # the [tb] POOL id message uses POOL_ID; replace with the pool name
    t = t.replace(
        "        $display(\"[tb] E2-5 POOL id=%0d programs=%0d cfg_reads=%0d lanes=%0d/%0d/%0d/%0d/%0d errors=%0d\",\n"
        "                 POOL_ID, n_prog, cfg_reads,",
        "        $display(\"[tb] E2-5 POOL %s programs=%%0d cfg_reads=%%0d lanes=%%0d/%%0d/%%0d/%%0d/%%0d errors=%%0d\",\n"
        "                 n_prog, cfg_reads," % spec["pool_name"])
    t = t.replace(
        "            $display(\"[tb] PASS: E2-5 pool run completed, %0d programs\", n_prog);",
        "            $display(\"[tb] PASS: E2-5 pool %s run completed, %%0d programs\", n_prog);"
        % spec["pool_name"])
    t = t.replace(
        "            $display(\"[tb] FAIL: E2-5 pool run had %0d errors\", pool_errors);",
        "            $display(\"[tb] FAIL: E2-5 pool %s run had %%0d errors\", pool_errors);"
        % spec["pool_name"])

    out = SIM / ("tb_exp2_five_lane_pool_%s.v" % suffix)
    out.write_text(t)
    return out


def main():
    tops = []
    tbs = []
    for suffix, spec in POOLS.items():
        tops.append(gen_top(suffix, spec))
        tbs.append(gen_tb(suffix, spec))
        print("[gen] top %s" % tops[-1].relative_to(ROOT))
        print("[gen] tb  %s" % tbs[-1].relative_to(ROOT))
    print("[gen] done: 3 tops + 3 tbs")


if __name__ == "__main__":
    sys.exit(main())

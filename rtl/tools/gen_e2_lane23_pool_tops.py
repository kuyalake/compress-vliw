#!/usr/bin/env python3
"""Generate the per-pool E2-3 (three-lane) and E2-2 (two-lane) tops and
testbenches.

Same repo convention as gen_e2_five_lane_pool_tops.py: the per-pool tops/tbs
are MECHANICALLY derived here from the verified generic
exp2_three_lane_pool_top.v / tb_exp2_three_lane_pool.v and
exp2_two_lane_pool_top.v / tb_exp2_two_lane_pool.v by substituting only the
pool-specific parts (module name, address widths, SRAM macros, data dir).

Per-pool macro caliber (from analysis_output_e2_lane23_2026-09-16, pow2ceil of
the measured pool config entries / longest lane):

  E2-3 (max-3, three lanes, mod-3 phase):
    BERT    : config 8192x5  (sram_8192x5_wrapper),   payload 3x 4096x34  (sram_4096x34_wrapper)
    SD-UNet : config 16384x5 (sram_8192x5_tiled #2),  payload 3x 8192x34  (sram_4096x34_tiled #2)
    LLaMA   : config 32768x5 (sram_32768x5_wrapper),  payload 3x 16384x34 (sram_16384x34_wrapper)

  E2-2 (max-2, two lanes, mod-2 phase):
    BERT    : config 8192x5  (sram_8192x5_wrapper),   payload 2x 4096x34  (sram_4096x34_wrapper)
    SD-UNet : config 16384x5 (sram_8192x5_tiled #2),  payload 2x 8192x34  (sram_4096x34_tiled #2)
    LLaMA   : config 32768x5 (sram_32768x5_wrapper),  payload 2x 32768x34 (sram_16384x34_tiled #2)

Run: python3 rtl/tools/gen_e2_lane23_pool_tops.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "rtl" / "src"
SIM = ROOT / "rtl" / "sim"

# ---------------------------------------------------------------------------
# per-lane-count generic anchors
# ---------------------------------------------------------------------------

VARIANTS = {
    "three_lane": dict(
        nlanes=3, tag="e2_3", issue=3, golden="golden_issue3.txt",
        top_generic="exp2_three_lane_pool_top.v",
        tb_generic="tb_exp2_three_lane_pool.v",
        top_module="exp2_three_lane_pool_top",
        tb_module="tb_exp2_three_lane_pool",
        header_old=("// E2 three-lane (model-pool): three shared payload lanes "
                    "for the deep program\n"
                    "// pools (BERT / SD-UNet / LLaMA), max-3 schedule"),
        header_new=("// E2 three-lane (model-pool): three shared payload lanes "
                    "for the %s pool,\n// max-3 schedule"),
        cfg_macro_generic="sram_32768x5_wrapper",
        pay_macro_generic="sram_16384x34_wrapper",
        pay_tiles_generic=1,
        lane_aw_generic=14,     # generic lane addr wire width
        tb_display_old=(
            "        $display(\"[tb] E2-3 POOL id=%0d programs=%0d "
            "cfg_reads=%0d lanes=%0d/%0d/%0d errors=%0d\",\n"
            "                 POOL_ID, n_prog, cfg_reads,"),
        tb_display_new=(
            "        $display(\"[tb] E2-3 POOL %s programs=%%0d "
            "cfg_reads=%%0d lanes=%%0d/%%0d/%%0d errors=%%0d\",\n"
            "                 n_prog, cfg_reads,"),
        tb_pass_old=("            $display(\"[tb] PASS: E2-3 pool run "
                     "completed, %0d programs\", n_prog);"),
        tb_pass_new=("            $display(\"[tb] PASS: E2-3 pool %s run "
                     "completed, %%0d programs\", n_prog);"),
        tb_fail_old=("            $display(\"[tb] FAIL: E2-3 pool run had "
                     "%0d errors\", pool_errors);"),
        tb_fail_new=("            $display(\"[tb] FAIL: E2-3 pool %s run had "
                     "%%0d errors\", pool_errors);"),
    ),
    "two_lane": dict(
        nlanes=2, tag="e2_2", issue=2, golden="golden_issue2.txt",
        top_generic="exp2_two_lane_pool_top.v",
        tb_generic="tb_exp2_two_lane_pool.v",
        top_module="exp2_two_lane_pool_top",
        tb_module="tb_exp2_two_lane_pool",
        header_old=("// E2 two-lane (model-pool): two shared payload lanes "
                    "for the deep program\n"
                    "// pools (BERT / SD-UNet / LLaMA), max-2 schedule"),
        header_new=("// E2 two-lane (model-pool): two shared payload lanes "
                    "for the %s pool,\n// max-2 schedule"),
        cfg_macro_generic="sram_32768x5_wrapper",
        pay_macro_generic="sram_16384x34_tiled",
        pay_tiles_generic=2,
        lane_aw_generic=15,     # generic lane addr wire width
        tb_display_old=(
            "        $display(\"[tb] E2-2 POOL id=%0d programs=%0d "
            "cfg_reads=%0d lanes=%0d/%0d errors=%0d\",\n"
            "                 POOL_ID, n_prog, cfg_reads,"),
        tb_display_new=(
            "        $display(\"[tb] E2-2 POOL %s programs=%%0d "
            "cfg_reads=%%0d lanes=%%0d/%%0d errors=%%0d\",\n"
            "                 n_prog, cfg_reads,"),
        tb_pass_old=("            $display(\"[tb] PASS: E2-2 pool run "
                     "completed, %0d programs\", n_prog);"),
        tb_pass_new=("            $display(\"[tb] PASS: E2-2 pool %s run "
                     "completed, %%0d programs\", n_prog);"),
        tb_fail_old=("            $display(\"[tb] FAIL: E2-2 pool run had "
                     "%0d errors\", pool_errors);"),
        tb_fail_new=("            $display(\"[tb] FAIL: E2-2 pool %s run had "
                     "%%0d errors\", pool_errors);"),
    ),
}

# pool -> per-pool macro caliber
POOLS = {
    "bert":    dict(CFG_AW=13, PAY_AW=12, CFG_DEPTH=8192,  LANE_DEPTH=4096,
                    cfg_mac="sram_8192x5_wrapper", cfg_tiles=1,
                    pay_mac="sram_4096x34_wrapper", pay_tiles=1,
                    pool_dir="BERT", pool_name="BERT"),
    "sd_unet": dict(CFG_AW=14, PAY_AW=13, CFG_DEPTH=16384, LANE_DEPTH=8192,
                    cfg_mac="sram_8192x5_tiled", cfg_tiles=2,
                    pay_mac="sram_4096x34_tiled", pay_tiles=2,
                    pool_dir="SD-UNet", pool_name="SD-UNet"),
    "llama":   dict(CFG_AW=15, PAY_AW=None, CFG_DEPTH=32768, LANE_DEPTH=None,
                    cfg_mac="sram_32768x5_wrapper", cfg_tiles=1,
                    pay_mac=None, pay_tiles=None,   # same as generic
                    pool_dir="LLaMA", pool_name="LLaMA"),
}
# llama payload = generic macro of each variant (16384x34 for 3-lane,
# 16384x34_tiled#2 for 2-lane); PAY_AW/LANE_DEPTH filled per variant below.
VARIANT_LLAMA_PAY = {
    "three_lane": dict(pay_mac="sram_16384x34_wrapper", pay_tiles=1,
                       PAY_AW=14, LANE_DEPTH=16384),
    "two_lane":   dict(pay_mac="sram_16384x34_tiled", pay_tiles=2,
                       PAY_AW=15, LANE_DEPTH=32768),
}


def macro_inst(macro, tiles, name, cen, wen, addr, rdata):
    head = macro if tiles == 1 else "%s #(.TILES(%d))" % (macro, tiles)
    return ("    %s %s (\n"
            "        .clk(clk), .cen(%s), .wen(%s), .addr(%s),\n"
            "        .wdata(load_wdata), .wmask(lane_wmask), .rdata(%s));"
            % (head, name, cen, wen, addr, rdata))


def gen_top(var_key, suffix, spec):
    v = VARIANTS[var_key]
    t = (SRC / v["top_generic"]).read_text()
    nlanes = v["nlanes"]
    cfg_aw, pay_aw = spec["CFG_AW"], spec["PAY_AW"]

    # module name
    t = t.replace("module %s (" % v["top_module"],
                  "module %s_%s (" % (v["top_module"], suffix))
    # header comment: note the pool
    t = t.replace(v["header_old"], v["header_new"] % spec["pool_name"])

    # config address width
    t = t.replace(
        "    wire [14:0] cfg_addr  = load_en ? load_addr : cfg_pc;",
        "    wire [%d:0] cfg_addr  = load_en ? load_addr[%d:0] : cfg_pc[%d:0];"
        % (cfg_aw - 1, cfg_aw - 1, cfg_aw - 1))

    # lane address widths
    gaw = v["lane_aw_generic"]
    for l in range(nlanes):
        old = ("    wire [%d:0] lane%d_addr = load_en ? load_addr[%d:0] "
               ": ptr%d[%d:0];" % (gaw - 1, l, gaw - 1, l, gaw - 1))
        new = ("    wire [%d:0] lane%d_addr = load_en ? load_addr[%d:0] "
               ": ptr%d[%d:0];" % (pay_aw - 1, l, pay_aw - 1, l, pay_aw - 1))
        if old not in t:
            raise AssertionError("lane %d addr wire not found (%s %s)"
                                 % (l, var_key, suffix))
        t = t.replace(old, new)

    # config macro
    old_cfg = ("    %s u_cfg (\n"
               "        .clk(clk), .cen(cfg_cen), .wen(cfg_wen), "
               ".addr(cfg_addr),\n"
               "        .wdata(cfg_wdata), .wmask(cfg_wmask), "
               ".rdata(cfg_rdata)\n"
               "    );" % v["cfg_macro_generic"])
    cfg_head = (spec["cfg_mac"] if spec["cfg_tiles"] == 1
                else "%s #(.TILES(%d))" % (spec["cfg_mac"], spec["cfg_tiles"]))
    new_cfg = ("    %s u_cfg (\n"
               "        .clk(clk), .cen(cfg_cen), .wen(cfg_wen), "
               ".addr(cfg_addr),\n"
               "        .wdata(cfg_wdata), .wmask(cfg_wmask), "
               ".rdata(cfg_rdata)\n"
               "    );" % cfg_head)
    if old_cfg not in t:
        raise AssertionError("config macro block not found (%s %s)"
                             % (var_key, suffix))
    t = t.replace(old_cfg, new_cfg)

    # payload lane macros
    for l in range(nlanes):
        old = macro_inst(v["pay_macro_generic"], v["pay_tiles_generic"],
                         "u_lane%d" % l, "lane%d_cen" % l, "lane%d_wen" % l,
                         "lane%d_addr" % l, "lane%d_rdata" % l)
        new = macro_inst(spec["pay_mac"], spec["pay_tiles"],
                         "u_lane%d" % l, "lane%d_cen" % l, "lane%d_wen" % l,
                         "lane%d_addr" % l, "lane%d_rdata" % l)
        if old not in t:
            raise AssertionError("lane %d macro block not found (%s %s)"
                                 % (l, var_key, suffix))
        t = t.replace(old, new)

    out = SRC / ("%s_%s.v" % (v["top_module"], suffix))
    out.write_text(t)
    return out


def gen_tb(var_key, suffix, spec):
    v = VARIANTS[var_key]
    t = (SIM / v["tb_generic"]).read_text()

    # module name
    t = t.replace("module %s;" % v["tb_module"],
                  "module %s_%s;" % (v["tb_module"], suffix))
    # drop the POOL_ID parameter -> hardcode; keep REV as a plain param
    t = t.replace(
        "    parameter POOL_ID = 0;   // 0=BERT, 1=SD-UNet, 2=LLaMA\n"
        "    parameter REV     = 0;   // 1 = run programs in reverse storage order\n"
        "                             //     (out-of-order descriptor switching, plan 9.4)",
        "    parameter REV     = 0;   // 1 = run programs in reverse storage order\n"
        "                             //     (out-of-order descriptor switching, plan 9.4)")
    # memory depths
    t = t.replace("    localparam integer CFG_DEPTH     = 32768;",
                  "    localparam integer CFG_DEPTH     = %d;"
                  % spec["CFG_DEPTH"])
    t = t.replace("    localparam integer LANE_DEPTH    = %d;"
                  % VARIANT_LLAMA_PAY[var_key]["LANE_DEPTH"]
                  if var_key == "two_lane" else
                  "    localparam integer LANE_DEPTH    = 16384;",
                  "    localparam integer LANE_DEPTH    = %d;"
                  % spec["LANE_DEPTH"])
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
    tag = v["tag"]
    t = t.replace(
        "        case (POOL_ID)\n"
        "            0: out_fd = $fopen(REV ? \"rtl_out_%s_BERT_rev.txt\"  : \"rtl_out_%s_BERT.txt\", \"w\");\n"
        "            1: out_fd = $fopen(REV ? \"rtl_out_%s_SD-UNet_rev.txt\" : \"rtl_out_%s_SD-UNet.txt\", \"w\");\n"
        "            2: out_fd = $fopen(REV ? \"rtl_out_%s_LLaMA_rev.txt\"  : \"rtl_out_%s_LLaMA.txt\", \"w\");\n"
        "            default: out_fd = $fopen(\"rtl_out_%s.txt\", \"w\");\n"
        "        endcase" % (tag, tag, tag, tag, tag, tag, tag),
        "        out_fd = $fopen(REV ? \"rtl_out_%s_%s_rev.txt\" : \"rtl_out_%s_%s.txt\", \"w\");"
        % (tag, spec["pool_dir"], tag, spec["pool_dir"]))
    # DUT instantiation: module name + drop POOL_ID param
    t = t.replace("    %s dut (" % v["top_module"],
                  "    %s_%s dut (" % (v["top_module"], suffix))
    # [tb] display messages: POOL_ID -> pool name
    t = t.replace(v["tb_display_old"],
                  v["tb_display_new"] % spec["pool_name"])
    t = t.replace(v["tb_pass_old"], v["tb_pass_new"] % spec["pool_name"])
    t = t.replace(v["tb_fail_old"], v["tb_fail_new"] % spec["pool_name"])

    out = SIM / ("%s_%s.v" % (v["tb_module"], suffix))
    out.write_text(t)
    return out


def main():
    made = []
    for var_key in ("three_lane", "two_lane"):
        for suffix, spec in POOLS.items():
            spec = dict(spec)
            if spec["pay_mac"] is None:        # llama: use variant generic
                spec.update(VARIANT_LLAMA_PAY[var_key])
            made.append(gen_top(var_key, suffix, spec))
            made.append(gen_tb(var_key, suffix, spec))
            print("[gen] %s + %s" % (made[-2].relative_to(ROOT),
                                     made[-1].relative_to(ROOT)))
    print("[gen] done: %d files" % len(made))


if __name__ == "__main__":
    sys.exit(main())

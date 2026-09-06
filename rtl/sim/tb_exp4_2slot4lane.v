`timescale 1ns/1ps
`default_nettype none

// -----------------------------------------------------------------------------
// Testbench for exp4_2slot4lane_top (rtl/plan.md section 6.1) -- pool mode only
//
//   iverilog -g2012 -o simv rtl/sim/tb_exp4_2slot4lane.v \
//       rtl/src/exp4_2slot4lane_top.v rtl/src/cfg_pair_codebook.v \
//       rtl/src/sram_8192x6_wrapper.v rtl/src/sram_2048x34_wrapper.v \
//       rtl/src/ts1n28hpcphvtb8192x6m8swbasod_180a_ffg0p88v0p99v0c.v \
//       rtl/src/ts1n28hpcphvtb2048x34m8swbasod_180a_ffg0p88v0p99v0c.v
//   vvp simv +DATA=rtl/data +OUT=rtl/out/pool/rtl_out_e4_pool.txt
//
// Pool flow identical to tb_exp2_adaptive_4slot; read-count checks: config
// reads == cfg_total (incl. the EOP entry) and lane l reads == lane_totals[l].
// -----------------------------------------------------------------------------

module tb_exp4_2slot4lane;

    localparam integer CFG_DEPTH     = 8192;
    localparam integer LANE_DEPTH    = 2048;
    localparam real    CLK_PERIOD_NS = 1.000;

    reg                    clk;
    reg                    rst_n;
    reg                    load_en;
    reg  [2:0]             load_sel;
    reg  [12:0]            load_addr;
    reg  [33:0]            load_wdata;
    reg                    start;
    reg  [12:0]            cfg_base;
    reg  [13:0]            prog_len;
    reg  [10:0]            lane_base0;
    reg  [10:0]            lane_base1;
    reg  [10:0]            lane_base2;
    reg  [10:0]            lane_base3;

    wire [1:0]  load_mem_fmt;
    wire [19:0] load_mem_addr;
    wire [1:0]  load_gpr_fmt;
    wire [7:0]  load_gpr_addr;
    wire [1:0]  load_optype;
    wire [1:0]  store_mem_fmt;
    wire [19:0] store_mem_addr;
    wire [1:0]  store_gpr_fmt;
    wire [7:0]  store_gpr_addr;
    wire [1:0]  store_optype;
    wire [1:0]  vector_half;
    wire        vector_imm;
    wire [1:0]  vector_connect;
    wire [7:0]  vector_dst;
    wire [7:0]  vector_src1;
    wire [7:0]  vector_src0;
    wire        vector_mask;
    wire [3:0]  vector_optype;
    wire        scalar_imm;
    wire        scalar_connect;
    wire [7:0]  scalar_dst;
    wire [7:0]  scalar_src1;
    wire [7:0]  scalar_src0;
    wire        scalar_mask;
    wire [3:0]  scalar_optype;
    wire [1:0]  sfu_borrow;
    wire [7:0]  sfu_dst;
    wire [7:0]  sfu_src;
    wire        sfu_is_vector;
    wire [7:0]  sfu_rounds;
    wire [3:0]  sfu_optype;
    wire        slot_valid;
    wire        eop;
    wire        done;

    exp4_2slot4lane_top dut (
        .clk           (clk),
        .rst_n         (rst_n),
        .load_en       (load_en),
        .load_sel      (load_sel),
        .load_addr     (load_addr),
        .load_wdata    (load_wdata),
        .start         (start),
        .cfg_base      (cfg_base),
        .prog_len      (prog_len),
        .lane_base0    (lane_base0),
        .lane_base1    (lane_base1),
        .lane_base2    (lane_base2),
        .lane_base3    (lane_base3),
        .load_mem_fmt  (load_mem_fmt),
        .load_mem_addr (load_mem_addr),
        .load_gpr_fmt  (load_gpr_fmt),
        .load_gpr_addr (load_gpr_addr),
        .load_optype   (load_optype),
        .store_mem_fmt  (store_mem_fmt),
        .store_mem_addr (store_mem_addr),
        .store_gpr_fmt  (store_gpr_fmt),
        .store_gpr_addr (store_gpr_addr),
        .store_optype   (store_optype),
        .vector_half    (vector_half),
        .vector_imm     (vector_imm),
        .vector_connect (vector_connect),
        .vector_dst     (vector_dst),
        .vector_src1    (vector_src1),
        .vector_src0    (vector_src0),
        .vector_mask    (vector_mask),
        .vector_optype  (vector_optype),
        .scalar_imm     (scalar_imm),
        .scalar_connect (scalar_connect),
        .scalar_dst     (scalar_dst),
        .scalar_src1    (scalar_src1),
        .scalar_src0    (scalar_src0),
        .scalar_mask    (scalar_mask),
        .scalar_optype  (scalar_optype),
        .sfu_borrow     (sfu_borrow),
        .sfu_dst        (sfu_dst),
        .sfu_src        (sfu_src),
        .sfu_is_vector  (sfu_is_vector),
        .sfu_rounds     (sfu_rounds),
        .sfu_optype     (sfu_optype),
        .slot_valid     (slot_valid),
        .eop            (eop),
        .done           (done)
    );

    // ------------------------------------------------------------------
    // Container reassembly from field ports (same as tb_exp0_uncompressed)
    // ------------------------------------------------------------------
    function [33:0] pack_ls;
        input [1:0]  mem_fmt;
        input [19:0] mem_addr;
        input [1:0]  gpr_fmt;
        input [7:0]  gpr_addr;
        input [1:0]  optype;
        begin
            pack_ls = ({32'b0, mem_fmt} << 24) | ({12'b0, mem_addr} << 12)
                    | ({30'b0, gpr_fmt} << 10) | ({26'b0, gpr_addr} << 2)
                    | {32'b0, optype};
        end
    endfunction

    function [33:0] pack_vector;
        input [1:0] half;
        input       imm;
        input [1:0] connect;
        input [7:0] dst;
        input [7:0] src1;
        input [7:0] src0;
        input       mask;
        input [3:0] optype;
        begin
            pack_vector = {half, imm, connect, dst, src1, src0, mask, optype};
        end
    endfunction

    function [33:0] pack_scalar;
        input       imm;
        input       connect;
        input [7:0] dst;
        input [7:0] src1;
        input [7:0] src0;
        input       mask;
        input [3:0] optype;
        begin
            pack_scalar = {3'b000, imm, connect, dst, src1, src0, mask, optype};
        end
    endfunction

    function [33:0] pack_sfu;
        input [1:0] borrow;
        input [7:0] dst;
        input [7:0] src;
        input       is_vector;
        input [7:0] rounds;
        input [3:0] optype;
        begin
            pack_sfu = {3'b000, borrow, dst, src, is_vector, rounds, optype};
        end
    endfunction

    // ------------------------------------------------------------------
    // Clock / data / output plumbing
    // ------------------------------------------------------------------
    initial begin
        clk = 1'b0;
        forever #(CLK_PERIOD_NS/2.0) clk = ~clk;
    end

    reg  [5:0]    cfg_imem   [0:CFG_DEPTH-1];
    reg  [33:0]   lane0_imem [0:LANE_DEPTH-1];
    reg  [33:0]   lane1_imem [0:LANE_DEPTH-1];
    reg  [33:0]   lane2_imem [0:LANE_DEPTH-1];
    reg  [33:0]   lane3_imem [0:LANE_DEPTH-1];
    reg  [31:0]   pool_meta [0:63];
    reg  [1023:0] data_dir;
    reg  [1023:0] out_path;
    integer       out_fd;
    integer       i;
    integer       p;
    integer       n_prog;
    integer       cfg_total;
    integer       lane_total [0:3];
    integer       emit_count;
    integer       cfg_reads;
    integer       lane_reads [0:3];
    integer       timeout;
    integer       pool_errors;

    // energy statistics: actual macro read cycles (hierarchical probes)
    always @(posedge clk) begin
        if (rst_n && dut.cfg_cen && !dut.cfg_wen) cfg_reads = cfg_reads + 1;
        if (rst_n && dut.lane0_cen && !dut.lane0_wen) lane_reads[0] = lane_reads[0] + 1;
        if (rst_n && dut.lane1_cen && !dut.lane1_wen) lane_reads[1] = lane_reads[1] + 1;
        if (rst_n && dut.lane2_cen && !dut.lane2_wen) lane_reads[2] = lane_reads[2] + 1;
        if (rst_n && dut.lane3_cen && !dut.lane3_wen) lane_reads[3] = lane_reads[3] + 1;
    end

    // capture one output line per accepted cycle
    always @(posedge clk) begin
        if (rst_n) begin
            #0.200;
            if (slot_valid) begin
                $fdisplay(out_fd, "%09h %09h %09h %09h %09h %01h",
                    pack_ls(load_mem_fmt, load_mem_addr, load_gpr_fmt,
                            load_gpr_addr, load_optype),
                    pack_ls(store_mem_fmt, store_mem_addr, store_gpr_fmt,
                            store_gpr_addr, store_optype),
                    pack_vector(vector_half, vector_imm, vector_connect,
                                vector_dst, vector_src1, vector_src0,
                                vector_mask, vector_optype),
                    pack_scalar(scalar_imm, scalar_connect, scalar_dst,
                                scalar_src1, scalar_src0, scalar_mask,
                                scalar_optype),
                    pack_sfu(sfu_borrow, sfu_dst, sfu_src, sfu_is_vector,
                             sfu_rounds, sfu_optype),
                    eop);
                emit_count = emit_count + 1;
            end
        end
    end

    // ------------------------------------------------------------------
    // helper tasks
    // ------------------------------------------------------------------
    task do_reset;
        begin
            rst_n = 1'b0;
            start = 1'b0;
            repeat (4) @(posedge clk);
            @(negedge clk);
            rst_n = 1'b1;
            @(negedge clk);
        end
    endtask

    task do_load_macro;
        input [2:0]   sel;
        input integer n;
        begin
            for (i = 0; i < n; i = i + 1) begin
                load_en    = 1'b1;
                load_sel   = sel;
                load_addr  = i[12:0];
                case (sel)
                    3'd0: load_wdata = {28'b0, cfg_imem[i]};
                    3'd1: load_wdata = lane0_imem[i];
                    3'd2: load_wdata = lane1_imem[i];
                    3'd3: load_wdata = lane2_imem[i];
                    3'd4: load_wdata = lane3_imem[i];
                    default: load_wdata = 34'b0;
                endcase
                @(negedge clk);
            end
        end
    endtask

    task do_run_one;
        input integer meta_idx;
        integer len;
        begin
            cfg_base   = pool_meta[meta_idx][12:0];
            prog_len   = pool_meta[meta_idx + 1][13:0];
            lane_base0 = pool_meta[meta_idx + 2][10:0];
            lane_base1 = pool_meta[meta_idx + 3][10:0];
            lane_base2 = pool_meta[meta_idx + 4][10:0];
            lane_base3 = pool_meta[meta_idx + 5][10:0];
            len        = pool_meta[meta_idx + 1];
            emit_count = 0;
            @(negedge clk);
            start = 1'b1;
            @(negedge clk);
            start = 1'b0;
            timeout = 10 * len + 1000;
            while (!done && timeout > 0) begin
                @(negedge clk);
                timeout = timeout - 1;
            end
            if (!done) begin
                $display("ERROR: watchdog timeout, done not asserted");
                $fdisplay(out_fd, "# ERROR: watchdog timeout");
                pool_errors = pool_errors + 1;
            end
            @(negedge clk);
            if (emit_count != len) begin
                $display("ERROR: emitted %0d cycles, expected %0d", emit_count, len);
                pool_errors = pool_errors + 1;
            end
        end
    endtask

    // ------------------------------------------------------------------
    // main flow (pool mode)
    // ------------------------------------------------------------------
    initial begin
        if (!$value$plusargs("DATA=%s", data_dir)) begin
            $display("ERROR: missing +DATA=<dir> plusarg");
            $finish;
        end
        if (!$value$plusargs("OUT=%s", out_path)) begin
            $display("ERROR: missing +OUT=<path> plusarg");
            $finish;
        end

        emit_count  = 0;
        cfg_reads   = 0;
        lane_reads[0] = 0; lane_reads[1] = 0;
        lane_reads[2] = 0; lane_reads[3] = 0;
        pool_errors = 0;
        rst_n       = 1'b0;
        load_en     = 1'b0;
        load_sel    = 3'd0;
        load_addr   = 13'd0;
        load_wdata  = 34'd0;
        start       = 1'b0;
        cfg_base    = 13'd0;
        prog_len    = 14'd0;
        lane_base0  = 11'd0; lane_base1 = 11'd0;
        lane_base2  = 11'd0; lane_base3 = 11'd0;

        out_fd = $fopen(out_path, "w");
        if (out_fd == 0) begin
            $display("ERROR: cannot open %0s", out_path);
            $finish;
        end

        // ---- read pool meta and images ----
        $readmemh({data_dir, "/e4_pool_meta.hex"}, pool_meta);
        n_prog        = pool_meta[0];
        cfg_total     = pool_meta[1];
        lane_total[0] = pool_meta[2];
        lane_total[1] = pool_meta[3];
        lane_total[2] = pool_meta[4];
        lane_total[3] = pool_meta[5];
        $readmemh({data_dir, "/e4_pool_config6.memh"}, cfg_imem, 0, cfg_total-1);
        $readmemh({data_dir, "/e4_pool_lane0.memh"}, lane0_imem, 0, lane_total[0]-1);
        $readmemh({data_dir, "/e4_pool_lane1.memh"}, lane1_imem, 0, lane_total[1]-1);
        $readmemh({data_dir, "/e4_pool_lane2.memh"}, lane2_imem, 0, lane_total[2]-1);
        $readmemh({data_dir, "/e4_pool_lane3.memh"}, lane3_imem, 0, lane_total[3]-1);

        // ---- load all five macros once ----
        do_reset;
        do_load_macro(3'd0, cfg_total);
        do_load_macro(3'd1, lane_total[0]);
        do_load_macro(3'd2, lane_total[1]);
        do_load_macro(3'd3, lane_total[2]);
        do_load_macro(3'd4, lane_total[3]);
        load_en = 1'b0;

        // ---- run programs one by one ----
        for (p = 0; p < n_prog; p = p + 1) begin
            $fdisplay(out_fd, "# prog %0d", p);
            do_reset;
            do_run_one(6 + 6 * p);
        end

        // ---- exact-gating read-count checks ----
        if (cfg_reads != cfg_total) begin
            $display("ERROR: config reads %0d != cfg_total %0d", cfg_reads, cfg_total);
            pool_errors = pool_errors + 1;
        end
        for (p = 0; p < 4; p = p + 1) begin
            if (lane_reads[p] != lane_total[p]) begin
                $display("ERROR: lane %0d reads %0d != total %0d",
                         p, lane_reads[p], lane_total[p]);
                pool_errors = pool_errors + 1;
            end
        end

        $fclose(out_fd);
        $display("[tb] E4 POOL programs=%0d cfg_reads=%0d lane_reads=%0d/%0d/%0d/%0d errors=%0d",
                 n_prog, cfg_reads,
                 lane_reads[0], lane_reads[1], lane_reads[2], lane_reads[3],
                 pool_errors);
        if (pool_errors == 0) begin
            $display("[tb] PASS: E4 pool run completed, %0d programs", n_prog);
        end else begin
            $display("[tb] FAIL: E4 pool run had %0d errors", pool_errors);
        end
        $finish;
    end

endmodule

`default_nettype wire

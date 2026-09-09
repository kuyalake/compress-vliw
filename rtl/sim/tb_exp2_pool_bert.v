`timescale 1ns/1ps
`default_nettype none

// -----------------------------------------------------------------------------
// E2 BERT-pool tb for exp2_adaptive_4slot_pool_top_bert.
//   Reads rtl/data_model_pools/BERT/e2_*.memh by default and writes
//   rtl_out_e2_BERT.txt with "# prog <k>" segment markers.
//   Use +pool_dir=<path> when running from a directory without rtl/.
// -----------------------------------------------------------------------------

module tb_exp2_pool_bert;

    localparam integer CFG_DEPTH     = 8192;
    localparam integer LANE_DEPTH    = 2048;
    localparam real    CLK_PERIOD_NS = 1.000;

    reg                    clk;
    reg                    rst_n;
    reg                    load_en;
    reg  [2:0]             load_sel;
    reg  [14:0]            load_addr;
    reg  [33:0]            load_wdata;
    reg                    start;
    reg  [14:0]            cfg_base;
    reg  [14:0]            prog_len;
    reg  [13:0]            lane_base0;
    reg  [13:0]            lane_base1;
    reg  [13:0]            lane_base2;
    reg  [13:0]            lane_base3;

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

    exp2_adaptive_4slot_pool_top_bert #(.TILES_CFG(1), .TILES_PAY(1)) dut (
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

    initial begin
        clk = 1'b0;
        forever #(CLK_PERIOD_NS/2.0) clk = ~clk;
    end

    reg  [4:0]    cfg_imem   [0:CFG_DEPTH-1];
    reg  [33:0]   lane0_imem [0:LANE_DEPTH-1];
    reg  [33:0]   lane1_imem [0:LANE_DEPTH-1];
    reg  [33:0]   lane2_imem [0:LANE_DEPTH-1];
    reg  [33:0]   lane3_imem [0:LANE_DEPTH-1];
    reg  [31:0]   pool_meta [0:63];
    reg  [1023:0] pool_dir;
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

    always @(posedge clk) begin
        if (rst_n && dut.cfg_cen && !dut.cfg_wen) cfg_reads = cfg_reads + 1;
        if (rst_n && dut.lane0_cen && !dut.lane0_wen) lane_reads[0] = lane_reads[0] + 1;
        if (rst_n && dut.lane1_cen && !dut.lane1_wen) lane_reads[1] = lane_reads[1] + 1;
        if (rst_n && dut.lane2_cen && !dut.lane2_wen) lane_reads[2] = lane_reads[2] + 1;
        if (rst_n && dut.lane3_cen && !dut.lane3_wen) lane_reads[3] = lane_reads[3] + 1;
    end

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
                load_addr  = i[14:0];
                case (sel)
                    3'd0: load_wdata = {29'b0, cfg_imem[i]};
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

    initial begin
        if (!$value$plusargs("pool_dir=%s", pool_dir)) begin
            pool_dir = "rtl/data_model_pools/BERT";
        end

        $readmemh({pool_dir, "/e2_meta.hex"}, pool_meta);
        n_prog        = pool_meta[0];
        cfg_total     = pool_meta[1];
        lane_total[0] = pool_meta[2];
        lane_total[1] = pool_meta[3];
        lane_total[2] = pool_meta[4];
        lane_total[3] = pool_meta[5];

        if (cfg_total > CFG_DEPTH) begin
            $display("ERROR: BERT config depth %0d exceeds CFG_DEPTH %0d", cfg_total, CFG_DEPTH);
            $finish;
        end
        for (p = 0; p < 4; p = p + 1) begin
            if (lane_total[p] > LANE_DEPTH) begin
                $display("ERROR: BERT lane %0d depth %0d exceeds LANE_DEPTH %0d",
                         p, lane_total[p], LANE_DEPTH);
                $finish;
            end
        end

        $readmemh({pool_dir, "/e2_config5.memh"}, cfg_imem, 0, cfg_total-1);
        $readmemh({pool_dir, "/e2_lane0.memh"}, lane0_imem, 0, lane_total[0]-1);
        $readmemh({pool_dir, "/e2_lane1.memh"}, lane1_imem, 0, lane_total[1]-1);
        $readmemh({pool_dir, "/e2_lane2.memh"}, lane2_imem, 0, lane_total[2]-1);
        $readmemh({pool_dir, "/e2_lane3.memh"}, lane3_imem, 0, lane_total[3]-1);

        out_fd = $fopen("rtl_out_e2_BERT.txt", "w");
        if (out_fd == 0) begin
            $display("ERROR: cannot open rtl_out_e2_BERT.txt");
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
        load_addr   = 15'd0;
        load_wdata  = 34'd0;
        start       = 1'b0;
        cfg_base    = 15'd0;
        prog_len    = 15'd0;
        lane_base0  = 14'd0; lane_base1 = 14'd0;
        lane_base2  = 14'd0; lane_base3 = 14'd0;

        do_reset;
        do_load_macro(3'd0, cfg_total);
        do_load_macro(3'd1, lane_total[0]);
        do_load_macro(3'd2, lane_total[1]);
        do_load_macro(3'd3, lane_total[2]);
        do_load_macro(3'd4, lane_total[3]);
        load_en = 1'b0;

        for (p = 0; p < n_prog; p = p + 1) begin
            $fdisplay(out_fd, "# prog %0d", p);
            do_reset;
            cfg_base   = pool_meta[6 + 6*p][14:0];
            prog_len   = pool_meta[6 + 6*p + 1][14:0];
            lane_base0 = pool_meta[6 + 6*p + 2][13:0];
            lane_base1 = pool_meta[6 + 6*p + 3][13:0];
            lane_base2 = pool_meta[6 + 6*p + 4][13:0];
            lane_base3 = pool_meta[6 + 6*p + 5][13:0];
            emit_count = 0;
            @(negedge clk);
            start = 1'b1;
            @(negedge clk);
            start = 1'b0;
            timeout = 10 * prog_len + 1000;
            while (!done && timeout > 0) begin
                @(negedge clk);
                timeout = timeout - 1;
            end
            @(negedge clk);
            if (!done) begin
                $display("ERROR: prog %0d watchdog timeout", p);
                pool_errors = pool_errors + 1;
            end
            if (emit_count != prog_len) begin
                $display("ERROR: prog %0d emitted %0d, expected %0d",
                         p, emit_count, prog_len);
                pool_errors = pool_errors + 1;
            end
        end

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
        $display("[tb] E2 BERT POOL programs=%0d cfg_reads=%0d lanes=%0d/%0d/%0d/%0d errors=%0d",
                 n_prog, cfg_reads,
                 lane_reads[0], lane_reads[1], lane_reads[2], lane_reads[3],
                 pool_errors);
        if (pool_errors == 0) begin
            $display("[tb] PASS: E2 BERT pool run completed, %0d programs", n_prog);
        end else begin
            $display("[tb] FAIL: E2 BERT pool run had %0d errors", pool_errors);
        end
        $finish;
    end

endmodule

`default_nettype wire

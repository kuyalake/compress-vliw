`timescale 1ns/1ps
`default_nettype none

// 最简 E3 testbench（2slot2lane，程序池模式，相对路径，无 plusarg）。
// 当前目录 = 仓库根。读 rtl/data/e3_pool_*.memh，结果写当前目录 rtl_out_e3.txt。
// 整池一次装入 3 个宏（config + 2 Lane），逐程序复位前端、按描述符切换。
module tb_exp3_simple;

    localparam integer CFG_DEPTH     = 8192;
    localparam integer LANE_DEPTH    = 4096;
    localparam real    CLK_PERIOD_NS = 1.000;

    reg                    clk;
    reg                    rst_n;
    reg                    load_en;
    reg  [1:0]             load_sel;
    reg  [12:0]            load_addr;
    reg  [33:0]            load_wdata;
    reg                    start;
    reg  [12:0]            cfg_base;
    reg  [13:0]            prog_len;
    reg  [11:0]            lane_base0;
    reg  [11:0]            lane_base1;

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

    exp3_2slot2lane_top dut (
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
    reg  [31:0]   pool_meta [0:63];
    integer       out_fd;
    integer       i;
    integer       p;
    integer       n_prog;
    integer       cfg_total;
    integer       lane_total [0:1];
    integer       emit_count;
    integer       cfg_reads;
    integer       lane_reads [0:1];
    integer       timeout;
    integer       pool_errors;

    always @(posedge clk) begin
        if (rst_n && dut.cfg_cen && !dut.cfg_wen) cfg_reads = cfg_reads + 1;
        if (rst_n && dut.lane0_cen && !dut.lane0_wen) lane_reads[0] = lane_reads[0] + 1;
        if (rst_n && dut.lane1_cen && !dut.lane1_wen) lane_reads[1] = lane_reads[1] + 1;
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
        input [1:0]   sel;
        input integer n;
        begin
            for (i = 0; i < n; i = i + 1) begin
                load_en    = 1'b1;
                load_sel   = sel;
                load_addr  = i[12:0];
                case (sel)
                    2'd0: load_wdata = {29'b0, cfg_imem[i]};
                    2'd1: load_wdata = lane0_imem[i];
                    2'd2: load_wdata = lane1_imem[i];
                    default: load_wdata = 34'b0;
                endcase
                @(negedge clk);
            end
        end
    endtask

    initial begin
        // 相对仓库根目录读池数据
        $readmemh("rtl/data/e3_pool_meta.hex", pool_meta);
        n_prog        = pool_meta[0];
        cfg_total     = pool_meta[1];
        lane_total[0] = pool_meta[2];
        lane_total[1] = pool_meta[3];
        $readmemh("rtl/data/e3_pool_config5.memh", cfg_imem, 0, cfg_total-1);
        $readmemh("rtl/data/e3_pool_lane0.memh", lane0_imem, 0, lane_total[0]-1);
        $readmemh("rtl/data/e3_pool_lane1.memh", lane1_imem, 0, lane_total[1]-1);

        out_fd = $fopen("rtl_out_e3.txt", "w");
        if (out_fd == 0) begin
            $display("ERROR: cannot open rtl_out_e3.txt");
            $finish;
        end

        emit_count  = 0;
        cfg_reads   = 0;
        lane_reads[0] = 0; lane_reads[1] = 0;
        pool_errors = 0;
        rst_n       = 1'b0;
        load_en     = 1'b0;
        load_sel    = 2'd0;
        load_addr   = 13'd0;
        load_wdata  = 34'd0;
        start       = 1'b0;
        cfg_base    = 13'd0;
        prog_len    = 14'd0;
        lane_base0  = 12'd0; lane_base1 = 12'd0;

        // 整池一次装入 3 个宏
        do_reset;
        do_load_macro(2'd0, cfg_total);
        do_load_macro(2'd1, lane_total[0]);
        do_load_macro(2'd2, lane_total[1]);
        load_en = 1'b0;

        // 逐程序切换运行
        for (p = 0; p < n_prog; p = p + 1) begin
            $fdisplay(out_fd, "# prog %0d", p);
            do_reset;
            cfg_base   = pool_meta[4 + 4*p][12:0];
            prog_len   = pool_meta[4 + 4*p + 1][13:0];
            lane_base0 = pool_meta[4 + 4*p + 2][11:0];
            lane_base1 = pool_meta[4 + 4*p + 3][11:0];
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

        // 精确门控读次数校验
        if (cfg_reads != cfg_total) begin
            $display("ERROR: config reads %0d != cfg_total %0d", cfg_reads, cfg_total);
            pool_errors = pool_errors + 1;
        end
        for (p = 0; p < 2; p = p + 1) begin
            if (lane_reads[p] != lane_total[p]) begin
                $display("ERROR: lane %0d reads %0d != total %0d",
                         p, lane_reads[p], lane_total[p]);
                pool_errors = pool_errors + 1;
            end
        end

        $fclose(out_fd);
        $display("[tb] E3 POOL programs=%0d cfg_reads=%0d lane_reads=%0d/%0d errors=%0d",
                 n_prog, cfg_reads, lane_reads[0], lane_reads[1], pool_errors);
        if (pool_errors == 0) begin
            $display("[tb] PASS: E3 pool run completed, %0d programs", n_prog);
        end else begin
            $display("[tb] FAIL: E3 pool run had %0d errors", pool_errors);
        end
        $finish;
    end

endmodule

`default_nettype wire

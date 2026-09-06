`timescale 1ns/1ps
`default_nettype none

// -----------------------------------------------------------------------------
// Testbench for exp0_uncompressed_top (rtl/plan.md section 6.1)
//
//   iverilog ... -o simv rtl/sim/tb_exp0_uncompressed.v \
//       rtl/src/exp0_uncompressed_top.v rtl/src/sram_8192x171_wrapper.v \
//       rtl/src/ts1n28hpcphvtb8192x144m4swbasod_180a_ffg0p88v0p99v0c.v \
//       rtl/src/ts1n28hpcphvtb8192x27m4swbasod_180a_ffg0p88v0p99v0c.v
//   vvp simv +DATA=rtl/data/softmax_x64 +OUT=rtl/out/softmax_x64/rtl_out_e0.txt
//
// Flow: reset -> load the 171-bit image through the DUT load port -> start ->
// every slot_valid cycle reassemble the five 34-bit containers from the field
// outputs and append them (hex) to the output file -> expect eop/done.
// -----------------------------------------------------------------------------

module tb_exp0_uncompressed;

    // override at compile time: iverilog -P tb_exp0_uncompressed.HOLD_EN=0
    parameter HOLD_EN = 1;

    localparam integer ADDR_WIDTH    = 13;
    localparam integer DATA_WIDTH    = 171;
    localparam integer DEPTH         = 8192;
    localparam real    CLK_PERIOD_NS = 1.000;

    reg                    clk;
    reg                    rst_n;
    reg                    load_en;
    reg  [ADDR_WIDTH-1:0]  load_addr;
    reg  [DATA_WIDTH-1:0]  load_wdata;
    reg                    start;
    reg  [12:0]            prog_base;
    reg  [13:0]            prog_len;

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

    exp0_uncompressed_top #(.HOLD_EN(HOLD_EN)) dut (
        .clk           (clk),
        .rst_n         (rst_n),
        .load_en       (load_en),
        .load_addr     (load_addr),
        .load_wdata    (load_wdata),
        .start         (start),
        .prog_base     (prog_base),
        .prog_len      (prog_len),
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
    // Container reassembly from field ports (must match the encoder and
    // the golden generator in gen_rtl_streams.py).
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

    reg  [DATA_WIDTH-1:0] imem [0:DEPTH-1];
    reg  [31:0]           meta [0:0];
    reg  [31:0]           pool_meta [0:15];
    reg  [1023:0]         data_dir;
    reg  [1023:0]         out_path;
    integer               out_fd;
    integer               i;
    integer               p;
    integer               n_prog;
    integer               total_words;
    integer               prog_cycles;
    integer               emit_count;
    integer               read_cycles;
    integer               timeout;
    integer               pool_mode;
    integer               pool_errors;

    // energy statistic: count actual macro read cycles (hierarchical probe)
    always @(posedge clk) begin
        if (rst_n && dut.mem_cen && !dut.mem_wen) begin
            read_cycles = read_cycles + 1;
        end
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

    task do_load;
        input integer n;
        begin
            for (i = 0; i < n; i = i + 1) begin
                load_en    = 1'b1;
                load_addr  = i[ADDR_WIDTH-1:0];
                load_wdata = imem[i];
                @(negedge clk);
            end
            load_en    = 1'b0;
            load_addr  = {ADDR_WIDTH{1'b0}};
            load_wdata = {DATA_WIDTH{1'b0}};
        end
    endtask

    task do_run_one;
        input [12:0] base;
        input [13:0] len;
        begin
            emit_count = 0;
            prog_base  = base;
            prog_len   = len;
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
    // main flow: single-program mode (default) or program-pool mode (+POOL=1)
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
        if (!$value$plusargs("POOL=%d", pool_mode)) begin
            pool_mode = 0;
        end

        emit_count  = 0;
        read_cycles = 0;
        pool_errors = 0;
        rst_n       = 1'b0;
        load_en     = 1'b0;
        load_addr   = {ADDR_WIDTH{1'b0}};
        load_wdata  = {DATA_WIDTH{1'b0}};
        start       = 1'b0;
        prog_base   = 13'd0;
        prog_len    = 14'd0;

        out_fd = $fopen(out_path, "w");
        if (out_fd == 0) begin
            $display("ERROR: cannot open %0s", out_path);
            $finish;
        end

        if (pool_mode) begin
            // ---- program pool: load once, then run program by program ----
            $readmemh({data_dir, "/e0_pool_meta.hex"}, pool_meta);
            n_prog      = pool_meta[0];
            total_words = pool_meta[1];
            $readmemh({data_dir, "/e0_pool_instr171.memh"}, imem, 0, total_words-1);
            do_reset;
            do_load(total_words);
            for (p = 0; p < n_prog; p = p + 1) begin
                $fdisplay(out_fd, "# prog %0d", p);
                // reset the front-end between programs; the macro keeps its
                // contents (it has no reset), so the pool stays resident.
                do_reset;
                do_run_one(pool_meta[2 + 2*p], pool_meta[3 + 2*p]);
            end
            $fclose(out_fd);
            $display("[tb] POOL programs=%0d total_words=%0d macro_read_cycles=%0d errors=%0d",
                     n_prog, total_words, read_cycles, pool_errors);
            if (pool_errors == 0) begin
                $display("[tb] PASS: pool run completed, %0d programs", n_prog);
            end else begin
                $display("[tb] FAIL: pool run had %0d errors", pool_errors);
            end
        end else begin
            // ---- single program at base 0 ----
            $readmemh({data_dir, "/e0_meta.hex"}, meta);
            prog_cycles = meta[0];
            $readmemh({data_dir, "/e0_instr171.memh"}, imem, 0, prog_cycles-1);
            do_reset;
            do_load(prog_cycles);
            do_run_one(13'd0, prog_cycles[13:0]);
            $fclose(out_fd);
            $display("[tb] case data=%0s T=%0d emitted=%0d macro_read_cycles=%0d done=%0b",
                     data_dir, prog_cycles, emit_count, read_cycles, done);
            if (pool_errors == 0) begin
                $display("[tb] PASS: emitted %0d cycles (expected %0d)",
                         emit_count, prog_cycles);
            end else begin
                $display("[tb] FAIL: pool_errors=%0d", pool_errors);
            end
        end
        $finish;
    end

endmodule

`default_nettype wire

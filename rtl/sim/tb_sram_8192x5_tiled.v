`timescale 1ns/1ps
`default_nettype none

// -----------------------------------------------------------------------------
// Unit tb for sram_8192x5_tiled (depth-tiled config SRAM).
// Covers (plan_sram_tiled_wrapper_2026-09-08.md section 5):
//   1. full-depth write then continuous per-cycle read-back (no bubble/dup/drop);
//   2. directed bursts across every tile boundary (8191->8192, ...);
//   3. gating assertion: at most one tile CEN active per read;
//   4. a read sequence ending exactly at a tile boundary (EOP-at-boundary).
// TILES is overridden at compile time (iverilog -P tb_sram_8192x5_tiled.TILES=4).
// -----------------------------------------------------------------------------

module tb_sram_8192x5_tiled;

    parameter TILES = 2;
    localparam integer BASE_AW    = 13;
    localparam integer DW         = 5;
    localparam integer BASE_DEPTH = 8192;
    localparam integer DEPTH      = BASE_DEPTH * TILES;
    localparam integer ADDR_W     = BASE_AW + ((TILES == 4) ? 2 : (TILES == 2) ? 1 : 0);
    localparam real    CLK_PERIOD_NS = 1.000;

    reg                clk;
    reg                rst_n;
    reg                in_valid;
    reg                in_write;
    reg  [ADDR_W-1:0]  in_addr;
    reg  [DW-1:0]      in_wdata;
    wire [DW-1:0]      rdata;

    integer errors;
    integer read_checks;
    integer gating_errors;

    sram_8192x5_tiled #(.TILES(TILES)) dut (
        .clk   (clk),
        .cen   (in_valid),
        .wen   (in_write),
        .addr  (in_addr),
        .wdata (in_wdata),
        .wmask ({DW{1'b1}}),
        .rdata (rdata)
    );

    initial begin
        clk = 1'b0;
        forever #(CLK_PERIOD_NS/2.0) clk = ~clk;
    end

    reg [DW-1:0] expected_mem [0:DEPTH-1];

    function [DW-1:0] data_pattern;
        input integer a;
        begin
            // addr-dependent, fits in DW bits
            data_pattern = (a * 3 + (a / 7)) & {DW{1'b1}};
        end
    endfunction

    // 1-cycle read-latency expectation (registered at the read-sample posedge)
    reg            exp_vld;
    reg [DW-1:0]   exp_data;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            exp_vld  <= 1'b0;
            exp_data <= {DW{1'b0}};
        end else begin
            exp_vld  <= in_valid & ~in_write;
            exp_data <= expected_mem[in_addr];
        end
    end

    // check rdata mid-cycle after the read (rdata stable through the cycle)
    always @(negedge clk) begin
        if (rst_n && exp_vld) begin
            if (rdata !== exp_data) begin
                $display("[%0t] ERROR: read exp=%h got=%h", $time, exp_data, rdata);
                errors = errors + 1;
            end
            read_checks = read_checks + 1;
        end
    end

    // gating assertion: at most one tile CEN active per read.
    // generate-guarded so scope references resolve for every TILES value.
    integer active_cen;
    generate
    if (TILES == 1) begin : g_g1
        always @(posedge clk) begin
            if (rst_n && in_valid && !in_write) begin
                active_cen = dut.g_tile[0].cen_i ? 1 : 0;
                if (active_cen != 1) begin
                    $display("[%0t] ERROR: gating violation, active=%0d", $time, active_cen);
                    gating_errors = gating_errors + 1;
                end
            end
        end
    end else if (TILES == 2) begin : g_g2
        always @(posedge clk) begin
            if (rst_n && in_valid && !in_write) begin
                active_cen = (dut.g_tile[0].cen_i ? 1 : 0)
                           + (dut.g_tile[1].cen_i ? 1 : 0);
                if (active_cen != 1) begin
                    $display("[%0t] ERROR: gating violation, active=%0d", $time, active_cen);
                    gating_errors = gating_errors + 1;
                end
            end
        end
    end else begin : g_g4
        always @(posedge clk) begin
            if (rst_n && in_valid && !in_write) begin
                active_cen = (dut.g_tile[0].cen_i ? 1 : 0)
                           + (dut.g_tile[1].cen_i ? 1 : 0)
                           + (dut.g_tile[2].cen_i ? 1 : 0)
                           + (dut.g_tile[3].cen_i ? 1 : 0);
                if (active_cen != 1) begin
                    $display("[%0t] ERROR: gating violation, active=%0d", $time, active_cen);
                    gating_errors = gating_errors + 1;
                end
            end
        end
    end
    endgenerate

    task drive_idle;
        begin
            in_valid = 1'b0;
            in_write = 1'b0;
            in_addr  = {ADDR_W{1'b0}};
            in_wdata = {DW{1'b0}};
        end
    endtask

    task drive_write;
        input integer addr;
        begin
            in_valid = 1'b1;
            in_write = 1'b1;
            in_addr  = addr[ADDR_W-1:0];
            in_wdata = expected_mem[addr];
        end
    endtask

    task drive_read;
        input integer addr;
        begin
            in_valid = 1'b1;
            in_write = 1'b0;
            in_addr  = addr[ADDR_W-1:0];
            in_wdata = {DW{1'b0}};
        end
    endtask

    integer i;
    integer b;

    initial begin
        errors = 0;
        read_checks = 0;
        gating_errors = 0;
        rst_n = 1'b0;
        drive_idle;
        for (i = 0; i < DEPTH; i = i + 1) begin
            expected_mem[i] = data_pattern(i);
        end

        repeat (4) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        // ---- phase 1: fill the whole depth ----
        @(negedge clk);
        for (i = 0; i < DEPTH; i = i + 1) begin
            drive_write(i);
            @(negedge clk);
        end
        drive_idle;
        repeat (3) @(posedge clk);

        // ---- phase 2: continuous per-cycle read-back of the whole depth ----
        @(negedge clk);
        for (i = 0; i < DEPTH; i = i + 1) begin
            drive_read(i);
            @(negedge clk);
        end
        drive_idle;
        repeat (3) @(posedge clk);

        // ---- phase 3: directed bursts across each tile boundary ----
        for (b = 1; b < TILES; b = b + 1) begin
            // read [base-2 .. base+1] straddling the boundary at b*BASE_DEPTH
            @(negedge clk);
            for (i = b * BASE_DEPTH - 2; i <= b * BASE_DEPTH + 1; i = i + 1) begin
                drive_read(i);
                @(negedge clk);
            end
            drive_idle;
            repeat (2) @(posedge clk);
        end

        // ---- phase 4: a read sequence ending exactly at a tile boundary ----
        @(negedge clk);
        for (i = BASE_DEPTH - 2; i <= BASE_DEPTH - 1; i = i + 1) begin
            drive_read(i);
            @(negedge clk);
        end
        drive_idle;  // stop right at the boundary (EOP-like)
        repeat (3) @(posedge clk);

        if (errors == 0 && gating_errors == 0 &&
            read_checks == (DEPTH + 4 * (TILES - 1) + 2)) begin
            $display("SRAM 8192x5 tiled (TILES=%0d, depth=%0d) PASSED at 1GHz. reads=%0d",
                     TILES, DEPTH, read_checks);
        end else begin
            $display("SRAM 8192x5 tiled (TILES=%0d) FAILED: errors=%0d gating_errors=%0d reads=%0d",
                     TILES, errors, gating_errors, read_checks);
        end
        $finish;
    end

endmodule

`default_nettype wire

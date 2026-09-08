`timescale 1ns/1ps
`default_nettype none

// -----------------------------------------------------------------------------
// Depth-tiled config SRAM: TILES x sram_8192x5_wrapper -> 5-bit x (8192*TILES)
// (rtl/plan_sram_tiled_wrapper_2026-09-08.md section 4)
//
//   addr high bit(s) -> chip-select decode -> only the selected tile's CEN is
//                       enabled (single-tile gating, for dynamic power);
//   addr low bits    -> all tiles' address port;
//   addr high, registered at the read-issue edge (sel_q) -> output MUX select
//                       (delayed chip-select, aligned with the sync read data;
//                       adds NO extra read-latency stage, II=1 unchanged);
//   TILES=4 output   -> balanced two-level 2:1 tree (NOT a priority chain).
//
// The base wrapper (with the TSMC macro inside) is instantiated directly, so
// synthesis treats it as a hard macro and does not flatten it.
// -----------------------------------------------------------------------------

module sram_8192x5_tiled #(
    parameter TILES  = 2,   // 1, 2, or 4
    parameter ADDR_W = 13 + ((TILES == 4) ? 2 : (TILES == 2) ? 1 : 0),
    parameter SEL_W  = (TILES == 4) ? 2 : 1
) (
    input  wire              clk,
    input  wire              cen,
    input  wire              wen,
    input  wire [ADDR_W-1:0] addr,
    input  wire [4:0]        wdata,
    input  wire [4:0]        wmask,
    output wire [4:0]        rdata
);

    localparam integer BASE_AW = 13;

    wire [BASE_AW-1:0] addr_lo = addr[BASE_AW-1:0];
    wire [SEL_W-1:0]   addr_hi;
    // TILES=1 has no tile-select bits; guard the part-select so it is never
    // elaborated into an invalid (reversed) range.
    generate
    if (TILES == 1) begin : g_hi1
        assign addr_hi = {SEL_W{1'b0}};
    end else begin : g_hiN
        assign addr_hi = addr[ADDR_W-1:BASE_AW];
    end
    endgenerate

    // delayed chip-select: capture the tile index when a read is issued
    reg  [SEL_W-1:0] sel_q;
    always @(posedge clk) begin
        if (cen & ~wen) begin
            sel_q <= addr_hi;
        end
    end

    // TILES base macros, each gated to read/write only when selected
    wire [TILES*5-1:0] tq;

    genvar gi;
    generate
        for (gi = 0; gi < TILES; gi = gi + 1) begin : g_tile
            wire cen_i = cen & (addr_hi == gi[SEL_W-1:0]);
            wire wen_i = wen & (addr_hi == gi[SEL_W-1:0]);
            sram_8192x5_wrapper u_tile (
                .clk   (clk),
                .cen   (cen_i),
                .wen   (wen_i),
                .addr  (addr_lo),
                .wdata (wdata),
                .wmask (wmask),
                .rdata (tq[(gi+1)*5-1 : gi*5])
            );
        end
    endgenerate

    // output mux
    generate
        if (TILES == 1) begin : g_mux1
            assign rdata = tq[4:0];
        end else if (TILES == 2) begin : g_mux2
            assign rdata = sel_q[0] ? tq[9:5] : tq[4:0];
        end else begin : g_mux4
            // balanced two-level 2:1 tree
            wire [4:0] lo = sel_q[0] ? tq[9:5]   : tq[4:0];
            wire [4:0] hi = sel_q[0] ? tq[19:15] : tq[14:10];
            assign rdata = sel_q[1] ? hi : lo;
        end
    endgenerate

endmodule

`default_nettype wire

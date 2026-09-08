`timescale 1ns/1ps
`default_nettype none

// -----------------------------------------------------------------------------
// Depth-tiled payload SRAM: TILES x sram_4096x34_wrapper -> 34-bit x (4096*TILES)
// (rtl/plan_sram_tiled_wrapper_2026-09-08.md section 4)
//
// Same structure as sram_8192x5_tiled: single-tile CEN gating, delayed
// chip-select (sel_q) for the output mux, balanced two-level 2:1 tree for
// TILES=4. No extra read-latency stage; II=1 unchanged.
// -----------------------------------------------------------------------------

module sram_4096x34_tiled #(
    parameter TILES  = 2,   // 1, 2, or 4
    parameter ADDR_W = 12 + ((TILES == 4) ? 2 : (TILES == 2) ? 1 : 0),
    parameter SEL_W  = (TILES == 4) ? 2 : 1
) (
    input  wire              clk,
    input  wire              cen,
    input  wire              wen,
    input  wire [ADDR_W-1:0] addr,
    input  wire [33:0]       wdata,
    input  wire [33:0]       wmask,
    output wire [33:0]       rdata
);

    localparam integer BASE_AW = 12;

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
    wire [TILES*34-1:0] tq;

    genvar gi;
    generate
        for (gi = 0; gi < TILES; gi = gi + 1) begin : g_tile
            wire cen_i = cen & (addr_hi == gi[SEL_W-1:0]);
            wire wen_i = wen & (addr_hi == gi[SEL_W-1:0]);
            sram_4096x34_wrapper u_tile (
                .clk   (clk),
                .cen   (cen_i),
                .wen   (wen_i),
                .addr  (addr_lo),
                .wdata (wdata),
                .wmask (wmask),
                .rdata (tq[(gi+1)*34-1 : gi*34])
            );
        end
    endgenerate

    // output mux
    generate
        if (TILES == 1) begin : g_mux1
            assign rdata = tq[33:0];
        end else if (TILES == 2) begin : g_mux2
            assign rdata = sel_q[0] ? tq[67:34] : tq[33:0];
        end else begin : g_mux4
            // balanced two-level 2:1 tree
            wire [33:0] lo = sel_q[0] ? tq[67:34]   : tq[33:0];
            wire [33:0] hi = sel_q[0] ? tq[135:102] : tq[101:68];
            assign rdata = sel_q[1] ? hi : lo;
        end
    endgenerate

endmodule

`default_nettype wire

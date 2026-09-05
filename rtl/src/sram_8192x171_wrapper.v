`timescale 1ns/1ps
`default_nettype none

module sram_8192x171_wrapper (
    input  wire         clk,
    input  wire         cen,
    input  wire         wen,
    input  wire [12:0]  addr,
    input  wire [170:0] wdata,
    input  wire [170:0] wmask,
    output wire [170:0] rdata
);

    wire         ceb      = ~cen;
    wire         web      = ~(cen & wen);
    wire [143:0] bweb_lo  = (cen & wen) ? ~wmask[143:0]   : {144{1'b1}};
    wire [26:0]  bweb_hi  = (cen & wen) ? ~wmask[170:144] : {27{1'b1}};
    wire [143:0] rdata_lo;
    wire [26:0]  rdata_hi;

    assign rdata[143:0]   = rdata_lo;
    assign rdata[170:144] = rdata_hi;

    TS1N28HPCPHVTB8192X144M4SWBASOD u_sram_lo (
        .SLP   (1'b0),
        .SD    (1'b0),
        .CLK   (clk),
        .CEB   (ceb),
        .WEB   (web),
        .CEBM  (1'b1),
        .WEBM  (1'b1),
        .AWT   (1'b0),
        .A     (addr),
        .D     (wdata[143:0]),
        .BWEB  (bweb_lo),
        .AM    ({13{1'b0}}),
        .DM    ({144{1'b0}}),
        .BWEBM ({144{1'b1}}),
        .BIST  (1'b0),
        .Q     (rdata_lo)
    );

    TS1N28HPCPHVTB8192X27M4SWBASOD u_sram_hi (
        .SLP   (1'b0),
        .SD    (1'b0),
        .CLK   (clk),
        .CEB   (ceb),
        .WEB   (web),
        .CEBM  (1'b1),
        .WEBM  (1'b1),
        .AWT   (1'b0),
        .A     (addr),
        .D     (wdata[170:144]),
        .BWEB  (bweb_hi),
        .AM    ({13{1'b0}}),
        .DM    ({27{1'b0}}),
        .BWEBM ({27{1'b1}}),
        .BIST  (1'b0),
        .Q     (rdata_hi)
    );

endmodule

`default_nettype wire

`timescale 1ns/1ps
`default_nettype none

module sram_8192x5_wrapper (
    input  wire        clk,
    input  wire        cen,
    input  wire        wen,
    input  wire [12:0] addr,
    input  wire [4:0]  wdata,
    input  wire [4:0]  wmask,
    output wire [4:0]  rdata
);

    wire        ceb  = ~cen;
    wire        web  = ~(cen & wen);
    wire [4:0]  bweb = (cen & wen) ? ~wmask : 5'b11111;

    TS1N28HPCPHVTB8192X5M8SWBASOD u_sram (
        .SLP   (1'b0),
        .SD    (1'b0),
        .CLK   (clk),
        .CEB   (ceb),
        .WEB   (web),
        .CEBM  (1'b1),
        .WEBM  (1'b1),
        .AWT   (1'b0),
        .A     (addr),
        .D     (wdata),
        .BWEB  (bweb),
        .AM    (13'b0),
        .DM    (5'b0),
        .BWEBM (5'b11111),
        .BIST  (1'b0),
        .Q     (rdata)
    );

endmodule

`default_nettype wire

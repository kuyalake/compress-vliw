`timescale 1ns/1ps
`default_nettype none

module sram_8192x6_timing_check (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        in_valid,
    input  wire        in_write,
    input  wire [12:0] in_addr,
    input  wire [5:0]  in_wdata,
    input  wire [5:0]  in_wmask,
    output reg         out_valid,
    output reg  [5:0]  out_rdata
);

    reg        mem_cen_q;
    reg        mem_wen_q;
    reg [12:0] mem_addr_q;
    reg [5:0]  mem_wdata_q;
    reg [5:0]  mem_wmask_q;
    reg        read_return_q;

    wire       mem_cen;
    wire       mem_wen;
    wire [12:0] mem_addr;
    wire [5:0]  mem_wdata;
    wire [5:0]  mem_wmask;
    wire [5:0]  mem_rdata;

`ifdef SRAM_TIMING_SIM_INPUT_DELAY
    assign #0.080 mem_cen   = mem_cen_q;
    assign #0.080 mem_wen   = mem_wen_q;
    assign #0.080 mem_addr  = mem_addr_q;
    assign #0.080 mem_wdata = mem_wdata_q;
    assign #0.080 mem_wmask = mem_wmask_q;
`else
    assign mem_cen   = mem_cen_q;
    assign mem_wen   = mem_wen_q;
    assign mem_addr  = mem_addr_q;
    assign mem_wdata = mem_wdata_q;
    assign mem_wmask = mem_wmask_q;
`endif

    sram_8192x6_wrapper u_mem (
        .clk   (clk),
        .cen   (mem_cen),
        .wen   (mem_wen),
        .addr  (mem_addr),
        .wdata (mem_wdata),
        .wmask (mem_wmask),
        .rdata (mem_rdata)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            mem_cen_q     <= 1'b0;
            mem_wen_q     <= 1'b0;
            mem_addr_q    <= 13'b0;
            mem_wdata_q   <= 6'b0;
            mem_wmask_q   <= 6'b0;
            read_return_q <= 1'b0;
            out_valid     <= 1'b0;
            out_rdata     <= 6'b0;
        end else begin
            mem_cen_q     <= in_valid;
            mem_wen_q     <= in_write;
            mem_addr_q    <= in_addr;
            mem_wdata_q   <= in_wdata;
            mem_wmask_q   <= in_wmask;
            read_return_q <= mem_cen_q & ~mem_wen_q;
            out_valid     <= read_return_q;
            out_rdata     <= mem_rdata;
        end
    end

endmodule

`default_nettype wire

`timescale 1ns/1ps
`default_nettype none

module tb_sram_8192x5_timing_check;

    localparam real CLK_PERIOD_NS = 1.000;
    localparam integer BURST_BASE = 32;
    localparam integer BURST_LEN  = 16;

    reg        clk;
    reg        rst_n;
    reg        in_valid;
    reg        in_write;
    reg [12:0] in_addr;
    reg [4:0]  in_wdata;
    reg [4:0]  in_wmask;
    wire       out_valid;
    wire [4:0] out_rdata;

    integer errors;
    integer read_checks;
    reg [4:0] expected_mem [0:8191];
    reg       exp_vld_0;
    reg       exp_vld_1;
    reg       exp_vld_2;
    reg [4:0] exp_data_0;
    reg [4:0] exp_data_1;
    reg [4:0] exp_data_2;

    sram_8192x5_timing_check dut (
        .clk       (clk),
        .rst_n     (rst_n),
        .in_valid  (in_valid),
        .in_write  (in_write),
        .in_addr   (in_addr),
        .in_wdata  (in_wdata),
        .in_wmask  (in_wmask),
        .out_valid (out_valid),
        .out_rdata (out_rdata)
    );

    initial begin
        clk = 1'b0;
        forever #(CLK_PERIOD_NS/2.0) clk = ~clk;
    end

    initial begin
        $dumpfile("sram_8192x5_timing_check.vcd");
        $dumpvars(0, tb_sram_8192x5_timing_check);
    end

    task init_expected;
        integer i;
        begin
            for (i = 0; i < 8192; i = i + 1) begin
                expected_mem[i] = 5'bxxxxx;
            end
        end
    endtask

    function [4:0] data_pattern;
        input integer index;
        begin
            data_pattern = (index * 5 + 3);
        end
    endfunction

    task drive_idle;
        begin
            in_valid = 1'b0;
            in_write = 1'b0;
            in_addr  = 13'b0;
            in_wdata = 5'b0;
            in_wmask = 5'b0;
        end
    endtask

    task drive_write;
        input [12:0] addr;
        input [4:0]  data;
        input [4:0]  mask;
        begin
            in_valid = 1'b1;
            in_write = 1'b1;
            in_addr  = addr;
            in_wdata = data;
            in_wmask = mask;
            expected_mem[addr] = (expected_mem[addr] & ~mask) | (data & mask);
        end
    endtask

    task drive_read;
        input [12:0] addr;
        begin
            in_valid = 1'b1;
            in_write = 1'b0;
            in_addr  = addr;
            in_wdata = 5'b0;
            in_wmask = 5'b0;
        end
    endtask

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            exp_vld_0  <= 1'b0;
            exp_vld_1  <= 1'b0;
            exp_vld_2  <= 1'b0;
            exp_data_0 <= 5'b0;
            exp_data_1 <= 5'b0;
            exp_data_2 <= 5'b0;
        end else begin
            exp_vld_0  <= in_valid & ~in_write;
            exp_vld_1  <= exp_vld_0;
            exp_vld_2  <= exp_vld_1;
            exp_data_0 <= expected_mem[in_addr];
            exp_data_1 <= exp_data_0;
            exp_data_2 <= exp_data_1;
        end
    end

    always @(posedge clk) begin
        if (rst_n) begin
            #0.200;
            if (exp_vld_2) begin
                if (out_valid !== 1'b1) begin
                    $display("[%0t] ERROR: out_valid is low during burst read", $time);
                    errors = errors + 1;
                end
                if (out_rdata !== exp_data_2) begin
                    $display("[%0t] ERROR: burst read exp=%b got=%b", $time, exp_data_2, out_rdata);
                    errors = errors + 1;
                end else begin
                    $display("[%0t] PASS: burst read data=%b", $time, out_rdata);
                end
                read_checks = read_checks + 1;
            end
        end
    end

    initial begin
        integer i;

        errors = 0;
        read_checks = 0;
        rst_n = 1'b0;
        drive_idle;
        init_expected;

        repeat (4) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        @(negedge clk);
        $display("Start continuous write burst: in_valid/cen stays high for %0d cycles", BURST_LEN);
        for (i = 0; i < BURST_LEN; i = i + 1) begin
            drive_write(BURST_BASE + i, data_pattern(i), 5'b11111);
            @(negedge clk);
        end

        $display("One idle cycle between write burst and read burst");
        drive_idle;
        @(negedge clk);

        $display("Start continuous read burst: in_valid/cen stays high for %0d cycles", BURST_LEN);
        for (i = 0; i < BURST_LEN; i = i + 1) begin
            drive_read(BURST_BASE + i);
            @(negedge clk);
        end

        drive_idle;
        repeat (5) @(posedge clk);
        if (errors == 0 && read_checks == BURST_LEN) begin
            $display("SRAM 8192x5 continuous-burst simulation PASSED at 1GHz.");
        end else begin
            $display("SRAM 8192x5 continuous-burst simulation FAILED, errors=%0d read_checks=%0d.", errors, read_checks);
        end
        $finish;
    end

endmodule

`default_nettype wire

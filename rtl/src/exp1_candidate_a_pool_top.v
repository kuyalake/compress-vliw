`timescale 1ns/1ps
`default_nettype none

// -----------------------------------------------------------------------------
// E1 (model-pool): Candidate A instruction supply for the deep program pools
// (BERT / SD-UNet / LLaMA).
//
// Same fetch/decode/hold logic as exp1_candidate_a_top, with pool-depth SRAM:
//   config : `ifdef CFG_MC` MC sram_32768x5_wrapper (LLaMA), else
//            sram_8192x5_tiled #(TILES_CFG)  (BERT=1, SD-UNet=2)
//   payload: `ifdef PAY_MC` MC sram_16384x34_wrapper (LLaMA), else
//            5x sram_4096x34_tiled #(TILES_PAY)  (BERT=1, SD-UNet=2)
//
// Implicit EOP via the program-length counter (mask=11111 is legal data).
// Hold-only output stage. No backpressure. II=1, 3-cycle latency.
// -----------------------------------------------------------------------------

module exp1_candidate_a_pool_top #(
    parameter TILES_CFG = 1,   // config tiles (tiled caliber): BERT=1, SD-UNet=2
    parameter TILES_PAY = 1    // payload tiles (tiled caliber): BERT=1, SD-UNet=2
) (
    input  wire         clk,
    input  wire         rst_n,
    // load port: load_sel 0 = config macro, 1..5 = payload bank slot 0..4
    input  wire         load_en,
    input  wire [2:0]   load_sel,
    input  wire [14:0]  load_addr,
    input  wire [33:0]  load_wdata,
    // run control: program descriptor
    input  wire         start,
    input  wire [14:0]  cfg_base,
    input  wire [14:0]  prog_len,     // total cycles T (incl. the EOP cycle)
    input  wire [13:0]  slot_base0,
    input  wire [13:0]  slot_base1,
    input  wire [13:0]  slot_base2,
    input  wire [13:0]  slot_base3,
    input  wire [13:0]  slot_base4,
    // LOAD slot fields
    output reg  [1:0]   load_mem_fmt,
    output reg  [19:0]  load_mem_addr,
    output reg  [1:0]   load_gpr_fmt,
    output reg  [7:0]   load_gpr_addr,
    output reg  [1:0]   load_optype,
    // STORE slot fields
    output reg  [1:0]   store_mem_fmt,
    output reg  [19:0]  store_mem_addr,
    output reg  [1:0]   store_gpr_fmt,
    output reg  [7:0]   store_gpr_addr,
    output reg  [1:0]   store_optype,
    // VECTOR slot fields
    output reg  [1:0]   vector_half,
    output reg          vector_imm,
    output reg  [1:0]   vector_connect,
    output reg  [7:0]   vector_dst,
    output reg  [7:0]   vector_src1,
    output reg  [7:0]   vector_src0,
    output reg          vector_mask,
    output reg  [3:0]   vector_optype,
    // SCALAR slot fields
    output reg          scalar_imm,
    output reg          scalar_connect,
    output reg  [7:0]   scalar_dst,
    output reg  [7:0]   scalar_src1,
    output reg  [7:0]   scalar_src0,
    output reg          scalar_mask,
    output reg  [3:0]   scalar_optype,
    // SFU slot fields
    output reg  [1:0]   sfu_borrow,
    output reg  [7:0]   sfu_dst,
    output reg  [7:0]   sfu_src,
    output reg          sfu_is_vector,
    output reg  [7:0]   sfu_rounds,
    output reg  [3:0]   sfu_optype,
    // control
    output reg          slot_valid,
    output reg          eop,
    output reg          done
);

    // config / payload SRAM address widths (match the chosen wrapper)
`ifdef CFG_MC
    localparam integer CFG_AW = 15;
`else
    localparam integer CFG_AW = 13 + ((TILES_CFG == 4) ? 2 : (TILES_CFG == 2) ? 1 : 0);
`endif
`ifdef PAY_MC
    localparam integer PAY_AW = 14;
`else
    localparam integer PAY_AW = 12 + ((TILES_PAY == 4) ? 2 : (TILES_PAY == 2) ? 1 : 0);
`endif

    // ------------------------------------------------------------------
    // Stage A: config fetch issue + descriptor state
    // ------------------------------------------------------------------
    reg         run_q;
    reg  [14:0] cfg_pc;
    reg  [14:0] cfg_cnt;
    reg         eop_inj;
    reg  [14:0] len_q;
    reg         b_vld;
    reg         b_eop;

    wire        cfg_cen_f = run_q & (cfg_cnt < len_q - 15'd1);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            run_q    <= 1'b0;
            cfg_pc   <= 15'd0;
            cfg_cnt  <= 15'd0;
            eop_inj  <= 1'b0;
            len_q    <= 15'd0;
            b_vld    <= 1'b0;
            b_eop    <= 1'b0;
        end else if (load_en) begin
            b_vld    <= 1'b0;
            b_eop    <= 1'b0;
        end else if (start) begin
            run_q    <= 1'b1;
            cfg_pc   <= cfg_base;
            cfg_cnt  <= 15'd0;
            eop_inj  <= 1'b0;
            len_q    <= prog_len;
            b_vld    <= 1'b0;
            b_eop    <= 1'b0;
        end else if (run_q) begin
            if (cfg_cnt < len_q - 15'd1) begin
                cfg_pc  <= cfg_pc + 15'd1;
                cfg_cnt <= cfg_cnt + 15'd1;
                b_vld   <= 1'b1;
                b_eop   <= 1'b0;
            end else if (!eop_inj) begin
                eop_inj <= 1'b1;            // EOP marker: no config read
                b_vld   <= 1'b1;
                b_eop   <= 1'b1;
                run_q   <= 1'b0;
            end
        end else begin
            b_vld <= 1'b0;
            b_eop <= 1'b0;
        end
    end

    // ------------------------------------------------------------------
    // Stage B: mask -> payload bank enables (exact gating) + pointer advance
    // ------------------------------------------------------------------
    reg  [13:0] ptr0, ptr1, ptr2, ptr3, ptr4;
    reg         c_vld;
    reg         c_eop;
    reg  [4:0]  mask_c;

    wire [4:0]  cfg_rdata;
    wire        pay_rd0 = b_vld & ~b_eop & cfg_rdata[0];
    wire        pay_rd1 = b_vld & ~b_eop & cfg_rdata[1];
    wire        pay_rd2 = b_vld & ~b_eop & cfg_rdata[2];
    wire        pay_rd3 = b_vld & ~b_eop & cfg_rdata[3];
    wire        pay_rd4 = b_vld & ~b_eop & cfg_rdata[4];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ptr0 <= 14'd0; ptr1 <= 14'd0; ptr2 <= 14'd0;
            ptr3 <= 14'd0; ptr4 <= 14'd0;
            c_vld  <= 1'b0; c_eop <= 1'b0; mask_c <= 5'b0;
        end else if (start) begin
            ptr0 <= slot_base0; ptr1 <= slot_base1; ptr2 <= slot_base2;
            ptr3 <= slot_base3; ptr4 <= slot_base4;
            c_vld  <= 1'b0; c_eop <= 1'b0; mask_c <= 5'b0;
        end else begin
            c_vld  <= b_vld;
            c_eop  <= b_eop;
            if (b_vld && !b_eop) begin
                mask_c <= cfg_rdata[4:0];
                if (cfg_rdata[0]) ptr0 <= ptr0 + 14'd1;
                if (cfg_rdata[1]) ptr1 <= ptr1 + 14'd1;
                if (cfg_rdata[2]) ptr2 <= ptr2 + 14'd1;
                if (cfg_rdata[3]) ptr3 <= ptr3 + 14'd1;
                if (cfg_rdata[4]) ptr4 <= ptr4 + 14'd1;
            end else begin
                mask_c <= 5'b0;
            end
        end
    end

    // ------------------------------------------------------------------
    // SRAM port muxes (loader vs fetch engine) and macro instances
    // ------------------------------------------------------------------
    wire        cfg_cen   = load_en ? (load_sel == 3'd0) : cfg_cen_f;
    wire        cfg_wen   = load_en & (load_sel == 3'd0);
    wire [CFG_AW-1:0] cfg_addr = load_en ? load_addr[CFG_AW-1:0] : cfg_pc[CFG_AW-1:0];
    wire [4:0]  cfg_wdata = load_wdata[4:0];
    wire [4:0]  cfg_wmask = 5'b11111;

    wire [4:0]  pay_sel   = {load_sel == 3'd5, load_sel == 3'd4,
                             load_sel == 3'd3, load_sel == 3'd2,
                             load_sel == 3'd1};
    wire        pay0_cen  = load_en ? pay_sel[0] : pay_rd0;
    wire        pay1_cen  = load_en ? pay_sel[1] : pay_rd1;
    wire        pay2_cen  = load_en ? pay_sel[2] : pay_rd2;
    wire        pay3_cen  = load_en ? pay_sel[3] : pay_rd3;
    wire        pay4_cen  = load_en ? pay_sel[4] : pay_rd4;
    wire        pay0_wen  = load_en & pay_sel[0];
    wire        pay1_wen  = load_en & pay_sel[1];
    wire        pay2_wen  = load_en & pay_sel[2];
    wire        pay3_wen  = load_en & pay_sel[3];
    wire        pay4_wen  = load_en & pay_sel[4];
    wire [PAY_AW-1:0] pay0_addr = load_en ? load_addr[PAY_AW-1:0] : ptr0[PAY_AW-1:0];
    wire [PAY_AW-1:0] pay1_addr = load_en ? load_addr[PAY_AW-1:0] : ptr1[PAY_AW-1:0];
    wire [PAY_AW-1:0] pay2_addr = load_en ? load_addr[PAY_AW-1:0] : ptr2[PAY_AW-1:0];
    wire [PAY_AW-1:0] pay3_addr = load_en ? load_addr[PAY_AW-1:0] : ptr3[PAY_AW-1:0];
    wire [PAY_AW-1:0] pay4_addr = load_en ? load_addr[PAY_AW-1:0] : ptr4[PAY_AW-1:0];
    wire [33:0] pay_wmask = {34{1'b1}};
    wire [33:0] pay0_rdata, pay1_rdata, pay2_rdata, pay3_rdata, pay4_rdata;

    // config macro: MC 32768x5 (LLaMA) or tiled 8192x5
`ifdef CFG_MC
    sram_32768x5_wrapper u_cfg (
        .clk(clk), .cen(cfg_cen), .wen(cfg_wen), .addr(cfg_addr),
        .wdata(cfg_wdata), .wmask(cfg_wmask), .rdata(cfg_rdata)
    );
`else
    sram_8192x5_tiled #(.TILES(TILES_CFG)) u_cfg (
        .clk(clk), .cen(cfg_cen), .wen(cfg_wen), .addr(cfg_addr),
        .wdata(cfg_wdata), .wmask(cfg_wmask), .rdata(cfg_rdata)
    );
`endif

    // payload banks: MC 16384x34 (LLaMA) or tiled 4096x34
`ifdef PAY_MC
    sram_16384x34_wrapper u_pay0 (
        .clk(clk), .cen(pay0_cen), .wen(pay0_wen), .addr(pay0_addr),
        .wdata(load_wdata), .wmask(pay_wmask), .rdata(pay0_rdata));
    sram_16384x34_wrapper u_pay1 (
        .clk(clk), .cen(pay1_cen), .wen(pay1_wen), .addr(pay1_addr),
        .wdata(load_wdata), .wmask(pay_wmask), .rdata(pay1_rdata));
    sram_16384x34_wrapper u_pay2 (
        .clk(clk), .cen(pay2_cen), .wen(pay2_wen), .addr(pay2_addr),
        .wdata(load_wdata), .wmask(pay_wmask), .rdata(pay2_rdata));
    sram_16384x34_wrapper u_pay3 (
        .clk(clk), .cen(pay3_cen), .wen(pay3_wen), .addr(pay3_addr),
        .wdata(load_wdata), .wmask(pay_wmask), .rdata(pay3_rdata));
    sram_16384x34_wrapper u_pay4 (
        .clk(clk), .cen(pay4_cen), .wen(pay4_wen), .addr(pay4_addr),
        .wdata(load_wdata), .wmask(pay_wmask), .rdata(pay4_rdata));
`else
    sram_4096x34_tiled #(.TILES(TILES_PAY)) u_pay0 (
        .clk(clk), .cen(pay0_cen), .wen(pay0_wen), .addr(pay0_addr),
        .wdata(load_wdata), .wmask(pay_wmask), .rdata(pay0_rdata));
    sram_4096x34_tiled #(.TILES(TILES_PAY)) u_pay1 (
        .clk(clk), .cen(pay1_cen), .wen(pay1_wen), .addr(pay1_addr),
        .wdata(load_wdata), .wmask(pay_wmask), .rdata(pay1_rdata));
    sram_4096x34_tiled #(.TILES(TILES_PAY)) u_pay2 (
        .clk(clk), .cen(pay2_cen), .wen(pay2_wen), .addr(pay2_addr),
        .wdata(load_wdata), .wmask(pay_wmask), .rdata(pay2_rdata));
    sram_4096x34_tiled #(.TILES(TILES_PAY)) u_pay3 (
        .clk(clk), .cen(pay3_cen), .wen(pay3_wen), .addr(pay3_addr),
        .wdata(load_wdata), .wmask(pay_wmask), .rdata(pay3_rdata));
    sram_4096x34_tiled #(.TILES(TILES_PAY)) u_pay4 (
        .clk(clk), .cen(pay4_cen), .wen(pay4_wen), .addr(pay4_addr),
        .wdata(load_wdata), .wmask(pay_wmask), .rdata(pay4_rdata));
`endif

    // ------------------------------------------------------------------
    // Stage C: dispatch into the field output registers (hold semantics)
    // ------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            slot_valid <= 1'b0;
            eop        <= 1'b0;
            done       <= 1'b0;
            load_mem_fmt   <= 2'b0;  load_mem_addr <= 20'b0;
            load_gpr_fmt   <= 2'b0;  load_gpr_addr <= 8'b0;
            load_optype    <= 2'b0;
            store_mem_fmt  <= 2'b0;  store_mem_addr <= 20'b0;
            store_gpr_fmt  <= 2'b0;  store_gpr_addr <= 8'b0;
            store_optype   <= 2'b0;
            vector_half    <= 2'b0;  vector_imm    <= 1'b0;
            vector_connect <= 2'b0;  vector_dst    <= 8'b0;
            vector_src1    <= 8'b0;  vector_src0   <= 8'b0;
            vector_mask    <= 1'b0;  vector_optype <= 4'b0;
            scalar_imm     <= 1'b0;  scalar_connect <= 1'b0;
            scalar_dst     <= 8'b0;  scalar_src1   <= 8'b0;
            scalar_src0    <= 8'b0;  scalar_mask   <= 1'b0;
            scalar_optype  <= 4'b0;
            sfu_borrow     <= 2'b0;  sfu_dst       <= 8'b0;
            sfu_src        <= 8'b0;  sfu_is_vector <= 1'b0;
            sfu_rounds     <= 8'b0;  sfu_optype    <= 4'b0;
        end else if (start) begin
            slot_valid <= 1'b0;
            eop        <= 1'b0;
            done       <= 1'b0;
        end else begin
            slot_valid <= c_vld;
            if (c_vld) begin
                eop <= c_eop;
                if (c_eop) begin
                    done <= 1'b1;
                end
                // LOAD (bank 0)
                if (mask_c[0]) begin
                    load_mem_fmt  <= pay0_rdata[25:24];
                    load_mem_addr <= pay0_rdata[31:12];
                    load_gpr_fmt  <= pay0_rdata[11:10];
                    load_gpr_addr <= pay0_rdata[9:2];
                    load_optype   <= pay0_rdata[1:0];
                end else begin
                    load_optype   <= 2'b00;
                end
                // STORE (bank 1)
                if (mask_c[1]) begin
                    store_mem_fmt  <= pay1_rdata[25:24];
                    store_mem_addr <= pay1_rdata[31:12];
                    store_gpr_fmt  <= pay1_rdata[11:10];
                    store_gpr_addr <= pay1_rdata[9:2];
                    store_optype   <= pay1_rdata[1:0];
                end else begin
                    store_optype   <= 2'b00;
                end
                // VECTOR (bank 2)
                if (mask_c[2]) begin
                    vector_half    <= pay2_rdata[33:32];
                    vector_imm     <= pay2_rdata[31];
                    vector_connect <= pay2_rdata[30:29];
                    vector_dst     <= pay2_rdata[28:21];
                    vector_src1    <= pay2_rdata[20:13];
                    vector_src0    <= pay2_rdata[12:5];
                    vector_mask    <= pay2_rdata[4];
                    vector_optype  <= pay2_rdata[3:0];
                end else begin
                    vector_optype  <= 4'b0000;
                end
                // SCALAR (bank 3)
                if (mask_c[3]) begin
                    scalar_imm     <= pay3_rdata[30];
                    scalar_connect <= pay3_rdata[29];
                    scalar_dst     <= pay3_rdata[28:21];
                    scalar_src1    <= pay3_rdata[20:13];
                    scalar_src0    <= pay3_rdata[12:5];
                    scalar_mask    <= pay3_rdata[4];
                    scalar_optype  <= pay3_rdata[3:0];
                end else begin
                    scalar_optype  <= 4'b0000;
                end
                // SFU (bank 4)
                if (mask_c[4]) begin
                    sfu_borrow     <= pay4_rdata[30:29];
                    sfu_dst        <= pay4_rdata[28:21];
                    sfu_src        <= pay4_rdata[20:13];
                    sfu_is_vector  <= pay4_rdata[12];
                    sfu_rounds     <= pay4_rdata[11:4];
                    sfu_optype     <= pay4_rdata[3:0];
                end else begin
                    sfu_optype     <= 4'b0000;
                end
            end
        end
    end

endmodule

`default_nettype wire

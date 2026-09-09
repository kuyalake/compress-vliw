`timescale 1ns/1ps
`default_nettype none

// -----------------------------------------------------------------------------
// E2 (model-pool): adaptive 4-slot (four shared lanes) instruction supply for
// the BERT program pool.
//
// Same fetch/decode/hold logic as exp2_adaptive_4slot_top, with pool-depth SRAM:
//   config : sram_8192x5_tiled #(TILES_CFG)
//   lanes  : 4x sram_2048x34_wrapper
//
// In-band EOP (config code 11111). Hold-only output stage. No backpressure.
// II=1, 3-cycle latency. See rtl/plan.md section 5.3 for the pipeline detail.
// -----------------------------------------------------------------------------

module exp2_adaptive_4slot_pool_top_bert #(
    parameter TILES_CFG = 1,   // BERT config depth: 8192 entries
    parameter TILES_PAY = 1    // kept for script compatibility; BERT lanes are fixed 2048 deep
) (
    input  wire         clk,
    input  wire         rst_n,
    // load port: load_sel 0 = config macro, 1..4 = payload lane 0..3
    input  wire         load_en,
    input  wire [2:0]   load_sel,
    input  wire [14:0]  load_addr,
    input  wire [33:0]  load_wdata,   // config uses [4:0]
    // run control: program descriptor
    input  wire         start,
    input  wire [14:0]  cfg_base,
    input  wire [14:0]  prog_len,     // total cycles T (incl. the EOP entry)
    input  wire [13:0]  lane_base0,
    input  wire [13:0]  lane_base1,
    input  wire [13:0]  lane_base2,
    input  wire [13:0]  lane_base3,
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
    localparam integer PAY_AW = 11;

    // ------------------------------------------------------------------
    // Stage A: config fetch issue (T entries per program, incl. EOP entry)
    // ------------------------------------------------------------------
    reg         run_q;
    reg  [14:0] cfg_pc;
    reg  [14:0] cfg_cnt;
    reg  [14:0] len_q;
    reg         b_vld;

    wire        cfg_cen_f = run_q & (cfg_cnt < len_q);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            run_q   <= 1'b0;
            cfg_pc  <= 15'd0;
            cfg_cnt <= 15'd0;
            len_q   <= 15'd0;
            b_vld   <= 1'b0;
        end else if (load_en) begin
            b_vld   <= 1'b0;
        end else if (start) begin
            run_q   <= 1'b1;
            cfg_pc  <= cfg_base;
            cfg_cnt <= 15'd0;
            len_q   <= prog_len;
            b_vld   <= 1'b0;
        end else if (run_q) begin
            if (cfg_cnt < len_q) begin
                cfg_pc  <= cfg_pc + 15'd1;
                cfg_cnt <= cfg_cnt + 15'd1;
                b_vld   <= 1'b1;
                if (cfg_cnt == len_q - 15'd1) begin
                    run_q <= 1'b0;          // last config entry (EOP) issued
                end
            end
        end else begin
            b_vld <= 1'b0;
        end
    end

    // ------------------------------------------------------------------
    // Stage B: mask decode -> lane enables; phase/pointer/mask pipeline regs
    // ------------------------------------------------------------------
    reg  [1:0]  phase_q;
    reg  [13:0] ptr0, ptr1, ptr2, ptr3;
    reg         c_vld;
    reg         c_eop;
    reg  [4:0]  mask_c;
    reg  [1:0]  phase_c;

    wire [4:0]  cfg_rdata;
    wire [4:0]  mask_w   = cfg_rdata;
    wire        is_eop_w = (mask_w == 5'b11111);

    // popcount and prefix ranks (shared logic)
    wire [2:0]  pre1 = {2'b00, mask_w[0]};
    wire [2:0]  pre2 = pre1 + {2'b00, mask_w[1]};
    wire [2:0]  pre3 = pre2 + {2'b00, mask_w[2]};
    wire [2:0]  pre4 = pre3 + {2'b00, mask_w[3]};
    wire [2:0]  pcnt = pre4 + {2'b00, mask_w[4]};

    // lane i carries rank (i - phase) mod 4; enabled iff rank < popcount
    wire [1:0]  rk_lane0 = 2'd0 - phase_q;
    wire [1:0]  rk_lane1 = 2'd1 - phase_q;
    wire [1:0]  rk_lane2 = 2'd2 - phase_q;
    wire [1:0]  rk_lane3 = 2'd3 - phase_q;
    wire        en0 = b_vld & ~is_eop_w & ({1'b0, rk_lane0} < pcnt);
    wire        en1 = b_vld & ~is_eop_w & ({1'b0, rk_lane1} < pcnt);
    wire        en2 = b_vld & ~is_eop_w & ({1'b0, rk_lane2} < pcnt);
    wire        en3 = b_vld & ~is_eop_w & ({1'b0, rk_lane3} < pcnt);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase_q <= 2'b0;
            ptr0 <= 14'd0; ptr1 <= 14'd0; ptr2 <= 14'd0; ptr3 <= 14'd0;
            c_vld   <= 1'b0; c_eop <= 1'b0; mask_c <= 5'b0; phase_c <= 2'b0;
        end else if (start) begin
            phase_q <= 2'b0;
            ptr0 <= lane_base0; ptr1 <= lane_base1;
            ptr2 <= lane_base2; ptr3 <= lane_base3;
            c_vld   <= 1'b0; c_eop <= 1'b0; mask_c <= 5'b0; phase_c <= 2'b0;
        end else begin
            c_vld   <= b_vld;
            c_eop   <= b_vld & is_eop_w;
            phase_c <= phase_q;
            if (b_vld && !is_eop_w) begin
                mask_c  <= mask_w;
                phase_q <= phase_q + pcnt[1:0];
                if (en0) ptr0 <= ptr0 + 14'd1;
                if (en1) ptr1 <= ptr1 + 14'd1;
                if (en2) ptr2 <= ptr2 + 14'd1;
                if (en3) ptr3 <= ptr3 + 14'd1;
            end else begin
                mask_c  <= 5'b0;    // idle or EOP: all slots invalid
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

    wire        lane0_cen  = load_en ? (load_sel == 3'd1) : en0;
    wire        lane1_cen  = load_en ? (load_sel == 3'd2) : en1;
    wire        lane2_cen  = load_en ? (load_sel == 3'd3) : en2;
    wire        lane3_cen  = load_en ? (load_sel == 3'd4) : en3;
    wire        lane0_wen  = load_en & (load_sel == 3'd1);
    wire        lane1_wen  = load_en & (load_sel == 3'd2);
    wire        lane2_wen  = load_en & (load_sel == 3'd3);
    wire        lane3_wen  = load_en & (load_sel == 3'd4);
    wire [PAY_AW-1:0] lane0_addr = load_en ? load_addr[PAY_AW-1:0] : ptr0[PAY_AW-1:0];
    wire [PAY_AW-1:0] lane1_addr = load_en ? load_addr[PAY_AW-1:0] : ptr1[PAY_AW-1:0];
    wire [PAY_AW-1:0] lane2_addr = load_en ? load_addr[PAY_AW-1:0] : ptr2[PAY_AW-1:0];
    wire [PAY_AW-1:0] lane3_addr = load_en ? load_addr[PAY_AW-1:0] : ptr3[PAY_AW-1:0];
    wire [33:0] lane_wmask = {34{1'b1}};
    wire [33:0] lane0_rdata, lane1_rdata, lane2_rdata, lane3_rdata;

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

    // payload lanes: BERT uses four 2048x34 macros.
    sram_2048x34_wrapper u_lane0 (
        .clk(clk), .cen(lane0_cen), .wen(lane0_wen), .addr(lane0_addr),
        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane0_rdata));
    sram_2048x34_wrapper u_lane1 (
        .clk(clk), .cen(lane1_cen), .wen(lane1_wen), .addr(lane1_addr),
        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane1_rdata));
    sram_2048x34_wrapper u_lane2 (
        .clk(clk), .cen(lane2_cen), .wen(lane2_wen), .addr(lane2_addr),
        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane2_rdata));
    sram_2048x34_wrapper u_lane3 (
        .clk(clk), .cen(lane3_cen), .wen(lane3_wen), .addr(lane3_addr),
        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane3_rdata));

    // ------------------------------------------------------------------
    // Stage C: 4:1 scatter (selects from mask_c/phase_c registers) + hold
    // ------------------------------------------------------------------
    wire [2:0]  c_pre1 = {2'b00, mask_c[0]};
    wire [2:0]  c_pre2 = c_pre1 + {2'b00, mask_c[1]};
    wire [2:0]  c_pre3 = c_pre2 + {2'b00, mask_c[2]};
    wire [2:0]  c_pre4 = c_pre3 + {2'b00, mask_c[3]};

    wire [1:0]  sel0 = phase_c;
    wire [1:0]  sel1 = phase_c + c_pre1[1:0];
    wire [1:0]  sel2 = phase_c + c_pre2[1:0];
    wire [1:0]  sel3 = phase_c + c_pre3[1:0];
    wire [1:0]  sel4 = phase_c + c_pre4[1:0];

    wire [33:0] data0 = lane0_rdata;
    wire [33:0] data1 = lane1_rdata;
    wire [33:0] data2 = lane2_rdata;
    wire [33:0] data3 = lane3_rdata;

    wire [33:0] sc_load   = (sel0 == 2'd0) ? data0 : (sel0 == 2'd1) ? data1 :
                            (sel0 == 2'd2) ? data2 : data3;
    wire [33:0] sc_store  = (sel1 == 2'd0) ? data0 : (sel1 == 2'd1) ? data1 :
                            (sel1 == 2'd2) ? data2 : data3;
    wire [33:0] sc_vector = (sel2 == 2'd0) ? data0 : (sel2 == 2'd1) ? data1 :
                            (sel2 == 2'd2) ? data2 : data3;
    wire [33:0] sc_scalar = (sel3 == 2'd0) ? data0 : (sel3 == 2'd1) ? data1 :
                            (sel3 == 2'd2) ? data2 : data3;
    wire [33:0] sc_sfu    = (sel4 == 2'd0) ? data0 : (sel4 == 2'd1) ? data1 :
                            (sel4 == 2'd2) ? data2 : data3;

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
                // LOAD (slot 0)
                if (mask_c[0]) begin
                    load_mem_fmt  <= sc_load[25:24];
                    load_mem_addr <= sc_load[31:12];
                    load_gpr_fmt  <= sc_load[11:10];
                    load_gpr_addr <= sc_load[9:2];
                    load_optype   <= sc_load[1:0];
                end else begin
                    load_optype   <= 2'b00;
                end
                // STORE (slot 1)
                if (mask_c[1]) begin
                    store_mem_fmt  <= sc_store[25:24];
                    store_mem_addr <= sc_store[31:12];
                    store_gpr_fmt  <= sc_store[11:10];
                    store_gpr_addr <= sc_store[9:2];
                    store_optype   <= sc_store[1:0];
                end else begin
                    store_optype   <= 2'b00;
                end
                // VECTOR (slot 2)
                if (mask_c[2]) begin
                    vector_half    <= sc_vector[33:32];
                    vector_imm     <= sc_vector[31];
                    vector_connect <= sc_vector[30:29];
                    vector_dst     <= sc_vector[28:21];
                    vector_src1    <= sc_vector[20:13];
                    vector_src0    <= sc_vector[12:5];
                    vector_mask    <= sc_vector[4];
                    vector_optype  <= sc_vector[3:0];
                end else begin
                    vector_optype  <= 4'b0000;
                end
                // SCALAR (slot 3)
                if (mask_c[3]) begin
                    scalar_imm     <= sc_scalar[30];
                    scalar_connect <= sc_scalar[29];
                    scalar_dst     <= sc_scalar[28:21];
                    scalar_src1    <= sc_scalar[20:13];
                    scalar_src0    <= sc_scalar[12:5];
                    scalar_mask    <= sc_scalar[4];
                    scalar_optype  <= sc_scalar[3:0];
                end else begin
                    scalar_optype  <= 4'b0000;
                end
                // SFU (slot 4)
                if (mask_c[4]) begin
                    sfu_borrow     <= sc_sfu[30:29];
                    sfu_dst        <= sc_sfu[28:21];
                    sfu_src        <= sc_sfu[20:13];
                    sfu_is_vector  <= sc_sfu[12];
                    sfu_rounds     <= sc_sfu[11:4];
                    sfu_optype     <= sc_sfu[3:0];
                end else begin
                    sfu_optype     <= 4'b0000;
                end
            end
        end
    end

endmodule

`default_nettype wire

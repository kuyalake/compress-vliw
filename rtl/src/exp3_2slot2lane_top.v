`timescale 1ns/1ps
`default_nettype none

// -----------------------------------------------------------------------------
// E3: 2slot2lane instruction supply (rtl/plan.md section 5.4)
//
// Storage: config 1x sram_8192x5 (5-bit pair code per cycle, T entries incl.
// the in-band EOP code 31) + payload 2x sram_4096x34 (shared lanes 0..1).
//
// Config semantics: code -> {valid0, slot0, valid1, slot1} via the
// script-generated cfg_pair_codebook (same enumeration as the encoder);
// lane i carries slot_i when valid_i. Code 31 = EOP -> all invalid.
//
// Pipeline (II=1, 3-cycle latency), config one stage ahead of payload:
//   stage A: config address = cfg_pc (registered) -> config macro;
//   stage B: config Q = code(k) -> codebook LUT -> {valid0, slot0, valid1,
//            slot1}; lane enables en(i) = valid_i -> lane CENs/addresses
//            (critical path 1: config Q -> LUT -> payload CEN/A setup).
//            Registered at end of B: decoded control {valid0_c, slot0_c,
//            valid1_c, slot1_c} (8 DFFs) so stage C is pure muxing;
//            lane pointers advance by en;
//   stage C: payload Q -> per-slot 2:1 mux -> field output registers
//            (hold semantics, plan.md section 3.4).
//
// Hold-only output stage (no HOLD_EN parameter, per 2026-09-06 decision).
// Program pool: descriptor {cfg_base, prog_len, lane_base0, lane_base1}
// latched at start; lane pointers start at the lane bases. No backpressure.
// -----------------------------------------------------------------------------

module exp3_2slot2lane_top (
    input  wire         clk,
    input  wire         rst_n,
    // load port: load_sel 0 = config macro, 1..2 = payload lane 0..1
    input  wire         load_en,
    input  wire [1:0]   load_sel,
    input  wire [12:0]  load_addr,
    input  wire [33:0]  load_wdata,   // config uses [4:0]
    // run control: program descriptor
    input  wire         start,
    input  wire [12:0]  cfg_base,
    input  wire [13:0]  prog_len,     // total cycles T (including the EOP entry)
    input  wire [11:0]  lane_base0,
    input  wire [11:0]  lane_base1,
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

    // ------------------------------------------------------------------
    // Stage A: config fetch issue (T entries per program, incl. EOP entry)
    // ------------------------------------------------------------------
    reg         run_q;
    reg  [13:0] cfg_pc;
    reg  [13:0] cfg_cnt;
    reg  [13:0] len_q;
    reg         b_vld;

    wire        cfg_cen_f = run_q & (cfg_cnt < len_q);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            run_q   <= 1'b0;
            cfg_pc  <= 14'd0;
            cfg_cnt <= 14'd0;
            len_q   <= 14'd0;
            b_vld   <= 1'b0;
        end else if (load_en) begin
            b_vld   <= 1'b0;
        end else if (start) begin
            run_q   <= 1'b1;
            cfg_pc  <= {1'b0, cfg_base};
            cfg_cnt <= 14'd0;
            len_q   <= prog_len;
            b_vld   <= 1'b0;
        end else if (run_q) begin
            if (cfg_cnt < len_q) begin
                cfg_pc  <= cfg_pc + 14'd1;
                cfg_cnt <= cfg_cnt + 14'd1;
                b_vld   <= 1'b1;
                if (cfg_cnt == len_q - 14'd1) begin
                    run_q <= 1'b0;          // last config entry (EOP) issued
                end
            end
        end else begin
            b_vld <= 1'b0;
        end
    end

    // ------------------------------------------------------------------
    // Stage B: pair-codebook decode -> lane enables; pointers; control regs
    // ------------------------------------------------------------------
    reg  [11:0] ptr0, ptr1;
    reg         c_vld;
    reg         c_eop;
    reg         valid0_c, valid1_c;
    reg  [2:0]  slot0_c, slot1_c;

    wire [4:0]  cfg_rdata;
    wire        is_eop_w = (cfg_rdata == 5'd31);

    // script-generated codebook (combinational case table)
    wire        valid0_w, valid1_w;
    wire [2:0]  slot0_w, slot1_w;
    cfg_pair_codebook u_codebook (
        .code   (cfg_rdata),
        .valid0 (valid0_w),
        .slot0  (slot0_w),
        .valid1 (valid1_w),
        .slot1  (slot1_w)
    );

    // code 31 decodes to all-invalid, so EOP automatically disables lanes
    wire        en0 = b_vld & valid0_w;
    wire        en1 = b_vld & valid1_w;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ptr0 <= 12'd0; ptr1 <= 12'd0;
            c_vld    <= 1'b0; c_eop <= 1'b0;
            valid0_c <= 1'b0; slot0_c <= 3'd0;
            valid1_c <= 1'b0; slot1_c <= 3'd0;
        end else if (start) begin
            ptr0 <= lane_base0; ptr1 <= lane_base1;
            c_vld    <= 1'b0; c_eop <= 1'b0;
            valid0_c <= 1'b0; slot0_c <= 3'd0;
            valid1_c <= 1'b0; slot1_c <= 3'd0;
        end else begin
            c_vld <= b_vld;
            c_eop <= b_vld & is_eop_w;
            if (b_vld) begin
                valid0_c <= valid0_w;
                slot0_c  <= slot0_w;
                valid1_c <= valid1_w;
                slot1_c  <= slot1_w;
                if (en0) ptr0 <= ptr0 + 12'd1;
                if (en1) ptr1 <= ptr1 + 12'd1;
            end else begin
                valid0_c <= 1'b0; slot0_c <= 3'd0;
                valid1_c <= 1'b0; slot1_c <= 3'd0;
            end
        end
    end

    // ------------------------------------------------------------------
    // SRAM port muxes (loader vs fetch engine) and macro instances
    // ------------------------------------------------------------------
    wire        cfg_cen   = load_en ? (load_sel == 2'd0) : cfg_cen_f;
    wire        cfg_wen   = load_en & (load_sel == 2'd0);
    wire [12:0] cfg_addr  = load_en ? load_addr : cfg_pc[12:0];
    wire [4:0]  cfg_wdata = load_wdata[4:0];
    wire [4:0]  cfg_wmask = 5'b11111;

    wire        lane0_cen  = load_en ? (load_sel == 2'd1) : en0;
    wire        lane1_cen  = load_en ? (load_sel == 2'd2) : en1;
    wire        lane0_wen  = load_en & (load_sel == 2'd1);
    wire        lane1_wen  = load_en & (load_sel == 2'd2);
    wire [11:0] lane0_addr = load_en ? load_addr[11:0] : ptr0;
    wire [11:0] lane1_addr = load_en ? load_addr[11:0] : ptr1;
    wire [33:0] lane_wmask = {34{1'b1}};
    wire [33:0] lane0_rdata, lane1_rdata;

    sram_8192x5_wrapper u_cfg (
        .clk   (clk),
        .cen   (cfg_cen),
        .wen   (cfg_wen),
        .addr  (cfg_addr),
        .wdata (cfg_wdata),
        .wmask (cfg_wmask),
        .rdata (cfg_rdata)
    );

    sram_4096x34_wrapper u_lane0 (
        .clk(clk), .cen(lane0_cen), .wen(lane0_wen), .addr(lane0_addr),
        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane0_rdata)
    );
    sram_4096x34_wrapper u_lane1 (
        .clk(clk), .cen(lane1_cen), .wen(lane1_wen), .addr(lane1_addr),
        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane1_rdata)
    );

    // ------------------------------------------------------------------
    // Stage C: per-slot 2:1 mux (from registered control) + hold
    // ------------------------------------------------------------------
    // lane l hits slot s iff valid_l_c && slot_l_c == s (codebook guarantees
    // the two lanes never target the same slot)
    wire [33:0] data0 = lane0_rdata;
    wire [33:0] data1 = lane1_rdata;

    // slot s selected and its payload
    // (comparators are 3-bit equality against constant slot ids)
    wire hit00 = valid0_c & (slot0_c == 3'd0);
    wire hit01 = valid0_c & (slot0_c == 3'd1);
    wire hit02 = valid0_c & (slot0_c == 3'd2);
    wire hit03 = valid0_c & (slot0_c == 3'd3);
    wire hit04 = valid0_c & (slot0_c == 3'd4);
    wire hit10 = valid1_c & (slot1_c == 3'd0);
    wire hit11 = valid1_c & (slot1_c == 3'd1);
    wire hit12 = valid1_c & (slot1_c == 3'd2);
    wire hit13 = valid1_c & (slot1_c == 3'd3);
    wire hit14 = valid1_c & (slot1_c == 3'd4);

    wire        sel_load   = hit00 | hit10;
    wire        sel_store  = hit01 | hit11;
    wire        sel_vector = hit02 | hit12;
    wire        sel_scalar = hit03 | hit13;
    wire        sel_sfu    = hit04 | hit14;

    wire [33:0] sc_load   = hit00 ? data0 : data1;
    wire [33:0] sc_store  = hit01 ? data0 : data1;
    wire [33:0] sc_vector = hit02 ? data0 : data1;
    wire [33:0] sc_scalar = hit03 ? data0 : data1;
    wire [33:0] sc_sfu    = hit04 ? data0 : data1;

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
                if (sel_load) begin
                    load_mem_fmt  <= sc_load[25:24];
                    load_mem_addr <= sc_load[31:12];
                    load_gpr_fmt  <= sc_load[11:10];
                    load_gpr_addr <= sc_load[9:2];
                    load_optype   <= sc_load[1:0];
                end else begin
                    load_optype   <= 2'b00;   // hold other fields
                end
                // STORE (slot 1)
                if (sel_store) begin
                    store_mem_fmt  <= sc_store[25:24];
                    store_mem_addr <= sc_store[31:12];
                    store_gpr_fmt  <= sc_store[11:10];
                    store_gpr_addr <= sc_store[9:2];
                    store_optype   <= sc_store[1:0];
                end else begin
                    store_optype   <= 2'b00;
                end
                // VECTOR (slot 2)
                if (sel_vector) begin
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
                if (sel_scalar) begin
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
                if (sel_sfu) begin
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

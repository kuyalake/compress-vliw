`timescale 1ns/1ps
`default_nettype none

// -----------------------------------------------------------------------------
// E1: Candidate A instruction supply (rtl/plan.md section 5.2)
//
// Storage: config 1x sram_8192x5 (5-bit slot mask per functional cycle,
// T-1 entries) + payload 5x sram_2048x34 (one dedicated bank per slot).
// EOP is implicit: mask=11111 is LEGAL data; the EOP cycle is produced by the
// accepted-instruction counter reaching prog_len-1 (no config read).
//
// Pipeline (II=1, 3-cycle latency), config one stage ahead of payload:
//   stage A: config address = cfg_pc (registered) -> config macro;
//   stage B: config Q = mask(k) drives payload bank enables (cen_s = mask[s],
//            exact gating) and addresses (ptr_s); mask captured; ptr_s advance;
//   stage C: payload Q captured -> field output registers (hold semantics,
//            plan.md section 3.4): selected[s]=mask[s]; invalid slot -> OP<=0.
//
// Program pool: descriptor {cfg_base, prog_len, slot_base0..4} latched at
// start; pointers start at the slot bases. No backpressure.
//
// Output stage is HOLD-only (2026-09-06): an invalid slot clears only its OP
// field to 0 and holds the other fields; the HOLD_EN=0 caliber is not
// implemented for E1 in this batch.
// -----------------------------------------------------------------------------

module exp1_candidate_a_top (
    input  wire         clk,
    input  wire         rst_n,
    // load port: load_sel 0 = config macro, 1..5 = payload bank slot 0..4
    input  wire         load_en,
    input  wire [2:0]   load_sel,
    input  wire [12:0]  load_addr,
    input  wire [33:0]  load_wdata,   // config uses [4:0]
    // run control: program descriptor
    input  wire         start,
    input  wire [12:0]  cfg_base,
    input  wire [13:0]  prog_len,     // total cycles T (including the EOP cycle)
    input  wire [10:0]  slot_base0,
    input  wire [10:0]  slot_base1,
    input  wire [10:0]  slot_base2,
    input  wire [10:0]  slot_base3,
    input  wire [10:0]  slot_base4,
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
    // Stage A: config fetch issue + descriptor/pointer state
    // ------------------------------------------------------------------
    reg         run_q;
    reg  [13:0] cfg_pc;     // absolute config address ([12:0] into the macro)
    reg  [13:0] cfg_cnt;    // config entries issued so far
    reg         eop_inj;    // EOP marker cycle issued
    reg  [13:0] len_q;      // latched prog_len
    reg         b_vld;      // stage-B valid
    reg         b_eop;      // stage-B EOP marker

    // config read is presented while entries remain (T-1 entries)
    wire        cfg_cen_f = run_q & (cfg_cnt < len_q - 14'd1);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            run_q    <= 1'b0;
            cfg_pc   <= 14'd0;
            cfg_cnt  <= 14'd0;
            eop_inj  <= 1'b0;
            len_q    <= 14'd0;
            b_vld    <= 1'b0;
            b_eop    <= 1'b0;
        end else if (load_en) begin
            b_vld    <= 1'b0;               // loader owns the macros
            b_eop    <= 1'b0;
        end else if (start) begin
            run_q    <= 1'b1;
            cfg_pc   <= {1'b0, cfg_base};
            cfg_cnt  <= 14'd0;
            eop_inj  <= 1'b0;
            len_q    <= prog_len;
            b_vld    <= 1'b0;
            b_eop    <= 1'b0;
        end else if (run_q) begin
            if (cfg_cnt < len_q - 14'd1) begin
                cfg_pc  <= cfg_pc + 14'd1;  // config read presented this cycle
                cfg_cnt <= cfg_cnt + 14'd1;
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
    reg  [10:0] ptr0, ptr1, ptr2, ptr3, ptr4;
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
            ptr0 <= 11'd0; ptr1 <= 11'd0; ptr2 <= 11'd0;
            ptr3 <= 11'd0; ptr4 <= 11'd0;
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
                if (cfg_rdata[0]) ptr0 <= ptr0 + 11'd1;
                if (cfg_rdata[1]) ptr1 <= ptr1 + 11'd1;
                if (cfg_rdata[2]) ptr2 <= ptr2 + 11'd1;
                if (cfg_rdata[3]) ptr3 <= ptr3 + 11'd1;
                if (cfg_rdata[4]) ptr4 <= ptr4 + 11'd1;
            end else begin
                mask_c <= 5'b0;
            end
        end
    end

    // ------------------------------------------------------------------
    // SRAM port muxes (loader vs fetch engine) and macro instances
    // ------------------------------------------------------------------
    // config (8192x5)
    wire        cfg_cen   = load_en ? (load_sel == 3'd0) : cfg_cen_f;
    wire        cfg_wen   = load_en & (load_sel == 3'd0);
    wire [12:0] cfg_addr  = load_en ? load_addr : cfg_pc[12:0];
    wire [4:0]  cfg_wdata = load_wdata[4:0];
    wire [4:0]  cfg_wmask = 5'b11111;

    // payload banks (2048x34), slot s uses load_sel == s+1
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
    wire [10:0] pay0_addr = load_en ? load_addr[10:0] : ptr0;
    wire [10:0] pay1_addr = load_en ? load_addr[10:0] : ptr1;
    wire [10:0] pay2_addr = load_en ? load_addr[10:0] : ptr2;
    wire [10:0] pay3_addr = load_en ? load_addr[10:0] : ptr3;
    wire [10:0] pay4_addr = load_en ? load_addr[10:0] : ptr4;
    wire [33:0] pay_wmask = {34{1'b1}};
    wire [33:0] pay0_rdata, pay1_rdata, pay2_rdata, pay3_rdata, pay4_rdata;

    sram_8192x5_wrapper u_cfg (
        .clk   (clk),
        .cen   (cfg_cen),
        .wen   (cfg_wen),
        .addr  (cfg_addr),
        .wdata (cfg_wdata),
        .wmask (cfg_wmask),
        .rdata (cfg_rdata)
    );

    sram_2048x34_wrapper u_pay0 (
        .clk(clk), .cen(pay0_cen), .wen(pay0_wen), .addr(pay0_addr),
        .wdata(load_wdata), .wmask(pay_wmask), .rdata(pay0_rdata)
    );
    sram_2048x34_wrapper u_pay1 (
        .clk(clk), .cen(pay1_cen), .wen(pay1_wen), .addr(pay1_addr),
        .wdata(load_wdata), .wmask(pay_wmask), .rdata(pay1_rdata)
    );
    sram_2048x34_wrapper u_pay2 (
        .clk(clk), .cen(pay2_cen), .wen(pay2_wen), .addr(pay2_addr),
        .wdata(load_wdata), .wmask(pay_wmask), .rdata(pay2_rdata)
    );
    sram_2048x34_wrapper u_pay3 (
        .clk(clk), .cen(pay3_cen), .wen(pay3_wen), .addr(pay3_addr),
        .wdata(load_wdata), .wmask(pay_wmask), .rdata(pay3_rdata)
    );
    sram_2048x34_wrapper u_pay4 (
        .clk(clk), .cen(pay4_cen), .wen(pay4_wen), .addr(pay4_addr),
        .wdata(load_wdata), .wmask(pay_wmask), .rdata(pay4_rdata)
    );

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
                    load_optype   <= 2'b00;   // hold other fields
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

`timescale 1ns/1ps
`default_nettype none

// -----------------------------------------------------------------------------
// E2 five-lane (model-pool): five shared payload lanes for the SD-UNet pool,
// original max-5 schedule (five-slot
// concurrency allowed; mask 11111 is legal data, NOT an EOP code).
//
// Per plan/e2_five_lane_detailed_experiment_plan_2026-09-13.html:
//   config : 5-bit mask per real execution cycle (implicit EOP via prog_len);
//            sram_32768x5_wrapper (covers LLaMA config depth).
//   lanes  : five 34-bit payload lanes, phase-striped (mod-5);
//            sram_4096x34_tiled #(TILES=2) -> 8192 deep (covers LLaMA lane).
//
// Implicit EOP: config holds (prog_len-1) real entries; output cycle
// prog_len-1 is a hardware-generated all-NOP + eop=1 (no config/payload read).
// Hold-only output stage. No backpressure. II=1, 3-cycle latency.
// -----------------------------------------------------------------------------

module exp2_five_lane_pool_top_sd_unet (
    input  wire         clk,
    input  wire         rst_n,
    // load port: load_sel 0 = config macro, 1..5 = payload lane 0..4
    input  wire         load_en,
    input  wire [2:0]   load_sel,
    input  wire [14:0]  load_addr,
    input  wire [33:0]  load_wdata,   // config uses [4:0]
    // run control: program descriptor
    input  wire         start,
    input  wire [14:0]  cfg_base,
    input  wire [14:0]  prog_len,     // total output cycles T (incl. implicit EOP)
    input  wire [13:0]  lane_base0,
    input  wire [13:0]  lane_base1,
    input  wire [13:0]  lane_base2,
    input  wire [13:0]  lane_base3,
    input  wire [13:0]  lane_base4,
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
    // Stage A: config fetch issue.
    //   real cycles cnt in [0, prog_len-2] read config; cycle prog_len-1 is
    //   the implicit EOP (no config read, b_eop=1).
    // ------------------------------------------------------------------
    reg         run_q;
    reg  [14:0] cfg_pc;
    reg  [14:0] cnt;
    reg  [14:0] len_q;
    reg         b_vld;
    reg         b_eop;

    wire        is_real   = run_q & (cnt < len_q - 15'd1);
    wire        is_eopc   = run_q & (cnt == len_q - 15'd1);
    wire        cfg_cen_f = is_real;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            run_q   <= 1'b0;
            cfg_pc  <= 15'd0;
            cnt     <= 15'd0;
            len_q   <= 15'd0;
            b_vld   <= 1'b0;
            b_eop   <= 1'b0;
        end else if (load_en) begin
            b_vld   <= 1'b0;
            b_eop   <= 1'b0;
        end else if (start) begin
            run_q   <= 1'b1;
            cfg_pc  <= cfg_base;
            cnt     <= 15'd0;
            len_q   <= prog_len;
            b_vld   <= 1'b0;
            b_eop   <= 1'b0;
        end else if (run_q) begin
            if (is_real) begin
                cfg_pc <= cfg_pc + 15'd1;
                cnt    <= cnt + 15'd1;
                b_vld  <= 1'b1;
                b_eop  <= 1'b0;
            end else if (is_eopc) begin
                cnt    <= cnt + 15'd1;
                b_vld  <= 1'b1;
                b_eop  <= 1'b1;     // implicit EOP cycle
                run_q  <= 1'b0;
            end else begin
                b_vld  <= 1'b0;
                b_eop  <= 1'b0;
            end
        end else begin
            b_vld <= 1'b0;
            b_eop <= 1'b0;
        end
    end

    // forward declarations (Icarus needs declaration before use)
    wire [4:0]  cfg_rdata;
    wire [33:0] lane0_rdata, lane1_rdata, lane2_rdata, lane3_rdata, lane4_rdata;

    // ------------------------------------------------------------------
    // Stage B: mask decode -> five lane enables; phase/pointer pipeline regs.
    //   lane i carries rank (i - phase) mod 5; enabled iff rank < popcount.
    // ------------------------------------------------------------------
    reg  [2:0]  phase_q;
    reg  [13:0] ptr0, ptr1, ptr2, ptr3, ptr4;
    reg         c_vld;
    reg         c_eop;
    reg  [4:0]  mask_c;
    reg  [2:0]  phase_c;

    wire [4:0]  mask_w   = cfg_rdata;

    // popcount (0..5, 4-bit) and per-lane rank (mod-5, 4-bit arithmetic)
    wire [3:0]  pcnt = {3'b000, mask_w[0]} + {3'b000, mask_w[1]}
                     + {3'b000, mask_w[2]} + {3'b000, mask_w[3]}
                     + {3'b000, mask_w[4]};
    wire [3:0]  ph4  = {1'b0, phase_q};

    // rank of lane i = (i - phase) mod 5  =  (i>=phase)? i-phase : i+5-phase
    wire [3:0]  rk0 = (4'd0 >= ph4) ? (4'd0 - ph4) : (4'd5 - ph4);
    wire [3:0]  rk1 = (4'd1 >= ph4) ? (4'd1 - ph4) : (4'd6 - ph4);
    wire [3:0]  rk2 = (4'd2 >= ph4) ? (4'd2 - ph4) : (4'd7 - ph4);
    wire [3:0]  rk3 = (4'd3 >= ph4) ? (4'd3 - ph4) : (4'd8 - ph4);
    wire [3:0]  rk4 = (4'd4 >= ph4) ? (4'd4 - ph4) : (4'd9 - ph4);

    wire        live = b_vld & ~b_eop;
    wire        en0 = live & (rk0 < pcnt);
    wire        en1 = live & (rk1 < pcnt);
    wire        en2 = live & (rk2 < pcnt);
    wire        en3 = live & (rk3 < pcnt);
    wire        en4 = live & (rk4 < pcnt);

    // phase update: (phase + popcount) mod 5, sum <= 9 -> one cond. subtract
    wire [3:0]  ph_sum  = {1'b0, phase_q} + {1'b0, pcnt};
    wire [2:0]  ph_next = (ph_sum >= 4'd5) ? (ph_sum - 4'd5) : ph_sum[2:0];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase_q <= 3'd0;
            ptr0 <= 14'd0; ptr1 <= 14'd0; ptr2 <= 14'd0;
            ptr3 <= 14'd0; ptr4 <= 14'd0;
            c_vld   <= 1'b0; c_eop <= 1'b0; mask_c <= 5'b0; phase_c <= 3'd0;
        end else if (start) begin
            phase_q <= 3'd0;
            ptr0 <= lane_base0; ptr1 <= lane_base1; ptr2 <= lane_base2;
            ptr3 <= lane_base3; ptr4 <= lane_base4;
            c_vld   <= 1'b0; c_eop <= 1'b0; mask_c <= 5'b0; phase_c <= 3'd0;
        end else begin
            c_vld   <= b_vld;
            c_eop   <= b_eop;
            phase_c <= phase_q;
            if (live) begin
                mask_c  <= mask_w;
                phase_q <= ph_next;
                if (en0) ptr0 <= ptr0 + 14'd1;
                if (en1) ptr1 <= ptr1 + 14'd1;
                if (en2) ptr2 <= ptr2 + 14'd1;
                if (en3) ptr3 <= ptr3 + 14'd1;
                if (en4) ptr4 <= ptr4 + 14'd1;
            end else begin
                mask_c  <= 5'b0;    // idle or implicit EOP: all slots invalid
            end
        end
    end

    // ------------------------------------------------------------------
    // SRAM port muxes (loader vs fetch engine) and macro instances
    // ------------------------------------------------------------------
    wire        cfg_cen   = load_en ? (load_sel == 3'd0) : cfg_cen_f;
    wire        cfg_wen   = load_en & (load_sel == 3'd0);
    wire [13:0] cfg_addr  = load_en ? load_addr[13:0] : cfg_pc[13:0];
    wire [4:0]  cfg_wdata = load_wdata[4:0];
    wire [4:0]  cfg_wmask = 5'b11111;

    wire        lane0_cen = load_en ? (load_sel == 3'd1) : en0;
    wire        lane1_cen = load_en ? (load_sel == 3'd2) : en1;
    wire        lane2_cen = load_en ? (load_sel == 3'd3) : en2;
    wire        lane3_cen = load_en ? (load_sel == 3'd4) : en3;
    wire        lane4_cen = load_en ? (load_sel == 3'd5) : en4;
    wire        lane0_wen = load_en & (load_sel == 3'd1);
    wire        lane1_wen = load_en & (load_sel == 3'd2);
    wire        lane2_wen = load_en & (load_sel == 3'd3);
    wire        lane3_wen = load_en & (load_sel == 3'd4);
    wire        lane4_wen = load_en & (load_sel == 3'd5);
    wire [11:0] lane0_addr = load_en ? load_addr[11:0] : ptr0[11:0];
    wire [11:0] lane1_addr = load_en ? load_addr[11:0] : ptr1[11:0];
    wire [11:0] lane2_addr = load_en ? load_addr[11:0] : ptr2[11:0];
    wire [11:0] lane3_addr = load_en ? load_addr[11:0] : ptr3[11:0];
    wire [11:0] lane4_addr = load_en ? load_addr[11:0] : ptr4[11:0];
    wire [33:0] lane_wmask = {34{1'b1}};

    sram_8192x5_tiled #(.TILES(2)) u_cfg (
        .clk(clk), .cen(cfg_cen), .wen(cfg_wen), .addr(cfg_addr),
        .wdata(cfg_wdata), .wmask(cfg_wmask), .rdata(cfg_rdata)
    );

    sram_4096x34_wrapper u_lane0 (
        .clk(clk), .cen(lane0_cen), .wen(lane0_wen), .addr(lane0_addr),
        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane0_rdata));
    sram_4096x34_wrapper u_lane1 (
        .clk(clk), .cen(lane1_cen), .wen(lane1_wen), .addr(lane1_addr),
        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane1_rdata));
    sram_4096x34_wrapper u_lane2 (
        .clk(clk), .cen(lane2_cen), .wen(lane2_wen), .addr(lane2_addr),
        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane2_rdata));
    sram_4096x34_wrapper u_lane3 (
        .clk(clk), .cen(lane3_cen), .wen(lane3_wen), .addr(lane3_addr),
        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane3_rdata));
    sram_4096x34_wrapper u_lane4 (
        .clk(clk), .cen(lane4_cen), .wen(lane4_wen), .addr(lane4_addr),
        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane4_rdata));

    // ------------------------------------------------------------------
    // Stage C: 5:1 scatter (selects from mask_c/phase_c registers) + hold.
    //   slot s with prefix rank r reads lane (phase_c + r) mod 5.
    // ------------------------------------------------------------------
    wire [2:0]  c_pre1 = {2'b00, mask_c[0]};
    wire [2:0]  c_pre2 = c_pre1 + {2'b00, mask_c[1]};
    wire [2:0]  c_pre3 = c_pre2 + {2'b00, mask_c[2]};
    wire [2:0]  c_pre4 = c_pre3 + {2'b00, mask_c[3]};

    // (phase_c + rank) mod 5; phase_c in 0..4, rank in 0..4 -> sum in 0..8
    wire [3:0]  s0 = {1'b0, phase_c};
    wire [3:0]  s1 = {1'b0, phase_c} + {1'b0, c_pre1};
    wire [3:0]  s2 = {1'b0, phase_c} + {1'b0, c_pre2};
    wire [3:0]  s3 = {1'b0, phase_c} + {1'b0, c_pre3};
    wire [3:0]  s4 = {1'b0, phase_c} + {1'b0, c_pre4};
    wire [2:0]  sel0 = s0[2:0];
    wire [2:0]  sel1 = (s1 >= 4'd5) ? (s1 - 4'd5) : s1[2:0];
    wire [2:0]  sel2 = (s2 >= 4'd5) ? (s2 - 4'd5) : s2[2:0];
    wire [2:0]  sel3 = (s3 >= 4'd5) ? (s3 - 4'd5) : s3[2:0];
    wire [2:0]  sel4 = (s4 >= 4'd5) ? (s4 - 4'd5) : s4[2:0];

    wire [33:0] data0 = lane0_rdata;
    wire [33:0] data1 = lane1_rdata;
    wire [33:0] data2 = lane2_rdata;
    wire [33:0] data3 = lane3_rdata;
    wire [33:0] data4 = lane4_rdata;

    wire [33:0] sc_load   = (sel0 == 3'd0) ? data0 : (sel0 == 3'd1) ? data1 :
                            (sel0 == 3'd2) ? data2 : (sel0 == 3'd3) ? data3 :
                            data4;
    wire [33:0] sc_store  = (sel1 == 3'd0) ? data0 : (sel1 == 3'd1) ? data1 :
                            (sel1 == 3'd2) ? data2 : (sel1 == 3'd3) ? data3 :
                            data4;
    wire [33:0] sc_vector = (sel2 == 3'd0) ? data0 : (sel2 == 3'd1) ? data1 :
                            (sel2 == 3'd2) ? data2 : (sel2 == 3'd3) ? data3 :
                            data4;
    wire [33:0] sc_scalar = (sel3 == 3'd0) ? data0 : (sel3 == 3'd1) ? data1 :
                            (sel3 == 3'd2) ? data2 : (sel3 == 3'd3) ? data3 :
                            data4;
    wire [33:0] sc_sfu    = (sel4 == 3'd0) ? data0 : (sel4 == 3'd1) ? data1 :
                            (sel4 == 3'd2) ? data2 : (sel4 == 3'd3) ? data3 :
                            data4;

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

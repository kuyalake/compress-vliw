`timescale 1ns/1ps
`default_nettype none

// -----------------------------------------------------------------------------
// E2 two-lane (model-pool): two shared payload lanes for the BERT pool,
// max-2 schedule (at most two slots active
// per cycle).  Supplementary lane-sweep experiment to E2-5: the E2 striping
// scheme is unchanged (5-bit mask per cycle, phase-rotated striping, implicit
// EOP via prog_len); only the scheduler's max concurrent slots is reduced to
// 2, so two shared physical lanes suffice (mod-2 phase).
//
//   config : 5-bit mask per real execution cycle (implicit EOP via prog_len);
//            sram_8192x5_wrapper (BERT config depth 8192).
//   lanes  : two 34-bit payload lanes, phase-striped (mod-2);
//            2x sram_2048x34_tiled #(TILES=2) -> 4096 deep per lane (BERT
//            longest lane 3561).  Uniform 2048x34 primitive with per-tile
//            CEN gating, so a payload read costs the same energy as the
//            E2-3/E2-4/E2-5 BERT variants (lane-sweep fairness, 2026-09-16).
//
// Decode contract: popcount(mask) <= 2 is guaranteed by the max-2 schedule
// (software exhaustively verified all 16 legal masks x 2 phases = 32 states).
// Implicit EOP: config holds (prog_len-1) real entries; output cycle
// prog_len-1 is a hardware-generated all-NOP + eop=1 (no config/payload read).
// Hold-only output stage. No backpressure. II=1, 3-cycle latency.
// -----------------------------------------------------------------------------

module exp2_two_lane_pool_top_bert (
    input  wire         clk,
    input  wire         rst_n,
    // load port: load_sel 0 = config macro, 1..2 = payload lane 0..1
    input  wire         load_en,
    input  wire [2:0]   load_sel,
    input  wire [14:0]  load_addr,
    input  wire [33:0]  load_wdata,   // config uses [4:0]
    // run control: program descriptor
    input  wire         start,
    input  wire [14:0]  cfg_base,
    input  wire [14:0]  prog_len,     // total output cycles T (incl. implicit EOP)
    input  wire [14:0]  lane_base0,
    input  wire [14:0]  lane_base1,
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
    wire [33:0] lane0_rdata, lane1_rdata;

    // ------------------------------------------------------------------
    // Stage B: mask decode -> two lane enables; phase/pointer pipeline regs.
    //   lane i carries rank (i - phase) mod 2; enabled iff rank < popcount.
    //   popcount <= 2 is a schedule contract (max-2); the mod-2 update below
    //   is a single conditional subtract, valid for phase+popcount <= 3.
    // ------------------------------------------------------------------
    reg         phase_q;
    reg  [14:0] ptr0, ptr1;
    reg         c_vld;
    reg         c_eop;
    reg  [4:0]  mask_c;
    reg         phase_c;

    wire [4:0]  mask_w   = cfg_rdata;

    // popcount (0..5, 3-bit; <=2 for legal schedules)
    wire [2:0]  pcnt = {2'b00, mask_w[0]} + {2'b00, mask_w[1]}
                     + {2'b00, mask_w[2]} + {2'b00, mask_w[3]}
                     + {2'b00, mask_w[4]};

    // rank of lane i = (i - phase) mod 2:  rk0 = phase, rk1 = ~phase
    wire        live = b_vld & ~b_eop;
    wire        en0 = live & ({2'b00, phase_q} < pcnt);
    wire        en1 = live & ({2'b00, ~phase_q} < pcnt);

    // phase update: (phase + popcount) mod 2 is simply the sum LSB
    // (no conditional subtract needed for mod 2)
    wire [2:0]  ph_sum  = {2'b00, phase_q} + pcnt;
    wire        ph_next = ph_sum[0];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase_q <= 1'b0;
            ptr0 <= 15'd0; ptr1 <= 15'd0;
            c_vld   <= 1'b0; c_eop <= 1'b0; mask_c <= 5'b0; phase_c <= 1'b0;
        end else if (start) begin
            phase_q <= 1'b0;
            ptr0 <= lane_base0; ptr1 <= lane_base1;
            c_vld   <= 1'b0; c_eop <= 1'b0; mask_c <= 5'b0; phase_c <= 1'b0;
        end else begin
            c_vld   <= b_vld;
            c_eop   <= b_eop;
            phase_c <= phase_q;
            if (live) begin
                mask_c  <= mask_w;
                phase_q <= ph_next;
                if (en0) ptr0 <= ptr0 + 15'd1;
                if (en1) ptr1 <= ptr1 + 15'd1;
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
    wire [12:0] cfg_addr  = load_en ? load_addr[12:0] : cfg_pc[12:0];
    wire [4:0]  cfg_wdata = load_wdata[4:0];
    wire [4:0]  cfg_wmask = 5'b11111;

    wire        lane0_cen = load_en ? (load_sel == 3'd1) : en0;
    wire        lane1_cen = load_en ? (load_sel == 3'd2) : en1;
    wire        lane0_wen = load_en & (load_sel == 3'd1);
    wire        lane1_wen = load_en & (load_sel == 3'd2);
    wire [11:0] lane0_addr = load_en ? load_addr[11:0] : ptr0[11:0];
    wire [11:0] lane1_addr = load_en ? load_addr[11:0] : ptr1[11:0];
    wire [33:0] lane_wmask = {34{1'b1}};

    sram_8192x5_wrapper u_cfg (
        .clk(clk), .cen(cfg_cen), .wen(cfg_wen), .addr(cfg_addr),
        .wdata(cfg_wdata), .wmask(cfg_wmask), .rdata(cfg_rdata)
    );

    sram_2048x34_tiled #(.TILES(2)) u_lane0 (
        .clk(clk), .cen(lane0_cen), .wen(lane0_wen), .addr(lane0_addr),
        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane0_rdata));
    sram_2048x34_tiled #(.TILES(2)) u_lane1 (
        .clk(clk), .cen(lane1_cen), .wen(lane1_wen), .addr(lane1_addr),
        .wdata(load_wdata), .wmask(lane_wmask), .rdata(lane1_rdata));

    // ------------------------------------------------------------------
    // Stage C: 2:1 scatter (selects from mask_c/phase_c registers) + hold.
    //   slot s with prefix rank r reads lane (phase_c + r) mod 2
    //   = phase_c ^ r[0].
    // ------------------------------------------------------------------
    wire [2:0]  c_pre1 = {2'b00, mask_c[0]};
    wire [2:0]  c_pre2 = c_pre1 + {2'b00, mask_c[1]};
    wire [2:0]  c_pre3 = c_pre2 + {2'b00, mask_c[2]};
    wire [2:0]  c_pre4 = c_pre3 + {2'b00, mask_c[3]};

    wire        sel0 = phase_c;
    wire        sel1 = phase_c ^ c_pre1[0];
    wire        sel2 = phase_c ^ c_pre2[0];
    wire        sel3 = phase_c ^ c_pre3[0];
    wire        sel4 = phase_c ^ c_pre4[0];

    wire [33:0] data0 = lane0_rdata;
    wire [33:0] data1 = lane1_rdata;

    wire [33:0] sc_load   = sel0 ? data1 : data0;
    wire [33:0] sc_store  = sel1 ? data1 : data0;
    wire [33:0] sc_vector = sel2 ? data1 : data0;
    wire [33:0] sc_scalar = sel3 ? data1 : data0;
    wire [33:0] sc_sfu    = sel4 ? data1 : data0;

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

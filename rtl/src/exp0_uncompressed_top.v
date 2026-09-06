`timescale 1ns/1ps
`default_nettype none

// -----------------------------------------------------------------------------
// E0: 171-bit uncompressed instruction-supply top (rtl/plan.md section 5.1)
//
// Storage: 1x sram_8192x171_wrapper; word = {LOAD, STORE, VECTOR, SCALAR, SFU,
// EOP} (5 x 34-bit slots + 1-bit EOP).
//
// Pipeline (II=1, 2-cycle latency):
//   stage A: pc_q drives the macro address (registered input discipline,
//            matching sram_*_timing_check);
//   stage B: Q is captured into the field output registers.
//
// Low-toggle output stage (plan.md section 3.4), common to all five schemes:
//   slot valid   -> all its field registers load the new payload fields;
//   slot invalid -> only its OP field register is cleared to 0 (NOP),
//                   other field registers hold their last valid value.
//   HOLD_EN=0 degenerates to plain load-every-cycle (raw baseline caliber).
// No backpressure: after start, one instruction is dispatched every cycle.
// -----------------------------------------------------------------------------

module exp0_uncompressed_top #(
    parameter HOLD_EN = 1
) (
    input  wire         clk,
    input  wire         rst_n,
    // load port: load_en=1 -> SRAM port owned by the loader (tb)
    input  wire         load_en,
    input  wire [12:0]  load_addr,
    input  wire [170:0] load_wdata,
    // run control
    input  wire         start,        // pulse: latch the descriptor and start
    input  wire [12:0]  prog_base,    // program descriptor: base address in the macro
    input  wire [13:0]  prog_len,     // program descriptor: cycles T (incl. EOP word)
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
    // Fetch control (stage A): pc_q is the macro address register.
    // The program descriptor {prog_base, prog_len} is latched at start, so
    // one loaded image (program pool) can be run program by program.
    // ------------------------------------------------------------------
    reg         run_q;      // fetching in progress
    reg  [13:0] pc_q;       // instruction address (uses [12:0] into the macro)
    reg         rd_vld_q;   // a read is being presented this cycle
    reg  [13:0] base_q;     // latched descriptor
    reg  [13:0] len_q;
    wire [13:0] last_addr = base_q + len_q - 14'd1;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            run_q    <= 1'b0;
            pc_q     <= 14'd0;
            rd_vld_q <= 1'b0;
            base_q   <= 14'd0;
            len_q    <= 14'd0;
        end else if (load_en) begin
            rd_vld_q <= 1'b0;               // loader owns the macro
        end else if (start) begin
            run_q    <= 1'b1;
            base_q   <= {1'b0, prog_base};
            len_q    <= prog_len;
            pc_q     <= {1'b0, prog_base};
            rd_vld_q <= 1'b1;               // first read (base) next cycle
        end else if (run_q) begin
            pc_q     <= pc_q + 14'd1;
            // next cycle keeps reading unless this cycle presented the last word
            rd_vld_q <= (pc_q != last_addr);
            if (pc_q == last_addr) begin
                run_q <= 1'b0;              // last read presented this cycle
            end
        end else begin
            rd_vld_q <= 1'b0;
        end
    end

    // ------------------------------------------------------------------
    // SRAM port mux (loader vs fetch engine) and macro instantiation.
    // All macro inputs are register-sourced; the optional input delay
    // mirrors the timing_check discipline for real-macro timing sims.
    // ------------------------------------------------------------------
    wire         mem_cen   = load_en | rd_vld_q;
    wire         mem_wen   = load_en;
    wire [12:0]  mem_addr  = load_en ? load_addr : pc_q[12:0];
    wire [170:0] mem_wdata = load_wdata;
    wire [170:0] mem_wmask = {171{1'b1}};
    wire [170:0] mem_rdata;

`ifdef SRAM_TIMING_SIM_INPUT_DELAY
    wire         w_cen;  wire         w_wen;   wire [12:0]  w_addr;
    wire [170:0] w_wdata; wire [170:0] w_wmask;
    assign #0.120 w_cen   = mem_cen;
    assign #0.120 w_wen   = mem_wen;
    assign #0.120 w_addr  = mem_addr;
    assign #0.120 w_wdata = mem_wdata;
    assign #0.120 w_wmask = mem_wmask;
`else
    wire         w_cen   = mem_cen;
    wire         w_wen   = mem_wen;
    wire [12:0]  w_addr  = mem_addr;
    wire [170:0] w_wdata = mem_wdata;
    wire [170:0] w_wmask = mem_wmask;
`endif

    sram_8192x171_wrapper u_imem (
        .clk   (clk),
        .cen   (w_cen),
        .wen   (w_wen),
        .addr  (w_addr),
        .wdata (w_wdata),
        .wmask (w_wmask),
        .rdata (mem_rdata)
    );

    // ------------------------------------------------------------------
    // Stage B: capture Q into the field output registers (hold semantics).
    // ------------------------------------------------------------------
    wire [33:0] c_load   = mem_rdata[170:137];
    wire [33:0] c_store  = mem_rdata[136:103];
    wire [33:0] c_vector = mem_rdata[102:69];
    wire [33:0] c_scalar = mem_rdata[68:35];
    wire [33:0] c_sfu    = mem_rdata[34:1];
    wire        q_eop    = mem_rdata[0];

    // NOP detection: an all-zero container is an invalid slot
    wire        sel_load   = |c_load;
    wire        sel_store  = |c_store;
    wire        sel_vector = |c_vector;
    wire        sel_scalar = |c_scalar;
    wire        sel_sfu    = |c_sfu;

    reg cap_vld_q;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cap_vld_q   <= 1'b0;
            slot_valid  <= 1'b0;
            eop         <= 1'b0;
            done        <= 1'b0;
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
            cap_vld_q  <= 1'b0;
            slot_valid <= 1'b0;
            eop        <= 1'b0;
            done       <= 1'b0;
        end else begin
            cap_vld_q  <= rd_vld_q;
            slot_valid <= cap_vld_q;
            if (cap_vld_q) begin
                eop <= q_eop;
                if (q_eop) begin
                    done <= 1'b1;
                end
                // LOAD
                if (!HOLD_EN || sel_load) begin
                    load_mem_fmt  <= c_load[25:24];
                    load_mem_addr <= c_load[31:12];
                    load_gpr_fmt  <= c_load[11:10];
                    load_gpr_addr <= c_load[9:2];
                    load_optype   <= c_load[1:0];
                end else begin
                    load_optype   <= 2'b00;
                end
                // STORE
                if (!HOLD_EN || sel_store) begin
                    store_mem_fmt  <= c_store[25:24];
                    store_mem_addr <= c_store[31:12];
                    store_gpr_fmt  <= c_store[11:10];
                    store_gpr_addr <= c_store[9:2];
                    store_optype   <= c_store[1:0];
                end else begin
                    store_optype   <= 2'b00;
                end
                // VECTOR
                if (!HOLD_EN || sel_vector) begin
                    vector_half    <= c_vector[33:32];
                    vector_imm     <= c_vector[31];
                    vector_connect <= c_vector[30:29];
                    vector_dst     <= c_vector[28:21];
                    vector_src1    <= c_vector[20:13];
                    vector_src0    <= c_vector[12:5];
                    vector_mask    <= c_vector[4];
                    vector_optype  <= c_vector[3:0];
                end else begin
                    vector_optype  <= 4'b0000;
                end
                // SCALAR
                if (!HOLD_EN || sel_scalar) begin
                    scalar_imm     <= c_scalar[30];
                    scalar_connect <= c_scalar[29];
                    scalar_dst     <= c_scalar[28:21];
                    scalar_src1    <= c_scalar[20:13];
                    scalar_src0    <= c_scalar[12:5];
                    scalar_mask    <= c_scalar[4];
                    scalar_optype  <= c_scalar[3:0];
                end else begin
                    scalar_optype  <= 4'b0000;
                end
                // SFU
                if (!HOLD_EN || sel_sfu) begin
                    sfu_borrow     <= c_sfu[30:29];
                    sfu_dst        <= c_sfu[28:21];
                    sfu_src        <= c_sfu[20:13];
                    sfu_is_vector  <= c_sfu[12];
                    sfu_rounds     <= c_sfu[11:4];
                    sfu_optype     <= c_sfu[3:0];
                end else begin
                    sfu_optype     <= 4'b0000;
                end
            end
        end
    end

endmodule

`default_nettype wire

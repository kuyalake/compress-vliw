# ----------------------------------------------------------------------
# run_e0_modelsim.do -- E0 regression under ModelSim/Questa (Windows GUI OK)
#
# Usage in the ModelSim transcript (any current directory):
#   do {C:/path/to/compress-vliw/rtl/sim/run_e0_modelsim.do}
# or via menu: Tools -> TCL -> Execute Macro... and pick this file.
#
# What it does: compile once, then run 3 cases x HOLD_EN={1,0},
# invoking the Python bit-exact checker after each run (if python exists).
# ----------------------------------------------------------------------

# ---- locate rtl/ from this script's own path (cwd-independent) ----
set script_path [info script]
if {$script_path eq ""} {
    set script_dir [pwd]
} else {
    set script_dir [file dirname [file normalize $script_path]]
}
set RTL_DIR [file normalize [file join $script_dir ..]]
puts "RTL_DIR = $RTL_DIR"

# ---- build ----
set BUILD [file join $RTL_DIR out modelsim_build]
file mkdir $BUILD
cd $BUILD
if {[file exists [file join $BUILD work]]} {
    vdel -all
}
vlib work

# Functional run: UNIT_DELAY skips the macro timing checks (fast, quiet).
# For a timing-checked run: remove UNIT_DELAY, keep SRAM_TIMING_SIM_INPUT_DELAY.
vlog +define+UNIT_DELAY +define+SRAM_TIMING_SIM_INPUT_DELAY \
    [file join $RTL_DIR src ts1n28hpcphvtb8192x144m4swbasod_180a_ffg0p88v0p99v0c.v] \
    [file join $RTL_DIR src ts1n28hpcphvtb8192x27m4swbasod_180a_ffg0p88v0p99v0c.v] \
    [file join $RTL_DIR src sram_8192x171_wrapper.v] \
    [file join $RTL_DIR src exp0_uncompressed_top.v] \
    [file join $RTL_DIR sim tb_exp0_uncompressed.v]

# ---- python checker (optional) ----
set PY ""
if {![catch {exec python3 --version}]} { set PY python3 }
if {$PY eq "" && ![catch {exec python --version}]} { set PY python }
if {$PY eq ""} {
    puts "WARNING: python not found on PATH; skipping automatic checks."
    puts "         run rtl/tools/check_rtl_output.py manually afterwards."
}

# ---- run loop: 2 calibers x (3 single cases + 1 pool run) ----
foreach hold {1 0} {
    if {$hold == 1} {
        set golden "golden_issue5.txt"
        set tag "e0"
        set rawflag ""
    } else {
        set golden "golden_raw_issue5.txt"
        set tag "e0_raw"
        set rawflag "--raw"
    }
    foreach case {softmax_x64 layernorm_x64 gelu_x64} {
        set data_dir [file join $RTL_DIR data $case]
        set out_dir  [file join $RTL_DIR out $case]
        file mkdir $out_dir
        set out_file [file join $out_dir rtl_out_${tag}.txt]

        puts "=== $case HOLD_EN=$hold ==="
        vsim -onfinish stop -GHOLD_EN=$hold work.tb_exp0_uncompressed \
            "+DATA=$data_dir" "+OUT=$out_file"
        run -all
        quit -sim

        if {$PY ne ""} {
            catch {exec $PY [file join $RTL_DIR tools check_rtl_output.py] \
                --rtl $out_file \
                --golden [file join $data_dir $golden] \
                --case "$case(HOLD_EN=$hold)"} result
            puts $result
        }
    }

    # ---- program-pool run: one image loaded once, descriptor switching ----
    set pool_out_dir [file join $RTL_DIR out pool]
    file mkdir $pool_out_dir
    set pool_out [file join $pool_out_dir rtl_out_e0_pool_hold${hold}.txt]
    puts "=== POOL HOLD_EN=$hold ==="
    vsim -onfinish stop -GHOLD_EN=$hold work.tb_exp0_uncompressed \
        +POOL=1 "+DATA=[file join $RTL_DIR data]" "+OUT=$pool_out"
    run -all
    quit -sim

    if {$PY ne ""} {
        catch {exec $PY [file join $RTL_DIR tools check_rtl_output.py] --pool \
            --rtl $pool_out \
            --map [file join $RTL_DIR data e0_pool_map.txt] \
            --data [file join $RTL_DIR data] {*}$rawflag} result
        puts $result
    }
}
puts "=== E0 regression done ==="

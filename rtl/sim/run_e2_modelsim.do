# ----------------------------------------------------------------------
# run_e2_modelsim.do -- E2 (adaptive 4-slot) pool regression, ModelSim/Questa
# Windows GUI friendly: self-locating, any current directory.
#
# Usage in the ModelSim transcript:
#   do {C:/path/to/compress-vliw/rtl/sim/run_e2_modelsim.do}
# or: Tools -> TCL -> Execute Macro... and pick this file.
# ----------------------------------------------------------------------

set script_path [info script]
if {$script_path eq ""} {
    set script_dir [pwd]
} else {
    set script_dir [file dirname [file normalize $script_path]]
}
set RTL_DIR [file normalize [file join $script_dir ..]]
puts "RTL_DIR = $RTL_DIR"

set BUILD [file join $RTL_DIR out modelsim_build_e2]
file mkdir $BUILD
cd $BUILD
if {[file exists [file join $BUILD work]]} {
    vdel -all
}
vlib work

vlog +define+UNIT_DELAY \
    [file join $RTL_DIR src ts1n28hpcphvtb8192x5m8swbasod_180a_ffg0p88v0p99v0c.v] \
    [file join $RTL_DIR src ts1n28hpcphvtb2048x34m8swbasod_180a_ffg0p88v0p99v0c.v] \
    [file join $RTL_DIR src sram_8192x5_wrapper.v] \
    [file join $RTL_DIR src sram_2048x34_wrapper.v] \
    [file join $RTL_DIR src exp2_adaptive_4slot_top.v] \
    [file join $RTL_DIR sim tb_exp2_adaptive_4slot.v]

set PY ""
if {![catch {exec python3 --version}]} { set PY python3 }
if {$PY eq "" && ![catch {exec python --version}]} { set PY python }
if {$PY eq ""} {
    puts "WARNING: python not found on PATH; skipping automatic checks."
}

set pool_out_dir [file join $RTL_DIR out pool]
file mkdir $pool_out_dir
set pool_out [file join $pool_out_dir rtl_out_e2_pool.txt]

puts "=== E2 POOL (hold-only) ==="
vsim -onfinish stop work.tb_exp2_adaptive_4slot \
    "+DATA=[file join $RTL_DIR data]" "+OUT=$pool_out"
run -all
quit -sim

if {$PY ne ""} {
    catch {exec $PY [file join $RTL_DIR tools check_rtl_output.py] --pool \
        --rtl $pool_out \
        --map [file join $RTL_DIR data e2_pool_map.txt] \
        --data [file join $RTL_DIR data] \
        --golden-name golden_issue4.txt} result
    puts $result
}
puts "=== E2 regression done ==="

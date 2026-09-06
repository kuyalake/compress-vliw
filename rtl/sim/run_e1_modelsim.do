# ----------------------------------------------------------------------
# run_e1_modelsim.do -- E1 (Candidate A) pool regression, ModelSim/Questa
# Windows GUI friendly: self-locating, any current directory.
#
# Usage in the ModelSim transcript:
#   do {C:/path/to/compress-vliw/rtl/sim/run_e1_modelsim.do}
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

set BUILD [file join $RTL_DIR out modelsim_build_e1]
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
    [file join $RTL_DIR src exp1_candidate_a_top.v] \
    [file join $RTL_DIR sim tb_exp1_candidate_a.v]

set PY ""
if {![catch {exec python3 --version}]} { set PY python3 }
if {$PY eq "" && ![catch {exec python --version}]} { set PY python }
if {$PY eq ""} {
    puts "WARNING: python not found on PATH; skipping automatic checks."
}

set pool_out_dir [file join $RTL_DIR out pool]
file mkdir $pool_out_dir
set pool_out [file join $pool_out_dir rtl_out_e1_pool.txt]

puts "=== E1 POOL (HOLD_EN=1) ==="
vsim -onfinish stop work.tb_exp1_candidate_a \
    "+DATA=[file join $RTL_DIR data]" "+OUT=$pool_out"
run -all
quit -sim

if {$PY ne ""} {
    catch {exec $PY [file join $RTL_DIR tools check_rtl_output.py] --pool \
        --rtl $pool_out \
        --map [file join $RTL_DIR data e1_pool_map.txt] \
        --data [file join $RTL_DIR data]} result
    puts $result
}
puts "=== E1 regression done ==="

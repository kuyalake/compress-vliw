# ----------------------------------------------------------------------
# run_e3_modelsim.do -- E3 (2slot2lane) pool regression, ModelSim/Questa
# Windows GUI friendly: self-locating, any current directory.
#
# Usage in the ModelSim transcript:
#   do {C:/path/to/compress-vliw/rtl/sim/run_e3_modelsim.do}
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

set BUILD [file join $RTL_DIR out modelsim_build_e3]
file mkdir $BUILD
cd $BUILD
if {[file exists [file join $BUILD work]]} {
    vdel -all
}
vlib work

vlog +define+UNIT_DELAY \
    [file join $RTL_DIR src ts1n28hpcphvtb8192x5m8swbasod_180a_ffg0p88v0p99v0c.v] \
    [file join $RTL_DIR src ts1n28hpcphvtb4096x34m8swbasod_180a_ffg0p88v0p99v0c.v] \
    [file join $RTL_DIR src sram_8192x5_wrapper.v] \
    [file join $RTL_DIR src sram_4096x34_wrapper.v] \
    [file join $RTL_DIR src cfg_pair_codebook.v] \
    [file join $RTL_DIR src exp3_2slot2lane_top.v] \
    [file join $RTL_DIR sim tb_exp3_2slot2lane.v]

set PY ""
if {![catch {exec python3 --version}]} { set PY python3 }
if {$PY eq "" && ![catch {exec python --version}]} { set PY python }
if {$PY eq ""} {
    puts "WARNING: python not found on PATH; skipping automatic checks."
}

set pool_out_dir [file join $RTL_DIR out pool]
file mkdir $pool_out_dir
set pool_out [file join $pool_out_dir rtl_out_e3_pool.txt]

puts "=== E3 POOL (hold-only) ==="
vsim -onfinish stop work.tb_exp3_2slot2lane \
    "+DATA=[file join $RTL_DIR data]" "+OUT=$pool_out"
run -all
quit -sim

if {$PY ne ""} {
    catch {exec $PY [file join $RTL_DIR tools check_rtl_output.py] --pool \
        --rtl $pool_out \
        --map [file join $RTL_DIR data e3_pool_map.txt] \
        --data [file join $RTL_DIR data] \
        --golden-name golden_issue2.txt} result
    puts $result
}
puts "=== E3 regression done ==="

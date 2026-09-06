# 最简 E0 仿真（单程序 softmax_x64）。
# 用法：只改下面第一行为你的文件夹路径，把 8 个文件放进去，然后 do 本文件。
# （不需要先 cd；全部用绝对路径。）
set DIR "D:/e0"

cd $DIR
vlib work
vlog +define+UNIT_DELAY \
  $DIR/ts1n28hpcphvtb8192x144m4swbasod_180a_ffg0p88v0p99v0c.v \
  $DIR/ts1n28hpcphvtb8192x27m4swbasod_180a_ffg0p88v0p99v0c.v \
  $DIR/sram_8192x171_wrapper.v \
  $DIR/exp0_uncompressed_top.v \
  $DIR/tb_exp0_uncompressed.v
vsim -onfinish stop work.tb_exp0_uncompressed "+DATA=$DIR" "+OUT=$DIR/rtl_out.txt"
run -all

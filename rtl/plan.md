# 第一批硬件实验 RTL 计划：指令 Fetch/Decode 顶层

日期：2026-09-06 ｜ 范围：171bit 无压缩、Candidate A、4slot、2slot2lane、2slot4lane 五个实验的取指+解码顶层、testbench 与校验脚本

---

## 1. 目标与实验对象

为五种指令存储/供给组织分别实现**顶层模块（指令 fetch + 解码）**，要求：

- 逐周期恢复五槽 VLIW 字段，**接口输出为各字段（field-level），寄存器输出**；
- **统一低翻转输出级**（沿用既有 plan §8/§13 设计）：槽有效时全部字段装载新 payload；槽无效时**仅 OP 字段清 0（NOP），其余字段保持上一有效值**——五方案（含 E0/E1）全部启用，属正交公共优化，不计入任何单一方案收益。**E1–E4 只实现保持口径（无 HOLD_EN 参数）；仅 E0 保留 HOLD_EN 双口径**用于论文消融（忠实再现原平台）；
- 每拍一条指令（II=1，零停顿供给），自由运行，**无背压**；
- 复用已生成并经 28nm 综合的 SRAM wrapper（`rtl/src/sram_*_wrapper.v`）；
- 每个实验配独立 testbench + Python 解码校验脚本，按「保持语义 golden」逐周期逐 bit 比对（见 §6）。

| 实验 | 模块名 | Config 存储 | Payload 存储 | Config 语义 |
|---|---|---|---|---|
| E0 无压缩 | `exp0_uncompressed_top` | — | 1× `sram_8192x171` | 无 config，整字直读 |
| E1 A baseline | `exp1_candidate_a_top` | 1× `sram_8192x5` | 5× `sram_2048x34`（每槽专属） | 5-bit 槽有效 mask，EOP 由程序长度隐式产生 |
| E2 4slot | `exp2_adaptive_4slot_top` | 1× `sram_8192x5` | 4× `sram_2048x34`（共享 Lane） | 5-bit mask + phase 条带化，带内 EOP=`11111` |
| E3 2slot2lane | `exp3_2slot2lane_top` | 1× `sram_8192x5` | 2× `sram_4096x34` | 5-bit (slot0,slot1) 对码，EOP=`11111`(31) |
| E4 2slot4lane | `exp4_2slot4lane_top` | 1× `sram_8192x6` | 4× `sram_2048x34` | 6-bit {group, 对码}，EOP=`111111`(63) |

**工作负载（第一批）**：softmax_x64 (Y=512)、layernorm_x64 (Y=768)、gelu_x64 (Y=3072)；
调度参数 `NUM_VE=256, VGPR_CAP=256, SGPR_CAP=256, MASK_FIFO=8, RQo=32/16/16`，
优先级策略统一 `PRIORITY_STRATEGY="index"`。

**三个调度族**（族内共享同一份 schedule；跨族周期分别报告）：

- **max-5 族**（E0/E1）：`MAX_ISSUE_SLOTS=5`，原生调度。注意 layernorm_x64 含 3 拍 5 槽同发（mask=`11111`），E1 的隐式 EOP 结构必须能正确处理——本批即会覆盖该边界。
- **max-4 族**（E2）：`MAX_ISSUE_SLOTS=4`。4slot 不能编码 5 槽同拍，故单独一族；已有数据表明其总周期与 max-5 相同，但逐拍槽内容不同，golden 独立生成。
- **max-2 族**（E3/E4）：`MAX_ISSUE_SLOTS=2`。

mode 选择沿用既有惯例：每 case 在 index 优先级下取候选 mode 中周期最短者（softmax 比较 mode 0/1/2；layernorm 固定 mode 0；gelu 固定 mode 2），由数据准备脚本自动完成并记录。

---

## 2. 指令格式真值（所有实验共用）

源文件：`schedule_v19_issue2_priority_174.py`（`MEM_ADDR_BITS=20`，`VLIW_BITS=174`）。

**174-bit 调度字**（`schedule.txt` 每行 44 hex = 176 bit，高 2 bit 恒 0）：

```
[173:140] LOAD    34b
[139:106] STORE   34b
[105:72]  VECTOR  34b
[71:38]   SCALAR  34b
[37:4]    SFU     34b
[3:1]     reserved 3b（恒 0）
[0]       EOP
```

**171-bit 无压缩字 = 5×34b 功能槽 + 1b EOP**（去掉 3 个保留位）：

```
[170:137] LOAD ｜ [136:103] STORE ｜ [102:69] VECTOR ｜ [68:35] SCALAR ｜ [34:1] SFU ｜ [0] EOP
```

槽内字段布局（仅供文档参考；**fetch/decode 硬件把槽当作不透明 34-bit payload，不解释字段**）：

| 槽 | 字段（高位→低位） | 备注 |
|---|---|---|
| LOAD/STORE | mem_fmt(2)@<<24, mem_addr(20)@<<12, gpr_fmt(2), gpr_addr(8), optype(2) | [33:32] 未用；mem_fmt 与 mem_addr 名义打包在 [25:24] 相邻/交叠，当前 trace mem_addr≤767 不受影响 |
| VECTOR | half(2), imm(1), connect(2), dst/src1/src0(8×3), mask(1), optype(4) | 34b 用满 |
| SCALAR | imm(1)@30, connect(1)@29, dst/src1/src0, mask, optype(4) | [33:31] 未用 |
| SFU | borrow(2)@30:29, dst, src, is_vector@12, rounds(8)@11:4, optype(4) | [33:31] 未用 |

**NOP 语义（区分存储侧与输出侧）**：

- **存储侧**（schedule.txt / SRAM 中的容器）：NOP 槽 = 34-bit 全 0；各槽 opcode 表中 optype=0 即 nop，有效操作的 optype 必非 0，故 `容器==0` 与 `optype==0` 等价。
- **输出侧**（顶层接口）：无效槽输出 `optype=0`（下游据此判 NOP），**其余字段保持上一有效值**（低翻转设计，见 §3.4）。因此下游只依据 OP 字段判 NOP，保持的字段值不参与执行。

**槽号约定**（编码/解码一致）：LOAD=0, STORE=1, VECTOR=2, SCALAR=3, SFU=4。

---

## 3. 统一硬件约定

### 3.1 SRAM 时序纪律（与 `rtl/src/sram_*_timing_check.v` 一致）

- TSMC 28nm 同步单口宏：`CEB/WEB/A` 在读采样沿被采样，`Q` 于该沿后 tCD 有效；`CEB=1`（不使能）时 `Q` **保持**上一次读结果。
- **所有宏输入一律由寄存器驱动**（地址级），`Q` 在下一拍被捕获（捕获级）。一次宏读 = 地址拍 + 数据拍。
- 顶层直接例化 `sram_*_wrapper`（非 timing_check）；timing_check 模块保留为宏级时序签收载体。顶层对宏输入的寄存纪律与 timing_check 相同，因此时序仿真可直接复用 `SRAM_TIMING_SIM_INPUT_DELAY=0.120ns` 模型。
- 目标频率沿用原平台 1 GHz；逻辑约束最重的两条路径见 §5.7。

### 3.2 统一顶层接口

```verilog
module expN_xxx_top (
    input  wire        clk,
    input  wire        rst_n,
    // 装载口（tb/烧录用）：load_en=1 时 SRAM 端口归装载器
    input  wire        load_en,
    input  wire        load_sel,     // 多宏方案选择目标宏（位宽按方案定）
    input  wire [12:0] load_addr,
    input  wire [170:0] load_wdata,  // 按最宽宏（171b）对齐，窄宏取低位
    // 运行控制
    input  wire        start,        // 脉冲：锁存描述符并开始取指
    input  wire [12:0] prog_base,    // 程序描述符：宏内基址
    input  wire [13:0] prog_len,     // 程序描述符：总拍数 T（含 EOP 拍）
    // ---- 逐周期字段级寄存器输出（低翻转保持语义，见 §3.4）----
    // LOAD 槽字段
    output reg  [1:0]  load_mem_fmt,
    output reg  [19:0] load_mem_addr,
    output reg  [1:0]  load_gpr_fmt,
    output reg  [7:0]  load_gpr_addr,
    output reg  [1:0]  load_optype,
    // STORE 槽字段
    output reg  [1:0]  store_mem_fmt,
    output reg  [19:0] store_mem_addr,
    output reg  [1:0]  store_gpr_fmt,
    output reg  [7:0]  store_gpr_addr,
    output reg  [1:0]  store_optype,
    // VECTOR 槽字段
    output reg  [1:0]  vector_half,
    output reg         vector_imm,
    output reg  [1:0]  vector_connect,
    output reg  [7:0]  vector_dst,
    output reg  [7:0]  vector_src1,
    output reg  [7:0]  vector_src0,
    output reg         vector_mask,
    output reg  [3:0]  vector_optype,
    // SCALAR 槽字段
    output reg         scalar_imm,
    output reg         scalar_connect,
    output reg  [7:0]  scalar_dst,
    output reg  [7:0]  scalar_src1,
    output reg  [7:0]  scalar_src0,
    output reg         scalar_mask,
    output reg  [3:0]  scalar_optype,
    // SFU 槽字段
    output reg  [1:0]  sfu_borrow,
    output reg  [7:0]  sfu_dst,
    output reg  [7:0]  sfu_src,
    output reg         sfu_is_vector,
    output reg  [7:0]  sfu_rounds,
    output reg  [3:0]  sfu_optype,
    // 控制
    output reg         slot_valid,   // 本拍输出构成一条有效指令
    output reg         eop,          // 最后一条指令
    output reg         done
);
```

字段在 34-bit 容器内的打包/解包公式（与编码器逐一对应，RTL 与 golden 共用）：

| 槽 | 字段提取（c = 34-bit 容器） | OP 字段位置 |
|---|---|---|
| LOAD/STORE | `optype=c[1:0]`，`gpr_addr=c[9:2]`，`gpr_fmt=c[11:10]`，`mem_addr=c[31:12]`，`mem_fmt=c[25:24]` | [1:0] |
| VECTOR | `optype=c[3:0]`，`mask=c[4]`，`src0=c[12:5]`，`src1=c[20:13]`，`dst=c[28:21]`，`connect=c[30:29]`，`imm=c[31]`，`half=c[33:32]` | [3:0] |
| SCALAR | `optype=c[3:0]`，`mask=c[4]`，`src0=c[12:5]`，`src1=c[20:13]`，`dst=c[28:21]`，`connect=c[29]`，`imm=c[30]`（[33:31] 空闲） | [3:0] |
| SFU | `optype=c[3:0]`，`rounds=c[11:4]`，`is_vector=c[12]`，`src=c[20:13]`，`dst=c[28:21]`，`borrow=c[30:29]`（[33:31] 空闲） | [3:0] |

注意：LOAD/STORE 编码器中 `mem_fmt<<24` 与 `mem_addr<<12` 在 [25:24] 名义交叠；当前 trace mem_addr≤767（<2¹⁰），该两位恒为 mem_fmt，按上式提取精确往返。mem_addr≥4096 时的混叠是调度器侧已知遗留问题（plan 风险表已列），fetch/decode 硬件不解释字段、不受影响。

- **程序池**：`{prog_base, prog_len}` 在 `start` 时锁存进描述符寄存器，PC 从基址开始取指。支持「整池镜像一次装入、逐程序切换运行」（E0 已验证：3 程序共 5515 字一次装入，按非连续顺序 gelu→softmax→layernorm 切换）；逐程序运行时 tb 复位前端（宏无复位引脚、内容保持），golden 按程序独立。
- **无背压**：`start` 后每拍无条件前进，状态每拍更新，直到 EOP 后 `done` 拉高停机。设计不含任何 ready/valid 握手。
- E0 无压缩无 config 宏，`load_sel` 省略；E1 有 6 个宏（1 config + 5 payload），`load_sel` 3 bit；E2/E4 5 个宏、E3 3 个宏。

### 3.3 统一流水线骨架（压缩方案 E1–E4：3 拍延迟，II=1）

核心思想：**config 比 payload 提前一拍取**。每拍同时有三条指令在飞：

| 拍 | 内容 | 说明 |
|---|---|---|
| **A（config 地址）** | `config_addr_reg <= PC` | PC 为已接受指令计数 |
| **B（config 数据 + payload 地址）** | 拍初 config `Q` 有效 → 译码（mask/码本 → 各 Bank 使能）；`mask_reg <= Q`；`payload_cen_reg <= 使能`；`payload_addr_reg <= ptr_next`（**前递新指针**） | 关键路径①：config Q(tCD) → 译码 → payload 输入寄存器建立 |
| **C（payload 数据 + 分发）** | 拍初 payload `Q` 有效 → scatter/mux → 拍末按字段写使能捕获进**字段输出寄存器**（§3.4）；同拍末状态更新：`ptr <= ptr_next`、`phase <= phase_next`、`PC <= PC+1` | 关键路径②：payload Q(tCD) → 4:1 mux → 字段寄存器建立 |

**指针前递（II=1 的关键）**：指令 k 的 payload 地址在拍 B(k) 末捕获，必须等于「指令 k−1 处理后的指针」。在拍 C(k−1)（= 拍 B(k)）内组合计算 `ptr_next = ptr + enable(k−1)`，拍末同时写 `ptr <= ptr_next` 与 `payload_addr_reg <= ptr_next`，两处使用同一组合结果，无冒险。无背压后该前递每拍无条件发生，逻辑进一步简化。

E0 无压缩为 2 拍：拍 A `addr_reg <= PC`；拍 B 宏 `Q` 有效，拍末按位切分捕获进 6 个输出寄存器（纯连线，捕获寄存器即输出寄存器）。

**周期计数口径**：跨方案比较周期数时以「指令拍」（accepted cycle）计，流水线填充延迟（2–3 拍）不计入，与软件研究的周期口径一致。

### 3.4 统一低翻转输出级（五方案公共，沿用既有 plan 设计）

每个槽一套**带字段写使能的输出寄存器**，`selected[s]` 为本拍该槽有效（来源因方案而异，见 §5）：

```
selected[s] = 1：该槽全部字段寄存器 ← 新 payload 的对应字段（含 OP）
selected[s] = 0：非 OP 字段寄存器保持（写使能关断）；OP 字段寄存器 ← 0
```

- OP 字段寄存器**每拍都写**（新 OP 或 0），非 OP 字段寄存器带使能（仅有效拍写）——无效周期只有 OP 总线翻转，地址/操作数/控制字段及其下游 Decoder/Crossbar 输入保持不动。既有 12 trace 实测输出总线翻转下降 47.58%。
- 该级对五方案**完全相同**（含 E0），是正交公共优化；比较面积/功耗时五方案都含此级，差额只反映存储/取指组织。
- 复位后全部字段寄存器为 0；EOP 拍五槽均无效（OP 全 0、其余保持）+ `eop=1`。
- 行为等价声明：无效槽的保持字段不参与执行（下游只看 OP），故输出不再与原 trace 逐 bit 相同；golden 按同一保持语义精确生成（§6），校验仍是全字段逐拍逐 bit。
- 成本口径：字段保持寄存器相对普通寄存器每 bit 多 1–2 GE 的使能逻辑，5 槽合计约 +250 GE；五方案公共，不影响相对比较。综合时应对非 OP 字段寄存器组自动识别为时钟门控/使能触发器。
- **论文口径与 `HOLD_EN` 参数**：E0 顶层带 `parameter HOLD_EN = 1`（`HOLD_EN=0` 时字段寄存器退化为每拍直接装载，无效槽输出存储侧全 0 容器），用于论文消融行忠实再现原平台，把总改善分解为 hold 贡献 + 压缩贡献。**E1–E4 顶层只实现保持口径（无 HOLD_EN 参数，2026-09-06 与用户确认）**：压缩方案的无效槽本无存储数据可言，保持语义是唯一良定义行为。hold 属已有技术（TACO 2018），不得主张新颖性；对 E0 启用 hold 是保守方向（压缩收益被低估而非高估）。

---

## 4. 数据准备：`rtl/tools/gen_rtl_streams.py`

每个 case × 每方案生成：SRAM 初始化 memh + golden 参考 + manifest。编码逻辑**直接复用**已验证的实验脚本函数（保证与既有软件研究逐 bit 一致）：

| 方案 | 复用/新增 | 输出文件（每 case） |
|---|---|---|
| E0 | 新增（从 174-bit 字丢 [3:1] 保留位） | `e0_instr171.memh`（43 hex/行）、`golden.txt` |
| E1 | 新增（mask + 每槽事件流，逻辑平凡） | `e1_config5.memh`（T−1 项）、`e1_slot{0..4}.memh`、`golden.txt`；池：`e1_pool_config5.memh`、`e1_pool_slot{0..4}.memh`、`e1_pool_meta.hex`、`e1_pool_map.txt` |
| E2 | 复用 `issue124_adaptive_four_lane_study.encode_rotating_lanes` | `e2_config5.memh`（T 项，末项 `1f`）、`e2_lane{0..3}.memh`、`golden_issue4.txt`（max-4 族 golden）；池：`e2_pool_config5.memh`、`e2_pool_lane{0..3}.memh`、`e2_pool_meta.hex`、`e2_pool_map.txt` |
| E3 | 复用 `issue2_lane_study.encode_two_lane` | `e3_config5.memh`（T 项，末项 `1f`）、`e3_lane{0..1}.memh`、`golden_issue2.txt`（max-2 族 golden）；池：`e3_pool_config5.memh`、`e3_pool_lane{0..1}.memh`、`e3_pool_meta.hex`、`e3_pool_map.txt`；另生成 `rtl/src/cfg_pair_codebook.v` |
| E4 | 复用 `four_lane_mapping_study.encode_program(policy="general_symmetric")` | `e4_config6.memh`（T 项，末项 `3f`）、`e4_lane{0..3}.memh`、`golden_issue2.txt`（与 E3 共用）；池：`e4_pool_config6.memh`、`e4_pool_lane{0..3}.memh`、`e4_pool_meta.hex`、`e4_pool_map.txt` |

另外生成：

- **`rtl/src/cfg_pair_codebook.v`**：E3/E4 共用的 32 项对码译码表（Verilog `case` 语句，**综合为组合逻辑门，不是存储宏**）。E3/E4 的 config 码值本身不直接等于槽号，需要一张「码值 → (lane0 载哪个槽, lane1 载哪个槽)」的逆表；该表在 Python 编码器里由 `build_config_codebook()` 的双重循环枚举隐式定义（码 0=`(None,None)`、码 1=`(None,LOAD)`…码 6=`(LOAD,None)`、码 7=`(LOAD,STORE)`…，顺序完全由枚举循环决定）。若手写 32 项 Verilog `case`，枚举顺序写错一项即静默解码错误。因此由 `gen_rtl_streams.py` 用**同一个枚举循环**把逆表打印成 Verilog 模块（输入 5-bit 码 → 输出 `{valid0, slot0[2:0], valid1, slot1[2:0]}`），编码器与译码器出自同一数据源，机械一致；编码规则变更时重跑脚本即可，禁止手改该文件。综合后约几十~一百 GE，正是既有实验 `config_decode_ge=100`（2-lane）与 `decoder_and_enable=140`（分组四 Lane）的假设对象；本批 RTL 综合将用真实网表替换该占位值。
- **`golden.txt`**：每行 `load store vector scalar sfu eop`（34-bit→9 hex，eop→1 hex）。**直接由原始 `schedule.txt` 生成**（不是任何压缩格式的再解码），并按 §3.4 保持语义做确定性变换：有效槽行 = 原容器；无效槽 = 上一有效容器将 OP 字段清零（LOAD/STORE 清 [1:0]，其余清 [3:0]），复位初值全 0。由此 golden 对 RTL 输出是**精确可预测**的，校验保持逐拍逐 bit，同时覆盖"保持寄存器是否真保持"。
- **`manifest.json`**：每 case 的 mode、T、各流深度、调度参数；tb 据此取 `prog_len`。

脚本内建自检：每种编码生成后立即用对应的软件解码器 roundtrip，与原始 schedule 逐 bit 比对（复用现有脚本断言），全部通过才落盘。

调度来源：调用 `schedule_v19_issue2_priority_174.run_scheduler(...)`，三族分别 `MAX_ISSUE_SLOTS=5 / 4 / 2`，`PRIORITY_STRATEGY="index"`；已有同参数目录（如 `analysis_output_issue2_174_priority/*_index/`、`analysis_output_issue5_174_priority/*_index/`）可复用则复用，否则现场调度（秒级）。

目录约定：
- **所有 Verilog 模块统一放 `rtl/src/`**：各实验顶层（`expN_*_top.v`）、译码表（`cfg_pair_codebook.v`）、SRAM wrapper/timing_check 都在同一目录，**不单独创建 `rtl/top/` 等子目录**（2026-09-06 与用户确认）。
- testbench 与回归脚本放 `rtl/sim/`；数据准备/校验脚本放 `rtl/tools/`。
- 生成数据放 `rtl/data/<case>/`（memh + golden + `manifest.json`，入库）；仿真输出放 `rtl/out/<case>/`。
- 程序池数据放 `rtl/data/`：`e0_pool_instr171.memh`（整池镜像）、`e0_pool_meta.hex`（[N, 总字数, 逐程序 base/len]）、`e0_pool_map.txt`（运行位置→case 映射，供校验脚本）。

---

## 5. 各实验辅助电路生成方法与时序分配

### 5.1 E0 无压缩（`exp0_uncompressed_top`）

- **存储**：1× `sram_8192x171_wrapper`。
- **辅助电路**：13-bit PC（`prog_len` 比较产生 done）+ 5× 34-bit NOR（NOP 检测）+ 公共低翻转输出级。无压缩译码逻辑——这是面积/功耗基线锚点。
- **时序**：2 拍（§3.3）。拍 B 内 `Q` 有效后：按容器切出五槽，`selected[s] = (容器[s] != 0)`（34-bit NOR），拍末按 §3.4 写字段寄存器（有效槽装载字段、无效槽仅 OP 清 0）；`eop <= Q[0]`。NOR34+字段使能加在拍 B 路径上，量级极小。
- **注意**：EOP 字五个功能槽全 0、bit0=1，与 schedule 末行一致；EOP 拍五槽 OP 全 0、其余字段保持，`slot_valid` 与 `eop` 同时拉高。

### 5.2 E1 Candidate A（`exp1_candidate_a_top`）

- **存储**：config 1× `sram_8192x5`；payload 5× `sram_2048x34`（LOAD/STORE/VECTOR/SCALAR/SFU 各一）。
- **辅助电路**：
  1. 13-bit config PC；
  2. **5× 11-bit 槽指针** + 每槽增量器（增量 = mask 对应位）；
  3. Bank 门控：`cen_s = mask[s]`（译码即 mask 本身，无额外逻辑）；
  4. 分发：`selected[s] = mask[s]`；拍 C 末按 §3.4 写字段寄存器——有效槽字段 ← payload_q_s 的对应字段，无效槽仅 OP 清 0（5× 字段级写使能，无数据 mux，专属 Bank 直达）；
  5. **隐式 EOP**：14-bit 已接受指令计数器，`eop = (count == prog_len-1)`；EOP 拍不读 config（config 流仅 T−1 项）、所有 payload `cen=0`、五槽 OP 全 0、其余字段保持。
- **时序**：3 拍骨架（§3.3）。拍 B 译码 = 直连 mask 各位到 5 个 payload 宏 CEN。
- **池与接口（E1 单独接口，2026-09-06 已实现）**：装载口带 `load_sel[2:0]`（0=config，1–5=payload 槽 0–4）；程序描述符 = `{cfg_base, prog_len, slot_base0..4}`（5 个槽基址各 11-bit），`start` 时锁存，槽指针从槽基址起步。池布局：config 宏按 case 顺序连续排放（968+1449+3095=5512 ≤ 8192），每个 payload 宏内按 case 顺序连续排放（LOAD 1094 / STORE 1088 / VECTOR 1856 / SCALAR 640 / SFU 1088 ≤ 2048）。
- **注意**：**mask=`11111` 是合法数据**（A 允许 5 槽同拍），绝不能当 EOP；本批 max-5 调度的 layernorm_x64 即含 3 拍 5 槽同发，该边界会被实际覆盖。EOP 只能由指令计数器 `== prog_len-1` 产生。
- **精确门控校验**（tb 内置）：池运行全程 config 读次数必须 == 5512（=Σ(T−1)），Bank s 读次数必须 == 该槽事件总数（1094/1088/1856/640/1088）——多一次少一次都算错。
- **输出级**：E1 顶层只实现保持语义（无 HOLD_EN 参数）；无效槽 OP 清 0、其余字段保持。

### 5.3 E2 4slot 自适应四 Lane（`exp2_adaptive_4slot_top`）

- **存储**：config 1× `sram_8192x5`；payload 4× `sram_2048x34`（共享 Lane 0–3）。
- **编码规则**（与软件一致）：有效槽按槽号升序排 rank；第 r 个有效事件写入 `lane=(phase+r) mod 4`；拍末 `phase=(phase+popcount(mask)) mod 4`。
- **辅助电路**：
  1. 13-bit config PC；
  2. **2-bit phase 寄存器**；`popcount5`（32×3 ROM 或 5 输入加法树）；`phase_next = (phase + popcount) & 2'b11`；
  3. **4× 11-bit Lane 指针**；Lane 使能 `en(i) = ((i − phase) mod 4) < popcount`（4 个 2-bit 减法和比较，拍 B 内）；
  4. **4→5 散布网络**（拍 C）：槽 s 有效时其源 Lane = `(phase + rank(s)) mod 4`，`rank(s) = popcount(mask & ((1<<s)−1))`（前缀计数，5 个微型逻辑）；`selected[s] = mask[s]`，有效槽字段 ← `lane_q[(phase+rank(s)) mod 4]` 的对应字段（5× 34-bit 4:1 mux 后接 §3.4 字段写使能）；无效槽仅 OP 清 0；
  5. **带内 EOP**：mask=`11111` → 全槽 NOP、eop=1、全部 `cen=0`、phase 保持。
- **时序**：3 拍骨架。关键路径①内含 popcount + mod-4 比较，为该方案主路径；散布 mux 在拍 C（路径②）。
- **已实现细节（2026-09-06，一次通过）**：
  - 拍 B 的前缀 popcount 链（`pre1..pre4`）同时供 popcount（lane 使能）与拍 C 的 rank 计算，不重复造加法器；
  - **phase 以 2-bit 流水线寄存器 `phase_c` 送到拍 C**（而不是寄存 5×2-bit 选择信号，省 8 个 DFF）；拍 C 的选择信号由 `mask_c`/`phase_c`（均为寄存器、拍初即稳）组合产生，与 payload Q 的到达并行，不进关键路径——拍 C 关键路径只剩「宏 Q → 4:1 mux → 字段寄存器」；
  - EOP 在拍 B 从数据发现（`cfg_rdata==11111`）：当拍全部 lane `cen=0`、phase/指针保持、`mask_c<=0`，EOP 标记随流水线到拍 C 置 `eop/done`；
  - config 每程序读 T 项（含 EOP 项），池总读 5515；lane 读精确门控 1442/1442/1441/1441。
- **注意**：编码器已断言无 5 槽同拍（`11111` 不歧义）；`phase` 与 4 个指针是**一组状态**，每拍末必须基于同一份 mask 原子更新（任一寄存器用错一拍的前递值即静默错位）；EOP 拍不得推进 phase/指针。

### 5.4 E3 2slot2lane（`exp3_2slot2lane_top`）

- **存储**：config 1× `sram_8192x5`；payload 2× `sram_4096x34`。
- **Config 码本**（5 bit，31 普通态 + EOP=31）：码值枚举 `(l0,l1)`，`l∈{None,0..4}`，合法条件 `l0==None or l1==None or l0!=l1`；枚举顺序 `l0=None→{None,0..4}` 得码 0–5，`l0=0→{None,1..4}` 得码 6–10，依此类推。语义：lane i 本拍承载槽 li（None=空）。
- **辅助电路**：
  1. 13-bit config PC；
  2. **对码译码表**（`cfg_pair_codebook.v`，脚本生成的 `case`，综合为组合逻辑）：5-bit 码 → `{valid0, slot0[2:0], valid1, slot1[2:0]}`；
  3. **2× 12-bit Lane 指针**（4096 深）；`en(i)=valid_i`，指针按 valid 递增；
  4. 分发（拍 C）：`selected[s] = (valid0 && slot0==s) || (valid1 && slot1==s)`；有效槽字段 ← 对应 Lane 字的字段（5× 34-bit 3:1 mux + 10 个 3-bit 比较器，后接 §3.4 字段写使能）；无效槽仅 OP 清 0；
  5. 带内 EOP：码=31 → 全 NOP + eop。
- **时序**：3 拍骨架；拍 B 关键路径 = config Q → 译码表（约 4–6 级门）→ payload CEN/A。
- **已实现细节（2026-09-06，一次通过）**：拍 B 用脚本生成的 `cfg_pair_codebook` 译出 `{valid0, slot0, valid1, slot1}` 并**寄存 8-bit 译码后控制**送拍 C（拍 C 纯 mux，不进 LUT）；码 31 译码为全无效 → EOP 拍 Lane 自动不读、指针不动；`is_eop` 仅用于产生 eop 标记。池：config 5608（=ΣT 含 EOP 项）、Lane 读 2883/2883 精确门控；max-2 index 周期 996/1516/3096（softmax 在 max-2 下 mode1 最优，与 max-5 的 mode2 不同——按族各自选 mode）。
- **注意**：编码器的「单事件进较浅 Lane」均衡规则只影响编码（流深度均衡），解码端无需感知；码 31 只能出现在末项。

### 5.5 E4 2slot4lane（`exp4_2slot4lane_top`）

- **存储**：config 1× `sram_8192x6`；payload 4× `sram_2048x34`。
- **Config 语义**（6 bit）：`{group[5], local[4:0]}`；local 与 E3 同码本（31 态），group 选择 Lane 对：0→Lane{0,1}，1→Lane{2,3}；物理 Lane = `group*2 + 局部序号`。EOP=`111111`(63)。
- **辅助电路**：
  1. 13-bit config PC；
  2. 与 E3 **共用**对码译码表（local[4:0] 部分）；
  3. **4× 11-bit Lane 指针**；使能 `en(2g)=valid0 & group==g`、`en(2g+1)=valid1 & group==g`；
  4. 分发（拍 C）：`selected[s] = (valid0&&slot0==s) || (valid1&&slot1==s)`；有效槽字段 ← `lane_q[{group,1'b0}]` 或 `lane_q[{group,1'b1}]` 的对应字段（后接 §3.4 字段写使能）；无效槽仅 OP 清 0；
  5. 带内 EOP：码=63。
- **时序**：3 拍骨架；拍 B 路径 = config Q → 译码表 + group 译码 → 4 个 CEN。
- **已实现细节（2026-09-06，一次通过）**：拍 B 用 `cfg_rdata[4:0]` 喂与 E3 共用的 `cfg_pair_codebook`，group=`cfg_rdata[5]`；Lane 使能 `en(2g+j)=valid_j & (group==g)`；译码后控制 `{valid0,slot0,valid1,slot1,group}` 寄存 9 DFF 送拍 C；拍 C 每槽 4:1 mux（源 Lane = `{group_c, hit0?0:1}`）。EOP=63（local=31 译码全无效 → Lane 自动不读）；码 31 保留不出现。池：config 5608、Lane 读 1442/1442/1441/1441 精确门控；与 E3 共用 `golden_issue2.txt`（同 max-2 族）。编码器 Lane 均衡状态**逐程序重置**（每程序独立描述符执行）。
- **注意**：单事件周期可落 4 条 Lane 中任意一条（编码器按深度均衡选择），解码严格按 `{group, local}` 即可，无需额外状态；无 phase 寄存器（与 E2 的本质区别）。

### 5.6 各方案状态/逻辑量一览

| 方案 | 状态寄存器 | 拍 B 译码 | 拍 C 分发 | 估算逻辑量级（不含公共输出级） |
|---|---|---|---|---|
| E0 | PC(13b) | 5× NOR34（NOP 检测） | 纯连线切分 | ~150 GE |
| E1 | PC + 5×ptr(11b) + cnt(14b) | mask 直连 CEN | 字段写使能（无数据 mux） | ~600 GE |
| E2 | PC + 4×ptr(11b) + phase(2b) | popcount + mod4 比较 | 5× 4:1 mux（散布） | ~2200 GE（含散布上界 1530） |
| E3 | PC + 2×ptr(12b) | 32 项译码表 | 5× 3:1 mux | ~800 GE |
| E4 | PC + 4×ptr(11b) | 32 项译码表 + group | 5× 3:1 mux（4 选源） | ~1000 GE |

公共输出级（§3.4，五方案相同）：5 槽 × 34 bit 字段寄存器（非 OP 字段带使能）≈ 850–1000 GE，与既有实验脚本中 "common output-hold registers and OP gating excluded" 的口径一致——相对比较时剔除，绝对面积报告时计入。

### 5.7 共同注意要点

1. **关键路径**：①拍 B「config Q(tCD) → 译码 → payload 宏输入寄存器建立」；②拍 C「payload Q(tCD) → 分发 mux → 字段输出寄存器建立」。两者预算 ≈ 1ns − tCD。若 1 GHz 不收敛，备选：(a) config Q 先寄存、payload 地址晚一拍（+1 延迟，II 不变）；(b) 拍 C 散布前加一级寄存器（+1 延迟）。延迟不影响周期数结论。
2. **无背压**：本设计不含任何握手/stall；`start` 后状态每拍无条件前进。若未来接真实下游需加背压，注意 PC/指针/phase/计数器/捕获寄存器必须原子保持，且宏 `CEN=0` 期间依赖 output-hold 保持在飞读数据。
3. **装载**：不用 `$readmemh` 直接灌 TSMC 宏内部数组（层次路径不可移植）；统一走顶层 `load_en` 装载口逐地址写（`wmask` 全 1）。8192 深度装载在仿真中为微秒级。
4. **宏容量 vs 实际占用**：3 个 case 实际流深（如 gelu_x64 max-4：T=3096，Lane 深 576）远小于宏容量。面积/能耗比较按**固定宏组合**计（物理公平口径），不按占用量；memh 只含有效项，装载器按 manifest 深度写。
5. **EOP 口径三选一，不可混用**：E0 字内 bit0；E1 计数器隐式；E2/E3/E4 带内码。tb 统一在 `slot_valid && eop` 后期待 done。
6. **NOP 输出语义**：无效槽输出 OP=0、其余字段保持上一有效值（§3.4）；校验按保持语义 golden 逐 bit 比对（含"保持值是否正确"），不允许把无效槽简单输出全 0，也不允许无效拍改写非 OP 字段。
7. **golden 来源**：`golden.txt` 直接由原始 174-bit `schedule.txt` 生成，禁止由压缩流再解码生成。
8. **码本单一来源**：E3/E4 的 ROM 由 `gen_rtl_streams.py` 生成，禁止手改；编码器枚举顺序改动必须同步重新生成。
9. **能耗口径**：`汇总28nm综合结果.docx` 的 wrapper 功耗是宏级口径；动态读能耗须按「实际读次数 × 宏读能量」从仿真统计（tb 记录各宏实际 CEN 有效拍数），不与 CACTI 数字混用。

---

## 6. Testbench 与校验

### 6.1 `rtl/sim/tb_expN_simple.v`（每方案一个，结构统一）

全部**程序池模式**、**相对仓库根路径**、**无 plusarg**：

1. 时钟/复位；从 `rtl/data/eN_pool_meta.hex` 读池描述（程序数、各宏总字数、逐程序基址/长度），从 `rtl/data/eN_pool_*.memh` 读整池镜像。
2. **装载阶段**：`load_en=1`，整池镜像逐地址写入各宏（只装这一次）。
3. **运行阶段**：逐程序：写 `# prog <k>` 分段标记 → 复位前端（宏内容保持）→ 驱动描述符 → `start` → 等 `done`。每拍若 `slot_valid`，tb 按 §3.2 打包公式把五槽字段端口无损重组为 34-bit 容器，连同 `eop` 以 hex 追加写入当前目录 `rtl_out_eN.txt`。
4. **结束**：每程序检查 `done` 与发射拍数；并校验各宏实际读使能拍数 == 池 meta 中的精确总数（门控正确性）；watchdog 超时报错。

### 6.2 `rtl/tools/check_rtl_output.py`

- 输入：`rtl_out_eN.txt` + 对应族的 golden（+ manifest）。
- 逐拍逐槽比对；报告首个不匹配的拍号、槽名、期望/实际；检查总拍数一致、EOP 位置正确、EOP 后无多余输出。golden 已含保持语义，故比对同时验证：有效槽字段全对、无效槽 OP=0 且非 OP 字段精确保持（任何无效拍的字段毛刺/误写都会被捕获）。
- **池模式**（`--pool --map eN_pool_map.txt --data rtl/data [--golden-name ...]`）：按 `# prog <k>` 标记切分段，按 map 把第 k 段与对应 case 的 golden 比对；段缺失/多余/段内不匹配均报错。golden 按调度族选：E0/E1 用 `golden_issue5.txt`（默认），E2 用 `golden_issue4.txt`，E3/E4 用 `golden_issue2.txt`。
- 退出码 0/1，供 CI；`--verbose` 打印前 N 拍对照表。
- 一次运行覆盖：五方案各 3 case 池回归（均为保持口径），全过才算通过。

### 6.3 在 ModelSim/Questa 中运行（另一台机器）

文件全部为可移植 Verilog-2001/2005 + 标准系统任务，无仿真器专有构造。按 §6.4 的最简约定运行：用户自己的 tcl 只做 `vlib/vlog/vsim/run` 四步，tb 为 `tb_expN_simple.v`，相对仓库根读数据、无需 plusarg。

要点：

1. **宏模型 define**：功能仿真加 `+define+UNIT_DELAY`（跳过时序检查、加速，并避免寄存器输出在时钟沿后 delta 时间变化引发的 $setuphold 告警）；做带时序检查的仿真时去掉它（顶层已为宏输入预留 `SRAM_TIMING_SIM_INPUT_DELAY` 0.120ns 延迟钩子，与 timing_check 模块同纪律）。
2. **装载可移植**：tb 经顶层 load 口逐地址写，不 `$readmemh` 进宏内部数组，跨仿真器可移植。
3. 后续功耗分析（M6）：ModelSim 下用 `power add -r` / SAIF 导出，tb 无需改动。

### 6.4 对用户的最简交付格式（2026-09-06 用户明确要求，务必遵守）

每个实验只给用户提供两项，**不做多余解释**：

1. **必须包含的文件路径清单**（相对仓库根，逐条列出）；
2. **仿真跑完后跑 Python 校验的命令**（一条）。

**最简 testbench 约定**（`rtl/sim/tb_expN_simple.v`）：

- 用户的 ModelSim 当前目录 = **仓库根**（`rtl/` 的上一级）；
- tb 一律用**相对仓库根**的路径读数据（`rtl/data/eN_pool_*.memh`），**不用任何 plusarg**；
- 一律**程序池模式**：整池镜像一次装入，逐程序复位前端、按描述符切换；
- 结果写到当前目录 `rtl_out_eN.txt`（含 `# prog <k>` 分段标记）；
- 用户自己的 tcl 只需四步：`vlib work` → `vlog +define+UNIT_DELAY <宏模型> <wrapper> <顶层> <tb>` → `vsim work.tb_expN_simple` → `run -all`。

---

## 7. 面积/功耗交叉检查（宏级，来自 28nm 综合汇总）

| 方案 | 宏组合 | 宏面积 (µm²) | 相对 E0 | wrapper 功耗 (mW，参考) |
|---|---|---|---|---|
| E0 无压缩 | 1× 8192×171 | 288,368 | 1.000 | 14.612 |
| E1 A | 8192×5 + 5× 2048×34 | 95,216 | 0.330 | 11.892 |
| E2 4slot | 8192×5 + 4× 2048×34 | 79,062 | 0.274 | 9.719 |
| E3 2slot2lane | 8192×5 + 2× 4096×34 | 78,626 | 0.273 | 6.777 |
| E4 2slot4lane | 8192×6 + 4× 2048×34 | 80,638 | 0.280 | 9.768 |

预期 sanity check：宏面积 E3 ≈ E2 < E4 < E1 ≪ E0；逻辑面积 E2 > E4 > E3 > E1 > E0。RTL 综合后若明显偏离（如 E2 逻辑吃掉宏收益），回到 plan 的 PPA 表复核。

---

## 8. 里程碑

| # | 交付 | 判定 |
|---|---|---|
| M1 | `gen_rtl_streams.py` + 3 case 三族调度 + 5 格式流 + golden + 码本译码表 | Python 侧 5 格式 roundtrip 全过；manifest 完整 |
| M2 | E0 顶层 + tb + checker | 3 case bit-exact（打通装载/捕获/校验链路） |
| M3 | E1、E2 顶层 + tb | 3 case bit-exact（E1 覆盖 layernorm 的 5 槽同发拍） |
| M4 | E3、E4 顶层 + tb | 3 case bit-exact |
| M5 | 15 组回归（3 case × 5 方案）全绿 | checker 退出码全 0 |
| M6（后续） | 五方案同接口综合 + 读能耗统计 | 面积/功耗表，与 §7 交叉检查 |

## 9. 已确认决策（2026-09-06 与用户对齐）

1. E0/E1 用 `MAX_ISSUE_SLOTS=5` 原生调度；E2 用 max-4；E3/E4 用 max-2。
2. 顶层无背压、无握手，自由运行。
3. `rtl/data/` 的 memh 入库，便于复现。
4. **E1–E4 只实现保持口径**（顶层无 HOLD_EN 参数，无效槽 OP 清 0、其余字段保持）；仅 E0 保留 HOLD_EN 双口径作论文消融。
5. E0 支持程序池：整池镜像一次装入、按描述符 `{prog_base, prog_len}` 切换；E1 池描述符为 `{cfg_base, prog_len, slot_base0..4}`。

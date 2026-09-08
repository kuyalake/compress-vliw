# 深 SRAM 拼接 wrapper 与单元 testbench 计划

日期：2026-09-08 ｜ 依据：`plan/sram_depth_tiling_vs_mc_decision_2026-09-08.html` ｜ 范围：BERT / SD-UNet / LLaMA 三池 × E0/E1/E2 三方案所需的深 SRAM

---

## 1. 任务目标

为下一批三种对比实验（E0 无压缩、E1 Candidate A、E2 4slot）在三个程序池上所需的**深 SRAM** 编写：

1. **拼接（depth-tiling）wrapper**：用现有宏拼出更深的逻辑 SRAM；
2. **单元 testbench**：验证拼接 wrapper 的功能正确性与跨页连续性。

**决策文档结论**（据此执行）：
- **32768×5 送 MC 生成**（LLaMA E1/E2 的 config）；**16384×34 作为 LLaMA E2 的时序保险**（暂由 MC 备，不先做）；
- **其余深度一律用现有宏拼接**，不等 MC 才开始 RTL。

## 2. 各池各方案所需 SRAM 与来源

| 池 | 方案 | 逻辑 SRAM | 来源 |
|---|---|---|---|
| **BERT**（7667 拍） | E0 | 171×8192 | **已有** `sram_8192x171_wrapper` |
| | E1 | 5×8192 config + 5×(34×4096) payload | **已有** `sram_8192x5_wrapper` + `sram_4096x34_wrapper` |
| | E2 | 5×8192 config + 4×(34×2048) payload | **已有** `sram_8192x5_wrapper` + `sram_2048x34_wrapper` |
| **SD-UNet**（11684 拍） | E0 | 171×16384 | **新建** 2×8192×171 拼接 |
| | E1 | 5×16384 config + 5×(34×8192) payload | **新建** config 2×8192×5 拼接 + payload 每 Bank 2×4096×34 拼接 |
| | E2 | 5×16384 config + 4×(34×4096) payload | config **新建** 2×8192×5 拼接；payload **已有** `sram_4096x34_wrapper` |
| **LLaMA**（30704 拍） | E0 | 171×32768 | **新建** 4×8192×171 拼接 |
| | E1 | 5×32768 config + 5×(34×16384) payload | config **MC 32768×5**（**等 MC 到位，不做拼接过渡**）；payload **新建** 每 Bank 4×4096×34 拼接 |
| | E2 | 5×32768 config + 4×(34×16384) payload | config **MC 32768×5**（**等 MC 到位**）；payload **新建** 每 Lane 4×4096×34 拼接 |

## 3. 已有 wrapper（直接复用，不新建）

| wrapper | 覆盖 |
|---|---|
| `sram_8192x171_wrapper` | BERT E0 |
| `sram_8192x5_wrapper` | BERT E1/E2 config |
| `sram_2048x34_wrapper` | BERT E2 payload |
| `sram_4096x34_wrapper` | BERT E1 payload、SD-UNet E2 payload |

## 4. 需新建的拼接 wrapper

按决策文档 §6.1「**通用 depth wrapper**」的要求，写 **3 个参数化拼接 wrapper**（每个基宏一个，`TILES` 参数取 1/2/4），覆盖全部 6 种目标深度：

| 新文件 | 基宏 | TILES=2 | TILES=4 |
|---|---|---|---|
| `rtl/src/sram_8192x171_tiled.v` | `sram_8192x171_wrapper` | 171×16384（SD-UNet E0） | 171×32768（LLaMA E0） |
| `rtl/src/sram_8192x5_tiled.v` | `sram_8192x5_wrapper` | 5×16384（SD-UNet E1/E2 config） | —（32768×5 等 MC，不拼接） |
| `rtl/src/sram_4096x34_tiled.v` | `sram_4096x34_wrapper` | 34×8192（SD-UNet E1 payload） | 34×16384（LLaMA E1/E2 payload） |

### 4.1 拼接 wrapper 的硬件设计（质量要点）

```
两片拼接（TILES=2）：

  addr 高位 ──► 片选译码 ──► 只使能被选中的一片（单片 CEN 门控）
  addr 低位 ──────────────► 两片宏的地址口
  延迟一拍的 addr 高位 ──► 2:1 输出 MUX ──► rdata

四片拼接（TILES=4）：输出 MUX 用**平衡两级 2:1 树**（不是优先级链）。
```

四条硬性要求（对应决策文档 §2.1/§6.1，也是"不影响时序/perf"的关键）：

1. **单片 CEN 门控**：`cen_i = cen & (addr_high == i)`——每拍只打开被选中那片，否则动态功耗 × 片数；
2. **延迟片选**：地址高位在**读发射的那个时钟沿**寄存一拍得 `sel_q`，输出 MUX 用 `sel_q`（而非当前地址高位）——与同步读数据同拍对齐，**不增加读延迟级数**（仍 1 拍宏读，II=1 不变）；
3. **平衡输出 MUX**：4 片用两级 2:1 平衡树（`sel_q[1]` 选高低半、`sel_q[0]` 选片内），禁止优先级链（链式延迟不均、可能拖累 1 GHz）；
4. **锁定实际宏**：拼接 wrapper 直接例化现有 `sram_*_wrapper`（其内含 TSMC 宏），综合时视为硬核、不被推平；`TILES` 参数只决定片数与译码/MUX 结构。

接口与现有 wrapper 完全一致（`clk/cen/wen/addr/wdata/wmask/rdata`），地址宽度 = 基宏地址宽 + log2(TILES)，数据宽度 = 基宏宽度。

## 5. 单元 testbench 设计

每个拼接 wrapper 配一个 `rtl/sim/tb_sram_*_tiled.v`，仿照现有 `tb_sram_*_timing_check.v` 的风格（先写后读、`expected_mem` 对照），并**重点覆盖决策文档 §6.2 的跨页连续性**：

1. **全深度写满再连续读回**：写入 addr 相关已知图案，0..DEPTH−1 每拍连续读一个地址，逐拍比对——不能有气泡、重复、丢字；
2. **跨片边界定向检查**：重点扫 `8191→8192`、`16383→16384`、`24575→24576` 等拼接边界前后，验证片选译码与延迟片选对齐（数据必须来自正确的片）；
3. **门控断言**：仿真中探针检查**每拍至多一片 CEN 有效**（门控正确性）；
4. **EOP 落在边界**：构造读序列使程序结束恰好落在片边界前后，确认不丢/不重。

## 6. 时序与 perf 保证

- 拼接 wrapper **不增加读延迟级数**（延迟片选只是对齐，宏读仍 1 拍），II=1 吞吐不变；
- 输出 MUX 只加在宏 Q 之后（2:1 或两级 2:1，约 2–4 级门），相对宏 tCD（0.39–0.75 ns）在 1 GHz 下余量充足；
- 片选译码是「地址高位 + cen」的一个门，在寄存器输出之后，路径极短；
- 宏输入仍遵循「寄存器驱动」纪律（与 `sram_*_timing_check` 一致），时序仿真可加 `SRAM_TIMING_SIM_INPUT_DELAY`。

## 7. 验证计划

1. 3 个拼接 wrapper × 各自 TILES=2/4 配置，单元 tb 全过（含边界与门控断言）；
2. 与现有单宏 wrapper 在重叠深度（如 8192×5 单宏 vs 拼接 TILES=1）做一致性对拍；
3. （后续）替换进 E0/E1/E2 顶层做深池功能仿真——**属下一步，不在本轮范围**。

## 8. 文件清单

| 操作 | 路径 |
|---|---|
| 新建 | `rtl/src/sram_8192x171_tiled.v`、`sram_8192x5_tiled.v`、`sram_4096x34_tiled.v` |
| 新建 | `rtl/sim/tb_sram_8192x171_tiled.v`、`tb_sram_8192x5_tiled.v`、`tb_sram_4096x34_tiled.v` |
| 复用 | 现有 5 个 `sram_*_wrapper.v`（不改动） |

## 9. 已确认决策（2026-09-08 与用户对齐）

1. **范围**：本轮只写 SRAM 拼接 wrapper + 单元 tb；把拼接集成进 E0/E1/E2 顶层以支持深池，是**下一步**。
2. **MC 过渡**：32768×5 **等 MC 到位**，不做 4×8192×5 拼接过渡；`sram_8192x5_tiled` 本轮只覆盖 TILES=2（16384）。
3. **复用确认**：§3 列的 4 个现有 wrapper 直接复用、不新建。

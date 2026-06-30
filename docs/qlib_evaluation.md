# Microsoft Qlib 对 berkshire-ai 的可借鉴/集成评估

> 类型：纯研究 + 方案设计（只读分析，未改动任何源码）。
> 评估对象：[microsoft/qlib](https://github.com/microsoft/qlib)（AI 量化投资平台）。
> 本项目：berkshire-ai —— 基于 TextGrad 思想的「四大师并行投研系统 + 自进化引擎」，
> **定性 / LLM 驱动**的投研系统，工程哲学为「轻量、可注入、可 mock、优雅降级、零/少重依赖」。
> 与 RD-Agent 的借鉴分工见本文「§5 与 RD-Agent 的关系」，不重复 `docs/rdagent_reference.md` 的内容。

---

## 0. 一句话结论（TL;DR）

**值得「借鉴理念」，但绝不值得「直接依赖 qlib」。**

- Qlib 是一套**重量级、面向因子/ML 量化**的平台（pandas/numpy/cython/可选 torch、二进制行情数据栈、qrun workflow、MLflow Recorder）。它的**世界观**（先有日频面板数据 → 算因子 → 训模型 → 组合优化 → 回测）与 berkshire-ai 的**世界观**（LLM 对少量标的做定性判断 → 决策快照 → 事后用真实收益做反馈闭环）**根本不同**。
- 真正高价值、可落地的是 **Qlib 的「绩效归因/风险分析」指标约定**（`risk_analysis`：年化收益、波动率、信息比率 IR、最大回撤，且**按求和而非累乘**计算累计收益以避免指数级失真），以及 **Recorder/实验追踪的理念**。这些可以用**零重依赖的本地实现**吸收，无需引入 qlib。
- **最小切口（最高 ROI）**：新建一个零依赖的 `tools/perf_metrics.py`，把 berkshire-ai 现有的「`decision_log` 决策快照 + `PriceProvider` 真实行情」拼成一条净值/超额收益曲线，输出 Qlib 风格的标准绩效指标（年化、波动、IR/Sharpe、最大回撤、胜率、含/不含成本、相对基准超额）。**借的是 Qlib 的指标定义与口径，不是 qlib 这个包。**

---

## 1. Qlib 是什么：定位与核心能力盘点

Qlib 自我定位为「AI-oriented 量化投资平台」，覆盖**完整 ML 量化流水线**：数据处理 → 模型训练 → 回测 → 绩效分析，并贯穿 alpha 挖掘、风险建模、组合优化、订单执行全链路。模块松耦合、可单独使用。

| 能力域 | Qlib 提供什么 | 依赖与重量 |
|---|---|---|
| **数据层** | 自有**二进制列式行情格式**（`.bin`）、表达式引擎（`$close`, `Ref()`, `Mean()` 等算子）、`ExpressionCache`/`DatasetCache` 两级缓存，号称比 HDF5/MySQL/MongoDB 快一个量级；offline/online（共享数据服务）两种模式 | 重：需 `qlib.init(mount_path=...)` + 下载/转换数据集（`~/.qlib/qlib_data`）；面板数据范式 |
| **Alpha 因子 / 数据集** | `Alpha158` / `Alpha360` 内置因子集（handler）、Quant Dataset Zoo | 重：pandas 面板 + 因子表达式 |
| **模型库（Model Zoo）** | LightGBM/XGBoost/CatBoost + 一众深度模型（LSTM/GRU/GATs/Transformer/TRA/TFT/TabNet…），SOTA 论文复现 | 极重：torch/tensorflow/lightgbm，按模型不同各有环境地狱 |
| **回测框架（backtest）** | 事件驱动回测、交易成本、`Exchange`、`NestedExecutor`（多层策略嵌套）、订单执行 | 中-重：依赖数据层 + 策略对象 |
| **组合优化 / 风险模型** | 基于规划的组合优化（`EnhancedIndexingStrategy` 等）、风险模型（协方差/因子风险） | 中-重：需 cvxpy 等优化器、风险因子数据 |
| **绩效分析（report/analysis）** | `risk_analysis`：std、annualized_return、information_ratio、max_drawdown（**累计用求和**）；`analysis_position`/`analysis_model`：IC、RankIC、分组累计收益、换手率、long-short 等图表 | **轻**：核心是 pandas Series 上的统计；图表才需 plotly |
| **Workflow（qrun）/ Recorder** | `qrun config.yaml` 一键跑「建数据集→训模型→回测→评估」；`R`（QlibRecorder，**基于 MLflow**）记录实验/参数/指标/产物 | 中：qrun 重，Recorder 本身是 MLflow 封装 |
| **RL** | 订单执行 RL（TWAP/PPO/OPDS）、嵌套决策环境 | 极重：RL 栈 |
| **市场动态自适应** | Rolling Retraining、DDG-DA、meta-learning | 重 |

### RD-Agent / RD-Agent(Q) 与 Qlib 的关系（要点）

- **RD-Agent 是独立仓库**（[microsoft/RD-Agent](https://github.com/microsoft/RD-Agent)），是「LLM 自主演化的工业级数据驱动 R&D」框架；其量化场景 **RD-Agent(Q)**（论文 *R&D-Agent-Quant*, arXiv:2505.15155）**本身就构建在 Qlib 之上**——用 LLM 自动挖因子/调模型，**把 Qlib 当作回测与执行底座**。
- 对 berkshire-ai 而言：**Qlib ≈ RD-Agent(Q) 的「执行底座/评测环境」**，RD-Agent ≈「LLM 演化外壳」。berkshire-ai 自己已有「LLM 演化外壳」（graph/optimizer/eval_harness 那套 TextGrad 自进化），所以**真正该向 Qlib 借的，是它作为「评测底座」沉淀下来的指标口径与实验追踪范式**，而不是再造一个因子/模型流水线。详细的 RD-Agent 借鉴见 `docs/rdagent_reference.md`。

---

## 2. berkshire-ai 现状（与 Qlib 能力对位）

只读核对了关键模块，确认现状如下：

- **决策快照**：`src/decision_log.py` —— `DecisionRecord`（ticker/date/四大师评分/price_anchor/benchmark/benchmark_anchor/trace_id）落 JSONL，零依赖。**这正是 Qlib Recorder 思路的轻量版**（已经有了，只是没有「指标」层）。
- **收益→评分闭环**：`src/realized_feedback.py` —— 已能算 `raw_return / benchmark_return / alpha / realized_base`，并有**可注入/可 mock 的 `PriceProvider`**（`StaticPriceProvider` 测试用、`NetworkPriceProvider` 接真实行情，非交易日回退到前一交易日）。**但只算单笔点对点收益，没有净值曲线/回撤/IR 等组合级指标。**
- **数据层**：`tools/data_sources.py` —— 多源降级链（native→tushare→efinance→akshare→baostock→yfinance），import 守卫 + 环境变量开关 + 统一 schema，全失败返回 `ok=False` 不崩。**这是 Qlib 数据层「理念」的轻量化、A 股本地化实现，已经做得很好；不需要 Qlib 的二进制数据栈。**
- **回测**：`tools/momentum_backtest.py` / `momentum_backtest_v2.py` —— 「动量发现 + 价值验证」规则回测，**只输出「首次买入信号到期末的总收益率 %」**，无年化/波动/回撤/夏普/IR、无交易成本、无多标的组合净值。**这是与 Qlib 差距最大、也最值得用 Qlib 口径补齐的地方。**
- **组合风险**：`tools/portfolio_risk.py` —— 集中度/主题暴露/相关性（本地 CSV，Pearson）规则检查，纯计算、离线。**对应 Qlib 风险模型的「轻量规则版」，已够用**；不建议升级为 Qlib 的因子风险模型/协方差优化。
- **财务严谨性**：`tools/financial_rigor.py` —— 市值/估值交叉校验、Benford 等，**与 Qlib 无关**（这是 LLM 数字幻觉防护，Qlib 没有对标）。
- **自进化评测台**：`src/eval_harness.py` —— `EvolutionReport`（逐轮均值质量、单调不降、收敛）。**这是 berkshire-ai 独有的「prompt 质量」评测**，与 Qlib 的「策略绩效」评测正交、互补。
- **打包**：`pyproject.toml` 核心依赖仅 `httpx`；extra 模式 `[ashare]` / `[service]` / `[dev]`。**任何 Qlib 相关集成都必须遵循此 extra 模式，绝不进核心 dependencies。**

---

## 3. 契合度对比表（逐能力裁决）

裁决口径：✅ 借鉴理念（零依赖自实现） / 🟡 可选 extra 依赖集成（谨慎） / ❌ 不建议引入。

| Qlib 能力 | 对 berkshire-ai 的价值 | 与轻量哲学冲突？ | 裁决 | 形态 |
|---|---|---|---|---|
| **绩效分析口径**（年化/波动/IR/最大回撤，累计用求和、含/不含成本、相对基准超额） | **高**：补齐回测/反馈闭环最大短板，让「自进化是否赚钱」可量化 | 否（纯 stdlib 统计即可） | ✅ | 借理念，新建 `tools/perf_metrics.py` |
| **Recorder / 实验追踪理念** | 中-高：把每次进化/回测的参数+指标+产物可复现地归档 | MLflow 太重；但**理念**轻 | ✅（理念）/ 🟡（MLflow 可选 extra） | 扩展 `decision_log` 或新增 `run_recorder`，MLflow 仅作可选导出 |
| **数据基础设施理念**（缓存、统一取数接口） | 中：`data_sources.py` 已实现轻量版；可借「本地缓存」一点 | qlib 二进制栈极重 | ✅（仅借「本地缓存」微理念） | 给 `NetworkPriceProvider` 加可选磁盘缓存 |
| **回测「指标」层** | 高：见上（与绩效分析同源） | 否 | ✅ | 同 `perf_metrics.py` |
| **回测「引擎」层**（Exchange/成本/嵌套执行） | 低-中：berkshire-ai 是少标的定性投研，不需要撮合级引擎 | 重 | 🟡（仅在确需多标的组合日频回测时，作 `[qlib]` extra 适配器） | 可选适配器，默认走本地轻量回测 |
| **组合优化 / 风险因子模型**（cvxpy/协方差） | 低：与「李录式集中持仓 + 规则风控」哲学相悖 | 重且哲学冲突 | ❌ | 不引入 |
| **Alpha158/360 因子集** | 低：本项目不做因子选股 | 范式冲突 | ❌ | 不引入 |
| **模型库（LightGBM/LSTM/Transformer…）** | 无：本项目是 LLM 定性，不训预测模型 | 极重 | ❌ | 不引入 |
| **数据二进制栈 / qrun workflow** | 低：需 `qlib.init` + 数据下载，绑死 panel 范式 | 极重 | ❌ | 不引入 |
| **RL（订单执行）** | 无 | 极重 | ❌ | 不引入 |
| **市场动态自适应（DDG-DA/meta）** | 无 | 极重 | ❌ | 不引入 |
| **IC / RankIC 等因子评测** | 低：无连续预测分数面板，IC 无意义；可借「校准度」类比已由 `realized_feedback` 覆盖 | 范式冲突 | ❌（直接借）/ ✅（类比思想已有） | 不引入 |

---

## 4. 分档可执行 backlog（按 ROI / 成本排序）

> 通则：所有项**默认零重依赖**；任何第三方库都走 extra（沿用 `[ashare]`/`[service]` 模式），**绝不进核心 `dependencies`**；所有外部数据/行情都经现有可注入 `PriceProvider` / `data_sources`，可 mock、失败优雅降级。

### 档位 A —— 高 ROI / 零重依赖（建议优先做）

**A1. 本地绩效指标库 `tools/perf_metrics.py`（= 最小切口，详见 §6）**
- 内容：给定收益序列（或净值序列），输出 Qlib `risk_analysis` 口径指标：`annualized_return`、`volatility(std*√N)`、`information_ratio`/`sharpe`、`max_drawdown`（峰谷法）、`cumulative_return`（**累加口径**，对齐 Qlib「避免指数失真」）、`win_rate`、`turnover`（可选）；支持**含/不含成本**与**相对基准的超额收益（CAR）**两套。
- 改造/新增模块：**新增** `tools/perf_metrics.py`（纯 stdlib）。
- extra 依赖：无。
- 与降级约束兼容：纯函数，输入是 `list[float]`/`list[(date, price)]`，不连网；与 `PriceProvider` 解耦。
- 测试：构造已知序列断言（如等比涨跌的回撤、固定均值/方差的年化与 IR），全离线；边界（空序列、单点、全 0 波动）返回明确值不崩。

**A2. 把 A1 接到反馈闭环 / 回测产出**
- 内容：在 `realized_feedback`（或新增薄封装）里，把同一标的的多条 `DecisionRecord` + `PriceProvider` 取价拼成净值/超额曲线，调用 `perf_metrics` 给出**组合级**绩效（现在只有单笔点收益）。给 `momentum_backtest_v2` 增加「年化/回撤/夏普」摘要输出（不改其信号逻辑）。
- 改造模块：`src/realized_feedback.py`（新增函数，不动既有签名）、`tools/momentum_backtest_v2.py`（追加指标打印）。
- extra：无。
- 测试：用 `StaticPriceProvider` 注入确定性价格，断言曲线与指标；mock 即离线。

**A3. 绩效报告 JSON/Markdown 导出（对齐 `docs/report-conventions.md`）**
- 内容：把 A1/A2 的指标渲染成结构化 JSON + 人读 Markdown 表（含/不含成本两行，对齐 Qlib 报告排版习惯）。
- 改造模块：`tools/perf_metrics.py` 增加 `render_*`；或并入 `src/metrics_export.py`。
- extra：无。
- 测试：快照断言渲染文本/JSON 结构。

### 档位 B —— 中 ROI / 仍零或轻依赖（按需做）

**B1. 轻量 Run Recorder（理念借鉴，非 MLflow）**
- 内容：把每次「进化轮次 / 回测」的（配置 + 指标 + 产物路径 + run_id）追加落一份 JSONL/目录，复用现有 `observability.run_context` 的 run_id 与 `decision_log` 落盘范式。提供 `list_runs()/load_run()` 便于复现与对比。
- 改造模块：**新增** `src/run_recorder.py`（或扩展 `decision_log`），复用 `observability`。
- extra：无（MLflow 仅作 B2 可选导出）。
- 测试：写入→读取→对比，确定性、离线。

**B2.（可选）MLflow 导出适配器**
- 内容：仅当用户想用 MLflow UI 看实验时，提供 `to_mlflow(run)` 适配器；缺 mlflow 时 import 守卫静默跳过。
- 改造模块：`src/run_recorder.py` 内可选分支。
- extra：新增 `[mlflow] = ["mlflow"]`（独立 extra，默认不装）。
- 测试：mock mlflow client；未安装时走降级路径不报错。

**B3. `NetworkPriceProvider` 可选磁盘缓存（借 Qlib 缓存「理念」）**
- 内容：把每标的日线序列缓存到本地（如 `~/.berkshire/price_cache/`），TTL 可配；默认仍是内存缓存，磁盘缓存为 opt-in 环境变量开关。
- 改造模块：`src/realized_feedback.py`（`NetworkPriceProvider` 增可选缓存路径）。
- extra：无（stdlib json/os）。
- 测试：注入临时目录，断言二次取数命中缓存、不再调用 fetcher。

### 档位 C —— 低 ROI / 重依赖（仅在明确需要时，强约束）

**C1.（可选）Qlib 回测适配器 `[qlib]` extra**
- 触发条件：**仅当** berkshire-ai 真的演进到「**多标的、日频、需撮合级成本/换手/嵌套执行**的组合回测」时才考虑。
- 形态：`tools/qlib_adapter.py`，import 守卫 + `[qlib] = ["pyqlib"]` 独立 extra；缺库/未 `qlib.init` 时**自动降级回 A1 本地回测**，不崩。
- 约束：绝不进核心依赖；不引入 qlib 数据二进制栈作为默认路径（仅在用户已自备 `~/.qlib` 数据时启用）。
- 测试：有 qlib 时跑通一条最小路径（CI 可标记 `skipif`）；无 qlib 时断言降级。
- **现实判断**：以本项目「少标的定性投研」定位，C1 大概率**长期不需要**；列出仅为完整性。

---

## 5. 与 RD-Agent 的关系（避免重复借鉴）

- **分工**：`docs/rdagent_reference.md` 负责「LLM 自主演化 R&D 外壳」的借鉴（假设生成→实验→反馈的演化循环），那部分与 berkshire-ai 的 `graph/optimizer/eval_harness` 自进化对位。**本报告只负责 Qlib 作为「评测底座」的指标口径与实验追踪**。
- **不重复**：因 RD-Agent(Q) 本就构建在 Qlib 之上，二者在「回测/绩效评测」处会交汇。**统一口径**：berkshire-ai 不直接依赖 RD-Agent 也不直接依赖 Qlib，而是把二者共同沉淀的「**标准绩效指标 + 可复现实验记录**」用**零依赖本地实现**吸收（即本文 A1+B1）。这样 RD-Agent 报告谈「演化逻辑」，本报告谈「绩效度量」，无重叠。

---

## 6. 推荐的「最小切口」（最高价值、不破坏轻量哲学）

> 一句话：**用零依赖本地实现，吸收 Qlib `risk_analysis` 的绩效指标口径，把它接到 berkshire-ai 已有的 `decision_log` + `PriceProvider` 上。借口径，不借包。**

**切口 1（必做）：`tools/perf_metrics.py`（纯 stdlib）**

实现以下函数（口径对齐 Qlib，但不 import qlib）：

- `returns_from_prices(prices) -> list[float]`：价格序列 → 简单日收益。
- `cumulative_return(returns, method="sum") -> float`：默认**求和**口径（对齐 Qlib「避免指数级失真」），另留 `compound` 备选。
- `annualized_return(returns, periods=252) -> float`
- `volatility(returns, periods=252) -> float`（`std * √periods`）
- `information_ratio(returns, periods=252) -> float` / `sharpe(returns, rf=0)`（= mean/std × √periods）
- `max_drawdown(returns_or_nav) -> float`（峰谷回撤）
- `win_rate(returns) -> float`
- `risk_analysis(returns, benchmark=None, cost=0.0) -> dict`：一次性返回上述全部，并在给 benchmark 时输出**超额收益（CAR）**版本与含成本版本（两行口径，对齐 Qlib 报告）。
- `render_markdown(report) -> str` / `to_json(report) -> dict`。

**为什么是它**：
1. **填的是真空**——当前 `momentum_backtest*` 只有「总收益率 %」，没有任何风险调整/回撤/年化指标；这是反馈闭环「证明自进化真的赚钱」缺的最后一块拼图。
2. **零依赖、可测、离线**——纯函数 + stdlib，完全契合「核心可离线单测」约束，无需 mock 网络。
3. **即插即用**——直接吃 `realized_feedback` 已经算好的收益/超额，吃 `decision_log` 的历史快照，吃 `PriceProvider`（可 mock）拼的曲线，不改动任何既有接口。
4. **不污染架构**——不进核心依赖、不引 panel 数据范式、不绑 qlib。

**切口 2（强烈建议、紧随其后）：把切口 1 接进闭环（backlog A2）**
- 在 `realized_feedback` 增一个「多决策 → 净值曲线 → `risk_analysis`」的薄封装，并让 `eval_harness` 的进化报告旁边能附一份「**这套 prompt 改进后，回放历史决策的绩效指标**」——把「prompt 质量提升」与「真实绩效提升」并排呈现，正是 berkshire-ai 自进化最有说服力的证据。

**明确边界**：到此为止。不做组合优化、不做因子/模型、不引 qlib 数据栈、不引 qrun/RL。

---

## 7. 「不建议引入」清单（明确拒绝 + 理由）

| 不建议引入 | 理由 |
|---|---|
| **`pyqlib` 作为核心或默认依赖** | 重依赖（pandas/numpy/cython，部分路径 torch/lightgbm/cvxpy），需 `qlib.init` + 下载/转换数据集，直接违背「核心仅 httpx、零/少重依赖、可离线单测」铁律 |
| **Qlib 数据二进制栈（.bin + Expression/Dataset Cache + qrun）** | 绑定 panel 数据范式与本地数据服务；`data_sources.py` 的多源降级链已是更贴合 A 股、更轻、可降级的方案 |
| **Alpha158 / Alpha360 因子集** | berkshire-ai 不做因子选股；引入即范式污染 |
| **模型库（LightGBM/LSTM/GRU/GATs/Transformer/TRA/TFT…）** | 本项目用 LLM 做定性判断，不训练价格预测模型；纯增重无收益 |
| **组合优化 / 因子风险模型（cvxpy/协方差优化）** | 与「李录式集中持仓 + 规则化风控」哲学冲突；`portfolio_risk.py` 规则版已够用 |
| **RL 订单执行 / 嵌套决策** | 与投研定位无关，极重 |
| **市场动态自适应（DDG-DA / meta-learning）** | 无对应需求，极重 |
| **IC / RankIC 因子评测指标（直接照搬）** | 无连续预测分数面板，IC 口径不成立；「校准度」类比已由 `realized_feedback.realized_base` 覆盖 |
| **MLflow 作为默认 Recorder** | 理念可借，但默认实现应是 JSONL 轻量版；MLflow 仅作可选 `[mlflow]` extra |

---

## 8. 落地优先级一览（给执行者）

1. **先做**：`tools/perf_metrics.py`（A1 / 最小切口 1）—— 零依赖、独立、可立刻单测。
2. **接着**：接入闭环与回测（A2）+ 报告导出（A3）。
3. **按需**：轻量 Run Recorder（B1），磁盘价格缓存（B3）。
4. **可选**：MLflow 导出（B2，独立 extra）。
5. **基本不做**：Qlib 回测适配器（C1，仅多标的撮合级组合回测确需时）。
6. **永不做**：第 7 节整张「不建议引入」清单。

> 全部改动须满足：核心依赖不变（仅 httpx）、新第三方库一律 extra、外部 IO 经可注入接口可 mock、失败优雅降级不崩链路、核心逻辑可离线单测。

---
name: investment-research
version: 10.2
type: meta-skill
description: >
  完整整合自 xbtlin/ai-berkshire 的四大师并行投研框架 + 工具链 + 技能库。
  巴菲特/芒格/段永平/李录 四视角并行分析，含反偏见机制与金融严谨性验证。
  V10.0: TextGrad 化 - 显式计算图 + 节点级诊断 + 文本梯度反向传播。
  V10.1: 上游全能力整合（skills/ 18个 + tools/ 9个 from xbtlin/ai-berkshire 完整并入，已规范化路径为本地 tools/ 相对引用）。
  V10.3: 集成 graphify 知识图谱 (graphify-out/graph.json)，用于项目代码/技能结构查询。
  V10.11: 已实现收益反馈闭环 + 多空辩论（吸收自 TradingAgents：decision_log/realized_feedback/debate）；
          A股多源降级数据层 tools/data_sources.py + 多通道推送 tools/notify.py（吸收自 JusticePlutus）。
  V10.12: SENSITIVITY 尺度校准 - 用真实历史行情把收益反馈映射默认 SENSITIVITY 2.5→0.5（旧值约78%样本过饱和）；
          新增 tools/calibrate_sensitivity.py，可用 BERKSHIRE_SENSITIVITY 覆盖。
  V10.13: 变量真实改写（Option B）- src/prompt_optimizer.py：apply_gradient 经 LLM 改写 Prompt；
          TextualGradientDescent(graph, llm=...) 注入后 step() 真实改写未达标 prompt 变量的 value，
          LLM 可注入/可 mock（StaticLLMClient / OpenAICompatibleLLMClient），失败优雅降级、不注入则向后兼容。
  V10.14: 生产化硬化 档A - pyproject.toml（ruff/mypy/pytest/coverage 集中配置 + extras）；CI 升级
          （py3.10-3.12 矩阵 + ruff + mypy(src) + 覆盖率门 + pip-audit + gitleaks + Dependabot）；
          src/config.py 中心配置（ENV_SPEC 单一来源 + .env 加载 + doctor 启动自检，不泄密钥）+ .env.example。
  V10.15: 生产化硬化 档B（让自进化真正成立）- src/prompt_validation.py 验证门控改写
          （validated_apply_gradient：改写后评分，只有不劣于旧版+min_improvement 才接受否则回滚）；
          TextualGradientDescent(graph, llm=..., scorer=...) 注入 scorer 即门控、不注入向后兼容；
          src/realized_feedback.py::NetworkPriceProvider 经 data_sources 接真实行情（缓存+非交易日回退，fetcher 可注入）；
          src/eval_harness.py 多轮迭代 run_multi_round + 离线评测台（EvolutionReport 证明单调不退化且收敛）。
  V10.16: 生产化硬化 档C（可观测 + 服务化 + 注入防护）- src/observability.py 结构化 JSON 日志
          + run_id 经 contextvar 贯穿（run_context）+ LLM 成本/token/延迟埋点（MetricsCollector，已接入
          OpenAICompatibleLLMClient）；src/service.py 服务边界（health/doctor/score/debate 纯函数处理器 +
          可选 FastAPI create_app 暴露 /health /score /debate，extras[service]）；src/sanitize.py 提示注入防护
          （sanitize_untrusted 清洗喂给改写 LLM 的不可信诊断：清控制符/中和越狱句/剥假角色标签，UNTRUSTED_ 分隔符兜底）。
  V10.17: 生产化硬化 档D（部署上线 + 访问控制 + 可监控 + 真梯度）- Dockerfile/docker-compose.yml 容器化
          （多阶段构建、非 root、HEALTHCHECK）+ service.run()/berkshire-serve uvicorn 入口；src/access_control.py
          访问控制（check_api_key 常量时间比较 API Key 鉴权 + RateLimiter 每客户端限流，经 create_app 挂到 /score /debate）；
          src/metrics_export.py 指标导出（ServiceMetrics + render_prometheus，/metrics 端点，零依赖）；
          src/llm_gradient.py ∇_LLM 真梯度（LLMGradientGenerator 让 LLM 生成批评 + enrich_gradients_with_llm 增强未达标节点梯度，
          失败优雅降级回规则化）；mypy 开 check_untyped_defs、覆盖率门升 50%、固化 golden 回归。
          生产化档 A→B→C→D 全部落地。
          生产化三档 A→B→C 全部落地，286 测试通过。
  V10.18: 借鉴 RD-Agent / Qlib（依据 docs/qlib_evaluation.md + docs/rdagent_reference.md 只读评估）三项最小切口 -
          tools/perf_metrics.py 本地绩效指标库（借 Qlib risk_analysis 口径，纯 stdlib：年化收益/波动、信息比率/夏普、
          最大回撤、累计收益求和口径、胜率、相对基准超额 CAR/α、含/不含成本；接 decision_log + 可注入 PriceProvider，
          render_markdown/to_json）；src/experience_store.py 经验库 RAG-lite（Experience + ExperienceStore JSONL +
          KeywordExperienceRetriever 零依赖关键词召回 + experience_from_stats 把 realized_feedback 成败信号转可检索经验，
          作为 few-shot 经 build_rewrite_messages(examples=None) 注入改写，examples=None 逐字节不变、sanitize 包裹、失败降级）；
          src/hypothesis.py 显式可证伪假设对象 + 最小 HypothesisStore + group_experiences_by_hypothesis（本次不接主链路）。
          明确不抄：CoSTEER 代码生成+Docker 沙箱、多 trace 调度/Web viewer、qlib 因子/ML/数据二进制栈/qrun/RL/组合优化直依赖。
          382 测试通过。
  V10.19: R/D 双循环（rdagent P1-C）- src/research_loop.py：HypothesisProposer 协议 +
          StaticHypothesisProposer / ExperienceDrivenProposer（零 LLM，从 refuted 经验归纳）/
          LLMHypothesisProposer（可 mock）；run_rd_cycle 每轮 R（提假设→可选 HypothesisStore 落盘）→
          D（复用 eval_harness.run_multi_round）；proposer=None 退化为纯 D（与 V10.18 等价）。
          D 段经验召回：TextualGradientDescent(retriever=, retriever_ticker=) + validated_apply_gradient(examples=)。
          decision_log.DecisionRecord 新增可选 hypothesis_id（向后兼容）。388 测试通过。
  V10.20: 主线接线 - run_with_realized_feedback：persist 时默认 persist_experience 自动沉淀经验
          （experience_from_stats→ExperienceStore，失败降级）；include_perf 返回 perf_metrics 摘要；
          retriever/retriever_k 透传 TextualGradientDescent（D 段 few-shot）。392 测试通过。
  V10.22: 路线图收尾 - pipeline.run_full_cycle 统一主链路；cron_evolution + scripts/cron-evolution.sh；
          trace_recorder；quality_scorer；report_html；stock_comparison；AktoolsSource；PROMPT_TEMPLATES。
  V10.23: 主链路强化 - run_with_realized_feedback 接入 ∇_LLM（DecisionRecord.analyses）；
          pipeline use_validation + dev_rounds=3；calibrate_conviction；aktools_diagnostic。431 测试通过。
  V10.24: 量化数据融合 - LocalCsvSource（BERKSHIRE_DATA_DIR/daily_ohlcv.csv）+ PytdxSource（env-gated）；
          quant_screener_bridge → thesis_queue JSON；docs/quant_data_fusion.md（AlphaGPT 仅文档边界）。
  V10.25: A股 AlphaGPT 因子挖掘 - tools/ashare_factor_mining.py + ashare_alphagpt/（移植 times.py）；
          factor_screener_bridge → thesis_queue --from-factor-scan；可选 extra [factor-mining]。
  重要：所有 skills 均为独立 Agent 指令模板，专为 OpenClaw / QwenPaw 这一类产品设计。
  - OpenClaw：带 YAML frontmatter 的 SKILL.md 格式，可直接安装到 ~/.openclaw/workspace/skills/
  - QwenPaw：作为 loop_engine 提示组件，与 evolution_loop_v10.py 配合使用。
  已移除所有 Claude Code 特定多代理编排指令。
---

# Investment Research Meta-Skill (V10.0 - TextGrad 化)

> **继承来源**: `xbtlin/ai-berkshire` (实盘验证: 2024 +69.29%, 2025 +66.38%)

## 🧩 1. Task Decomposition (研究框架)

### 前置步骤：AI研究偏见自觉（必须执行）

在开始研究前，评估该公司的"AI可研究性"：

**信息丰富度评级**：
| 等级 | 特征 | AI研究陷阱 | 应对策略 |
|------|------|-----------|---------|
| A级 | 上市多年、券商覆盖多 | 共识过强，alpha有限 | 重点做反面检验 |
| B级 | 上市1-3年、覆盖有限 | 可能用"合理推测"填补空白 | 每个推算数据标注置信度 |
| C级 | 刚上市/冷门股 | AI会因资料不足而过度保守 | 用第一性原理提问 |

**偏见自查清单**：
- [ ] 我的"确定性"感受是来自生意本质，还是来自资料数量？
- [ ] 如果把这家公司的资料量减少一半，我的结论会变吗？
- [ ] AI输出的分析是否与市场共识高度雷同？
- [ ] 是否存在"公开资料很少但生意本质极好"的可能性被低估了？

### 日期锚定（强制执行）

当前日期为 `$CURRENT_DATE`。所有数据请求必须基于此日期：
- "最近财年"= 截至今日已披露的最近完整财年年报
- "最近季度"= 截至今日已披露的最近一个季度报告
- "近5年"= 从最近完整财年往回推5年
- 股价/市值 = 最近一个交易日收盘价，必须标注具体日期
- **搜索query中必须包含当前年份**

## 👤 2. Agent Engineering (四大师团队)

| 角色 | 大师 | 分析框架 | 核心追问 |
|:-----|:-----|:---------|:---------|
| **生意分析师** | 段永平 | 商业模式 & 护城河 | "这门生意好在哪？如果只能用一句话描述，是什么？" |
| **财务分析师** | 巴菲特 | 财务报表 & 估值 | "10年后这条护城河还在吗？什么能摧毁它？" |
| **行业研究员** | 芒格 | 行业格局 & 竞争 | "我最可能在哪里犯错？聪明人为什么会不买？" |
| **风险评估师** | 李录 | 风险 & 管理层 | "站在20年后回看，这是'时代的标准石油'还是'昙花一现'？" |

### 模型分配 (Polyglot MAS) - V9.1 优化版

> **优化依据**: 基于 20 条轨迹数据分析，deepseek-v4-pro 表现最佳 (0.915分)

| 角色 | 大师 | 模型 | 引擎 | 性能评分 |
|:-----|:-----|:-----|:-----|:---------|
| **生意分析师** | 段永平 | `deepseek-v4-pro` | 火山引擎 | 0.915 ⭐⭐⭐ |
| **财务分析师** | 巴菲特 | `deepseek-v4-pro` | 火山引擎 | 0.915 ⭐⭐⭐ |
| **行业研究员** | 芒格 | `glm-5.2` | 火山引擎 | 0.770 ⭐ |
| **风险评估师** | 李录 | `kimi-k2.6` | 火山引擎 | 0.880 ⭐⭐ |

**优化说明**:
- 段永平角色从 `qwen3.7-plus` (0.763分) 升级为 `deepseek-v4-pro` (0.915分)
- 预期平均评分提升: 0.838 → 0.870 (+3.8%)

## ⚙️ 3. Workflow Orchestration (7-Step 研究流程)

### 强制要求：四大师全覆盖

> **V9.1 新增**: 每次投研任务**必须**执行全部四大师分析，缺一不可。

| 大师 | 分析阶段 | 必须执行 |
|:-----|:---------|:---------|
| 段永平 | 生意本质分析 | ✅ 必须 |
| 巴菲特 | 护城河评估 | ✅ 必须 |
| 芒格 | 逆向思考 | ✅ 必须 |
| 李录 | 风险评估 | ✅ 必须 |

**违反规则**: 如果任何大师分析缺失，轨迹记录将标记为低分 (< 0.7)，触发对比反思。

### Step 1: 数据收集 (V9.3: Tavily 实时搜索)

> **V9.3 核心升级**: 所有财务数据必须通过 Tavily 实时搜索获取，禁止依赖 LLM 内部知识。

**数据获取流程**:
```bash
# 1. 获取股票实时数据 (股价/市值/PE/PB/股息率)
python3 src/tavily_search.py stock {ticker} {company_name}

# 2. 获取财务指标 (收入/利润/ROE/负债率)
python3 src/tavily_search.py financial {ticker}

# 3. 获取行业新闻 (竞争格局/最新动态)
python3 src/tavily_search.py news {industry} {company}
```

**数据要求**:
- 收入结构、财务指标、竞争格局、商业模式、管理层、行业前景、风险因素、估值
- **所有数据必须标注来源 URL 和获取时间**
- **必须使用 `financial_rigor.py` 进行数据交叉验证**

**数据质量检查**:
- [ ] 股价数据是否为最近交易日？
- [ ] 财务数据是否来自最新财报？
- [ ] 多来源数据是否一致？（不一致时标注差异）

### Step 2: 生意本质分析 — 段永平"对的生意"
- 用一句话定义这门生意的本质
- **收入漏斗分析**：从顶层业务量到自由现金流，逐层标注金额和去向
- 段永平式追问

### Step 3: 护城河评估 — 巴菲特"经济护城河"
- 五类护城河逐一验证：品牌/转换成本/网络效应/规模效应/技术壁垒
- 巴菲特式追问

### Step 4: 逆向思考 — 芒格"反过来想"
- 列出"这家公司可能失败的所有路径"
- 历史类比、跨学科分析、偏误自查
- 芒格式追问

### Step 5: 管理层评估 — 段永平"对的人"
- CEO关键决策复盘、资本配置能力、股东利益一致性
- 段永平式追问

### Step 6: 行业趋势 — 李录"文明演进框架"
- 判断是否处于"文明级范式转移"
- 李录式追问

### Step 7: 估值与安全边际
- 反向DCF、三情景估值（必须用工具验算）
- 段永平式追问

## 🔧 4. 金融严谨性工具 (必须使用)

### 4.1 Tavily 实时搜索 (V9.3 新增)

```bash
# 股票实时数据
python3 src/tavily_search.py stock 0700.HK 腾讯控股

# 财务指标
python3 src/tavily_search.py financial 0700.HK

# 行业新闻
python3 src/tavily_search.py news 互联网 腾讯
```

**环境变量**: `TAVILY_API_KEYS`（逗号分隔多 Key，推荐）或单 Key `TAVILY_API_KEY`。**切勿把真实 Key 写入仓库**，请放 `~/.bashrc` 或 `.env`。
**免费额度**: 1000 次/月/Key（多 Key 轮询见 `src/tavily_search.py`）

### 4.2 财务验证工具

```bash
# 市值验算
python3 tools/financial_rigor.py verify-market-cap \
  --price {股价} --shares {总股本} --reported {报告市值} --currency {币种}

# 估值验算
python3 tools/financial_rigor.py verify-valuation \
  --price {股价} --eps {EPS} --bvps {每股净资产}

# 三情景估值
python3 tools/financial_rigor.py three-scenario \
  --price {股价} --eps {EPS} --shares {股本亿} \
  --growth {乐观} {中性} {悲观} \
  --pe {乐观PE} {中性PE} {悲观PE}

# 数据交叉验证
python3 tools/financial_rigor.py cross-validate \
  --field {字段名} --values '{"来源1": 数值, "来源2": 数值}' --unit {单位}
```

## 🧬 5. Loop Engineering & Skill-MAS 进化机制

### 5.0 TextGrad 化进化 (V10.0 新增)

> **核心思想**: 借鉴 TextGrad (Nature 2025) 的自动微分思想，实现节点级诊断和针对性优化。

> ⚠️ **实现状态（重要，避免文档与代码脱节）**
> - ✅ **已实现**：`src/graph.py`（`BerkshireGraph`：5 层计算图、拓扑排序、`backward()` 文本梯度）+ `src/optimizer.py`（`TextualGradientDescent.step()`）+ `src/evolution_loop_v10.py`（`run_example()` 串起 backward→step 的演示）。`backward()` 默认产出**规则化诊断模板**；V10.17 起可经 `src/llm_gradient.py::enrich_gradients_with_llm` 用 LLM 生成真实批评（∇_LLM）增强，失败自动降级回规则化。
> - ✅ **变量真实改写（V10.13 / Option B）**：`src/prompt_optimizer.py` 的 `apply_gradient` 经 LLM 把诊断落到 Prompt 上；`TextualGradientDescent(graph, llm=...)` 注入后 `step()` 真实改写未达标 prompt 变量的 `value`（LLM 可注入/可 mock，失败优雅降级；不注入则向后兼容）。
> - ✅ **验证门控改写 + 多轮迭代（V10.15 / 档B）**：`src/prompt_validation.py` 的 `validated_apply_gradient`（改写后评分，只有不劣于旧版+`min_improvement` 才接受否则回滚）；`TextualGradientDescent(graph, llm=..., scorer=...)` 注入 scorer 即门控；`src/eval_harness.py` 的 `run_multi_round` 跑多轮并产出 `EvolutionReport`（离线证明单调不退化且收敛）；`src/realized_feedback.py::NetworkPriceProvider` 接真实行情（多源降级链+缓存+非交易日回退，fetcher 可注入）。
> - ✅ **可观测 + 服务化 + 注入防护（V10.16 / 档C）**：`src/observability.py` 结构化 JSON 日志 + `run_id` 经 contextvar 贯穿（`run_context()`）+ LLM 成本/token/延迟埋点（`MetricsCollector`，已接入 `OpenAICompatibleLLMClient`）；`src/service.py` 服务边界（`health/doctor/score/debate` 纯函数处理器 + 可选 FastAPI `create_app()` 暴露 `/health` `/score` `/debate`，`extras[service]`）；`src/sanitize.py` 提示注入防护（`sanitize_untrusted` 清洗喂给改写 LLM 的不可信诊断，配合 `UNTRUSTED_` 分隔符兜底）。
> - ✅ **部署 + 访问控制 + 可监控 + 真梯度（V10.17 / 档D）**：容器化 `Dockerfile`/`docker-compose.yml`（非 root + HEALTHCHECK）+ `service.run()`/`berkshire-serve` uvicorn 入口；`src/access_control.py`（`check_api_key` API Key 鉴权 + `RateLimiter` 限流，经 `create_app` 挂到 `/score` `/debate`）；`src/metrics_export.py`（`/metrics` Prometheus 文本，零依赖）；`src/llm_gradient.py` 的 `enrich_gradients_with_llm` 让 LLM 生成真实批评（∇_LLM）增强未达标节点梯度，失败优雅降级回规则化；mypy 开 `check_untyped_defs`、覆盖率门 50%、golden 回归基线。
> - ✅ **路线图收尾（V10.22）**：`pipeline.run_full_cycle`；`cron` 子命令 + `scripts/cron-evolution.sh`；`trace_recorder`；`quality_scorer`；`report_html`；`stock_comparison`；`docs/PROMPT_TEMPLATES.md`。
> - ✅ **Scenario + CLI + Recorder（V10.21）**：`scenario`；`status`/`reflect`/`optimize`；`run_recorder`；磁盘缓存。
> - ✅ **R/D 双循环（V10.19）**：`src/research_loop.py` 的 `HypothesisProposer` + `run_rd_cycle`（R 提假设 → D 验证门控进化；`proposer=None` 等价纯 D）；`ExperienceDrivenProposer` / `LLMHypothesisProposer` 可注入；D 段经验召回经 `optimizer.retriever`；`decision_log` 可选 `hypothesis_id`。
> - ✅ **借鉴 RD-Agent / Qlib（V10.18）**：`tools/perf_metrics.py` 本地绩效指标库（Qlib `risk_analysis` 口径：年化/波动/IR/夏普/最大回撤/求和累计/超额 CAR/含成本，纯 stdlib，接 `decision_log`+可注入 `PriceProvider`，`render_markdown`/`to_json`）；`src/experience_store.py` 经验库 RAG-lite（`Experience`+`ExperienceStore` JSONL+`KeywordExperienceRetriever` 零依赖召回+`experience_from_stats`；作为 few-shot 经 `build_rewrite_messages(..., examples=None)` 注入改写，`examples=None` 逐字节不变、`sanitize_untrusted` 包裹、失败降级）；`src/hypothesis.py` 显式可证伪 `Hypothesis` 对象+最小 `HypothesisStore`+`group_experiences_by_hypothesis`。
> - 🚧 **明确不做 / 可选后续**：CoSTEER 代码沙箱、qlib 因子栈直依赖、Redis 共享限流、OTel 导出（见 `docs/ROADMAP.md`）。

**计算图结构**:
```
Layer 0: 输入 (ticker, tavily_query, date_anchor)
Layer 1: 数据获取 (tavily_search)
Layer 2: 四大师分析 (duan/buffett/munger/lilu × prompt+model)
Layer 3: 财务验证 (financial_rigor)
Layer 4: 输出 (final_report)
```

**文本梯度反向传播**:
```python
# 模拟失败案例
scores = {"duan": 0.92, "buffett": 0.68, "munger": 0.85, "lilu": 0.55}
gradients = graph.backward(scores)

# 输出:
# buffett_prompt: ❌ 需要补充 PE/PB/DCF 估值分析
# lilu_prompt: ❌ 需要补充长期趋势和管理层分析
```

**对比 V9.3 vs V10.0**:
| 维度 | V9.3 | V10.0 |
|:-----|:-----|:------|
| 诊断精度 | 整体评分 | 节点级定位 |
| 优化方式 | 全局修改 | 针对性修改 |
| 可解释性 | 低 | 高 (梯度可视化) |

**实现文件**: `src/evolution_loop_v10.py`（部署到 QwenPaw 后位于 `~/.qwenpaw/loop_engine/berkshire_v8/`）

**运行演示**:
```bash
python3 src/evolution_loop_v10.py   # 打印计算图节点数与本轮需更新的变量数
```

### 5.0.1 已实现收益反馈闭环 + 多空辩论 (V10.11，吸收自 TradingAgents)

> ✅ **已实现**：用真实已实现收益反推"校准评分"替代硬编码 scores，并在四大师并行之上加显式多空对抗。详见 `docs/textgrad_design.md`。

- **决策落盘** `src/decision_log.py`：`DecisionRecord`（四大师信心 + 价格锚点）追加 JSONL，路径 `BERKSHIRE_DECISION_LOG`（默认 `~/.berkshire/decisions.jsonl`）。
- **收益 → 评分** `src/realized_feedback.py`：`alpha = raw_return - benchmark_return`；`realized_base = clip(0.5 + alpha*SENSITIVITY, 0, 1)`（默认 0.5，V10.12 校准，可用 `BERKSHIRE_SENSITIVITY` 覆盖）；`master_score = clip(1 - |conviction - realized_base|, 0, 1)`。价格经可注入/可 mock 的 `PriceProvider`/`StaticPriceProvider`，核心不连网络。
- **多空辩论** `src/debate.py` + `BerkshireGraph.debate()`：`net_score∈[-1,1]`，中性区 `NET_MARGIN=0.15`，结构化 `DebateResult`（读 `net_stance`/`ok`）。
- **串联** `run_with_realized_feedback(...)`：收益 → 评分 → `backward()` → `optimizer.step()`，附带辩论净判断。

```python
from src import DecisionRecord, run_with_realized_feedback, StaticPriceProvider, BerkshireGraph
d = DecisionRecord("600519","2026-01-02",{"duan":0.9,"buffett":0.8,"munger":0.6,"lilu":0.7},
                   price_anchor=1500.0, benchmark="000300", benchmark_anchor=3800.0)
provider = StaticPriceProvider({("600519","2026-03-31"):1650.0,("000300","2026-03-31"):3900.0})
run_with_realized_feedback(d, realized_date="2026-03-31", price_provider=provider)
BerkshireGraph().debate({"duan":0.9,"buffett":0.8,"munger":0.4,"lilu":0.7}).net_stance
```

### 5.1 轨迹记录 (Trajectory Recording)

每次投研任务执行后，**必须**记录轨迹至 `~/.qwenpaw/berkshire_traces/`：

```bash
# 轨迹记录格式
{
  "task_id": "unique_id",
  "ticker": "AAPL",
  "timestamp": "2026-06-25T19:00:00",
  "phase": "hunter|maker|checker|pm",
  "agent_role": "段永平|巴菲特|芒格|李录",
  "model_used": "qwen3.7-plus|deepseek-v4-pro|glm-5.2|kimi-k2.6",
  "input_data": {...},
  "output_data": {...},
  "latency_ms": 1234,
  "score": 0.85,  // 0-1 自评质量分
  "errors": [],
  "notes": "..."
}
```

**轨迹记录触发点**：
1. 每个大师分析完成后
2. 数据验证失败时
3. 用户反馈修正后

### 5.2 对比反思 (Contrastive Reflection)

**触发条件**：
- 同一标的多次分析（≥2次）
- 评分差异 > 0.2
- 用户明确反馈"分析有误"

**反思流程**：
```bash
# 运行对比反思
python3 src/evolution_loop_v10.py reflect <ticker>
```

**输出**：
- Divergence Points: 高分/低分路径的分歧点
- Success Factors: 高分运行的成功因素
- Failure Modes: 低分运行的失败模式
- Volatility Root Cause: 结果不一致的根本原因

### 5.3 自动优化 (Skill Optimization)

**触发条件**：
- 对比反思完成
- 发现可改进的模式

**优化动作**：
| 类型 | 触发条件 | 动作 |
|:-----|:---------|:-----|
| `add_rule` | 重复错误 | 添加到 Principles History |
| `update_agent` | 模型选择分歧 | 更新 Agent Engineering |
| `reinforce_model` | 某模型表现优异 | 强化模型偏好 |
| `add_safeguard` | 一致性低 | 添加验证检查点 |

**执行优化**：
```bash
# 运行完整优化循环
python3 src/evolution_loop_v10.py optimize <ticker>
```

### 5.4 进化日志 (Evolution Log)

| Date | Event | Action Taken | Score Impact |
|:-----|:------|:-------------|:-------------|
| 2026-06-25 | **V9.1 - 模型优化** | 段永平角色从 qwen3.7-plus 升级为 deepseek-v4-pro (基于20条轨迹数据分析) | +3.8% avg |
| 2026-06-25 | **V9.0 - 继承 ai-berkshire** | 整合四大师并行框架、反偏见机制、金融严谨性工具 | Baseline |
| 2026-06-25 | V8.1 - Self-Evolving | 添加对比反思 + 技能优化 | +0.15 avg |
| 2026-06-25 | V7.3 - Tri-Engine | Qwen + GLM-5.2 + DeepSeek-V4-Pro | +0.10 consistency |

### Principles History

| Round | Issue Identified | Principle Added |
|:------|------------------|-----------------|
| v1.0 | Initial deployment | Baseline structure |
| v2.0 | LLM hallucinated math | Added `financial_rigor.py` hard constraint |
| v7.0 | Model Groupthink | Added Cross-Model Adversarial Validation |
| v8.0 | Static Skill Decay | Added Contrastive Reflection |
| **v9.0** | **Missing 四大师 Framework** | **Inherited from xbtlin/ai-berkshire: 反偏见机制 + 收入漏斗 + 日期锚定** |
| **v9.1** | **Model Performance Gap** | **段永平角色从 qwen3.7-plus (0.763) 升级为 deepseek-v4-pro (0.915)，基于20条轨迹数据分析** |

## 📝 Prompt 模板 (V9.1 优化版)

> **详细模板**: 参见 `docs/PROMPT_TEMPLATES.md`（部署后位于 `~/.qwenpaw/loop_engine/berkshire_v8/`）

### 四大师 Prompt 结构

| 大师 | 角色 | 核心问题 | 输出要求 |
|:-----|:-----|:---------|:---------|
| **段永平** | 生意分析师 | 生意本质、商业模式、竞争壁垒 | 一句话定义 + 收入漏斗 |
| **巴菲特** | 财务分析师 | 护城河、财务健康、估值 | 三情景估值 + 安全边际 |
| **芒格** | 行业研究员 | 失败路径、行业格局、偏误自查 | 失败路径表 + 空方论点 |
| **李录** | 风险评估师 | 文明趋势、风险评估、长期视角 | 风险表 + 20年预判 |

### Prompt 优化要点

1. **结构化输出**: 使用表格和清单，提高可读性
2. **强制验证**: 所有财务数据必须通过 `financial_rigor.py` 验证
3. **反偏见**: 执行信息丰富度评级 (A/B/C) 和偏见自查清单
4. **收入漏斗**: 必须画出从 TPV 到 FCF 的完整漏斗

## 📚 6. 继承的 Skills (18个)

| 类别 | Skills |
|:-----|:-------|
| **投研核心** | `investment-research`, `investment-team`, `investment-checklist` |
| **财报分析** | `earnings-review`, `earnings-team` |
| **行业研究** | `industry-research`, `industry-funnel`, `quality-screen` |
| **组合管理** | `portfolio-review`, `thesis-tracker` |
| **深度分析** | `management-deep-dive`, `bottleneck-hunter`, `deep-company-series` |
| **数据工具** | `financial-data`, `news-pulse` |
| **特色** | `dyp-ask` (段永平问答), `wechat-article`, `private-company-research` |

## 🔧 7. 工具链

| 工具 | 功能 |
|:-----|:-----|
| `financial_rigor.py` | 金融严谨性验证（市值/估值/交叉验证/三情景） |
| `report_audit.py` | 报告数据抽检（15%随机抽样） |
| `ashare_data.py` | A股数据获取（行情/财务/估值/日线） |
| `data_sources.py` | **A股多源降级数据层**（native→tushare→efinance→akshare→baostock→yfinance；全失败不抛崩） |
| `notify.py` | **多通道交付**（Telegram/飞书/本地兜底；零配置只落地不报错） |
| `stock_screener.py` | 股票筛选 |
| `portfolio_scan.py` / `portfolio_risk.py` / `thesis_queue.py` | PM/Risk 层：扫描 + 行动卡草案 / 组合风险 / 研究队列 |
| `xueqiu_scraper.py` | 雪球数据抓取 |
| `morningstar_fair_value.py` | 晨星公允价值计算 |
| `momentum_backtest.py` / `momentum_backtest_v2.py` | 动量回测 |

完整 CLI 用法与可选依赖表见 [`tools/README.md`](../tools/README.md)。

## 📍 8. 数据路径

| 数据 | 路径 |
|:-----|:-----|
| Skills（仓库内） | `skills/` |
| Tools（仓库内） | `tools/` |
| 部署后根目录（QwenPaw） | `~/.qwenpaw/loop_engine/berkshire_v8/` |
| 部署后根目录（OpenClaw） | `~/.openclaw/workspace/skills/berkshire-*/` |
| State | `~/.qwenpaw/berkshire_state.md` |
| Traces | `~/.qwenpaw/berkshire_traces/` |
| Reflections | `~/.qwenpaw/berkshire_reflections/` |
| Evolution Engine | `~/.qwenpaw/loop_engine/berkshire_v8/` |

## 🔄 9. Loop Engineering 集成 (V9.1)

### 9.1 感知层 (Perception)

**触发器**：
- Cron 定时任务（每日 08:30 / 周五 16:00 / 周五 20:00）
- 用户手动触发
- 市场异动事件

**状态感知**：
```bash
# 读取全局状态
cat ~/.qwenpaw/berkshire_state.md
```

### 9.2 认知层 (Cognition)

**四大师并行分析**：
1. 段永平 (生意分析师) → `qwen3.7-plus`
2. 巴菲特 (财务分析师) → `deepseek-v4-pro`
3. 芒格 (行业研究员) → `glm-5.2`
4. 李录 (风险评估师) → `kimi-k2.6`

**认知输出**：
- 7-Step 研究报告
- 信息丰富度评级 (A/B/C)
- 收入漏斗分析
- 三情景估值

### 9.3 行动层 (Action)

**工具调用**：
```bash
# 数据获取（实时检索）
python3 src/tavily_search.py stock <ticker> <company_name>

# 金融严谨性验证
python3 tools/financial_rigor.py verify-market-cap ...

# 报告抽检
python3 tools/report_audit.py extract ...
```

**输出动作**：
- 写入研究报告至 `~/[公司名]投资研究报告.md`
- 更新 `berkshire_state.md`
- 记录轨迹至 `berkshire_traces/`

### 9.4 自愈层 (Healing)

**错误检测**：
- 数据验证失败 → 自动重试或标记
- 模型输出异常 → 切换备用模型
- 工具执行失败 → 降级处理

**错误日志**：
```json
{
  "error_type": "data_mismatch",
  "ticker": "AAPL",
  "field": "market_cap",
  "expected": 3000000000000,
  "actual": 300000000000,
  "action": "retry_with_corrected_unit"
}
```

### 9.5 进化层 (Evolution)

**进化循环**：
```
轨迹记录 → 对比反思 → 技能优化 → 更新 SKILL.md
```

**触发条件**：
- 每周五 20:00 自动运行
- 用户手动触发 `evolution_loop_v10.py optimize`（✅ V10.21+）或 Cron `evolution-loop`（✅ V10.22）

**进化输出**：
- 更新 `SKILL.md` 的 Evolution Log
- 更新 `berkshire_state.md` 的进化日志
- 生成反思报告至 `berkshire_reflections/`

## 🎯 10. Skill-MAS 集成 (V9.1)

### 10.1 Meta-Skill 结构

```yaml
name: investment-research
version: 9.1
type: meta-skill
description: 四大师并行投研框架 + Loop Engineering 自我进化
```

### 10.2 Task Decomposition

| Task | Agent | Model | Output |
|:-----|:------|:------|:-------|
| 数据收集 | Hunter | qwen3-coder-plus | 结构化数据 |
| 生意分析 | 段永平 | qwen3.7-plus | 商业模式画布 |
| 财务分析 | 巴菲特 | deepseek-v4-pro | 估值模型 |
| 行业分析 | 芒格 | glm-5.2 | 竞争格局 |
| 风险评估 | 李录 | kimi-k2.6 | 风险清单 |
| 数据验证 | Checker | - | 验证报告 |
| 报告生成 | PM | - | 完整报告 |

### 10.3 Workflow Orchestration

```
[感知] → [认知: 四大师并行] → [行动: 工具调用] → [自愈: 错误处理] → [进化: 对比反思]
```

### 10.4 对比反思机制 (Skill-MAS 核心)

**输入**：
- 高分轨迹 (score ≥ 0.8)
- 低分轨迹 (score < 0.6)

**分析维度**：
1. **分歧点**：高分/低分路径在哪里开始不同？
2. **成功因素**：高分运行做对了什么？
3. **失败模式**：低分运行哪里出错了？
4. **波动根因**：为什么结果不一致？

**输出**：
- 优化建议列表
- 自动更新 SKILL.md
- 记录至 Evolution Log

## 📊 11. 系统状态监控

### 11.1 健康检查

```bash
# 检查进化循环状态
python3 src/evolution_loop_v10.py status

# 检查轨迹数量
ls ~/.qwenpaw/berkshire_traces/*.json | wc -l

# 检查反思报告
ls ~/.qwenpaw/berkshire_reflections/*.json | wc -l
```

### 11.2 性能指标

| 指标 | 目标 | 当前 |
|:-----|:-----|:-----|
| 轨迹记录数 | ≥ 10 | 待验证 |
| 反思报告数 | ≥ 5 | 待验证 |
| 平均评分 | ≥ 0.75 | 待验证 |
| 评分一致性 | std_dev ≤ 0.15 | 待验证 |
| 进化次数 | ≥ 1/周 | 待验证 |

## 🚀 12. 下一步行动

### 12.1 首次进化循环 (待执行)

```bash
# 1. 运行一次完整投研任务（如分析腾讯控股）
# 2. 记录轨迹
# 3. 运行对比反思
python3 src/evolution_loop_v10.py reflect 0700.HK

# 4. 运行优化
python3 src/evolution_loop_v10.py optimize 0700.HK

# 5. 验证 SKILL.md 更新
grep "v9.1" skills/investment-research.md
```

### 12.2 持续监控

- 每日 08:30: Thesis Tracker 扫描持仓
- 周五 16:00: Deep Research 四大师并行分析
- 周五 20:00: Evolution Loop 对比反思 + 技能优化

### 12.3 长期目标

| 目标 | 时间线 | 状态 |
|:-----|:-------|:-----|
| 完成首次进化循环 | 本周 | ⏳ Pending |
| 达到 10 次轨迹记录 | 2周 | ⏳ Pending |
| 平均评分 ≥ 0.80 | 1月 | ⏳ Pending |
| 自动优化 3 个 Skills | 1月 | ⏳ Pending |

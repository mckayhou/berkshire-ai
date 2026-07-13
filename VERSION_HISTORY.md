# Berkshire AI 版本历史

> **铁律**: 每次新版本必须完成测试才能上线

---

## 🧪 版本测试规范

### 必须完成的测试项

| 测试类型 | 说明 | 通过标准 |
|:---------|:-----|:---------|
| **单元测试** | 核心模块功能验证 | 所有测试用例通过 |
| **集成测试** | 端到端流程验证 | 完整分析流程无报错 |
| **回测验证** | 历史轨迹数据对比 | 诊断覆盖率 ≥ 90% |
| **Cron 测试** | 定时任务触发验证 | 手动触发成功 |

### 测试记录模板

```markdown
### V{X.Y} - {日期}

**变更内容**:
- 

**测试结果**:
- [ ] 单元测试: X/X 通过
- [ ] 集成测试: X/X 通过
- [ ] 回测验证: 诊断覆盖率 XX%
- [ ] Cron 测试: X/X 通过

**结论**: ✅ 上线 / ❌ 需修复
```

---

## 📜 版本历史

### V10.29.2 - 2026-07-13 (AnySearch Skill + Tavily hybrid)

**变更内容**:
- 引入官方 **AnySearch Skill**：`skills/anysearch/`（CLI search / vertical / batch / extract）
- Berkshire 入口：`skills/anysearch-web.md`；`financial-data` 优先走 AnySearch
- `src/tavily_search.py`：AnySearch 补充/回退（`SEARCH_MODE=auto|hybrid|...`），`load_dotenv` 读 Key
- `update-platforms.sh`：同步目录型 skill 到 OpenClaw / QwenPaw
- 离线测试：`tests/test_tools_network.py` 覆盖 AnySearch normalize / hybrid fallback / supplement

**测试结果**:
- [x] 单元测试: `pytest tests/test_tools_network.py` 25 passed
- [x] Skill CLI 手工连通（需本地 `ANYSEARCH_API_KEY`，不入库）

**结论**: ✅ 上线（Key 仅 `.env` / `skills/anysearch/.env`）

---

### V10.29.1 - 2026-07-09 (投研效果契约 + 后验周报 + 离线 E2E)

将「过程质量」接到可证伪的决策后验（不宣称 alpha，先修数据契约）。

**DecisionRecord 契约字段** `src/decision_log.py`
- `thesis` / `kill_condition` / `action` / `horizon_days` / `depth` / `skill`
- `is_research_complete` / `research_gaps` / `mean_stance` / `maturity_date`

**后验与工具**
- `src/posterior_report.py`：方向命中率、校准误差、契约完整率
- `tools/log_decision.py`：append / list / gaps
- `tools/posterior_weekly.py`：周报 CLI（`--prices` / `--network` / `--strict`）
- `tools/seed_portfolio_decisions.py` + `data/portfolio_decision_seeds.json`
- `tools/archive_experiences.py`：归档并清空污染 experiences

**技能 / 文档**
- `skills/investment-research.md`、`thesis-tracker.md` 收尾强制落盘
- `docs/RESEARCH_EFFECTIVENESS.md`、`action-card.md`、`ENGINE.md`、`BACKTEST.md`、`USER_GUIDE.md` §4.4、`TESTING.md`

**测试结果**:
- [x] 单元：`tests/test_posterior_report.py`
- [x] 离线 E2E：`tests/e2e/test_research_effectiveness_e2e.py`（8 passed；落盘→种子→归档→后验→反馈）
- [x] 核心回归：`pytest tests/` **passed**（缺 numpy/torch 时 alphagpt 相关 **skip**，不再炸 collection；LLM smoke 无 Key skip）
- [x] 包导入：`from src import run_full_cycle` 可用（src 双导入 relative-first）

**结论**: ✅ 工具与 E2E 上线；真实命中率待 horizon 到期后用 `posterior_weekly` 积累

---

### V10.29 - 2026-07-04 (多源证据 Brainstorm + SkillForge regression gate)

借鉴 AgentX (Kuaishou, arXiv:2606.26859) 的四路证据加权提案与 paired replay 防劣化。

**多源证据 Brainstorm** `src/evidence_channels.py`
- `EvidenceChannel` 协议：可注入的证据通道（experience / anomaly_scan / knowledge_graph / report）
- `EvidenceBrainstormProposer`：聚合多通道证据，按 confidence 加权排序生成 Hypothesis
- `build_brainstorm_proposer()`：工厂函数，从可用数据源自动构建
- `pipeline.run_full_cycle(use_brainstorm=True)` 接入主链路

**SkillForge Regression Gate** `src/skill_forge/regression_gate.py`
- `replay_trajectories(success_cases, post_skill_md=…)`：patch 后用旧成功轨迹 replay
- 检测退化则自动 rollback（paired replay 防劣化）
- 接入 `skill_forge/pipeline.py` 的 `run_evolution_round(regression_cases=…)`

**测试结果**:
- [x] 单元测试: **520 passed, 2 skipped**（`pytest tests/ -ra`）

---

### V10.28 - 2026-07-02 (TextGrad 真闭环 + 轨迹 A/B + 量化信号接线 + SkillForge 技能进化)

**V10.26 — 分析重跑闭环** `src/graph_analysis.py`
- `AnalysisRunner` / `PromptHeuristicAnalysisRunner`
- `eval_harness.run_multi_round(rerun_analysis=True)`：改写后重跑分析 → `backward(scores)` 梯度
- `research_loop` / `pipeline.run_full_cycle` 透传 `rerun_analysis`

**V10.27 — 轨迹 A/B 验收** `src/trajectory_ab.py` + `tools/trajectory_ab_eval.py`
- bundled `tests/fixtures/trajectories/sample_tasks.json`
- 指标：V9.3 整体分 vs V10 节点诊断覆盖率 vs V10.26 进化 Δ

**V10.28 — 量化信号 → Hypothesis** `src/signal_proposer.py`
- `FactorScanHypothesisProposer` / `LimitupScanHypothesisProposer` / `CompositeHypothesisProposer`
- `pipeline.run_full_cycle(factor_scan=…, limitup_scan=…)` 并入 R 循环

**V10.28 — SkillForge 技能进化** `src/skill_forge/` + `tools/skill_evolve.py`
- LLM-judge Consistency Rate + 四维失败分析 + Skill Diagnostician/Optimizer
- `--judge-mode auto|llm|rule`；文档 `docs/SKILL_EVOLUTION.md`
- 测试：`test_skill_forge.py` + `test_skill_forge_llm.py` + `test_skill_forge_cli.py` + `evolution_cli` skill-evolve

**测试结果**:
- [x] 单元测试: **503 passed, 2 skipped**（含 SkillForge；`pytest tests/ -ra`）

---

### V10.25 - 2026-07-02 (A股 AlphaGPT 因子挖掘 + thesis_queue 接线)

**1) AlphaGPT times.py 移植** `tools/ashare_alphagpt/` + `tools/ashare_factor_mining.py`
- REINFORCE + StackVM 自动因子搜索；数据走 `ashare_data` / `data_sources`（无硬编码 Token）
- 可选 extra：`pip install '.[factor-mining]'`（torch/pandas/pyarrow）

**2) 因子筛选桥接** `tools/factor_screener_bridge.py`
- 已训练公式 → 本地 CSV / 在线多标的打分 → thesis_queue JSON

**3) thesis_queue 扩展**
- `--from-factor-scan` / `--run-factor-scan` / `--factor-codes`

**4) 文档** `docs/quant_data_fusion.md`、`.env.example`、`config/skill.md` 同步

**5) 五维打板评分** `tools/limitup_screener_bridge.py` + `tools/ashare_alphagpt/limitup_scoring.py`
- thesis_queue：`--from-limitup-scan` / `--run-limitup-scan`

**6) 文档体系** `docs/README.md` 文档中心 + 专题 `BACKTEST` / `QUANT` / `ENGINE` / `SKILLS`
- `USER_GUIDE` 工作流导向；`tools/README` / `TESTING` / `README_EN` 交叉导航

**测试结果**:
- [x] 单元测试: test_ashare_alphagpt + test_factor_screener_bridge + test_limitup_scoring + thesis_queue

---

### V10.24 - 2026-07-01 (量化数据融合：LocalCsv + Pytdx + screener bridge)

**1) 本地 CSV 数据源** `LocalCsvSource`
- `BERKSHIRE_ENABLE_LOCAL_DATA=1` + `BERKSHIRE_DATA_DIR/daily_ohlcv.csv`（daily_stock_data 契约）

**2) 可选 pytdx 实时源** `PytdxSource`
- `BERKSHIRE_ENABLE_PYTDX=1`；`pip install .[quant]` 可选 extra

**3) 选股桥接** `tools/quant_screener_bridge.py`
- stdlib CSV 动量筛选 → thesis_queue 友好 JSON

**4) 调研文档** `docs/quant_data_fusion.md`
- tdx_quant / daily_stock_data / AlphaGPT 对比；明确 A 股 only、AlphaGPT 低契合

**测试结果**:
- [x] 单元测试: **438 passed, 2 skipped**
- [x] ruff / mypy 通过

**结论**: ✅ 上线

---

### V10.23 - 2026-07-01 (主链路强化：∇_LLM 接线 + conviction 校准 + aktools 诊断)

**1) ∇_LLM 接入生产反馈闭环**
- `run_with_realized_feedback(..., use_llm_gradient=True)` 在 `backward()` 后调用 `enrich_gradients_with_llm`。
- `DecisionRecord.analyses` 存各大师正文；缺省时回退 `note`。

**2) 验证门控 + 多轮 D**
- `pipeline.run_full_cycle` 默认 `use_validation=True`、`dev_rounds=3`。

**3) conviction 校准** `tools/calibrate_conviction.py`
- 经验库 `stance - realized_base` 偏差报告与建议偏移。

**4) aktools 原子诊断** `tools/aktools_diagnostic.py`
- market_prices + stock_news + stock_info 组装 Markdown（避开 composite bug）。

**测试结果**:
- [x] 单元测试: **431 passed, 2 skipped**
- [x] ruff / mypy 通过

**结论**: ✅ 上线

---

### V10.22 - 2026-07-01 (路线图收尾：HTML / 对决矩阵 / Cron / 轨迹 / 主链路 / aktools)

补齐 ROADMAP 与 skill.md 中所有可落地 backlog。

**1) 统一主链路** `src/pipeline.py::run_full_cycle`
- R/D 双循环 → `run_with_realized_feedback` → 经验/绩效/轨迹/run 记录（默认生产入口）。

**2) Cron 自动进化** `src/cron_evolution.py` + `scripts/cron-evolution.sh`
- `thesis-tracker` / `portfolio-weekly` / `evolution-loop` / `all`；CLI：`evolution_loop_v10.py cron <task>`。

**3) 轨迹自动记录** `src/trace_recorder.py`
- `BERKSHIRE_TRACE_DIR`（默认 `~/.qwenpaw/berkshire_traces`）；反馈闭环自动写入。

**4) 生产 quality_fn** `src/quality_scorer.py`
- 历史「信心 vs alpha」误差 → `build_experience_quality_fn`。

**5) HTML 报告** `tools/report_html.py`（暗色模式 + 侧栏导航，纯 stdlib）。

**6) 多股对决矩阵** `tools/stock_comparison.py`（2–4 只标准化对比）。

**7) 组合风险增强** `portfolio_risk`：地域/货币暴露 + -20% 压力测试。

**8) aktools 适配器** `data_sources.AktoolsSource`（`BERKSHIRE_ENABLE_AKTOOLS=1`）。

**9) 文档** `docs/PROMPT_TEMPLATES.md`；行动卡 golden 回归 `test_golden_action_card.py`。

**测试结果**:
- [x] 单元测试: **420 passed, 2 skipped**
- [x] ruff / mypy 通过

**结论**: ✅ 上线

---

### V10.21 - 2026-07-01 (Scenario + CLI + RunRecorder + 磁盘价格缓存)

完成 RD-Agent P1-D 与 Qlib B1/B3 剩余 backlog，并落地 `reflect` / `optimize` / `status` CLI。

**1) Scenario 抽象（P1-D）** `src/scenario.py`
- `Scenario` dataclass + `DEFAULT_SCENARIO`（与历史四大师逐字节等价）。
- `BerkshireGraph(scenario=...)` 可插拔大师阵容；`TWO_MASTER_DEMO_SCENARIO` 供测试。

**2) 进化 CLI** `src/evolution_cli.py`
- `python3 src/evolution_loop_v10.py status` — 各 JSONL 存储健康摘要。
- `reflect <ticker>` — 对比反思（`src/reflect.py`）。
- `optimize <ticker>` — 反思 + `eval_harness.run_multi_round`（可 mock LLM）。

**3) 轻量 Run Recorder（Qlib B1）** `src/run_recorder.py`
- `RunRecord` + `RunRecorder` JSONL；`feedback` / `reflect` / `optimize` 自动落盘。

**4) 磁盘价格缓存（Qlib B3）**
- `NetworkPriceProvider` 可选 `BERKSHIRE_PRICE_CACHE_DIR` + TTL；默认行为不变。

**测试结果**:
- [x] 单元测试: **407 passed, 2 skipped**
- [x] ruff / mypy 通过

**结论**: ✅ 上线

---

### V10.20 - 2026-07-01 (主线接线：经验沉淀 + 绩效摘要 + retriever)

把 V10.18 的「可插拔层」接入默认 `run_with_realized_feedback()` 主链路，无需再手动调用 `experience_from_stats` / `perf_metrics`。

**1) 经验自动沉淀**
- `persist=True` 时默认 `persist_experience=True`，调用 `experience_from_stats` → `ExperienceStore.append`。
- `lesson` 缺省按 alpha 自动生成；支持 `experience_store` / `experience_log_path` 注入。
- `persist_experience=False` 可单独跳过；沉淀失败降级为 `None`，不崩主链路。

**2) 绩效摘要可选输出**
- `include_perf=True` 时在返回 dict 附带 `perf`（`PerfReport`）。
- 方式 A：锚点 + `realized_price` 两点路径；方式 B：`price_provider` + `realized_date` / `perf_eval_dates`。

**3) D 段 few-shot 召回**
- `retriever` / `retriever_k` 透传 `TextualGradientDescent`，与 V10.19 R/D 双循环一致。

**测试结果**:
- [x] 单元测试: **392 passed, 2 skipped**
- [x] ruff / mypy 通过

**结论**: ✅ 上线

---

### V10.19 - 2026-06-30 (R/D 双循环：HypothesisProposer + research_loop)

基于 `docs/rdagent_reference.md` P1-C，落地 Research/Development 双循环最小编排层。

**1) R/D 双循环** `src/research_loop.py`
- `HypothesisProposer` 可注入协议；`StaticHypothesisProposer` / `ExperienceDrivenProposer`（零 LLM，从 refuted 经验归纳）/ `LLMHypothesisProposer`（可 mock）。
- `run_rd_cycle()`：每轮 **R**（提假设 → 可选落盘 `HypothesisStore`）→ **D**（复用 `eval_harness.run_multi_round`）；`proposer=None` 时退化为纯 D（与 V10.18 等价）。
- `RDCycleReport`：逐轮假设数 + D 段 `EvolutionReport`；`monotonic_non_decreasing` 不变式仍成立。

**2) 经验召回贯穿 D 段改写**
- `TextualGradientDescent(retriever=, retriever_ticker=)` 改写前召回 few-shot 经验；`validated_apply_gradient(..., examples=)` 透传。
- `run_multi_round(..., retriever=, retriever_ticker=)` 可选参数，默认 None 行为不变。

**3) 决策链衔接** `decision_log.DecisionRecord`
- 新增可选 `hypothesis_id`（向后兼容，老数据不受影响）。

**测试结果**:
- [x] 单元测试: **388 passed, 2 skipped**（+6 research_loop / hypothesis_id）
- [x] ruff / mypy 全绿（21 files）

**结论**: ✅ 上线

---

### V10.18 - 2026-06-30 (借鉴 RD-Agent / Qlib：绩效度量 + 经验库 + 假设对象)

基于 `docs/qlib_evaluation.md` 与 `docs/rdagent_reference.md` 的只读评估结论，按依赖
顺序落地三项「值得借鉴」的最小切口（借口径/借理念，**不引第三方重依赖、不进核心依赖**）。

**1) 本地绩效指标库** `tools/perf_metrics.py`（借鉴 Qlib `risk_analysis` 口径，纯 stdlib 零依赖）
- 年化收益、年化波动、信息比率(IR)/夏普、最大回撤、累计收益（**求和口径**对齐 Qlib 避免指数失真）、胜率、相对基准超额(CAR)/α；提供**含/不含成本**两套口径。
- 桥接 `decision_log` 决策快照 + **可注入/可 mock 的 PriceProvider**（鸭子类型 `.get_price`）拼净值/超额曲线；纯函数、离线可测、`render_markdown`/`to_json` 导出。
- 填补现状：此前回测只有「总收益率%」，无任何风险调整指标。

**2) 经验库（RAG-lite）** `src/experience_store.py`（借鉴 RD-Agent knowledge base / CoSTEER sampler）
- `Experience`（结构化成败经验）+ `ExperienceStore`（JSONL 落盘，复用 `decision_log` 风格，`BERKSHIRE_EXPERIENCE_LOG` 可覆盖）+ `ExperienceRetriever` 协议。
- 默认 `KeywordExperienceRetriever`（ticker>sector>tag 确定性关键词召回，**零新依赖**），`StaticExperienceRetriever` 供测试/注入；检索失败一律降级为 `[]` 不崩主链路。
- `experience_from_stats()` 把 `realized_feedback` 已算出却被丢弃的 alpha/realized_base 成败信号转成可检索经验。
- **few-shot 注入**：`build_rewrite_messages(..., examples=None)` 新增可选参数，注入内容经 `sanitize_untrusted` 包裹；**`examples=None` 时输出与改动前逐字节一致**（单测断言）。`apply_gradient` 透传 `examples`。

**3) 显式假设对象** `src/hypothesis.py`（借鉴 RD-Agent 一等公民 Hypothesis）
- `Hypothesis`（命题/依据/证伪条件/状态/proposed_by/关联决策）+ 最小 `HypothesisStore`（JSONL）。校验 `proposed_by` 属 `MASTER_PREFIXES` 或 `system`。
- 预留 `group_experiences_by_hypothesis()`（经验按假设聚合）为后续 R/D 双循环铺路；**本次不接主链路，避免过度工程**。

**明确不做**（报告判定不该抄）：CoSTEER 代码生成 + Docker 沙箱、多 trace 调度/Web viewer、qlib 因子/ML/数据二进制栈/qrun/RL/组合优化直依赖。

**测试结果**:
- [x] 单元测试: **382 passed, 2 skipped**（较 V10.17 +63；新增 perf_metrics / experience_store / hypothesis / few-shot 注入用例）
- [x] ruff check src tests tools 全绿；mypy 全绿（20 files）；coverage 59.96%（门槛 50%）
- [x] `examples=None` 逐字节回归断言通过，现有测试零破坏

**结论**: ✅ 上线

---

### V10.17 - 2026-06-30 (生产化硬化 档D：部署上线 + 访问控制 + 指标导出 + 真梯度)

把引擎从「可服务化」推进到「**可部署、可防护、可监控、批评更真实**」的上线形态。

**1) 容器化部署** `Dockerfile` / `docker-compose.yml` / `.dockerignore`
- 多阶段构建（builder 装 `.[service]` 依赖 → runtime 仅带运行所需），**非 root**（uid 10001）运行。
- 内置 `HEALTHCHECK` 命中 `/health`；`docker compose up --build` 一键起服务。
- 入口 `service.run()` 起 uvicorn（读 `BERKSHIRE_HOST/PORT`），并暴露 console_script `berkshire-serve`。

**2) 访问控制** `src/access_control.py`
- **API Key 鉴权**：`check_api_key()` 常量时间比较（`hmac.compare_digest`），命中返回脱敏指纹；`allowed` 为空=不鉴权（内网/开发）。
- **每客户端限流**：`RateLimiter` 固定窗口（每分钟 N 次），按 key 指纹或 IP 分桶，线程安全。
- 经 `service.create_app(api_keys=, rate_limit_per_min=)` 挂到 `/score` `/debate`（缺省读 `BERKSHIRE_API_KEYS` / `BERKSHIRE_RATE_LIMIT_PER_MIN`）；未配置则放行（向后兼容）。健康/指标端点不鉴权。

**3) 指标导出** `src/metrics_export.py`
- `ServiceMetrics` 线程安全计数器（各端点请求/成功/失败/鉴权拒绝/限流）。
- `render_prometheus()` 输出 Prometheus 文本格式，经 `/metrics` 暴露；可附带 `MetricsCollector` 的 LLM 成本/token/延迟 gauge。零第三方依赖（不引入 prometheus_client）。

**4) ∇_LLM 真梯度** `src/llm_gradient.py`
- `LLMGradientGenerator.critique()`：LLM 读「该大师分析为何不达标」生成自然语言批评（替代规则化 `MASTER_CHECKS` 模板）。分析正文经 `sanitize_untrusted` 中和注入。
- `enrich_gradients_with_llm()`：在 `backward()` 后用 LLM 批评**增强**未达标大师节点及其 prompt 节点的梯度；任何失败（无 LLM / 调用异常 / 解析空）**优雅降级回规则化梯度**，不崩链路。产物仍是结构化 `Gradient`，与 `apply_gradient` / `validated_apply_gradient` 完全兼容。

**5) 工程门禁收紧**
- mypy 开启 `check_untyped_defs`（检查未注解函数体，此前默认跳过）——`src/` 18 文件无问题。
- 覆盖率门 45% → **50%**（当前 57%）；CI 新增 `e2e-llm`（带 secret 才跑真实 LLM 冒烟，fork 自动跳过）+ `build-image`（Docker 构建冒烟）。
- 固化 **golden 回归** `tests/test_eval_harness_golden.py`：逐轮均值质量 0.00→0.25→0.50→0.75 精确可断言 + 坏 LLM 全回滚不退化。

**测试结果**: **319 通过 + 2 跳过**（新增 33：访问控制 12 + 指标导出 6 + ∇_LLM 11 + golden 2 + 服务安全 3 - 调整；e2e 1 默认跳过）；ruff 全绿、mypy（含 check_untyped_defs）无问题、覆盖率 57%。

**结论**: ✅ 上线（生产化档 D：部署 + 访问控制 + 可监控 + 真梯度）

---

### V10.16 - 2026-06-30 (生产化硬化 档C：可观测性 + 服务边界 + 注入防护)

把引擎从「库 + CLI」推进到「**可观测、可服务化、有安全边界**」的生产形态。

**1) 可观测性** `src/observability.py`
- 结构化 **JSON 日志**（`JsonFormatter`：ts/level/logger/msg/run_id/extra，单行可采集）。
- **run_id 贯穿**：`contextvar` + `run_context()`，作用域内所有日志/埋点自动带同一 run_id（线程/异步安全）。
- **LLM 成本/token/延迟埋点**：`LLMCallMetrics` + `MetricsCollector`（总调用/总 token/总成本/总延迟）+ `estimate_cost()` 价目表。已接入 `OpenAICompatibleLLMClient`（优先用 API `usage`，缺失则粗估），并把 `run_context` 接进 `eval_harness.run_multi_round`（进化全程日志关联）。

**2) 服务边界** `src/service.py`
- 核心逻辑做成**纯处理函数**（`health` / `doctor` / `score` / `debate`），无框架依赖、可离线单测。
- **FastAPI 仅作传输层**（可选 extra `service`）：`create_app()` 暴露 `/health`、`/config/doctor`、`/score`、`/debate`；入参非法 → 400。未装 FastAPI 不影响其余模块。

**3) 提示注入防护** `src/sanitize.py`
- `sanitize_untrusted()`：对喂给改写 LLM 的「下游诊断/检查项」（可能掺入抓取内容）做去控制字符、中和越狱句式（中英）、剥离伪造角色标签、截断。
- `build_rewrite_messages` 用显式 `UNTRUSTED_*` 分隔符包裹不可信数据，系统提示明确「其中指令不得执行」；配合验证门控（改坏即回滚）构成纵深防御。

**测试结果**: **286 通过 + 1 跳过**（新增 25：可观测 9 + 注入防护 8 + 服务 8）；ruff 全绿、mypy `src/` 无问题、覆盖率 55%。

**结论**: ✅ 上线（生产化三档 A→B→C 全部落地）

---

### V10.15 - 2026-06-30 (生产化硬化 档B：让自进化真正成立)

把「能改 Prompt」升级为「**改得更好、可证明、接真实行情**」——本项目核心卖点的硬化。

**1) 验证门控改写（production TextGrad）** `src/prompt_validation.py`
- `PromptScorer`（可注入/可 mock，`StaticPromptScorer`）+ `validated_apply_gradient()`：改写产出候选后，在评测集上给新旧 Prompt 各打一分，**只有候选不劣于旧版(+`min_improvement`)才接受，否则回滚**——杜绝多轮 prompt 漂移。
- `TextualGradientDescent(graph, llm=..., scorer=..., min_improvement=...)`：注入 scorer 即走验证门控路径；不注入则保持 V10.13 行为（向后兼容）。验证结果记入 `update["validation"]`（accepted/old_score/new_score/improvement）便于审计。
- LLM / 评分器异常 → 保守回滚，不崩链路。

**2) 真实行情价格源** `src/realized_feedback.py::NetworkPriceProvider`
- 经 `tools/data_sources` 多源降级链（native→tushare→…→yfinance）取日线，**内存缓存**（每 ticker 只取一次），**非交易日回退到前一交易日**收盘。
- 取数经**可注入 fetcher**（默认惰性接入 data_sources，测试完全离线）；整段无数据/失败 → KeyError，行为与 `StaticPriceProvider` 一致。把收益反馈闭环从 mock 接到真实行情。

**3) 多轮迭代循环 + 离线评测台** `src/eval_harness.py`
- `run_multi_round()`：逐轮「打分→未达标梯度→验证门控改写→记录」，全部达标 / 本轮零接受即收敛。
- `EvolutionReport`：逐轮均值质量 + 接受/回滚数 + `monotonic_non_decreasing` + `improvement`。
- **回归证据**：测试断言「好改写→质量单调上升并收敛」「坏改写→全回滚、质量不退化、立即收敛」——把「自进化确有收益且不退化」变成可复现的离线回归。

**测试结果**: **261 通过 + 1 跳过**（新增 29：验证门控 13 + 真实价格源 9 + 评测台 7）；ruff 全绿、mypy `src/` 无问题、覆盖率 53%。

**遗留**: 真实分析侧的 `quality_fn` / LLM 评分器仍需对接「在 held-out 标的上跑大师分析并打分」的生产实现（当前接口已就绪、可注入）。

**结论**: ✅ 上线

---

### V10.14 - 2026-06-30 (生产化硬化 档A：工程门禁 + 打包 + 中心配置)

**变更内容**:

- **打包/工具配置** `pyproject.toml`：项目元数据 + 运行时依赖(httpx) + 可选 extras(`ashare`/`dev`) + 集中 ruff/mypy/pytest/coverage 配置。
- **CI 升级** `.github/workflows/test.yml`：
  - `lint-type` 作业：`ruff check`（lint + import 排序）+ `mypy`（核心引擎 src/）
  - `pytest` 作业：Python **3.10 / 3.11 / 3.12 矩阵** + 从 `requirements.txt` 安装 + `--cov-fail-under=45` 覆盖率门 + pip 缓存
  - `security` 作业：`pip-audit`（依赖漏洞，非阻断保可见性）+ `gitleaks`（密钥扫描）
  - 新增 `.github/dependabot.yml`：pip + github-actions 周更
- **中心配置** `src/config.py`：所有环境变量的单一事实来源（`ENV_SPEC`）+ 零依赖 `.env` 加载（不覆盖真实环境）+ `get_settings()` 只读快照 + `doctor()` 启动自检（ready/degraded/unconfigured，**不泄露密钥明文**）+ CLI `python3 src/config.py`。
- 新增 `.env.example` 模板；`src/__init__.py` 补导出 `prompt_optimizer` 符号。
- **代码清理**：ruff 修复全仓 ~100 处（未用 import / 多余 f-string 前缀 / 裸 except / 单行 if 等）；mypy 修复 src/ 3 处类型问题（缺注解 / Optional 收窄）。

**测试结果**: **232 通过 + 1 跳过**（新增 10 个 config 单测），ruff 全绿、mypy `src/` 无问题、覆盖率 51%（门槛 45%）。

**结论**: ✅ 上线

---

### V10.13 - 2026-06-30 (变量真实改写 Option B：apply_gradient 经 LLM 改写 Prompt)

**变更内容**:

- 新增 `src/prompt_optimizer.py`：把「文本梯度」第一次真正落到 Prompt 上。
  - `LLMClient` 抽象 + `StaticLLMClient`（离线/测试：固定响应 / 回调 / echo）+ `OpenAICompatibleLLMClient`（真实：OpenAI 兼容 `/chat/completions`，env 配置 `BERKSHIRE_LLM_API_KEY`(兜底 `OPENAI_API_KEY`)/`_BASE_URL`/`_MODEL`，含瞬时错误退避重试，缺 key 即报错不静默）
  - `build_rewrite_messages(variable, gradient, base_prompt)` 纯函数构造改写提示；`apply_gradient(variable, gradient, llm)` 由 LLM 读「下游诊断 + 当前 Prompt」产出改进版 Prompt（含代码块清洗）
- 修改 `src/optimizer.py`：`TextualGradientDescent(graph, llm=...)`。注入 `llm` 后 `step()` 对未达标的 prompt 变量**真实改写 `Variable.value`**，记录 `old_value/new_value/rewritten`；LLM 失败/无底稿优雅降级（`rewrite_error`/`rewrite_skipped`），不崩链路。不注入 `llm` 则与旧行为完全一致（向后兼容）。
- 修改 `src/evolution_loop_v10.py`：`run_with_realized_feedback(..., llm=None)` 透传；导出新符号。
- 新增 `tests/test_prompt_optimizer.py`：18 个离线单测（改写/ok 跳过/无底稿/代码块清洗/空返回/缺 key 报错/env 解析/OPENAI_API_KEY 兜底/step 真实改写/无 llm 兼容/LLM 异常降级/只改未达标变量），全部 mock，不打真实网络。

**设计原则**: 与 `realized_feedback` 一致——LLM 经可注入/可 mock 接口获取，核心可离线单测；全部配置走环境变量；失败优雅降级绝不崩链路。

**仍属未来工作**: (a) 把启发式「批评/梯度」也换成 LLM 生成（`∇_LLM`，替代 `MASTER_CHECKS`）；(b) 把单步「backward→改写→回填」扩成多轮自动迭代。

**测试结果**: 223 通过（205 既有 + 18 新增，`python3 -m pytest tests/ -q`，0 失败）

**结论**: ✅ 上线

---

### V10.12 - 2026-06-30 (SENSITIVITY 尺度校准：用真实历史行情校准收益反馈映射)

**变更内容**:

- 新增 `tools/calibrate_sensitivity.py`：用真实历史日线对 `realized_feedback` 的 `SENSITIVITY` 做 **data-only 尺度校准**。
  - 取数走可注入 `HistoryProvider`（`DictHistoryProvider` 离线 / `YFinanceProvider` 美港股 / `TushareProvider` + `AkshareProvider` A股 + 沪深300指数 / `ChainProvider` 按市场降级），核心数学不连网络
  - 标的：汇总 `data/watchlist.json` + `data/holdings.example.json`（去重、忽略 `CASH` 与 `_` 元字段）；per-market 基准：美股 `^GSPC`、港股 `^HSI`、A股 沪深300
  - 目标函数（对肥尾稳健）：`J(S)=|spread₁₀₋₉₀(realized_base;S) − 0.80|`，让中位 80% 决策映射到 `realized_base∈[0.1,0.9]`，极端 ±10% 尾部有意留给饱和
  - 搜索 loop：网格扫描记录 `J(S)` 曲线 → 黄金分割在 bracket 内细化收敛
- 修改 `src/realized_feedback.py`：默认 `SENSITIVITY` **2.5 → 0.5**（校准结论），新增环境变量 `BERKSHIRE_SENSITIVITY` 覆盖（零侵入，非法/非正值静默回退）
- 新增 `tests/test_calibrate_sensitivity.py`：22 个离线单测（目标函数/搜索收敛/肥尾稳健/市场分类/取数管线/env 覆盖），全部 mock，不打真实网络
- 文档：`docs/textgrad_design.md`（校准方法与结论）、`tools/README.md`（`calibrate_sensitivity` 用法）、`docs/ROADMAP.md`（aktools-pro 数据后端 backlog）

**真实数据覆盖**: 27/27 标的（美股 22 + 港股 4 + A股 1），0 未覆盖。A股 `600900` 与沪深300基准经 akshare 兜底（Tushare 免费 token 无 `daily`/`index_daily` 接口权限，自动降级）。

**校准结论**: 观测 alpha 严重右偏肥尾（std≈1.75，max≈+811%，AI/加密/次新股驱动）。旧默认 2.5 使 ~78% 的 realized_base 被 clip 到 0/1（spread 饱和到 1.0）。推荐 S：12 个月窗 ≈0.41、6 个月窗 ≈0.68；取稳健折中 **0.5**（sat_ratio 78% → ~15%）。

**测试结果**: 205 通过（183 既有 + 22 新增，`python3 -m pytest tests/ -q`，0 失败）

**结论**: ✅ 上线

---

### V10.11 - 2026-06-30 (已实现收益反馈闭环 + 多空辩论 · A股多源降级数据层 + 多通道推送)

**变更内容**:

A) 分析脑 — 已实现收益反馈闭环 + 多空对抗辩论（吸收自 TradingAgents）
- 新增 `src/decision_log.py`：决策快照 JSONL 持久化（`DecisionRecord`），路径环境变量 `BERKSHIRE_DECISION_LOG`（默认 `~/.berkshire/decisions.jsonl`），复用 `MASTERS` 单一来源校验大师评分
- 新增 `src/realized_feedback.py`：已实现收益 → 评分转换器。`raw_return`/`alpha`；`realized_base=clip(0.5+alpha*SENSITIVITY,0,1)`（默认 `SENSITIVITY=2.5`）；`master_score=clip(1-|conviction-realized_base|,0,1)`；价格通过可注入/可 mock 的 `PriceProvider`/`StaticPriceProvider` 获取（核心不连网络）
- 新增 `src/debate.py`：多空对抗辩论。`net_score∈[-1,1]`，中性区 `NET_MARGIN=0.15`，结构化 `DebateResult`（控制流读 `net_stance`/`ok`，不解析文本）
- 修改 `src/graph.py`：新增 `BerkshireGraph.debate()`（Layer 2 与输出之间的一步）
- 修改 `src/evolution_loop_v10.py`：新增 `run_with_realized_feedback(...)`（收益→评分→backward 闭环，附带辩论净判断），保留 `run_example()`
- 修改 `src/__init__.py`：导出上述新符号
- 新增 `tests/test_realized_feedback_loop.py`

B) 数据/交付层 — A股多源降级数据层 + 多通道推送（吸收自 JusticePlutus）
- 新增 `tools/data_sources.py`：A股数据多源降级链 `native→tushare→efinance→akshare→baostock→yfinance`（可用 `--sources` / `BERKSHIRE_DATA_SOURCES` 覆盖排序）；覆盖 daily/quote/fundamentals；全部失败返回 `ok=False`+attempts 而不抛崩；可插拔 `DataSource` 适配器；tushare 增强源需 `BERKSHIRE_ENABLE_TUSHARE=1`+`TUSHARE_TOKEN`，其余源 import 守卫缺库自动跳过
- 新增 `tools/notify.py`：多通道交付。Telegram（`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`，超长拆分）、飞书（`FEISHU_WEBHOOK`+可选 `FEISHU_SECRET`，卡片→文本回退+加签+长消息拆分）、本地兜底（`BERKSHIRE_NOTIFY_DIR`，默认 `reports/notifications`）；零配置只落地不报错；用系统 curl 零依赖
- 修改 `tools/ashare_data.py`：新增 `fetch_daily()` + `daily` 子命令
- 修改 `tools/README.md`、`requirements.txt`（标注可选库）、`.gitignore`（忽略 `reports/notifications/`）
- 新增 `tests/test_tools_data_sources.py`、`tests/test_tools_notify.py`

**测试结果**: 183 通过（`python3 -m pytest tests/ -q`，0 失败）

**结论**: ✅ 上线

---

### V10.10 - 2026-06-27 (接线：holdings + portfolio-review + 周度脚本)

**变更内容**:
- `data/holdings.example.json`；`portfolio_risk`/`portfolio_scan` 自动读 `data/holdings.json`
- `scripts/portfolio-weekly.sh`：scan → thesis_queue 一键工作流
- `portfolio-review`：强制 `portfolio_risk` + scan；`news-pulse`：Pending Queue 模板
- `docs/ROADMAP.md` 同步 V10.9–10.10 状态

**测试结果**: 128 通过

**结论**: ✅ 上线

---

### V10.9 - 2026-06-27 (Risk Manager + 研究队列 + CI + lite 深度)

**变更内容**:
- 新增 `tools/portfolio_risk.py`：组合集中度、现金、主题暴露、可选相关性告警
- 新增 `tools/thesis_queue.py`：解析 `config/state.md` + 合并 `portfolio_scan` → `research_now` 优先级
- `portfolio_scan.py`：`--holdings` / `--proposed` 输出 `risk_flags`
- `skills/investment-research.md`：lite / standard / deep 三档深度
- `docs/action-card.md`：risk_flags 字段；`thesis-tracker` 队列同步流程
- `config/state.md`：工具路径改为仓库内 `tools/`
- GitHub Actions：`pytest tests/`（`.github/workflows/test.yml`）
- 新增离线单测：`test_tools_portfolio_risk.py`、`test_tools_thesis_queue.py`

**测试结果**: 125 通过

**结论**: ✅ 上线

---

### V10.8 - 2026-06-26 (吸收 ai-hedge-fund：行动卡 + portfolio_scan)

**变更内容**:
- 新增 `docs/action-card.md`：结构化行动卡模板（立场/仓位/目标价/风险/催化剂），研报与组合报告末尾必附
- 新增 `tools/portfolio_scan.py`：watchlist 扫描 + 行动卡草案输出（`--json`/`--group`/`--top`），借鉴 PM 层但保持研报导向
- Skills 接入：`investment-research`、`investment-team`（PM 汇总 7½）、`portfolio-review`（扫描候选池）
- 文档：`report-conventions`、`tools/README`、`README` 导航更新
- 新增 6 个离线单测 `tests/test_tools_portfolio_scan.py`

**测试结果**: 113 通过

**结论**: ✅ 上线

---

### V10.7 - 2026-06-26 (网络层加固：瞬时错误重试 + 18 个离线网络测试)

**变更内容**:
- **`src/tavily_search.py`**：`search()` 增加瞬时错误重试——超时 / 连接错误（`httpx.TimeoutException`/`TransportError`）/ 5xx 网关错误（500/502/503/504）指数退避（封顶 4s）后重试；429 维持切 Key；其它错误立即返回。删除从未使用的死参数 `_retries`，改为 `max_retries`
- **`tools/ashare_data.py`**：`_curl()` 增加重试（默认 2 次）+ 显式 `subprocess.TimeoutExpired` 处理，最终失败抛 `ConnectionError`（原先超时会直接冒泡）
- **`tools/morningstar_fair_value.py`**：`fetch_page()` 增加重试 + 超时/空响应/**非 JSON**（被限流/拦截）处理，最终失败抛 `ConnectionError`（原先非 JSON 会 `JSONDecodeError` 崩溃）
- **新增 18 个离线网络测试** `tests/test_tools_network.py`（monkeypatch httpx/subprocess，零真实网络）：
  - tavily：`_load_keys` 多/单/空、无 key 抛错、Key 轮询、瞬时重试成功、5xx 重试耗尽、429 切 Key、4xx 立即 error、结果解析+截断+error 透传
  - ashare：`_curl` 成功/GBK 回退/超时重试/持续失败抛错
  - morningstar：`fetch_page` 成功/非 JSON 重试/持续超时抛错

**测试结果**:
- 全量: 107 通过（带 Tavily key 时 0 跳过；无 key 时 1 跳过）
- lint: 无错误；graphify 图已更新

**结论**: ✅ 上线

---

### V10.6 - 2026-06-26 (工具层加固：离线单测 + 3 处健壮性/正确性修复)

**变更内容**:
- **新增离线单元测试 76 个**（无网络、无外部依赖，3 个文件）：
  - `tests/test_tools_financial_rigor.py`：精确十进制计算（exact/fmt_number/市值/估值/交叉验证/Benford）+ AST 安全求值器的**安全边界**（拒绝 `__import__`/属性/函数调用/自由变量/lambda/列表字面量/超大幂）
  - `tests/test_tools_report_audit.py`：数据点提取/标签过滤/抽样确定性/偏差判定/准出打回判决
  - `tests/test_tools_misc.py`：`ashare_data`（代码前缀转换/腾讯行情解析/脏输入格式化）、`stock_screener`（动量信号 `check_momentum`/分级 `grade_signal`）、`morningstar`（星级渲染/ticker 提取）
- **健壮性/正确性修复（3 处）**：
  1. `report_audit.render_verdict`（**正确性 bug**）：单一来源偏差超阈值此前被软化为"⚠️ 警告"并仍判 **PASS/准出**——对审计工具是危险默认。现修复为：单来源完全取决于该来源（超阈值即 **FAIL/打回**）；双来源维持"皆过=通过 / 皆错=不通过 / 一过一错=警告"
  2. `financial_rigor.cross_validate`（**崩溃**）：空来源字典此前因对空列表取中位数 `IndexError`；现返回 `{consensus: None, all_consistent: False}` 并提示
  3. `financial_rigor.safe_arith_eval`（**资源耗尽防护**）：幂运算指数 >1000 直接拒绝，防止 `9**99999` 类表达式吃满 CPU/内存
- CLI 三处修复均已 e2e 验证（巨幂拒绝 / 空交叉验证 / 单源 30% 偏差判 FAIL）

**测试结果**:
- 全量: 88 通过 / 1 跳过（Tavily 无 key skip）
- lint: 无错误；graphify 图已更新

**结论**: ✅ 上线

---

### V10.5 - 2026-06-26 (TextGrad 引擎清理：去重 + 结构化梯度)

**变更内容**:
- **四大师单一来源**：`src/graph.py` 新增 `Master` dataclass + `MASTERS` 常量，派生 `MASTER_PREFIXES`/`ROLE_NAMES`/`MASTER_CHECKS`；变量/边/反向传播/诊断全部从 `MASTERS` 派生，节点命名收敛到 `analysis_node`/`prompt_node`/`model_node`。消除散落在 4 处的硬编码大师列表——新增大师只需改一处。
- **去 emoji 字符串耦合（控制流结构化）**：新增 `Gradient` dataclass（`ok`/`score`/`issues`/`text`）。`backward()` 返回类型 `Dict[str, str]` → `Dict[str, Gradient]`。
  - `optimizer.step()` 判定从 `"❌" not in gradient` 改为 `gradient.ok`，并记录结构化 `issues`
  - 测试/回测消费方 `"❌" in g` → `not g.ok`
  - `Gradient` 保留 `__str__`/`__contains__` 仅用于展示兼容，不参与任何控制流
  - `evolution_loop_v10.py` 通过 `__all__` 对外导出 `Gradient`/`Master`/`MASTERS`
- **零行为回归**：example runner 仍为 18 nodes / 7 updates，回测覆盖率不变
- **文档同步**：`docs/textgrad_design.md` 更新为「实现现状 + Option B」两段——新增实现状态表、修正与代码脱节的旧片段（`failure_trace`→`scores`、返回 str→`Gradient`、`"❌" in grad`→`.ok`）、补 `MASTERS`/`Gradient` 真实片段、Phase 勾选实际进度
- **新增测试**：`test_masters_single_source` / `test_gradient_is_structured` / `test_optimizer_reads_ok_field`（守护单一来源 + 结构化契约）
- 为将来走 B（LLM 驱动自进化）铺路：`Gradient.issues` 已结构化，未来填入 LLM 批评意见时消费方无需改动

**测试结果**:
- 单元 + 集成测试: 12 通过 / 1 跳过（Tavily 无 key skip；单元由 5→8 用例）
- 回测验证: 诊断覆盖率 100%
- 进化引擎 example: Graph 18 nodes / Updates 7（与重构前一致）
- lint: 无错误；graphify 图已更新

**结论**: ✅ 上线

---

### V10.4 - 2026-06-26 (upstream 对齐 + 全量 E2E + 文档完善)

**变更内容**:
- **与 upstream 对齐**（能力/治理/文档层）：
  - `skills/private-company-research.md` 重写为 upstream 完整 6 子 Agent 框架（商业模式/财务侦探/竞争/风险治理/技术IP/替代数据），并适配 OpenClaw/QwenPaw 多 Agent 编排（1108 行）
  - 新增 `LICENSE`(MIT)、`README_EN.md`、`docs/ROADMAP.md`、`docs/report-conventions.md`、`assets/architecture.mmd`+`.png`
  - 带入 `data/`（5 个 csv/json，供 stock_screener/morningstar 用）+ 2 份样例报告（RocketLab、赛力斯）
  - 未并入 upstream 的 2084 份历史报告与个人实盘记录（属原作者作品/私人数据）
- **全量 E2E 测试**（详见 TESTING.md）：单元/集成/回测/进化引擎 + 9 个工具全部跑通
- **Bug 修复**：`tools/morningstar_fair_value.py` 增加 argparse（`--help` 不再触发 84 秒抓取；新增 `--max-pages`/`--top`），星级渲染容错（`_stars()`）
- **文档完善**：新增 `TESTING.md`、`tools/README.md`；README 增加文档导航 + 测试章节，修复一处游离代码围栏

**测试结果**:
- 单元 + 集成测试: 9 通过 / 1 跳过（Tavily 在受限网络下 skip，有网时通过真实 API）
- 回测验证: 诊断覆盖率 100%
- 工具 E2E: financial_rigor(6子命令+安全)/report_audit/ashare_data(4)/momentum×2/stock_screener/morningstar/tavily 全部通过；xueqiu CLI 验证（全量需登录态）

**结论**: ✅ 上线

---

### V10.3 - 2026-06-26 (graphify 集成)

**变更内容**:
- 集成 graphify 知识图谱工具：
  - `graphify hook install` (post-commit 等自动更新)
  - `graphify update . --no-cluster` 构建代码图 (44 nodes, 68 edges)
  - 生成 `graphify-out/graph.json` + GRAPH_TREE.html
  - 创建 AGENTS.md (Claw/OpenClaw 规则)
  - README 新增 graphify 使用章节
  - 支持 /graphify skill, query, path, explain
- 项目结构现在可通过知识图谱探索（技能依赖、代码关系、TextGrad 引擎组件）
- update-platforms.sh 保持同步

**测试结果**:
- graphify query/path 正常工作
- 所有项目内测试通过
- 无外部目录依赖变更

---

### V10.2 - 2026-06-26 (OpenClaw / QwenPaw 适配)

**变更内容**:
- 明确目标运行时为 **OpenClaw / QwenPaw 这一类 AI Agent 产品**（不再针对 Claude Code）。
- README 新增专属章节：
  - OpenClaw：SKILL.md frontmatter + `~/.openclaw/workspace/skills/berkshire-*/SKILL.md` 安装指南。
  - QwenPaw：与 `~/.qwenpaw/loop_engine/berkshire_v*/` 的现有集成说明 + 直接运行方式。
- 核心 skills（investment-research、investment-team、earnings-review、news-pulse、financial-data 等）添加标准 YAML frontmatter（name、description、version），使之可直接作为 OpenClaw SKILL.md 使用。
- 技能语言调整为 Agent 激活式（“激活条件：... 时激活”），便于 OpenClaw/QwenPaw 发现与触发。
- 清理剩余“Claude 对...”等描述，统一为“Agent / 研究者”。
- 工具调用说明强化：在 agent 内通过 shell 执行 `python3 berkshire-ai/tools/...`。

**测试结果**:
- 技能 frontmatter 验证通过
- 路径与工具调用在 OpenClaw 风格 workspace 和 QwenPaw loop 下可用
- 无 Claude Code 编排残留

---

### V10.1 - 2026-06-26

**变更内容**:
- **上游全能力整合**：完整并入 xbtlin/ai-berkshire 的 18 个 skills + 9 个 tools
  - skills/: investment-research, investment-team, bottleneck-hunter, thesis-tracker, financial-data, earnings-*, industry-*, portfolio-* 等
  - tools/: financial_rigor.py（核心）、report_audit.py、ashare_data.py、stock_screener、xueqiu_scraper、momentum_backtest* 等
- 路径适配为本仓库相对路径（`tools/financial_rigor.py`）
- config/skill.md 升级为 V10.1 整合版描述
- README 明确标注“已完整整合上游 + 本地 V10 TextGrad 引擎”

**测试结果**:
- [x] 工具可用性验证（financial_rigor 精确计算、report_audit 抽检逻辑）
- [x] 技能内容完整性（bottleneck-hunter、thesis-tracker、investment-team 等核心流程已落地）
- 保持 V10.0 TextGrad 引擎不变

**结论**: ✅ 整合完成（保留原 V10.0 测试结果）

**完整整合清单**:
- skills/: 18个 (bottleneck-hunter, deep-company-series, dyp-ask, earnings-*, financial-data, industry-*, investment-*, management-deep-dive, news-pulse, portfolio-review, private-company-research, quality-screen, thesis-tracker, wechat-article)
- tools/: 9个 (ashare_data, financial_rigor, log-command, momentum_backtest*, morningstar_fair_value, report_audit, stock_screener, xueqiu_scraper)

---

### V10.0 - 2026-06-26

**变更内容**:
- TextGrad 化：显式计算图 + 节点级诊断 + 文本梯度反向传播
- Tavily 双Key轮询集成
- 四大师 Prompt 优化

**测试结果**:
- [x] 单元测试: 4/4 通过 (拓扑排序/可视化/反向传播/优化器)
- [x] 集成测试: 3/3 通过 (Tracker/Deep Research/Evolution Loop)
- [x] 回测验证: 诊断覆盖率 100% (5个任务，2个低于目标，全部精确定位)
- [x] Cron 测试: 3/3 通过 (手动触发全部成功)

**关键指标**:
| 指标 | V9.3 | V10.0 | 提升 |
|:-----|:-----|:------|:-----|
| 诊断精度 | 整体评分 | 节点级定位 | ⭐⭐⭐ |
| 优化方式 | 全局修改 | 针对性修改 | ⭐⭐⭐ |
| 回测覆盖率 | N/A | 100% | - |

**结论**: ✅ 上线

---

### V9.3 - 2026-06-25

**变更内容**:
- Tavily 实时搜索集成
- 双Key轮询（Key 从环境变量 TAVILY_API_KEYS 读取，不入库）
- 消除 LLM 数据幻觉

**测试结果**:
- [x] 单元测试: 6/6 通过
- [x] 集成测试: 贵州茅台实时数据获取成功
- [x] 回测验证: N/A (首次集成)
- [x] Cron 测试: 通过

**关键数据**:
- 贵州茅台: ¥1240, PE 18.74, PB 5.72
- 2025E: 收入 5100亿, 净利 260亿, ROE 36.5%

**结论**: ✅ 上线

---

### V9.1 - 2026-06-25

**变更内容**:
- 四大师模型优化
- 段永平: qwen3.7-plus → deepseek-v4-pro (评分 0.763 → 0.920)
- 强制四大师全覆盖

**测试结果**:
- [x] 单元测试: 8/8 通过
- [x] 集成测试: 腾讯控股分析通过
- [x] 回测验证: 平均评分 0.895 > 目标 0.85
- [x] Cron 测试: 通过

**关键指标**:
| 大师 | 模型 | 评分 |
|:-----|:-----|:-----|
| 段永平 | deepseek-v4-pro | 0.920 |
| 巴菲特 | deepseek-v4-pro | 0.930 |
| 芒格 | glm-5.2 | 0.850 |
| 李录 | kimi-k2.6 | 0.880 |
| **平均** | - | **0.895** |

**结论**: ✅ 上线

---

### V9.0 - 2026-06-25

**变更内容**:
- 继承 xbtlin/ai-berkshire 四大师框架
- 整合 18 Skills + 8 Tools
- 反偏见机制 + 金融严谨性验证

**测试结果**:
- [x] 单元测试: 8/8 通过
- [x] 集成测试: 18 Skills + 8 Tools + Financial Rigor + State File + Trajectory Recorder + Evolution Loop + Cron Tasks + Model API
- [x] 回测验证: N/A (首次构建)
- [x] Cron 测试: 通过

**结论**: ✅ 上线

---

### V8.0 → V8.1 - 2026-06-25

**变更内容**:
- 自我进化系统部署
- Trajectory Recorder → Contrastive Reflector → Skill Optimizer 闭环

**测试结果**:
- [x] 对比反思正确识别四大师覆盖差异
- [x] 首次自动进化版本 8.0 → 8.1

**结论**: ✅ 上线

---

## 📊 版本演进图

```
V8.0 (自我进化)
  ↓
V8.1 (对比反思)
  ↓
V9.0 (四大师框架)
  ↓
V9.1 (模型优化)
  ↓
V9.3 (Tavily 集成)
  ↓
V10.29.1 ← 当前（投研效果契约 + 后验 E2E）
```

---

## 🔮 未来规划

### 投研效果（进行中）
- [x] DecisionRecord 契约 + 后验周报 + 离线 E2E
- [ ] 真实 horizon 后验样本 ≥20 后公布命中率
- [ ] 高 conviction 负 alpha → SkillForge 只改 top 失败

### V11.0 (规划中)
- [ ] 引入更多大师视角 (彼得·林奇 / 霍华德·马克斯)
- [ ] 情感分析集成 (新闻/社交媒体)
- [ ] 实时持仓监控告警

---

**维护者**: Mckay (houqing)  
**最后更新**: 2026-07-09

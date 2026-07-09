# berkshire-ai Roadmap

> 本路线图源自 upstream（xbtlin/ai-berkshire），并标注本 fork（OpenClaw/QwenPaw 适配版）的实现状态。
> 状态图例：✅ 已实现 · 🟡 部分实现 · ⬜ 未开始 / 明确不做

## P0：近期（1-2个月）

### A股数据源接入 — ✅ 已实现（V10.24 量化融合）
- 已通过 `tools/ashare_data.py` 接入腾讯财经 / 东方财富（含 `daily` 日线）
- V10.11：`tools/data_sources.py` 多源降级链，全失败优雅返回 `ok=False`
- V10.22：可选 `AktoolsSource` HTTP 适配器（`BERKSHIRE_ENABLE_AKTOOLS=1`）
- V10.24：`LocalCsvSource`（`BERKSHIRE_DATA_DIR` + `daily_ohlcv.csv`）+ 可选 `PytdxSource`；`tools/quant_screener_bridge.py`；见 `docs/quant_data_fusion.md`
- 市值/估值校验由 `tools/financial_rigor.py` 完成

### 多通道交付 — ✅ V10.11（吸收自 JusticePlutus）
- `tools/notify.py`：Telegram / 飞书 / 本地兜底

### 组合工具接线 — ✅ V10.10
- `data/holdings.example.json` → 本地 `data/holdings.json`
- `portfolio-review` / `news-pulse` 强制引用 `portfolio_risk` + `portfolio_scan`
- `scripts/portfolio-weekly.sh`：scan → thesis_queue 周度工作流

## P1：中期（3-6个月）

### HTML 报告输出 — ✅ V10.22
- `tools/report_html.py`：Markdown → HTML，暗色模式、侧栏导航、表格/代码块（纯 stdlib）

### 多档深度模式 — ✅ V10.9
- `lite` / `standard` / `deep`（`skills/investment-research.md`）

### 多股横向对比 — ✅ V10.22
- `tools/stock_comparison.py`：2–4 只标准化对决矩阵（Markdown + 可选 HTML）

## P2：长期（6个月+）

### 测试覆盖 + 工程门禁 — 🟢 完善（V10.22：420 pytest）
- GitHub Actions CI：py3.10-3.12 + ruff + mypy + 覆盖率门 50% + pip-audit + gitleaks + e2e-llm + build-image
- ✅ V10.17 golden 回归：`tests/test_eval_harness_golden.py`
- ✅ V10.22 行动卡 golden：`tests/test_golden_action_card.py`
- 可选后续：继续提高覆盖率门

### 组合级分析 — ✅ V10.22（规则层完备）
- `portfolio_risk.py`：集中度、主题、相关性 + **地域/货币暴露** + **-20% 压力测试**
- `portfolio_scan` + `risk_flags`；`portfolio-review` 已接线

## 本 fork 专属方向

### V10.29 多源证据 Brainstorm + Regression Gate — ✅
- `src/evidence_channels.py`：4 通道证据协议 + `EvidenceBrainstormProposer`
- `src/skill_forge/regression_gate.py`：paired trajectory replay 防劣化
- `pipeline.run_full_cycle(use_brainstorm=True)` 主链路接入
- 参考：AgentX (Kuaishou, arXiv:2606.26859)

### SkillForge 技能进化 — ✅（LLM-judge + bad-case 闭环 + regression gate）
- `src/skill_forge/`：Consistency Rate、四维失败分析、诊断、VFS 版本化 patch
- `tools/skill_evolve.py` + `evolution_loop_v10.py skill-evolve`
- V10.29：`regression_gate.py` paired replay 接入 `run_evolution_round`
- 文档：`docs/SKILL_EVOLUTION.md`；测试：`test_skill_forge*.py` + `test_regression_gate.py`

### TextGrad V10 自进化引擎 — ✅ V10.28 真闭环 + 轨迹 A/B + 信号接线
- 计算图 + 验证门控 + eval_harness + ∇_LLM + 经验 few-shot
- ✅ V10.26 **`rerun_analysis`**：`run_multi_round` 改写后重跑分析，`graph_analysis.AnalysisRunner`
- ✅ V10.27 **`tools/trajectory_ab_eval.py`**：V9.3 vs V10 诊断 vs V10.26 进化 A/B（bundled fixtures）
- ✅ V10.28 **量化信号 → HypothesisProposer**：`signal_proposer` + `pipeline.run_full_cycle(factor_scan=…)`
- ✅ V10.23 **∇_LLM 接入主链路**：`run_with_realized_feedback` / `run_full_cycle` 默认增强梯度
- ✅ V10.23 **验证门控默认**：`pipeline` 的 `use_validation=True` + `dev_rounds=3`
- ✅ V10.21 Scenario + `status`/`reflect`/`optimize` CLI
- ✅ V10.22 **统一主链路** `pipeline.run_full_cycle`（R/D → 反馈 → 沉淀）
- ✅ V10.22 **Cron 自动进化** `cron_evolution` + `scripts/cron-evolution.sh`
- ✅ V10.22 **轨迹自动记录** `trace_recorder`（`BERKSHIRE_TRACE_DIR`）

### 借鉴 RD-Agent / Qlib — ✅ V10.18–10.22 全部落地
- perf_metrics / experience_store / hypothesis / research_loop（R/D）
- run_recorder / 磁盘价格缓存 / Scenario / 主线接线
- ⬜ 明确不抄：CoSTEER、多 trace Web viewer、qlib 因子栈直依赖

### 可观测 + 服务化 + 部署 — ✅ V10.16–10.17
- observability / service / access_control / metrics_export / Docker
- 可选后续：Redis 共享限流、OTel、TLS 运维清单

### 已实现收益反馈闭环 + 多空辩论 — ✅ V10.22
- `run_with_realized_feedback` + `pipeline.run_full_cycle`
- ✅ V10.22 生产 `quality_fn`：`quality_scorer.build_experience_quality_fn`

### 多运行时部署 — ✅ 已实现
- `update-platforms.sh` 同步 skills/tools

### ai-hedge-fund 吸收 — ✅ PM/Risk 层（V10.8–10.10）

### SENSITIVITY 尺度校准 — ✅ V10.12
- ✅ V10.23 **conviction 校准**：`tools/calibrate_conviction.py`（经验库 stance vs realized_base 偏差报告）

### 投研效果北极星（过程 → 可证伪结果）— ✅ V10.29.1 工具+E2E / 🟡 样本积累中
- ✅ `DecisionRecord` 契约字段：`thesis` / `kill_condition` / `action` / `horizon_days` / `depth` / `skill`
- ✅ `tools/log_decision.py` 落盘 + gaps；`skills/investment-research.md` 收尾清单
- ✅ `tools/posterior_weekly.py` + `src/posterior_report.py`（方向命中 / 校准 / 完整率）
- ✅ `tools/seed_portfolio_decisions.py` + `data/portfolio_decision_seeds.json`
- ✅ `tools/archive_experiences.py` 清理测试污染经验库
- ✅ 离线 E2E：`tests/e2e/test_research_effectiveness_e2e.py`；包版本 **10.29.1**
- 🟡 持续：真实决策后验样本 ≥20 后再谈 IR；禁止用假 experiences 宣称 alpha

## 可选 / 未排期

### aktools-pro MCP 后端 — ✅ V10.23（HTTP + 原子诊断）
- `AktoolsSource` 经 `BERKSHIRE_AKTOOLS_BASE_URL`；失败自动降级到 import 链
- `tools/aktools_diagnostic.py`：避开 composite bug，用 market_prices + stock_news + stock_info 组装

### 量化数据融合（tdx_quant / daily_stock_data 参考）— ✅ V10.24
- `LocalCsvSource` + `PytdxSource`（env-gated，非核心依赖）
- `tools/quant_screener_bridge.py`：本地 CSV 动量 → thesis_queue JSON
- `docs/quant_data_fusion.md`：三库对比 + AlphaGPT 边界（不引入 torch/qlib）
- ⬜ 明确不做：整库 fork、AlphaGPT 训练栈、qlib 因子栈


### A股 AlphaGPT 因子挖掘 + 打板评分 — ✅ V10.25
- `tools/ashare_alphagpt/` + `tools/ashare_factor_mining.py`（可选 extra `factor-mining`）
- `tools/factor_screener_bridge.py`：已训练公式 → thesis_queue JSON
- `tools/limitup_screener_bridge.py` + `limitup_scoring.py`（五维打板，无 torch）
- `tools/thesis_queue.py`：`--from-factor-scan` / `--run-factor-scan` / `--from-limitup-scan` / `--run-limitup-scan`
- 见 `docs/quant_data_fusion.md` §7 finance-quant-skills


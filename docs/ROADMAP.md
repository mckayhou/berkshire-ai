# berkshire-ai Roadmap

> 本路线图源自 upstream（xbtlin/ai-berkshire），并标注本 fork（OpenClaw/QwenPaw 适配版）的实现状态。
> 状态图例：✅ 已实现 · 🟡 部分实现 · ⬜ 未开始

## P0：近期（1-2个月）

### A股数据源接入 — ✅ 已实现（V10.11 升级为多源降级链）
- 已通过 `tools/ashare_data.py` 接入腾讯财经 / 东方财富（含 `daily` 日线）
- V10.11：`tools/data_sources.py` 多源降级链 `native→tushare→efinance→akshare→baostock→yfinance`，全失败优雅返回 `ok=False`，可插拔 `DataSource` 适配器
- 市值/估值校验由 `tools/financial_rigor.py` 完成

### 多通道交付 — ✅ V10.11（吸收自 JusticePlutus）
- `tools/notify.py`：Telegram / 飞书（卡片→文本回退+加签）/ 本地兜底
- 零配置只落地 `reports/notifications/` 不报错；系统 curl 零依赖

### 组合工具接线 — ✅ V10.10
- `data/holdings.example.json` → 本地 `data/holdings.json`（gitignore）
- `portfolio-review` / `news-pulse` 强制引用 `portfolio_risk` + `portfolio_scan`
- `scripts/portfolio-weekly.sh`：scan → thesis_queue 周度工作流

## P1：中期（3-6个月）

### HTML 报告输出 — ⬜ 未开始
- Markdown → HTML，暗色模式、导航、图表

### 多档深度模式 — ✅ V10.9
- `lite` / `standard` / `deep`（`skills/investment-research.md`）

### 多股横向对比 — 🟡 部分实现
- `investment-checklist` 有多公司清单
- 待补：2–4 只标准化对决矩阵工具或模板

## P2：长期（6个月+）

### 测试覆盖 + 工程门禁 — 🟡 部分实现（V10.14 升级）
- 232 pytest（引擎、prompt_optimizer、config、financial_rigor、report_audit、网络层、portfolio_*、thesis_queue、收益反馈闭环、data_sources、notify）
- GitHub Actions CI（`.github/workflows/test.yml`）：py3.10-3.12 矩阵 + ruff + mypy(src) + 覆盖率门 45% + pip-audit + gitleaks；`.github/dependabot.yml` 周更
- 集中工具配置 `pyproject.toml`；中心配置 + 启动自检 `src/config.py`
- 待补：Skill 输出回归（golden 行动卡/报告片段）；逐步提高覆盖率门 / 收紧 mypy（check_untyped_defs）

### 组合级分析 — 🟡 部分实现（V10.9–10.10）
- `portfolio_risk.py`：集中度、现金、主题、相关性 CSV
- `portfolio_scan` + `risk_flags`；`portfolio-review` 已接线
- 待补：地域/货币暴露规则、压力测试半自动化

## 本 fork 专属方向

### TextGrad V10 自进化引擎 — 🟡 设计 + 雏形（V10.13–10.15 大幅推进）
- `src/graph.py` + `src/optimizer.py`：结构化 `Gradient`，`backward()` 文本梯度
- ✅ V10.13 变量真实改写（Option B）：`src/prompt_optimizer.py` 经 LLM 改写 Prompt
- ✅ V10.15 验证门控改写：`src/prompt_validation.py`（改写后评分，只有不劣于旧版才接受否则回滚）
- ✅ V10.15 多轮迭代 + 离线评测台：`src/eval_harness.py::run_multi_round`（`EvolutionReport` 证明单调不退化且收敛）
- 待补：LLM 生成「批评/梯度」(`∇_LLM`)；`reflect` / `optimize` / `status` CLI 完整化（见 `config/skill.md`）

### 已实现收益反馈闭环 + 多空辩论 — ✅ V10.11（吸收自 TradingAgents）
- `src/decision_log.py`：决策快照 JSONL 持久化（`BERKSHIRE_DECISION_LOG` 可覆盖）
- `src/realized_feedback.py`：收益→评分（`alpha`/`realized_base`/`master_score`，`PriceProvider` 可注入）
- `src/debate.py` + `BerkshireGraph.debate()`：多空净判断（`net_score`，中性区 `NET_MARGIN=0.15`）
- `src/evolution_loop_v10.py`：`run_with_realized_feedback(...)` 串起收益→评分→backward 闭环（V10.15 支持 `scorer`/`min_improvement` 验证门控）
- ✅ V10.15 真实价格取数：`src/realized_feedback.py::NetworkPriceProvider` 经 `tools/data_sources` 多源降级链取数（内存缓存 + 非交易日回退；`StaticPriceProvider` 仍作离线/测试默认）
- 待补：`quality_fn`/评分器对接「在 held-out 标的上跑大师分析并打分」的生产实现

### 多运行时部署 — ✅ 已实现
- `update-platforms.sh` 同步 skills/tools

### ai-hedge-fund 吸收 — ✅ PM/Risk 层（V10.8–10.10）
- 行动卡、`portfolio_scan`、`portfolio_risk`、`thesis_queue`；不采纳自动交易图

### SENSITIVITY 尺度校准 — ✅ V10.12
- `tools/calibrate_sensitivity.py`：用真实历史行情校准 `realized_feedback` 的 `SENSITIVITY`
- 目标函数 `J(S)=|spread₁₀₋₉₀(realized_base)−0.80|`（对肥尾稳健）；网格 + 黄金分割搜索
- 结论：默认 2.5 严重过饱和（~78% clip），更新为 **0.5**（12m≈0.41/6m≈0.68 折中），保留 `BERKSHIRE_SENSITIVITY` env 覆盖
- 待补：拿到历史大师 conviction 后升级为「信心 vs alpha」误差校准

## 可选 / 未排期：aktools-pro 作为 MCP 数据/回测后端 + financial_rigor 校验层

### 背景
- **aktools-pro** 是基于 akshare 的 MCP 服务器（`uvx aktools-pro`），提供 A股 / 港股 /
  美股 / 加密 / 贵金属 / 外汇 / 期货 / 基金 / 宏观 共 ~65 个工具，自带**双层缓存**、
  **回测引擎**、**模拟盘**、**分析师 SOP**。
- 已加入 Cursor MCP 配置并完成冒烟测试。

### 方案
- 为 `tools/data_sources.py` 增加可选 `AktoolsSource` 适配器（经 MCP/HTTP 调用），
  优先用它取数、失败回退现有 import 降级链（tushare/efinance/akshare/baostock/yfinance）。
- 数字仍统一过 `financial_rigor` 校验，保持「数据源可换、校验层不变」。

### 已知限制
- 该版本复合诊断工具 `composite_stock_diagnostic`（及 `*_composite_*`）报内部 bug
  `'function' object has no attribute 'fn'`——先绕开，用原子工具（`market_prices` /
  `stock_indicators_*` / `stock_news` 等）组合。
- **北向资金净买额**为数据源侧停披露（返回空值），靠 `financial_rigor` 拦截空/异常值。

### 收益
- 多 agent / 多语言共享同一数据源；服务层统一缓存 / 限流；贴合 OpenClaw / QwenPaw
  的工具调用与 MCP 风格，便于后续把取数从「进程内 import」迁到「服务化 MCP」。

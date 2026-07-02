# Berkshire AI - 四大师并行投研系统（已完整整合上游）

> **完整整合自** [xbtlin/ai-berkshire](https://github.com/xbtlin/ai-berkshire)（原始四大师框架 + 18 Skills + 9 Tools + 反偏见 + 金融严谨性 + 大量实战报告）
> 
> 叠加本地 **V10 TextGrad 自进化引擎**（显式计算图 + 节点级文本梯度反向传播 + 针对性优化）

**当前版本**：**V10.25**（AlphaGPT 因子挖掘 `ashare_alphagpt` / `factor_screener_bridge`；五维打板 `limitup_screener_bridge`；累积 V10.24 量化数据融合）。完整版本历史见 [VERSION_HISTORY.md](VERSION_HISTORY.md)。

**使用指南**：[docs/USER_GUIDE.md](docs/USER_GUIDE.md) — 全部功能的工作流与 CLI 说明。

**当前状态**：上游全能力 + V10 引擎已并入本仓库。**自 V10.2 起重点适配 OpenClaw / QwenPaw 风格 Agent 运行时**。

**重要**：用户明确说明 **不在 Claude Code 中使用**，而是在 **OpenClaw / QwenPaw 这一类 AI Agent 产品/运行时**中使用。

- **多 Agent 并行运行方式完整保留并适配**：investment-team、news-pulse、earnings-team 等技能里的“team-lead + 4 个专业子 Agent 并发研究”结构完整保留（这是上游四大师并行的核心价值）。只是把 Claude Code 的 TeamCreate/TaskCreate/SendMessage 等语法，换成了：
  - OpenClaw：sessions_spawn、ACP 子代理、ACP 消息 / sessions_send 通信。
  - QwenPaw：loop_engine 的并行角色实例或 harness 多 agent 调度。
  - 降级方案：当平台不支持轻松 spawn 并行子 agent 时，用手动多个会话或强模型顺序模拟。
- **OpenClaw**：将 skills 作为标准 `SKILL.md` 安装到 agent workspace（支持 frontmatter + 详细行为指令 + 如何 spawn 子 agent）。
- **QwenPaw**：作为 loop_engine 的一部分运行（berkshire-ai 的 evolution_loop_v10 直接集成在 `~/.qwenpaw/loop_engine/` 下）。
- 所有 skills 已清理为**独立可移植的 Agent 指令模板**（无 Claude Code Team/Task 编排），但**多 agent 团队运行的流程和价值保留**。

## 🎯 核心理念

**四大师并行视角**:
- **段永平**: 生意本质 (Duan Yongping - Business Essence)
- **巴菲特**: 护城河估值 (Warren Buffett - Moat & Valuation)
- **芒格**: 逆向风险 (Charlie Munger - Inversion & Risk)
- **李录**: 文明趋势 (Li Lu - Civilization Trends)

**TextGrad 自进化**: 借鉴 Nature 2025 论文，实现节点级诊断 + 文本梯度反向传播

**已实现收益反馈闭环 + 多空辩论**（吸收自 TradingAgents）: 把每次决策落盘 → 事后用真实价格算 alpha → 转成各大师"校准评分"喂回反向传播；并在四大师并行之上插入一个显式的多空对抗辩论环节，给出 bull/bear case 与净判断。

**A股多源降级数据层 + 多通道推送**（吸收自 JusticePlutus）: 数据获取走 `native→tushare→efinance→akshare→baostock→yfinance` 降级链，全失败优雅返回不抛崩；报告/信号可经 Telegram / 飞书 / 本地兜底多通道交付，零配置只落地不报错。

## 📊 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Berkshire AI V10.0                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 0: 输入 (ticker, tavily_query, date_anchor)         │
│      ↓                                                      │
│  Layer 1: 数据获取 (Tavily 双Key轮询 / A股多源降级链)      │
│      ↓                                                      │
│  Layer 2: 四大师分析 (段永平/巴菲特/芒格/李录)             │
│      ↓                                                      │
│  Layer 2.5: 多空对抗辩论 (bull/bear case + 净判断)         │
│      ↓                                                      │
│  Layer 3: 财务验证 (financial_rigor.py)                    │
│      ↓                                                      │
│  Layer 4: 输出 (final_report) → 多通道交付 (notify.py)     │
│                                                             │
│  ← TextGrad 反向传播 (节点级诊断 + 梯度优化)              │
│  ← 已实现收益反馈 (decision_log → realized_feedback → 评分)│
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始（整合后）

### OpenClaw 中使用（推荐方式）

OpenClaw 技能格式：目录 + `SKILL.md`（带 YAML frontmatter）。

推荐使用项目自带的更新脚本（推荐）：
```bash
cd ~/Documents/Github/berkshire-ai
./update-platforms.sh
```
这会自动把所有 skills 和 tools 同步到 OpenClaw（和 QwenPaw）。

手动方式（一次性）：
```bash
mkdir -p ~/.openclaw/workspace/skills/berkshire-investment-research
cp berkshire-ai/skills/investment-research.md ~/.openclaw/workspace/skills/berkshire-investment-research/SKILL.md
# 同理其他...
```

所有 SKILL.md 顶部已包含兼容 frontmatter（name / description / version 10.2），OpenClaw agent 会自动发现并在匹配场景时激活。

工具调用：技能内会指导 agent 执行 `python3 ~/Documents/Github/berkshire-ai/tools/financial_rigor.py ...`（或使用 update 后 v8 里的相对路径）。

示例触发：对 agent 说“对腾讯做四大师投资研究”或“运行 berkshire investment research on 0700.HK”。

还有一个总入口技能：`berkshire`（激活后可列出所有子技能）。

### QwenPaw 中使用

berkshire-ai 已经深度集成到 QwenPaw：

- 核心 runner：`src/evolution_loop_v10.py` 放在 `~/.qwenpaw/loop_engine/berkshire_v8/`（或当前版本目录）。
- 技能模板作为 prompt 组件被 loop 加载（见 `config/skill.md` 和 loop 内的 PROMPT_TEMPLATES 引用）。
- 状态/轨迹/反射：写入 `~/.qwenpaw/berkshire_state.md`、`~/.qwenpaw/berkshire_traces/` 等。
- 直接运行：
```bash
python3 ~/.qwenpaw/loop_engine/berkshire_v8/evolution_loop_v10.py --ticker 600519 --company 贵州茅台
```

如果要手动加载单个技能提示，可在 QwenPaw 的上下文或 skill_pool 中引用 `berkshire-ai/skills/*.md`。

### 其他环境（通用）

- 直接把 `skills/xxx.md` 内容作为系统提示或 user message 喂给任何支持工具调用的 agent（Grok、Qwen、Claude 等）。
- 结合本地 Python 工具链使用（推荐把 `tools/` 加入 PATH 或在调用前 cd 到 berkshire-ai 目录）。

### 使用 TextGrad V10 进化引擎

```bash
python3 src/evolution_loop_v10.py --ticker 600519 --company 贵州茅台
```

### 进化循环 CLI（V10.21+）

```bash
python3 src/evolution_loop_v10.py status
python3 src/evolution_loop_v10.py reflect AAPL
python3 src/evolution_loop_v10.py optimize AAPL
python3 src/evolution_loop_v10.py cron evolution-loop    # Cron 自动进化（V10.22）
python3 src/evolution_loop_v10.py cycle AAPL --anchor 100 --price 110  # 完整主链路（V10.22）
./scripts/cron-evolution.sh thesis-tracker               # 定时任务脚本
```

### 报告与对比工具（V10.22+）

```bash
python3 tools/report_html.py reports/foo.md -o reports/foo.html
python3 tools/stock_comparison.py AAPL MSFT GOOGL --html /tmp/compare.html
python3 tools/aktools_diagnostic.py AAPL          # aktools 原子 API 复合诊断（V10.23）
python3 tools/calibrate_conviction.py report      # 经验库 conviction 校准（V10.23）
```

### 生产主链路（推荐默认入口 · V10.22+）

```python
from src import DecisionRecord, run_full_cycle

d = DecisionRecord(
    ticker="AAPL", date="2026-01-02",
    scores={"duan": 0.8, "buffett": 0.75, "munger": 0.7, "lilu": 0.65},
    price_anchor=100.0,
    analyses={"buffett": "护城河尚可，但估值偏贵…"},  # 供 ∇_LLM 批评（V10.23）
)
out = run_full_cycle(d, realized_price=110.0)  # R/D → 反馈 → 经验/轨迹
```

### 已实现收益反馈闭环 + 多空辩论

```python
from src import (DecisionRecord, append_decision, run_with_realized_feedback,
                 StaticPriceProvider, BerkshireGraph)

# 1) 决策时落盘快照（含四大师信心 + 价格锚点）
d = DecisionRecord(ticker="600519", date="2026-01-02",
                   scores={"duan":0.9,"buffett":0.8,"munger":0.6,"lilu":0.7},
                   price_anchor=1500.0, benchmark="000300", benchmark_anchor=3800.0)
append_decision(d)  # → ~/.berkshire/decisions.jsonl（BERKSHIRE_DECISION_LOG 可覆盖）

# 2) 事后用真实价格回填 → 算 alpha → 转评分 → 反向传播（不连网络，可注入价格）
provider = StaticPriceProvider({("600519","2026-03-31"):1650.0, ("000300","2026-03-31"):3900.0})
result = run_with_realized_feedback(d, realized_date="2026-03-31", price_provider=provider)

# V10.20：persist=True 时自动沉淀经验；include_perf 附带绩效摘要；retriever 注入 D 段 few-shot
result = run_with_realized_feedback(
    d, realized_date="2026-03-31", price_provider=provider,
    persist=True, include_perf=True,
    retriever=KeywordExperienceRetriever(ExperienceStore()),
)
# result["experience"]  → Experience；result["perf"] → PerfReport

# 3) 决策时信心的多空净判断（也可单独调用）
debate = BerkshireGraph().debate({"duan":0.9,"buffett":0.8,"munger":0.4,"lilu":0.7})
print(debate.net_stance, debate.net_score)   # bullish / +0.x（中性区 |net|<0.15）
```

# A股多源降级数据 + 多通道交付 + 量化筛选

详见 [docs/USER_GUIDE.md](docs/USER_GUIDE.md) §5–§8。快速命令：
```bash
# 数据：按 native→tushare→efinance→akshare→baostock→yfinance 降级，全失败不抛崩
python3 tools/data_sources.py sources                  # 列出各源可用状态（离线）
python3 tools/data_sources.py daily 600519 --limit 60  # 日线（走降级链）
python3 tools/quant_screener_bridge.py --json          # 本地 CSV 动量 → thesis_queue JSON
python3 tools/limitup_screener_bridge.py --json        # 五维打板评分（V10.25）
python3 tools/factor_screener_bridge.py --json         # AlphaGPT 因子筛选（需 torch）

# 交付：Telegram / 飞书 / 本地兜底；零配置只落地到 reports/notifications/
python3 tools/notify.py channels
python3 tools/notify.py send --title "组合周报" --file reports/portfolio-latest.md
```

### Agent 内工具调用（OpenClaw / QwenPaw 推荐）

Agent 技能会指导你使用 shell / 集成工具执行：

```bash
# 金融严谨性验证（必须用于任何关键数字）
python3 berkshire-ai/tools/financial_rigor.py verify-market-cap --price 510 --shares 9.11e9 --reported 4.65e12 --currency HKD
python3 berkshire-ai/tools/financial_rigor.py cross-validate --field revenue --values '123.4 123.5' --sources 'macrotrends aastocks'

# 报告 15% 随机抽检 + 准出判决
python3 berkshire-ai/tools/report_audit.py extract --report reports/腾讯-2025Q4.md
python3 berkshire-ai/tools/report_audit.py verdict --results '{...}' --report reports/xxx.md
```

**重要**：在 OpenClaw/QwenPaw 中，确保 berkshire-ai 目录对 agent 可见（workspace 挂载或 git clone），或在 skill 描述中写明绝对路径。

所有工具位于 `./tools/`（Decimal 精确计算、Benford 检验、三情景估值等）。

## 🕸️ Knowledge Graph (graphify)

本项目已集成 [graphify](https://graphify.dev) 用于代码/技能结构理解。

- Hook 已安装 (post-commit 等自动更新)
- Graph: `graphify-out/graph.json`（graphify 对**整个代码库**构建的知识图谱；节点/边数量随代码演进而变化，以 `graphify-out/manifest.json` 实际为准）
- 注意：此处的 graphify 代码图 ≠ TextGrad 引擎的 `BerkshireGraph`（后者是固定的 18 个变量节点 / 5 层投研计算图，见 `src/graph.py`）
- 使用方式（在支持的 AI 助手中）：
  - `/graphify` 激活 skill
  - `graphify query "项目核心组件?"`
  - `graphify path "evolution_loop" "financial_rigor"`
  - `graphify explain "BerkshireGraph"`
  - 更新: `graphify update .` (代码仅, 无 LLM 成本)
- AGENTS.md 中有集成规则。
- 适合探索技能依赖、代码关系、投资框架结构。

安装/更新: `./update-platforms.sh` 会同步 graphify-out (如果需要)。

## 📁 项目结构（已整合上游）

```
berkshire-ai/
├── README.md                    # 本文件（整合说明）
├── VERSION_HISTORY.md
├── src/                         # TextGrad V10 自进化引擎（本地核心）
│   ├── evolution_loop_v10.py    # run_example + run_with_realized_feedback（收益反馈闭环）
│   ├── graph.py / optimizer.py  # 计算图（含 debate()）+ 文本梯度优化器（可注入 LLM 真实改写）
│   ├── prompt_optimizer.py      # 变量真实改写 Option B：apply_gradient 经 LLM 改写 Prompt（LLMClient 可注入/可 mock）
│   ├── decision_log.py          # 决策快照 JSONL 持久化（DecisionRecord）
│   ├── realized_feedback.py     # 已实现收益 → 评分（PriceProvider 可注入）
│   ├── debate.py                # 多空对抗辩论（DebateResult，净判断）
│   └── tavily_search.py
├── skills/                      # ★ 完整上游 18 个技能（已并入，OpenClaw 兼容）
│   ├── investment-research.md   # 带 frontmatter，可直接作为 SKILL.md 使用
│   ├── investment-team.md
│   ├── earnings-review.md
│   ├── news-pulse.md
│   ├── financial-data.md        # 数据源规范（所有技能必须引用）
│   └── ... (其他 13 个)
│   # OpenClaw 安装示例见上方“OpenClaw 中使用”章节
├── tools/                       # ★ 完整上游工具链（已并入）
│   ├── financial_rigor.py       # 精确市值/估值/交叉验证（核心）
│   ├── report_audit.py          # 报告数据抽检（15%）
│   ├── ashare_data.py           # A股行情/财务/估值/日线
│   ├── data_sources.py          # A股多源降级数据层（可插拔适配器）
│   ├── notify.py                # 多通道交付（Telegram/飞书/本地兜底）
│   └── ... (stock_screener, portfolio_*, xueqiu_scraper, momentum backtests, etc.)
├── config/
│   ├── skill.md                 # V10.1 整合版 meta-skill
│   └── state.md
├── docs/
│   └── textgrad_design.md
├── graphify-out/                # 知识图谱 (graphify) - 用于项目结构查询、代码/技能关系
├── tests/
└── traces/ / reflections/       # 运行时
```

## 📚 文档导航

| 文档 | 内容 |
|---|---|
| **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)** | **全功能使用指南**（工作流 + 全部 CLI） |
| [README_EN.md](README_EN.md) | English version |
| [TESTING.md](TESTING.md) | **测试指南**（pytest 分层、CI、冒烟清单、验收入口） |
| [tools/README.md](tools/README.md) | 工具链 CLI 参数逐项说明 |
| [docs/quant_data_fusion.md](docs/quant_data_fusion.md) | A 股三库融合、因子/打板筛选边界 |
| [docs/action-card.md](docs/action-card.md) | 结构化行动卡（PM 汇总层，可执行结论模板） |
| [docs/report-conventions.md](docs/report-conventions.md) | 报告目录/命名规范、投研核心原则 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 路线图（含本 fork 实现状态） |
| [docs/textgrad_design.md](docs/textgrad_design.md) | TextGrad V10 引擎设计 |
| [docs/tdx_mcp_tool_design.md](docs/tdx_mcp_tool_design.md) | 通达信 MCP（不实施，备忘） |
| [LICENSE](LICENSE) | MIT（fork 自 xbtlin/ai-berkshire，保留原作者版权） |

## 🧪 测试

完整说明见 **[TESTING.md](TESTING.md)**（分层、459+ 用例索引、CI、手工冒烟、按功能验收入口）。

```bash
pip install -r requirements.txt pytest pytest-cov
python3 -m pytest tests/ -v -rs      # 全量；无 LLM Key 时 1 个 e2e skip
python3 -m pytest tests/ -q --cov --cov-fail-under=50   # 与 CI 一致
python3 tests/test_v10_backtest.py   # TextGrad 诊断覆盖率（非 pytest）
```

按功能快速验收示例：

```bash
python3 -m pytest tests/test_limitup_scoring.py -v          # 打板评分
python3 -m pytest tests/test_tools_financial_rigor.py -v     # 金融严谨性
python3 -m pytest tests/test_tools_thesis_queue.py -v        # 研究队列
```

## 🔄 版本规范

**铁律**: 每次新版本必须完成以下测试才能上线：

1. **单元测试**: 核心模块功能验证
2. **集成测试**: 端到端流程验证
3. **回测验证**: 历史轨迹数据对比
4. **Cron 测试**: 定时任务触发验证

详见 [VERSION_HISTORY.md](VERSION_HISTORY.md)

## 📊 当前版本

**V10.11** (2026-06-30)
- ✅ TextGrad 化 (节点级诊断 + 梯度反向传播)
- ✅ Tavily 双Key轮询 (2000次/月)
- ✅ 四大师全覆盖 (100%)
- ✅ 回测诊断覆盖率 100%
- ✅ **上游全能力整合**：完整 skills/ (18个) + tools/ from xbtlin/ai-berkshire 并入 (已规范化路径引用)
- ✅ **已实现收益反馈闭环 + 多空辩论**（吸收自 TradingAgents）：`decision_log` / `realized_feedback` / `debate` + `run_with_realized_feedback`
- ✅ **A股多源降级数据层 + 多通道推送**（吸收自 JusticePlutus）：`tools/data_sources.py` / `tools/notify.py`
- ✅ **变量真实改写（V10.13 / Option B）**：`prompt_optimizer.apply_gradient` 经 LLM 改写 Prompt，`TextualGradientDescent(graph, llm=...)` 真实更新变量值（可注入/可 mock，失败优雅降级）
- ✅ **生产化硬化（V10.14 档A）**：`pyproject.toml` 集中配置 + CI 门禁（ruff / mypy / 覆盖率 / pip-audit / gitleaks，py3.10-3.12 矩阵）+ `src/config.py` 中心配置与启动自检（`python3 src/config.py`）
- ✅ **自进化硬化（V10.15 档B）**：验证门控改写 `prompt_validation`（改写后评分，只有不劣于旧版才接受否则回滚）+ 真实行情 `NetworkPriceProvider`（多源降级链 + 缓存 + 非交易日回退）+ 多轮迭代 `eval_harness.run_multi_round`（离线证明进化单调不退化并收敛）
- ✅ **可观测 + 服务化（V10.16 档C）**：结构化 JSON 日志 + run_id 贯穿 + LLM 成本/token/延迟埋点 `observability`；服务边界 `service.create_app()`（FastAPI，`/health` `/score` `/debate`，可选 extra）；提示注入防护 `sanitize`（清洗喂给改写 LLM 的不可信诊断）
- ✅ **部署上线 + 访问控制 + 真梯度（V10.17 档D）**：容器化 `Dockerfile` + `docker-compose.yml`（非 root + HEALTHCHECK）；访问控制 `access_control`（API Key 鉴权 + 每客户端限流）；指标导出 `metrics_export`（`/metrics` Prometheus 文本）；∇_LLM 真梯度 `llm_gradient`（LLM 生成批评，失败降级回规则化）；mypy 收紧 `check_untyped_defs` + golden 回归基线
- ✅ **路线图收尾（V10.22）**：`pipeline.run_full_cycle` 统一主链路；`cron_evolution` + `scripts/cron-evolution.sh`；`trace_recorder`；`quality_scorer`；`tools/report_html.py`；`tools/stock_comparison.py`；组合地域/货币/压力测试；`AktoolsSource`
- ✅ **Scenario + CLI + Recorder（V10.21）**：`src/scenario.py`；`status`/`reflect`/`optimize`；`run_recorder`；磁盘价格缓存
- ✅ **主线接线（V10.20）**：`run_with_realized_feedback` 在 `persist=True` 时自动 `experience_from_stats` → `ExperienceStore`；`include_perf=True` 返回 `perf` 摘要；`retriever`/`retriever_k` 透传 D 段 few-shot 改写
- ✅ **R/D 双循环（V10.19）**：`src/research_loop.py` 的 `HypothesisProposer` + `run_rd_cycle`（R 提假设 → D 验证门控进化；`proposer=None` 等价纯 D）；`ExperienceDrivenProposer` / `LLMHypothesisProposer` 可注入；D 段经验召回经 `optimizer.retriever`；`decision_log` 可选 `hypothesis_id`
- ✅ **借鉴 RD-Agent / Qlib（V10.18）**：本地绩效指标库 `tools/perf_metrics.py`（Qlib `risk_analysis` 口径：年化/波动/IR/夏普/最大回撤/累计求和/超额 CAR/含成本，纯 stdlib，接 `decision_log`+可注入 `PriceProvider`）；经验库 RAG-lite `experience_store`（成败经验 JSONL 沉淀 + 确定性关键词召回 + 作为 few-shot 注入 `build_rewrite_messages`，`examples=None` 逐字节不变、失败降级）；显式假设对象 `hypothesis`（可证伪命题 + 最小存储）
- ✅ 测试 382 通过（详见 [VERSION_HISTORY.md](VERSION_HISTORY.md)）

## 🚀 服务部署（V10.17 档D）

把引擎作为带鉴权/限流/指标的 HTTP 服务跑起来：

```bash
# 1) 配置（强烈建议生产开启鉴权 + 限流）
cp .env.example .env
#   在 .env 填：BERKSHIRE_API_KEYS=key1,key2   BERKSHIRE_RATE_LIMIT_PER_MIN=120
#   （可选）BERKSHIRE_LLM_API_KEY 等用于 Option B 改写 / 自进化

# 2) 一键起服务（Docker，非 root + 内置 HEALTHCHECK）
docker compose up --build
#   或本地：pip install '.[service]' && berkshire-serve

# 3) 验证
curl localhost:8000/health
curl localhost:8000/metrics                       # Prometheus 文本格式
curl -X POST localhost:8000/debate \
  -H 'X-API-Key: key1' -H 'Content-Type: application/json' \
  -d '{"scores":{"duan":0.9,"buffett":0.85,"munger":0.8,"lilu":0.8}}'
```

端点：`GET /health`、`GET /config/doctor`、`GET /metrics`、`POST /score`、`POST /debate`。
`/score` `/debate` 在配置了 `BERKSHIRE_API_KEYS` 时要求请求头 `X-API-Key`；超过 `BERKSHIRE_RATE_LIMIT_PER_MIN` 返回 429。

## 🔗 相关链接

- 原始框架: [xbtlin/ai-berkshire](https://github.com/xbtlin/ai-berkshire)
- TextGrad 论文: [arXiv:2406.07496](https://arxiv.org/abs/2406.07496)
- QwenPaw: [内部系统]

## 📝 维护者

- Mckay (houqing)
- 最后更新: 2026-06-30 (V10.11: 收益反馈闭环 + 多空辩论；A股多源降级数据 + 多通道推送)

# Berkshire AI 功能使用指南

> 本文档汇总 **berkshire-ai** 全部主要功能的使用方法（**工作流导向**）。  
> 命令默认在**仓库根目录**执行：`cd /path/to/berkshire-ai`。

**文档导航**：[docs/README.md](README.md)（推荐从这里选阅读路径）

| 专题 | 文档 |
|------|------|
| 回测（5 条路线对照） | [BACKTEST.md](BACKTEST.md) |
| A 股量化 | [QUANT.md](QUANT.md) |
| TextGrad 引擎 | [ENGINE.md](ENGINE.md) |
| 技能进化 SkillForge | [SKILL_EVOLUTION.md](SKILL_EVOLUTION.md) |
| Agent 技能 | [SKILLS.md](SKILLS.md) |
| 测试验收 | [TESTING.md](../TESTING.md) |
| 工具 CLI 逐项 | [tools/README.md](../tools/README.md) |

---

## 目录

1. [前置条件与安装](#1-前置条件与安装)
2. [典型工作流总览](#2-典型工作流总览)
3. [环境与配置](#3-环境与配置)
4. [TextGrad 进化引擎](#4-textgrad-进化引擎)
5. [数据获取层](#5-数据获取层)
6. [A 股量化：因子挖掘与筛选](#6-a-股量化因子挖掘与筛选)
7. [组合扫描与风险](#7-组合扫描与风险)
8. [研究队列 thesis_queue](#8-研究队列-thesis_queue)
9. [金融严谨性与报告质检](#9-金融严谨性与报告质检)
10. [报告产出与对比](#10-报告产出与对比)
11. [推送与定时任务](#11-推送与定时任务)
12. [Agent / Skills 使用](#12-agent--skills-使用)
13. [环境变量速查](#13-环境变量速查)
14. [测试与验收](#14-测试与验收)
15. [文档索引](#15-文档索引)

---

## 1. 前置条件与安装

### 1.1 基础环境

| 组件 | 要求 |
|------|------|
| Python | 3.10+（推荐 3.11） |
| 操作系统 | macOS / Linux（**无需 Windows**；通达信实盘层不实施） |
| 网络 | 实时行情/检索需联网；大量工具可离线 |

### 1.2 安装

```bash
cd berkshire-ai
pip install -r requirements.txt          # 核心依赖
pip install -e .                           # 可编辑安装 src 包
pip install -e '.[quant]'                  # 可选：pytdx / pyarrow 本地量化
pip install -e '.[factor-mining]'          # 可选：PyTorch + AlphaGPT 因子挖掘
pip install -e '.[service]'                # 可选：FastAPI 服务边界
```

### 1.3 配置模板

```bash
cp .env.example .env    # 填入 API Key 等（.env 不提交）
python3 src/config.py   # 体检：各功能就绪度，不打印密钥
```

### 1.4 本地数据目录（量化筛选必备）

```bash
export BERKSHIRE_DATA_DIR=./data
# 日线 CSV 格式见 docs/quant_data_fusion.md（daily_stock_data 兼容）
# 路径：$BERKSHIRE_DATA_DIR/daily_ohlcv.csv
```

可用外部 [daily_stock_data](https://github.com/bzcsk2/daily_stock_data) cron 落盘，或 `data_sources.py daily` 手工导出后写入 CSV。

---

## 2. 典型工作流总览

```text
┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐
│ 数据获取      │ →  │ 筛选 / 因子      │ →  │ thesis_queue      │
│ data_sources │    │ factor/limitup/ │    │ 研究待办优先级     │
│ ashare_data  │    │ quant_screener  │    └────────┬─────────┘
└──────────────┘    └─────────────────┘             │
                                                    ▼
┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐
│ 四大师研究    │ ←  │ investment-*   │ ←  │ portfolio_scan   │
│ TextGrad     │    │ skills          │    │ stock_screener   │
└──────┬───────┘    └─────────────────┘    └──────────────────┘
       │
       ▼
┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐
│ financial_   │ →  │ report_audit     │ →  │ notify / HTML    │
│ rigor        │    │ 准出判决         │    │ 交付             │
└──────────────┘    └─────────────────┘    └──────────────────┘
```

**最小 A 股量化链路（无 torch）：**

```bash
python3 tools/limitup_screener_bridge.py --json -o data/limitup_scan.json
python3 tools/thesis_queue.py --from-limitup-scan data/limitup_scan.json --suggest-md
```

**完整 A 股因子链路（需 torch）：**

```bash
pip install -e '.[factor-mining]'
python3 tools/ashare_factor_mining.py train --code 511260 --steps 200
python3 tools/factor_screener_bridge.py --json -o data/factor_scan.json
python3 tools/thesis_queue.py --from-factor-scan data/factor_scan.json --json
```

---

## 3. 环境与配置

| 命令 | 作用 |
|------|------|
| `python3 src/config.py` | 打印各模块配置就绪状态 |
| `cp .env.example .env` | 创建本地环境变量文件 |

关键变量见 [§13 环境变量速查](#13-环境变量速查) 与 [.env.example](../.env.example)。

---

## 4. TextGrad 进化引擎

> 深度说明（CLI 全集、API、HTTP 服务、存储路径）：[ENGINE.md](ENGINE.md)

### 4.1 单次研究运行

```bash
python3 src/evolution_loop_v10.py --ticker 600519 --company 贵州茅台
```

### 4.2 进化循环 CLI

```bash
python3 src/evolution_loop_v10.py status
python3 src/evolution_loop_v10.py reflect AAPL
python3 src/evolution_loop_v10.py optimize AAPL --rounds 3
python3 src/evolution_loop_v10.py cycle AAPL --anchor 100 --price 110
python3 src/evolution_loop_v10.py cycle 600519 --anchor 1500 --price 1650 --rerun-analysis
python3 src/evolution_loop_v10.py cycle 600519 --anchor 1500 --price 1650 --factor-scan factor.json
python3 src/evolution_loop_v10.py cron evolution-loop
./scripts/cron-evolution.sh thesis-tracker
```

| 子命令 | 说明 |
|--------|------|
| `status` | 决策日志 / 经验库 / 轨迹存储健康摘要 |
| `reflect TICKER` | 基于历史经验对比反思 |
| `optimize TICKER` | 反思 + 验证门控进化 |
| `cycle TICKER` | 完整主链路 `run_full_cycle`（R/D + 收益反馈）；可加 `--rerun-analysis`、`--factor-scan` |
| `cron TASK` | 定时任务：`thesis-tracker` / `portfolio-weekly` / `evolution-loop` / `all` |

### 4.3 Python API（生产主链路）

```python
from src import DecisionRecord, run_full_cycle, run_with_realized_feedback
from src.realized_feedback import StaticPriceProvider

d = DecisionRecord(
    ticker="AAPL", date="2026-01-02",
    scores={"duan": 0.8, "buffett": 0.75, "munger": 0.7, "lilu": 0.65},
    price_anchor=100.0,
    analyses={"buffett": "护城河尚可…"},
)
out = run_full_cycle(d, realized_price=110.0)

provider = StaticPriceProvider({("AAPL", "2026-03-31"): 110.0})
result = run_with_realized_feedback(
    d, realized_date="2026-03-31", price_provider=provider,
    persist=True, include_perf=True,
)
```

设计细节见 [docs/textgrad_design.md](textgrad_design.md)。

### 4.4 经验库校准

```bash
python3 tools/calibrate_conviction.py report
python3 tools/calibrate_conviction.py report --ticker AAPL --json
```

### 4.5 灵敏度校准

```bash
python3 tools/calibrate_sensitivity.py universe
python3 tools/calibrate_sensitivity.py run --lookback 365 --also 182 --json
```

### 4.6 V10.26–10.28 进化增强

**分析重跑（V10.26）** — 改写 Prompt 后重跑分析，用 `backward(scores)` 产梯度（默认关，省 LLM）：

```python
from src.eval_harness import run_multi_round
from src.graph_analysis import PromptHeuristicAnalysisRunner

run_multi_round(graph, llm, quality_fn, rerun_analysis=True, ticker="600519")
# 或 pipeline / CLI：
# run_full_cycle(d, realized_price=110.0, rerun_analysis=True)
```

**轨迹 A/B（V10.27）** — 离线验收 V9.3 vs V10 诊断 vs 进化 Δ：

```bash
python3 tools/trajectory_ab_eval.py
python3 tools/trajectory_ab_eval.py --tasks tests/fixtures/trajectories/sample_tasks.json --json
```

**量化信号 → Hypothesis（V10.28）** — factor/limitup 扫描 JSON 并入 R 循环：

```python
run_full_cycle(d, realized_price=110.0, factor_scan=scan_json, limitup_scan=lu_json)
```

详见 [ENGINE.md](ENGINE.md) §9、[BACKTEST.md](BACKTEST.md) §4.1。

### 4.7 SkillForge 技能进化（`skills/*.md`）

> 与 TextGrad 互补：TextGrad 改大师 Prompt；SkillForge 改 `skills/*.md` 工作流与工具规则。  
> 专题：[SKILL_EVOLUTION.md](SKILL_EVOLUTION.md)

```bash
# LLM-judge Consistency Rate + 四维失败分析 + 技能 patch
python3 tools/skill_evolve.py judge tests/fixtures/skill_forge/bad_cases.jsonl --judge-mode auto
python3 tools/skill_evolve.py evolve investment-research --dry-run --judge-mode rule

# 统一入口
python3 src/evolution_loop_v10.py skill-evolve list
python3 src/evolution_loop_v10.py skill-evolve evolve investment-research --dry-run --judge-mode rule
```

| 子命令 | 说明 |
|--------|------|
| `judge FIXTURE` | Strict / Lenient CR（`--judge-mode auto\|llm\|rule`） |
| `analyze FIXTURE` | 四维失败分析 |
| `evolve SKILL` | bad-case → 诊断 → 版本化 patch（`--dry-run` 不写 live） |
| `status SKILL` | 查看 `skills/.evolution/` 版本清单 |
| `create NAME DESC` | 从 reports/ + 现有 skills 挖掘生成 Skill v0 |

验收：`pytest tests/test_skill_forge.py tests/test_skill_forge_llm.py tests/test_skill_forge_cli.py -v`（见 [TESTING.md](../TESTING.md) §SkillForge）。

---

## 5. 数据获取层

### 5.1 A 股多源降级链（推荐）

```bash
python3 tools/data_sources.py sources
python3 tools/data_sources.py daily 600519 --limit 60
python3 tools/data_sources.py daily 600519 --json --sources native,efinance
python3 tools/data_sources.py quote 600519
python3 tools/data_sources.py fundamentals 600519
```

默认链：`native → tushare → efinance → akshare → baostock → yfinance`。全失败返回 `ok=False`，不抛崩。

启用增强源示例：

```bash
export BERKSHIRE_ENABLE_TUSHARE=1
export TUSHARE_TOKEN=your_token
pip install tushare efinance akshare baostock yfinance   # 按需
```

本地 CSV / pytdx：

```bash
export BERKSHIRE_ENABLE_LOCAL_DATA=1
export BERKSHIRE_DATA_DIR=./data
export BERKSHIRE_ENABLE_PYTDX=1    # 需 pip install -e '.[quant]'
```

### 5.2 A 股直连工具（curl）

```bash
python3 tools/ashare_data.py quote 600519
python3 tools/ashare_data.py financials 600519
python3 tools/ashare_data.py valuation 600519
python3 tools/ashare_data.py daily 600519 --limit 60
python3 tools/ashare_data.py search 茅台
```

### 5.3 aktools 复合诊断（可选本地服务）

```bash
export BERKSHIRE_ENABLE_AKTOOLS=1
export BERKSHIRE_AKTOOLS_BASE_URL=http://127.0.0.1:8080
python3 tools/aktools_diagnostic.py 600519
python3 tools/aktools_diagnostic.py AAPL --json -o reports/aapl_diag.md
```

### 5.4 Tavily 实时检索

```bash
export TAVILY_API_KEYS=key1,key2

# 子命令（与 config/skill.md 一致）
python3 src/tavily_search.py stock 600519 贵州茅台
python3 src/tavily_search.py financial 0700.HK
python3 src/tavily_search.py news 互联网 腾讯
python3 src/tavily_search.py test   # 集成自测
```

多 Key 轮询；也可用单变量 `TAVILY_API_KEY`。无 Key 时相关技能应降级为公开源或跳过。

---

## 6. A 股量化：因子挖掘与筛选

> 完整专题（数据准备、日更工作流、环境变量）：[QUANT.md](QUANT.md)  
> 回测验收（train/OOS/打板能否回测）：[BACKTEST.md](BACKTEST.md)

### 6.1 AlphaGPT 因子训练

```bash
pip install -e '.[factor-mining]'

# 训练（默认标的 511260 可转债 ETF）
python3 tools/ashare_factor_mining.py train --code 511260 --steps 400
python3 tools/ashare_factor_mining.py train --code 600519 --steps 100 --plot

# 解码公式 token
python3 tools/ashare_factor_mining.py decode --tokens '[0,6,1,7]'

# 样本外检验
python3 tools/ashare_factor_mining.py oos --formula data/alphagpt/best_ashare_formula.json

# 内置 screen 子命令（同 factor_screener_bridge）
python3 tools/ashare_factor_mining.py screen --json --top 20
```

输出：`$BERKSHIRE_DATA_DIR/alphagpt/best_ashare_formula.json`。

### 6.2 因子筛选桥接

```bash
python3 tools/factor_screener_bridge.py --json -o data/factor_scan.json
python3 tools/factor_screener_bridge.py --codes 600519,000001 --source online --json
python3 tools/factor_screener_bridge.py --min-score 0.1 --top 30 --json
```

| `--source` | 行为 |
|------------|------|
| `auto`（默认） | 优先本地 CSV，无 CSV 且给了 `--codes` 则在线 |
| `csv` | 仅本地 CSV |
| `online` | 必须 `--codes` |

### 6.3 五维打板评分（无 torch）

移植自 [TDX-MCP-LHDB-Agent](https://github.com/adambbhe/TDX-MCP-LHDB-Agent)，用日线代理涨停/竞价信号。

```bash
python3 tools/limitup_screener_bridge.py --json -o data/limitup_scan.json
python3 tools/limitup_screener_bridge.py --codes 600519,000001 --min-score 70 --json
python3 tools/limitup_screener_bridge.py --auction-min 2 --auction-max 7 --top 20 --json
```

五维权重：信号强度 25% / 价格位置 20% / 量能 20% / 动能 20% / 风控 15%。

> **注意**：本模块是**选股评分**，仓库**未内置**打板策略历史收益回测；若需验证规则，见 [BACKTEST.md §6](BACKTEST.md#6-打板评分limitup与回测)。

### 6.4 本地 CSV 动量突破

```bash
python3 tools/quant_screener_bridge.py --json
python3 tools/quant_screener_bridge.py --codes 600519,000001 --lookback 20 --vol-mult 1.5 --json
```

### 6.5 因子 + 打板叠加（Python）

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("tools").resolve()))  # 仓库根目录执行
from ashare_alphagpt.screener import run_screen, enrich_with_limitup_scores

factor = run_screen(source="csv", min_score=0.0)
combined = enrich_with_limitup_scores(factor, min_limitup_score=60)
```

> `quant_screener_bridge` 输出**尚未**接入 `thesis_queue`（无 `--from-quant-scan`）；需手工合并 JSON 或走 §8.2 的 portfolio/factor/limitup 路径。

---

## 7. 组合扫描与风险

### 7.1 动量 + 价值筛选（美股 watchlist）

```bash
python3 tools/stock_screener.py
python3 tools/stock_screener.py --update NVDA
```

依赖 `data/watchlist.json`、`data/fundamentals.json`。

### 7.2 组合扫描（行动卡草案）

```bash
python3 tools/portfolio_scan.py
python3 tools/portfolio_scan.py --group us_ai_chip hk_internet
python3 tools/portfolio_scan.py NVDA MU --json --top 5
python3 tools/portfolio_scan.py --json --holdings '{"NVDA":25,"0700.HK":20,"CASH":15}'
```

模板见 [action-card.md](action-card.md)。

### 7.3 组合风险检查（离线）

```bash
python3 tools/portfolio_risk.py --holdings '{"NVDA":45,"CASH":55}' --json
python3 tools/portfolio_risk.py --holdings-file data/holdings.json --proposed MU 5
```

复制 `data/holdings.example.json` → `data/holdings.json`（本地，不提交）。

### 7.4 动量回测（演示）

> 五种「回测」路线对照：[BACKTEST.md](BACKTEST.md)

```bash
python3 tools/momentum_backtest.py
python3 tools/momentum_backtest_v2.py
```

美股 NVDA/AMD/MU 演示；A 股因子 OOS 见 §6 与 BACKTEST §1。

### 7.5 Morningstar 公允价值

```bash
python3 tools/morningstar_fair_value.py
python3 tools/morningstar_fair_value.py --max-pages 1 --top 5
```

---

## 8. 研究队列 thesis_queue

解析 `config/state.md`，合并扫描信号，输出 `research_now` 优先级列表。

### 8.1 基本用法

```bash
python3 tools/thesis_queue.py --json
python3 tools/thesis_queue.py --suggest-md
```

### 8.2 合并外部扫描 JSON

```bash
# portfolio_scan 输出
python3 tools/portfolio_scan.py --json -o /tmp/scan.json
python3 tools/thesis_queue.py --from-scan /tmp/scan.json --suggest-md

# AlphaGPT 因子扫描
python3 tools/thesis_queue.py --from-factor-scan data/factor_scan.json --json

# 五维打板扫描
python3 tools/thesis_queue.py --from-limitup-scan data/limitup_scan.json --json
```

### 8.3 内联运行扫描（无需中间文件）

```bash
# 联网 portfolio_scan
python3 tools/thesis_queue.py --run-scan --quiet --json

# 因子扫描（需 torch + 公式 + CSV 或 --factor-codes）
python3 tools/thesis_queue.py --run-factor-scan --json
python3 tools/thesis_queue.py --run-factor-scan --factor-codes 600519,511260 --json

# 打板扫描（需 CSV）
python3 tools/thesis_queue.py --run-limitup-scan --json
python3 tools/thesis_queue.py --run-limitup-scan --limitup-codes 600519,000001 --json
```

### 8.4 输出字段

| 字段 | 含义 |
|------|------|
| `triggered_theses` | state.md 中已 TRIGGERED 的论文 |
| `scan_suggestions` | 来自 portfolio / factor / limitup 的新建议 |
| `research_now` | 按优先级排序的待研究列表 |

---

## 9. 金融严谨性与报告质检

### 9.1 financial_rigor.py（任何关键数字必过）

```bash
python3 tools/financial_rigor.py verify-market-cap --price 510 --shares 9.11e9 --reported 4.65e12 --currency HKD
python3 tools/financial_rigor.py verify-valuation --price 510 --eps 23.5 --bvps 120
python3 tools/financial_rigor.py cross-validate --field revenue --values '{"年报": 7518, "Yahoo": 7500}' --unit 亿
python3 tools/financial_rigor.py three-scenario --price 510 --eps 23.5 --shares 91.1 --growth 0.15 0.10 0.05 --pe 25 20 15
python3 tools/financial_rigor.py benford --values '[1234,2345,...]'
python3 tools/financial_rigor.py calc --expr '510 * 9.11e9'
```

### 9.2 report_audit.py（发布前准出）

```bash
# Step 1：提取并随机抽样 15%
python3 tools/report_audit.py extract --report reports/腾讯/腾讯-research-20260101.md
python3 tools/report_audit.py extract --report reports/foo.md --dry-run --ratio 0.2

# Step 2：人工/Agent 对清单逐项核验两个独立来源

# Step 3：准出判决
python3 tools/report_audit.py verdict --report reports/foo.md --results '[{"id":1,"label":"营收",...}]'
```

---

## 10. 报告产出与对比

### 10.1 Markdown → HTML

```bash
python3 tools/report_html.py reports/foo.md -o reports/foo.html
python3 tools/report_html.py reports/foo.md --stdout
```

### 10.2 多标的对比矩阵

```bash
python3 tools/stock_comparison.py AAPL MSFT GOOGL
python3 tools/stock_comparison.py --from-decisions --limit 4 --html /tmp/compare.html
```

### 10.3 绩效指标库（Python API）

`tools/perf_metrics.py` 为纯函数库（无 CLI），供 `run_with_realized_feedback(include_perf=True)` 及测试使用：

```python
from tools.perf_metrics import summarize_returns, PerfReport
```

---

## 11. 推送与定时任务

### 11.1 多通道通知

```bash
python3 tools/notify.py channels
python3 tools/notify.py send --title "标题" --text "正文"
python3 tools/notify.py send --title "周报" --file reports/portfolio-latest.md
python3 tools/notify.py send --title "x" --text "y" --channels feishu --local
```

| 通道 | 环境变量 |
|------|----------|
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| 飞书 | `FEISHU_WEBHOOK`, 可选 `FEISHU_SECRET` |
| 本地兜底 | `BERKSHIRE_NOTIFY_DIR`（默认 `reports/notifications`） |

零配置时只写本地文件，不报错。

### 11.2 Cron 与周度脚本

```bash
# 进化 / 论文跟踪（src/cron_evolution.py 封装）
./scripts/cron-evolution.sh thesis-tracker
./scripts/cron-evolution.sh portfolio-weekly   # 等同 cron 子命令，非下方 shell
./scripts/cron-evolution.sh evolution-loop
./scripts/cron-evolution.sh all

# 组合周度：portfolio_scan → thesis_queue（读 data/holdings.json 若存在）
./scripts/portfolio-weekly.sh
./scripts/portfolio-weekly.sh --json
./scripts/portfolio-weekly.sh --suggest-md   # 可粘贴进 config/state.md §2
```

---

## 12. Agent / Skills 使用

> 18 个技能目录与触发语：[SKILLS.md](SKILLS.md)

### 12.1 OpenClaw

```bash
./update-platforms.sh    # 同步 skills + tools 到 OpenClaw workspace
```

对 Agent 说：「对腾讯做四大师投资研究」或「运行 berkshire investment research on 0700.HK」。

技能目录：`skills/*.md`（带 YAML frontmatter，可作 `SKILL.md`）。

### 12.2 QwenPaw

```bash
python3 ~/.qwenpaw/loop_engine/berkshire_v8/evolution_loop_v10.py --ticker 600519 --company 贵州茅台
```

### 12.3 技能清单（18 个）

| 技能 | 用途 |
|------|------|
| `investment-research.md` | 四大师单标的深度研究 |
| `investment-team.md` | 多 Agent 并行团队研究 |
| `investment-checklist.md` | 研究检查清单 |
| `financial-data.md` | 数据源规范（各技能必须引用） |
| `thesis-tracker.md` | 论文状态跟踪 |
| `portfolio-review.md` | 组合审视 |
| `earnings-review.md` / `earnings-team.md` | 财报季 |
| `news-pulse.md` | 新闻脉冲 |
| `industry-research.md` / `industry-funnel.md` | 行业研究 |
| `quality-screen.md` | 质量筛选 |
| `bottleneck-hunter.md` | 瓶颈挖掘 |
| `management-deep-dive.md` | 管理层深度 |
| `private-company-research.md` | 非上市公司 |
| `deep-company-series.md` | 系列深度 |
| `wechat-article.md` | 微信文章分析 |
| `dyp-ask.md` | 段永平式提问 |

Meta-skill：`config/skill.md`。

### 12.4 graphify 知识图谱

```bash
graphify query "thesis_queue 如何合并 factor scan"
graphify path "factor_screener_bridge" "thesis_queue"
graphify explain "limitup_scoring"
graphify update .
```

图谱：`graphify-out/graph.json`（与 TextGrad `BerkshireGraph` 不同）。

### 12.5 雪球抓取（需登录）

```bash
pip install playwright && playwright install chromium
python3 tools/xueqiu_scraper.py --user-id <ID> --keywords 拼多多,PDD --output /tmp/pdd.md
```

---

## 13. 环境变量速查

| 变量 | 作用 |
|------|------|
| `TAVILY_API_KEYS` | 实时检索多 Key |
| `BERKSHIRE_LLM_*` | Prompt 改写 LLM |
| `BERKSHIRE_SENSITIVITY` | 收益反馈灵敏度（默认 0.5） |
| `BERKSHIRE_DECISION_LOG` | 决策 JSONL 路径 |
| `BERKSHIRE_EXPERIENCE_LOG` | 经验库路径 |
| `BERKSHIRE_RUN_LOG` | Run 记录 JSONL |
| `BERKSHIRE_TRACE_DIR` | TextGrad 轨迹目录 |
| `BERKSHIRE_PRICE_CACHE_DIR` / `TTL` | 行情缓存 |
| `BERKSHIRE_DATA_DIR` | 本地数据根（含 `daily_ohlcv.csv`） |
| `BERKSHIRE_ENABLE_LOCAL_DATA` | 启用本地 CSV 数据源 |
| `BERKSHIRE_ENABLE_PYTDX` | 启用 pytdx 实时源 |
| `BERKSHIRE_DATA_SOURCES` | 覆盖数据降级链顺序 |
| `BERKSHIRE_ENABLE_TUSHARE` + `TUSHARE_TOKEN` | Tushare 增强源 |
| `BERKSHIRE_ALPHAGPT_*` | 因子训练超参（见 `.env.example` 分组） |
| `BERKSHIRE_LIMITUP_SCORE_MIN` | 打板最低分（默认 60） |
| `BERKSHIRE_LIMITUP_MIN_BARS` | 打板最少 K 线（默认 22） |
| `BERKSHIRE_ENABLE_AKTOOLS` / `BERKSHIRE_AKTOOLS_BASE_URL` | aktools 诊断 |
| `WENCAI_COOKIE` | 问财选股（外部 `pywencai` skill） |
| `TDX_API_KEY` | 外部通达信脚本（本仓库不内置） |
| `TELEGRAM_*` / `FEISHU_*` | 推送通道 |
| `BERKSHIRE_API_KEYS` | HTTP 服务鉴权 |
| `BERKSHIRE_RATE_LIMIT_PER_MIN` | HTTP 限流 |
| `BERKSHIRE_HOST` / `BERKSHIRE_PORT` | HTTP 监听 |

完整列表见 [.env.example](../.env.example)。

---

## 14. 测试与验收

完整测试文档：**[TESTING.md](../TESTING.md)**

```bash
# 全量（推荐改代码后）
python3 -m pytest tests/ -v -rs

# 与 CI 一致（覆盖率 ≥50%）
python3 -m pytest tests/ -q --cov --cov-fail-under=50

# 按功能
python3 -m pytest tests/test_limitup_scoring.py -v
python3 -m pytest tests/test_factor_screener_bridge.py -v   # 需 torch
python3 -m pytest tests/test_tools_thesis_queue.py -v
python3 -m pytest tests/test_skill_forge.py tests/test_skill_forge_llm.py tests/test_skill_forge_cli.py -v
```

| 场景 | 命令 |
|------|------|
| 仅打板 | `pytest tests/test_limitup_scoring.py` |
| 仅因子 | `pytest tests/test_ashare_alphagpt.py tests/test_factor_screener_bridge.py` |
| 仅引擎 | `pytest tests/test_v10_unit.py tests/test_v10_integration.py` |
| 技能进化 SkillForge | `pytest tests/test_skill_forge.py tests/test_skill_forge_llm.py tests/test_skill_forge_cli.py` |
| 真实 LLM e2e | `BERKSHIRE_LLM_API_KEY=... pytest tests/e2e/` |

---

## 15. 文档索引

| 文档 | 内容 |
|------|------|
| **[docs/README.md](README.md)** | **文档中心**（按角色选阅读路径） |
| [USER_GUIDE.md](USER_GUIDE.md) | 本文件：全功能工作流 |
| [BACKTEST.md](BACKTEST.md) | 回测 5 条路线 |
| [QUANT.md](QUANT.md) | A 股量化专题 |
| [ENGINE.md](ENGINE.md) | TextGrad 引擎专题 |
| [SKILLS.md](SKILLS.md) | Agent 技能目录 |
| [TESTING.md](../TESTING.md) | 测试与验收 |
| [tools/README.md](../tools/README.md) | 工具 CLI 逐项 |
| [quant_data_fusion.md](quant_data_fusion.md) | 三库融合与边界 |
| [textgrad_design.md](textgrad_design.md) | 引擎设计深度 |
| [action-card.md](action-card.md) | 行动卡模板 |
| [report-conventions.md](report-conventions.md) | 报告规范 |
| [tdx_mcp_tool_design.md](tdx_mcp_tool_design.md) | 通达信 MCP（不实施） |
| [PROMPT_TEMPLATES.md](PROMPT_TEMPLATES.md) | 四大师 Prompt 模板 |
| [config/state.md](../config/state.md) | 论文状态机（thesis_queue 输入） |
| [ROADMAP.md](ROADMAP.md) | 路线图 |
| [README.md](../README.md) | 项目总览 |
| [VERSION_HISTORY.md](../VERSION_HISTORY.md) | 版本历史 |

---

## 附录：工具一览表

| 工具 | 网络 | 依赖 | 一句话 |
|------|:----:|------|--------|
| `financial_rigor.py` | 否 | 无 | 精确验算 / 交叉验证 |
| `report_audit.py` | 否 | 无 | 报告抽检准出 |
| `data_sources.py` | 是* | 可选多库 | A 股多源降级 |
| `ashare_data.py` | 是 | curl | A 股直连 |
| `ashare_factor_mining.py` | 是* | torch | AlphaGPT 训练 |
| `factor_screener_bridge.py` | 否* | torch | 因子打分筛选 |
| `limitup_screener_bridge.py` | 否 | 无 | 五维打板评分 |
| `quant_screener_bridge.py` | 否 | 无 | CSV 动量突破 |
| `thesis_queue.py` | 否* | state.md | 研究队列合并 |
| `stock_screener.py` | 是 | curl | 美股动量价值 |
| `portfolio_scan.py` | 是 | curl | 组合行动卡 |
| `portfolio_risk.py` | 否 | 无 | 集中度 / 主题风险 |
| `calibrate_sensitivity.py` | 是* | 可选 | SENSITIVITY 校准 |
| `calibrate_conviction.py` | 否 | 无 | 经验库 conviction |
| `notify.py` | 是* | curl | 多通道推送 |
| `report_html.py` | 否 | 无 | MD → HTML |
| `stock_comparison.py` | 否 | 无 | 标的对比矩阵 |
| `aktools_diagnostic.py` | 是* | aktools | 复合诊断 |
| `morningstar_fair_value.py` | 是 | curl | MS 公允价值 |
| `xueqiu_scraper.py` | 是 | playwright | 雪球时间线 |
| `momentum_backtest*.py` | 是 | curl | 演示回测 |
| `perf_metrics.py` | 否 | 无 | 绩效指标库（API） |

\* 部分模式可离线或降级。

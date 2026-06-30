# Berkshire AI — Four-Masters Parallel Investment Research (Upstream fully integrated)

> English version of [README.md](README.md). 中文版见 [README.md](README.md)。

> **Fully integrated from** [xbtlin/ai-berkshire](https://github.com/xbtlin/ai-berkshire) (the original four-masters framework + 18 skills + 9 tools + anti-bias discipline + financial rigor + a large body of real research reports)
>
> Plus a local **V10 TextGrad self-evolution engine** (explicit computation graph + node-level textual-gradient backpropagation + targeted optimization).

**Current version**: **V10.14** (production hardening, tier A: CI gates ruff/mypy/coverage + `pyproject.toml` packaging + `src/config.py` central config & startup doctor; cumulative with V10.13 Option B LLM prompt rewriting + V10.11 realized-return feedback loop / bull-bear debate + V10.12 SENSITIVITY calibration). Full history in [VERSION_HISTORY.md](VERSION_HISTORY.md).

**Status**: full upstream capability + the V10 engine are merged into this repo. **Adapted for OpenClaw / QwenPaw-style agent runtimes since V10.2.**

**Important**: this fork is **not used inside Claude Code**. It is designed for **OpenClaw / QwenPaw**-class AI agent products/runtimes.

- **Multi-agent parallel execution is fully preserved and adapted**: the "team-lead + 4 specialist sub-agents researching concurrently" structure in `investment-team`, `news-pulse`, `earnings-team`, etc. is kept intact (this is the core value of the upstream four-masters design). Only the Claude-Code-specific `TeamCreate`/`TaskCreate`/`SendMessage` syntax is replaced by:
  - OpenClaw: `sessions_spawn`, ACP sub-agents, ACP messages / `sessions_send`.
  - QwenPaw: parallel role instances in `loop_engine`, or harness multi-agent scheduling.
  - Fallback: when a platform can't easily spawn parallel sub-agents, use multiple manual sessions or a strong model running the roles sequentially.
- **OpenClaw**: skills install as standard `SKILL.md` into the agent workspace (frontmatter + behavior instructions + how to spawn sub-agents).
- **QwenPaw**: runs as part of `loop_engine` (the `evolution_loop_v10` is integrated under `~/.qwenpaw/loop_engine/`).
- All skills are cleaned into **portable, self-contained agent instruction templates** (no Claude-Code Team/Task orchestration), while the multi-agent team flow and value are retained.

## 🎯 Core Idea

**Four masters, in parallel:**
- **Duan Yongping** — business essence
- **Warren Buffett** — moat & valuation
- **Charlie Munger** — inversion & risk
- **Li Lu** — civilization-level trends

**TextGrad self-evolution**: inspired by the Nature 2025 work, implementing node-level diagnosis + textual-gradient backpropagation.

**Realized-return feedback loop + bull/bear debate** (absorbed from TradingAgents): each decision is persisted → real prices later compute alpha → mapped into per-master "calibration scores" fed back into backpropagation; plus an explicit bull/bear debate step on top of the parallel four-masters analysis, producing bull/bear cases and a net stance.

**A-share multi-source fallback data layer + multi-channel delivery** (absorbed from JusticePlutus): data fetching walks a `native→tushare→efinance→akshare→baostock→yfinance` fallback chain and degrades gracefully (never crashes the main flow); reports/signals can be delivered via Telegram / Feishu / local fallback, and with zero config it just writes to a local file without erroring.

**Real variable rewriting (V10.13 / Option B)**: `prompt_optimizer.apply_gradient` makes the textual gradient actually land on the prompt — an LLM reads the downstream diagnosis + current prompt and produces an improved prompt. `TextualGradientDescent(graph, llm=...)` then truly rewrites `Variable.value` for under-performing prompt nodes. The `LLMClient` is injectable/mockable (`StaticLLMClient` / `OpenAICompatibleLLMClient`), so the core is fully offline-testable and degrades gracefully on LLM failure; without an injected `llm` the behavior is unchanged (backward compatible).

## 📊 System Architecture

See [`assets/architecture.mmd`](assets/architecture.mmd) (Mermaid source) / [`assets/architecture.png`](assets/architecture.png).

```
┌─────────────────────────────────────────────────────────────┐
│                    Berkshire AI V10                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 0: Input (ticker, query, date_anchor)                │
│      ↓                                                       │
│  Layer 1: Data fetch (Tavily round-robin / A-share fallback)│
│      ↓                                                       │
│  Layer 2: Four-masters analysis (Duan/Buffett/Munger/Li Lu) │
│      ↓                                                       │
│  Layer 2.5: Bull/Bear debate (cases + net stance)           │
│      ↓                                                       │
│  Layer 3: Financial verification (financial_rigor.py)       │
│      ↓                                                       │
│  Layer 4: Output (final_report) → multi-channel (notify.py) │
│                                                             │
│  ← TextGrad backprop (node-level diagnosis + gradient opt)  │
│  ← Realized-return feedback (decision_log → realized scores)│
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### In OpenClaw (recommended)

OpenClaw skill format: a directory + `SKILL.md` (with YAML frontmatter).

Use the bundled sync script (recommended):
```bash
cd ~/Documents/Github/berkshire-ai
./update-platforms.sh
```
This syncs all skills and tools to OpenClaw (and QwenPaw).

Manual (one-off):
```bash
mkdir -p ~/.openclaw/workspace/skills/berkshire-investment-research
cp skills/investment-research.md ~/.openclaw/workspace/skills/berkshire-investment-research/SKILL.md
# ...same for the others
```

Every `SKILL.md` already includes compatible frontmatter (name / description / version 10.2); the OpenClaw agent auto-discovers and activates them when the scenario matches.

Example triggers: "do a four-masters investment study on Tencent" or "run berkshire investment research on 0700.HK".

There is also a top-level entry skill, `berkshire`, which lists all sub-skills when activated.

### In QwenPaw

berkshire-ai is deeply integrated into QwenPaw:

- Core runner: `src/evolution_loop_v10.py`, placed under `~/.qwenpaw/loop_engine/berkshire_v8/` (or the current version directory).
- Skill templates are loaded by the loop as prompt components (see `config/skill.md`).
- State / traces / reflections: written to `~/.qwenpaw/berkshire_state.md`, `~/.qwenpaw/berkshire_traces/`, etc.
- Direct run:
```bash
python3 ~/.qwenpaw/loop_engine/berkshire_v8/evolution_loop_v10.py --ticker 600519 --company 贵州茅台
```

### Other environments (generic)

- Feed any `skills/xxx.md` content as a system prompt or user message to any tool-calling agent (Grok, Qwen, Claude, etc.).
- Use together with the local Python toolchain (add `tools/` to PATH, or `cd` into the repo before calling).

### Run the TextGrad V10 engine

```bash
python3 src/evolution_loop_v10.py --ticker 600519 --company 贵州茅台
```

### Realized-return feedback loop + bull/bear debate

```python
from src import (DecisionRecord, append_decision, run_with_realized_feedback,
                 StaticPriceProvider, BerkshireGraph)

# 1) Persist a decision snapshot (per-master convictions + price anchor)
d = DecisionRecord(ticker="600519", date="2026-01-02",
                   scores={"duan":0.9,"buffett":0.8,"munger":0.6,"lilu":0.7},
                   price_anchor=1500.0, benchmark="000300", benchmark_anchor=3800.0)
append_decision(d)  # → ~/.berkshire/decisions.jsonl (override via BERKSHIRE_DECISION_LOG)

# 2) Later: backfill real prices → alpha → calibration scores → backprop (offline, injectable prices)
provider = StaticPriceProvider({("600519","2026-03-31"):1650.0, ("000300","2026-03-31"):3900.0})
result = run_with_realized_feedback(d, realized_date="2026-03-31", price_provider=provider)

# 3) Net bull/bear stance for the decision-time convictions (also callable standalone)
debate = BerkshireGraph().debate({"duan":0.9,"buffett":0.8,"munger":0.4,"lilu":0.7})
print(debate.net_stance, debate.net_score)   # bullish / +0.x (neutral band |net|<0.15)
```

### A-share multi-source fallback data + multi-channel delivery

```bash
# Data: native→tushare→efinance→akshare→baostock→yfinance fallback; never crashes on total failure
python3 tools/data_sources.py sources                  # list source availability (offline)
python3 tools/data_sources.py daily 600519 --limit 60  # daily bars (via fallback chain)

# Delivery: Telegram / Feishu / local fallback; zero config writes to reports/notifications/
python3 tools/notify.py channels
python3 tools/notify.py send --title "Weekly portfolio" --file reports/portfolio-latest.md
```

### Tool calls inside the agent (OpenClaw / QwenPaw)

Skills instruct the agent to run, via shell / integrated tools:

```bash
# Financial rigor (mandatory for any key figure)
python3 tools/financial_rigor.py verify-market-cap --price 510 --shares 9.11e9 --reported 4.65e12 --currency HKD
python3 tools/financial_rigor.py cross-validate --field revenue --values '123.4 123.5' --sources 'macrotrends aastocks'

# 15% random report audit + pass/fail verdict
python3 tools/report_audit.py extract --report reports/腾讯/腾讯-2025Q4.md
python3 tools/report_audit.py verdict --results '{...}' --report reports/xxx.md
```

All tools live under `./tools/` (Decimal-exact math, Benford's-law checks, three-scenario valuation, etc.).

## 🕸️ Knowledge Graph (graphify)

This project integrates [graphify](https://graphify.dev) for code/skill structure understanding.

- Hooks installed (post-commit auto-update, etc.)
- Graph: `graphify-out/graph.json` (a knowledge graph over the **whole codebase**; node/edge counts evolve with the code — see `graphify-out/manifest.json` for current numbers)
- Note: this graphify code graph ≠ the TextGrad engine's `BerkshireGraph` (the latter is a fixed 18-variable / 5-layer research computation graph, see `src/graph.py`)
- Usage (in supporting AI assistants): `/graphify`, `graphify query "..."`, `graphify path "A" "B"`, `graphify explain "..."`, update via `graphify update .` (code-only, no LLM cost)

## 📁 Project Layout

```
berkshire-ai/
├── README.md / README_EN.md     # docs (this file is the EN version)
├── LICENSE                      # MIT
├── VERSION_HISTORY.md
├── src/                         # TextGrad V10 self-evolution engine (local core)
│   ├── evolution_loop_v10.py    # run_example + run_with_realized_feedback (feedback loop)
│   ├── graph.py / optimizer.py  # computation graph (incl. debate()) + textual-gradient optimizer (LLM-injectable real rewrite)
│   ├── prompt_optimizer.py      # real variable rewriting (Option B): apply_gradient rewrites prompts via LLM (injectable/mockable LLMClient)
│   ├── decision_log.py          # decision snapshot JSONL persistence (DecisionRecord)
│   ├── realized_feedback.py     # realized return → scores (injectable PriceProvider)
│   ├── debate.py                # bull/bear debate (DebateResult, net stance)
│   └── tavily_search.py
├── skills/                      # 18 upstream skills (merged, OpenClaw-compatible, with frontmatter)
├── tools/                       # full toolchain (financial_rigor, report_audit, ashare_data, data_sources, notify, ...)
├── config/                      # skill.md (meta-skill) + state.md
├── docs/                        # textgrad_design, ROADMAP, report-conventions, articles
├── assets/                      # architecture.mmd / architecture.png
├── reports/                     # research report output (reports/{company}/*.md)
├── graphify-out/                # knowledge graph
├── tests/
└── traces/ + reflections/       # runtime
```

Report output conventions (directory layout + naming + analysis principles): see [`docs/report-conventions.md`](docs/report-conventions.md).

## 🔄 Versioning rule

Every new version must pass: (1) unit tests, (2) integration tests, (3) backtest verification, (4) cron-trigger test. See [VERSION_HISTORY.md](VERSION_HISTORY.md).

## 🔗 Links

- Original framework: [xbtlin/ai-berkshire](https://github.com/xbtlin/ai-berkshire)
- TextGrad paper: [arXiv:2406.07496](https://arxiv.org/abs/2406.07496)
- Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)

## 📝 License

MIT — see [LICENSE](LICENSE). This is a fork of xbtlin/ai-berkshire; the original copyright notice is retained.

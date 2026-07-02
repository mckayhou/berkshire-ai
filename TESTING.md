# 测试指南（TESTING）

> 本文档说明 berkshire-ai **如何跑测试、测什么、CI 怎么配、如何手工冒烟**。  
> **文档中心**：[docs/README.md](docs/README.md)  
> 功能用法：[docs/USER_GUIDE.md](docs/USER_GUIDE.md)；回测验收入口：[docs/BACKTEST.md](docs/BACKTEST.md)；工具 CLI：[tools/README.md](tools/README.md)。

---

## 目录

1. [快速开始](#1-快速开始)
2. [环境要求](#2-环境要求)
3. [测试分层](#3-测试分层)
4. [常用命令](#4-常用命令)
5. [测试文件索引](#5-测试文件索引)
6. [按功能验收入口](#6-按功能验收入口)
7. [工具手工冒烟清单](#7-工具手工冒烟清单)
8. [CI 流水线](#8-ci-流水线)
9. [覆盖率与质量门](#9-覆盖率与质量门)
10. [编写新测试](#10-编写新测试)（含 [§10.4 新功能交付清单](#104-新功能交付清单)）

---

## 1. 快速开始

```bash
cd berkshire-ai

# 最小安装（与 CI 一致）
pip install -r requirements.txt
pip install pytest pytest-cov

# 全量单元 + 集成（推荐每次改代码后跑）
python3 -m pytest tests/ -v -rs

# 带覆盖率（CI 门槛 ≥50%）
python3 -m pytest tests/ -q --cov --cov-report=term-missing --cov-fail-under=50

# 回测诊断脚本（非 pytest，单独跑）
python3 tests/test_v10_backtest.py
```

**当前规模（2026-07）**：`tests/` 下 **505** 个 pytest 用例；典型本地结果 **503 passed, 2 skipped**（e2e LLM + Tavily integration）；以 `pytest tests/ -ra` 为准。

---

## 2. 环境要求

| 组件 | 要求 |
|------|------|
| Python | **3.10–3.12**（CI 矩阵）；本地 3.14 亦可 |
| 核心依赖 | `pip install -r requirements.txt`（`httpx`） |
| 测试 | `pip install pytest pytest-cov` 或 `pip install -e '.[dev]'` |
| 可选 extras | 见下表 |

### 可选依赖与对测试的影响

| Extra | 安装 | 影响的测试 |
|-------|------|------------|
| `[dev]` | `pip install -e '.[dev]'` | ruff、mypy、pytest-cov |
| `[factor-mining]` | `pip install -e '.[factor-mining]'` | `test_ashare_alphagpt.py`、`test_factor_screener_bridge.py`（无 torch 时 `importorskip` 跳过） |
| `[service]` | `pip install -e '.[service]'` | `test_service.py` 中 FastAPI 用例（无 fastapi 时 skip） |
| `[quant]` | `pip install -e '.[quant]'` | `test_quant_data_fusion.py` 中 pytdx 相关（mock 为主） |
| `[ashare]` | akshare/tushare 等 | 仅手工在线冒烟；单测用 monkeypatch |

### 环境变量（测试相关）

| 变量 | 用途 | 无配置时 |
|------|------|----------|
| `BERKSHIRE_LLM_API_KEY` / `OPENAI_API_KEY` | `tests/e2e/test_llm_smoke.py` | **skip**（非失败） |
| `TAVILY_API_KEYS` | 手工 `tavily_search.py test` | 手工跳过 |
| `BERKSHIRE_*` | 各模块配置 | 单测多用 `monkeypatch` 清理 |

---

## 3. 测试分层

```text
                    ┌─────────────────────┐
                    │  E2E LLM 冒烟        │  tests/e2e/（需 API Key）
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
   ┌──────▼──────┐    ┌────────▼────────┐   ┌──────▼──────┐
   │ 集成测试     │    │ 工具层单测       │   │ 引擎核心单测 │
   │ v10_integration│  │ test_tools_*    │   │ src/* tests  │
   │ pipeline     │    │ limitup/factor  │   │ graph/opt... │
   └──────────────┘    └─────────────────┘   └─────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ 离线 mock 为主       │
                    │ 网络层 monkeypatch   │
                    └─────────────────────┘
```

| 层级 | 目录/文件 | 特点 |
|------|-----------|------|
| **引擎单元** | `test_v10_unit.py`、`test_graph*`、`test_prompt_*` 等 | 纯逻辑，无 I/O |
| **引擎集成** | `test_v10_integration.py`、`test_pipeline.py`、`test_realized_feedback_loop.py` | 多模块串联 |
| **工具单测** | `test_tools_*.py` | `tools/` 下 CLI 逻辑；网络用 mock |
| **量化/A股** | `test_ashare_alphagpt.py`、`test_factor_screener_bridge.py`、`test_limitup_scoring.py`、`test_quant_data_fusion.py` | 因子/打板/CSV；torch 可选 |
| **E2E** | `tests/e2e/test_llm_smoke.py` | 真实 LLM，默认 skip |
| **诊断脚本** | `tests/test_v10_backtest.py` | 非 pytest，打印覆盖率 |

---

## 4. 常用命令

### 4.1 全量 / verbosity

```bash
python3 -m pytest tests/ -q                    # 安静
python3 -m pytest tests/ -v                   # 逐条
python3 -m pytest tests/ -v -rs               # 显示 skip 原因（推荐）
python3 -m pytest tests/ -x                   # 首败即停
python3 -m pytest tests/ --lf                   # 只跑上次失败
```

### 4.2 按文件 / 目录

```bash
# 引擎核心
python3 -m pytest tests/test_v10_unit.py tests/test_v10_integration.py -v

# 工具链
python3 -m pytest tests/test_tools_financial_rigor.py tests/test_tools_report_audit.py -v

# A 股量化（含打板）
python3 -m pytest tests/test_limitup_scoring.py tests/test_factor_screener_bridge.py \
                 tests/test_ashare_alphagpt.py tests/test_quant_data_fusion.py -v

# thesis_queue
python3 -m pytest tests/test_tools_thesis_queue.py tests/test_limitup_scoring.py::test_merge_limitup_scan_suggestions -v

# 仅 e2e（需 LLM Key）
python3 -m pytest tests/e2e/ -v
```

### 4.3 按关键字

```bash
python3 -m pytest tests/ -k "limitup" -v
python3 -m pytest tests/ -k "factor or alphagpt" -v
python3 -m pytest tests/ -k "thesis_queue" -v
python3 -m pytest tests/ -k "financial_rigor" -v
```

### 4.4 Lint / 类型（与 CI 一致）

```bash
pip install ruff mypy
ruff check src tools tests
mypy
```

### 4.5 进化引擎 CLI 冒烟

```bash
python3 src/evolution_loop_v10.py              # run_example
python3 src/evolution_loop_v10.py status
python3 src/evolution_loop_v10.py reflect AAPL
python3 src/evolution_loop_v10.py optimize AAPL --rounds 1
python3 src/evolution_loop_v10.py cycle AAPL --anchor 100 --price 110
```

---

## 5. 测试文件索引

| 文件 | 覆盖模块 | 说明 |
|------|----------|------|
| `test_v10_unit.py` | `graph.py`, `optimizer.py` | 计算图拓扑、反向传播 |
| `test_v10_integration.py` | 引擎端到端 | 图创建、更新节点 |
| `test_v10_backtest.py` | 诊断覆盖率 | **脚本**，非 pytest |
| `test_pipeline.py` | `src/pipeline.py` | `run_full_cycle` |
| `test_realized_feedback_loop.py` | `realized_feedback.py` | 收益反馈闭环 |
| `test_network_price_provider.py` | 价格提供者 | 缓存、非交易日 |
| `test_decision_log` *(via loop)* | `decision_log.py` | JSONL 持久化 |
| `test_experience_store.py` | `experience_store.py` | 经验库 JSONL |
| `test_research_loop.py` | `research_loop.py` | R/D 双循环 |
| `test_hypothesis.py` | `hypothesis.py` | 可证伪假设 |
| `test_eval_harness.py` | `eval_harness.py` | 多轮评测 |
| `test_skill_forge.py` | `src/skill_forge/` | SkillForge 规则管线 + VFS |
| `test_skill_forge_llm.py` | `llm_judge.py` | LLM-judge CR / 四维分析 / 诊断（StaticLLMClient） |
| `test_eval_harness_golden.py` | 黄金回归 | 单调不退化 |
| `test_prompt_optimizer.py` | `prompt_optimizer.py` | LLM 改写 |
| `test_prompt_validation.py` | `prompt_validation.py` | 验证门控 |
| `test_llm_gradient.py` | `llm_gradient.py` | ∇_LLM |
| `test_evolution_llm_wiring.py` | 主链路接线 | LLM 梯度注入 |
| `test_sanitize.py` | `sanitize.py` | 提示注入防护 |
| `test_observability.py` | `observability.py` | 埋点 / run_id |
| `test_service.py` | `service.py` | FastAPI（需 extra） |
| `test_access_control.py` | `access_control.py` | API Key / 限流 |
| `test_metrics_export.py` | `metrics_export.py` | Prometheus |
| `test_config.py` | `config.py` | 环境变量 doctor |
| `test_evolution_cli.py` | `evolution_cli.py` | CLI 子命令（含 skill-evolve） |
| `test_cron_evolution.py` | cron 任务 | 定时入口 |
| `test_reflect.py` | 反思 | 经验对比 |
| `test_trace_recorder.py` | 轨迹记录 | |
| `test_run_recorder.py` | Run 记录 | |
| `test_quality_scorer.py` | 质量评分 | |
| `test_scenario.py` | 情景分析 | |
| `test_rewrite_fewshot.py` | few-shot 注入 | |
| `test_golden_action_card.py` | 行动卡黄金样例 | |
| `test_tools_financial_rigor.py` | `financial_rigor.py` | 精确计算 + AST 安全 |
| `test_tools_report_audit.py` | `report_audit.py` | 提取 / 判决 |
| `test_tools_data_sources.py` | `data_sources.py` | 降级链、适配器 |
| `test_tools_network.py` | 网络重试 | monkeypatch httpx |
| `test_tools_notify.py` | `notify.py` | 多通道 mock |
| `test_tools_misc.py` | ashare/screener 等 | 纯函数 |
| `test_tools_portfolio_scan.py` | `portfolio_scan.py` | |
| `test_tools_portfolio_risk.py` | `portfolio_risk.py` | |
| `test_tools_thesis_queue.py` | `thesis_queue.py` | state.md 解析 |
| `test_tools_perf_metrics.py` | `perf_metrics.py` | 夏普/回撤等 |
| `test_calibrate_sensitivity.py` | `calibrate_sensitivity.py` | SENSITIVITY |
| `test_calibrate_conviction.py` | `calibrate_conviction.py` | conviction |
| `test_report_html.py` | `report_html.py` | MD→HTML |
| `test_stock_comparison.py` | `stock_comparison.py` | |
| `test_aktools_diagnostic.py` | `aktools_diagnostic.py` | mock HTTP |
| `test_quant_data_fusion.py` | LocalCsv / quant bridge | V10.24 |
| `test_ashare_alphagpt.py` | `ashare_alphagpt/*` | 需 torch |
| `test_factor_screener_bridge.py` | `factor_screener_bridge` | 需 torch |
| `test_limitup_scoring.py` | `limitup_scoring` + thesis 合并 | **无 torch** |
| `test_graph_analysis.py` | `graph_analysis.py` | V10.26 分析重跑 |
| `test_eval_harness_rerun.py` | `eval_harness` + `rerun_analysis` | V10.26 真闭环 |
| `test_trajectory_ab.py` | `trajectory_ab.py` | V10.27 A/B |
| `test_trajectory_ab_eval_cli.py` | `tools/trajectory_ab_eval.py` | CLI smoke |
| `test_signal_proposer.py` | `signal_proposer.py` | V10.28 信号→Hypothesis |
| `test_pipeline_signals.py` | `pipeline` + factor scan | V10.28 接线 |
| `test_skill_forge_cli.py` | `tools/skill_evolve.py` CLI | 子命令 subprocess 冒烟 |
| `e2e/test_llm_smoke.py` | 真实 LLM 链路 | 需 Key |

---

## 6. 按功能验收入口

改动了某块代码后，优先跑对应测试：

| 你改了… | 跑这些 |
|---------|--------|
| `src/graph.py` / `optimizer.py` | `pytest tests/test_v10_unit.py tests/test_v10_integration.py` |
| `src/realized_feedback.py` | `pytest tests/test_realized_feedback_loop.py tests/test_network_price_provider.py` |
| `src/prompt_optimizer.py` | `pytest tests/test_prompt_optimizer.py tests/test_prompt_validation.py` |
| `tools/financial_rigor.py` | `pytest tests/test_tools_financial_rigor.py` |
| `tools/data_sources.py` | `pytest tests/test_tools_data_sources.py tests/test_quant_data_fusion.py` |
| `tools/thesis_queue.py` | `pytest tests/test_tools_thesis_queue.py tests/test_limitup_scoring.py tests/test_factor_screener_bridge.py` |
| `tools/ashare_alphagpt/*` | `pytest tests/test_ashare_alphagpt.py tests/test_factor_screener_bridge.py` |
| `tools/limitup_screener_bridge.py` / `limitup_scoring.py` | `pytest tests/test_limitup_scoring.py` |
| `tools/quant_screener_bridge.py` | `pytest tests/test_quant_data_fusion.py` |
| `src/service.py` | `pytest tests/test_service.py tests/test_access_control.py` |
| `src/eval_harness.py` / `rerun_analysis` | `pytest tests/test_eval_harness.py tests/test_eval_harness_rerun.py tests/test_eval_harness_golden.py` |
| `src/graph_analysis.py` | `pytest tests/test_graph_analysis.py tests/test_eval_harness_rerun.py` |
| `src/trajectory_ab.py` | `pytest tests/test_trajectory_ab.py`；`python3 tools/trajectory_ab_eval.py` |
| `src/signal_proposer.py` / `pipeline` 信号接线 | `pytest tests/test_signal_proposer.py tests/test_pipeline_signals.py` |
| `src/skill_forge/` / `tools/skill_evolve.py` | `pytest tests/test_skill_forge.py tests/test_skill_forge_llm.py tests/test_skill_forge_cli.py` |
| 回测相关（OOS / 轨迹诊断） | 见 [BACKTEST.md](docs/BACKTEST.md)；`pytest tests/test_ashare_alphagpt.py`；`python3 tests/test_v10_backtest.py`；`python3 tools/trajectory_ab_eval.py` |

### SkillForge 技能进化验收

```bash
python3 -m pytest tests/test_skill_forge.py tests/test_skill_forge_llm.py tests/test_skill_forge_cli.py -v
python3 tools/skill_evolve.py judge tests/fixtures/skill_forge/bad_cases.jsonl --judge-mode rule
python3 tools/skill_evolve.py evolve investment-research --dry-run --judge-mode rule
```

文档：[docs/SKILL_EVOLUTION.md](docs/SKILL_EVOLUTION.md)

### V10.28 TextGrad 进化验收

```bash
# V10.26 分析重跑 + V10.27 A/B + V10.28 信号接线
python3 -m pytest tests/test_graph_analysis.py tests/test_eval_harness_rerun.py \
  tests/test_trajectory_ab.py tests/test_signal_proposer.py tests/test_pipeline_signals.py -v
python3 tools/trajectory_ab_eval.py --json   # 诊断覆盖率 ≥ 90% → exit 0
```

### V10.25+ 量化最小验收

```bash
# 无 torch：打板评分 + CSV 动量 + thesis 合并
python3 -m pytest tests/test_limitup_scoring.py tests/test_quant_data_fusion.py -v

# 有 torch：再加因子
pip install -e '.[factor-mining]'
python3 -m pytest tests/test_ashare_alphagpt.py tests/test_factor_screener_bridge.py -v
```

---

## 7. 工具手工冒烟清单

自动化单测 **不替代** 第三方 API 可用性验证。发版前可选跑：

### 7.1 离线（无需网络）

```bash
python3 tools/financial_rigor.py verify-market-cap \
  --price 510 --shares 9.11e9 --reported 4.65e12 --currency HKD
python3 tools/financial_rigor.py calc --expr '510 * 9.11e9'
python3 tools/report_audit.py extract --report reports/RocketLab/RKLB-investment-research.md --dry-run
python3 tools/report_html.py README.md -o /tmp/readme.html
python3 tools/thesis_queue.py --json
python3 tools/portfolio_risk.py --holdings '{"NVDA":45,"CASH":55}' --json
python3 tools/skill_evolve.py list
python3 tools/skill_evolve.py judge tests/fixtures/skill_forge/bad_cases.jsonl --judge-mode rule
python3 src/config.py
```

### 7.2 本地 CSV 量化（无需网络）

```bash
export BERKSHIRE_DATA_DIR=./data
# 需存在 data/daily_ohlcv.csv
python3 tools/quant_screener_bridge.py --json
python3 tools/limitup_screener_bridge.py --json
python3 tools/factor_screener_bridge.py --json   # 另需 torch + 已训练公式
```

### 7.3 在线（需外网）

```bash
python3 tools/data_sources.py sources
python3 tools/data_sources.py quote 600519
python3 tools/ashare_data.py quote 600519
python3 tools/momentum_backtest.py
python3 tools/stock_screener.py
python3 tools/morningstar_fair_value.py --max-pages 1 --top 5
python3 src/tavily_search.py test    # 需 TAVILY_API_KEYS
```

### 7.4 需额外服务 / 登录

| 工具 | 前置条件 |
|------|----------|
| `aktools_diagnostic.py` | `BERKSHIRE_ENABLE_AKTOOLS=1` + 本地 aktools HTTP |
| `xueqiu_scraper.py` | Playwright + 雪球 cookie |
| `notify.py send` | Telegram / 飞书 webhook（或仅本地兜底） |
| `tests/e2e/test_llm_smoke.py` | OpenAI 兼容 API Key |

### 7.5 一键研究队列链路冒烟

```bash
export BERKSHIRE_DATA_DIR=./data
python3 tools/limitup_screener_bridge.py --json -o /tmp/limitup.json
python3 tools/thesis_queue.py --from-limitup-scan /tmp/limitup.json --suggest-md
```

---

## 8. CI 流水线

配置文件：`.github/workflows/test.yml`

| Job | 内容 | 触发 |
|-----|------|------|
| `lint-type` | `ruff check` + `mypy src/` | push/PR → main |
| `pytest` | Python **3.10 / 3.11 / 3.12** 矩阵 + **coverage ≥50%** | push/PR |
| `e2e-llm` | `tests/e2e/`，需 repo secret `BERKSHIRE_LLM_API_KEY` | 仅 **push**（非 PR fork） |
| `build-image` | `docker build` 冒烟 | push/PR |
| `security` | `pip-audit`（非阻断）+ `gitleaks` | push/PR |

本地复现 CI pytest job：

```bash
pip install -r requirements.txt pytest pytest-cov
pytest tests/ -q --tb=short --cov --cov-report=term-missing --cov-fail-under=50
```

---

## 9. 覆盖率与质量门

```bash
# 终端报告
python3 -m pytest tests/ --cov --cov-report=term-missing

# HTML 报告
python3 -m pytest tests/ --cov --cov-report=html
open htmlcov/index.html
```

| 门控 | 值 | 配置位置 |
|------|-----|----------|
| 覆盖率下限 | **50%** | CI `pytest --cov-fail-under=50` |
| mypy | `src/` only | `pyproject.toml` `[tool.mypy]` |
| ruff | E, F, I | `pyproject.toml` `[tool.ruff]` |

覆盖率统计范围：`src/` + `tools/`（见 `pyproject.toml` `[tool.coverage.run]`）。

---

## 10. 编写新测试

### 10.1 约定

- 新测试放在 `tests/test_<模块>.py`
- 工具测试：`sys.path.insert(0, "../tools")` 后 `import xxx`
- 引擎测试：`sys.path.insert(0, "../src")` 或 `from src import ...`（editable install 后）
- **网络必须 mock**：参考 `test_tools_network.py`、`test_aktools_diagnostic.py`
- 可选依赖用 `pytest.importorskip("torch")` 或 `pytest.importorskip("fastapi")`
- 需跳过时写清 `reason=`，跑 `-rs` 可看到

### 10.2 模板：离线工具测试

```python
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import my_tool  # noqa: E402


def test_happy_path(tmp_path, monkeypatch):
    monkeypatch.setenv("BERKSHIRE_DATA_DIR", str(tmp_path))
    result = my_tool.run(...)
    assert result["ok"] is True
```

### 10.3 模板：CSV 筛选类

参考 `tests/test_limitup_scoring.py`、`tests/test_factor_screener_bridge.py`：
- 用 `tmp_path` 写 `daily_ohlcv.csv`
- `monkeypatch.setenv("BERKSHIRE_DATA_DIR", ...)`
- 断言 `candidates` 结构与 `thesis_queue_line`

### 10.4 新功能交付清单

> **硬性要求**：每次新功能或行为变更，在标记完成前必须跑通测试并补全文档。发版前再跑 `release-check`（§12）。

#### 测试

- [ ] 新增/更新 `tests/test_<模块>.py`（含 CLI subprocess 冒烟时 `tests/test_*_cli.py`）
- [ ] `pytest tests/ -v -rs` 全绿（允许 e2e / Tavily / torch skip，须在 `VERSION_HISTORY` 或本文件附录写明）
- [ ] 新 CLI 在 §6「按功能验收入口」增加一行命令
- [ ] §5「测试文件索引」表增加对应行
- [ ] `ruff check src tools tests`；改 `src/` 时跑 `mypy`

#### 文档（按暴露面逐项核对）

| 暴露面 | 必改文件 |
|--------|----------|
| 用户可见能力 | `README.md`、`README_EN.md`、`docs/USER_GUIDE.md` |
| 引擎 / API / CLI | `docs/ENGINE.md`、`src/evolution_cli.py` 帮助、`tools/README.md` |
| 版本发版 | `VERSION_HISTORY.md`、`config/state.md`、`pyproject.toml` + `APP_VERSION` |
| 专题能力 | 对应专题 doc（如 `SKILL_EVOLUTION.md`、`BACKTEST.md`、`textgrad_design.md`） |
| 路线图 | `docs/ROADMAP.md`（里程碑级变更） |
| 测试与冒烟 | **本文件** `TESTING.md`（§5、§6、§10.4、附录计数） |
| 文档导航 | `docs/README.md` 表格/地图（新专题时） |

#### 工程

- [ ] `graphify update .`（改 Python 后）；提交 `graphify-out/` sync
- [ ] `./scripts/release-check.sh --skip-tag-check`（工作区干净、版本横幅一致）

#### 一键核对（功能开发中，非发版）

```bash
pytest tests/ -v -rs
./scripts/release-check.sh --skip-tag-check --skip-pytest   # 或含 pytest 的完整门控
```

---

## 11. 已知限制与排错

| 现象 | 原因 | 处理 |
|------|------|------|
| `SKIPPED e2e/test_llm_smoke` | 无 LLM Key | 正常；配 Key 后再跑 `pytest tests/e2e/` |
| `SKIPPED` torch 相关 | 未装 `[factor-mining]` | `pip install -e '.[factor-mining]'` 或接受 skip |
| `SKIPPED` fastapi | 未装 `[service]` | 装 extra 或接受 skip |
| 在线工具失败 | 第三方限流/鉴权 | 环境问题；单测不应依赖外网 |
| `benford` 样本不足 | 需要 ≥50 个点 | 加大 `--values` 样本 |
| `xueqiu_scraper` | 需浏览器登录 | 不纳入 CI |
| coverage 低于 50% | 新代码无测试 | 补单测或扩展现有文件 |

### 常见问题

**Q: 为什么 CI 不跑 factor-mining / torch 测试？**  
A: CI 仅装 `requirements.txt` + pytest；torch 用例通过 `importorskip` 跳过。本地发版前请手动装 `[factor-mining]` 跑量化测试。

**Q: 如何只验证打板评分？**  
A: `pytest tests/test_limitup_scoring.py -v`（6 用例，无 torch）。

**Q: `test_v10_backtest.py` 和 pytest 关系？**  
A: 独立诊断脚本，检查 TextGrad 节点诊断覆盖率（需 `~/.qwenpaw/berkshire_traces`）。**V10.27** 起可用离线 bundled fixtures：`python3 tools/trajectory_ab_eval.py`（纳入发版门控，exit 0 = 覆盖率 ≥ 90%）。

---

## 12. 发版前检查（release-check）

每次打版本标签或宣布「已发版」前，**必须**跑完本清单。可一键执行：

```bash
chmod +x scripts/release-check.sh   # 首次
./scripts/release-check.sh
```

仅验证元数据、跳过 pytest（CI 已跑过时）：

```bash
./scripts/release-check.sh --skip-pytest
```

### 检查项（脚本自动 + 人工）

| # | 检查 | 通过标准 |
|---|------|----------|
| 1 | 工作区干净 | `git status --short` 无输出（含 graphify hook 产生的 `graphify-out/`） |
| 2 | 包版本一致 | `pyproject.toml` `version` == `src/service.py` `APP_VERSION` |
| 3 | 对外横幅一致 | `README.md`、`config/state.md` 的 **V10.XY** 与上项主版本号一致 |
| 4 | 无幽灵版本号 | 核心文档无高于当前 **V10.XY** 的未发布标签 |
| 5 | 标签指向 HEAD | `git rev-parse HEAD` == `git rev-parse v10.XY^{commit}` |
| 6 | 远端同步 | `main` 与 `origin/main` 同 SHA（有 upstream 时） |
| 7 | 单元测试 | `pytest -q tests/` 全绿 |
| 8 | 变更记入历史 | `VERSION_HISTORY.md` 有对应 **V10.XY** 条目且含测试结论 |
| 9 | graphify（改 Python 时） | `graphify update .` 后 `graphify-out/` 已提交 |

### 推荐发版顺序

```bash
# 1. 改版本号 + VERSION_HISTORY + ROADMAP/state/skill
# 2. 跑测试
pytest -q tests/
# 3. 提交全部（含 graphify）；若 hook 再次脏 graphify-out，再提交一次 sync
git add -A && git commit -m "chore: bump version to X.Y.Z"
# 4. 发版门控（改版本号并提交后；**最后一笔 graphify sync 提交后等 ~60s** 再跑，避免 hook 未结束）
./scripts/release-check.sh --skip-tag-check   # 可选：首跑跳过标签项（见脚本 --help）
# 5. 打标签并推送
git tag -a vX.Y -m "VX.Y: summary"
git push origin main && git push origin vX.Y
# 6. 终验（含标签必须在 HEAD）
./scripts/release-check.sh
```

> **教训（V10.25）**：分多次 subagent 提交、未跑全库 `git status`、标签打在版本 bump 而文档提交在后、graphify post-commit hook 反复弄脏工作区，会导致「以为发完其实还漏」。以后以 `release-check.sh` 为唯一收口。

---

## 附录：历史 E2E 记录

| 日期 | Python | pytest | 备注 |
|------|--------|--------|------|
| 2026-06-26 | 3.14.6 | 107 passed | 早期版本基线 |
| 2026-07-02 | 3.14 | **503 passed, 2 skipped**（V10.28 + SkillForge；e2e LLM + Tavily integration skip） |
| 2026-07-02 | 3.14 | **458 passed, 1 skipped** | 含 limitup/factor/quant 测试；e2e LLM skip |

> 历史数字仅作参考；以本地 `pytest tests/ --co` 与 `-rs` 输出为准。

---

## 相关文档

- [docs/README.md](docs/README.md) — **文档中心**（按场景导航）
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) — 功能使用
- [docs/BACKTEST.md](docs/BACKTEST.md) — 回测 5 条路线与验收
- [tools/README.md](tools/README.md) — CLI 参数
- [docs/ENGINE.md](docs/ENGINE.md) — TextGrad 引擎测试上下文
- [docs/QUANT.md](docs/QUANT.md) — A 股量化验收工作流
- [VERSION_HISTORY.md](VERSION_HISTORY.md) — 版本与测试要求
- [docs/textgrad_design.md](docs/textgrad_design.md) — 引擎设计

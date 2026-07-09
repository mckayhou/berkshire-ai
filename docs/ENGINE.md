# TextGrad 引擎指南（ENGINE）

> 四大师计算图、收益反馈、进化 CLI、HTTP 服务。  
> 深度设计：[textgrad_design.md](textgrad_design.md) | 导航：[docs/README.md](README.md)

---

## 1. 架构一览

```text
输入 (ticker, 四大师 scores)
    → BerkshireGraph（18 变量节点）
    → debate() 多空净判断
    → decision_log 落盘
    → realized_feedback（事后价格 → 评分）
    → backward() + optimizer.step()（文本梯度）
    → experience_store（经验沉淀）
```

与 **graphify 代码图**（`graphify-out/`）不同；引擎图见 `src/graph.py`。

---

## 2. CLI 入口

### 2.1 单次演示

```bash
python3 src/evolution_loop_v10.py --ticker 600519 --company 贵州茅台
```

### 2.1.1 投研效果 CLI（决策落盘 / 后验）

```bash
python3 tools/log_decision.py append --ticker AAPL --date 2026-01-02 --price 100 \
  --stance 0.8 --thesis "..." --kill "..." --action hold
python3 tools/posterior_weekly.py report --as-of 2026-02-01 --prices '{"AAPL|2026-01-22":110}'
```

详见 [RESEARCH_EFFECTIVENESS.md](RESEARCH_EFFECTIVENESS.md)。验收：

```bash
pytest tests/e2e/test_research_effectiveness_e2e.py tests/test_posterior_report.py -v
```

### 2.2 进化循环 CLI（`src/evolution_cli.py`）
通过 `evolution_loop_v10.py` 子命令调用：

```bash
python3 src/evolution_loop_v10.py status
python3 src/evolution_loop_v10.py reflect AAPL
python3 src/evolution_loop_v10.py optimize AAPL --rounds 3
python3 src/evolution_loop_v10.py cycle AAPL --anchor 100 --price 110 --date 2026-01-02
python3 src/evolution_loop_v10.py cron evolution-loop
python3 src/evolution_loop_v10.py cron thesis-tracker
python3 src/evolution_loop_v10.py cron all --json
```

| 子命令 | 作用 |
|--------|------|
| `status` | 决策/经验/轨迹存储健康摘要 |
| `reflect TICKER` | 基于经验库对比反思 |
| `optimize TICKER` | 反思 + 验证门控进化 |
| `cycle TICKER` | `run_full_cycle` 完整主链路 |
| `cron TASK` | 定时任务入口 |
| `skill-evolve ACTION` | SkillForge 技能进化（见 [SKILL_EVOLUTION.md](SKILL_EVOLUTION.md)） |

Cron 脚本：`./scripts/cron-evolution.sh thesis-tracker`

### 2.3 配置体检

```bash
python3 src/config.py
cp .env.example .env   # 可选
```

---

## 3. Python API

### 3.1 决策落盘（投研效果契约）

正式研究须带 `thesis` / `kill_condition` / `action` / `horizon_days`。完整说明见 [RESEARCH_EFFECTIVENESS.md](RESEARCH_EFFECTIVENESS.md)。

```python
from src import DecisionRecord, append_decision, is_research_complete

d = DecisionRecord(
    ticker="600519",
    date="2026-01-02",
    scores={"duan": 0.9, "buffett": 0.8, "munger": 0.6, "lilu": 0.7},
    price_anchor=1500.0,
    benchmark="000300",
    benchmark_anchor=3800.0,
    analyses={"buffett": "护城河…"},  # 供 ∇_LLM
    thesis="白酒护城河宽、现金流强",
    kill_condition="吨价失守或渠道库存危机",
    action="hold",
    horizon_days=20,
    depth="standard",
    skill="investment-research",
)
assert is_research_complete(d)
append_decision(d)  # → ~/.berkshire/decisions.jsonl
# 或 CLI: python3 tools/log_decision.py append ...
```

### 3.2 完整主链路

```python
from src import DecisionRecord, run_full_cycle

d = DecisionRecord(...)
out = run_full_cycle(d, realized_price=1650.0)
```

### 3.3 收益反馈 + 进化

```python
from src import run_with_realized_feedback
from src.realized_feedback import StaticPriceProvider, NetworkPriceProvider
from src.experience_store import ExperienceStore, KeywordExperienceRetriever

provider = StaticPriceProvider({("600519", "2026-03-31"): 1650.0})
# 或 NetworkPriceProvider()  # 走 data_sources，需网络

result = run_with_realized_feedback(
    d,
    realized_date="2026-03-31",
    price_provider=provider,
    persist=True,           # 沉淀经验到 ExperienceStore
    include_perf=True,        # perf_metrics 摘要
    retriever=KeywordExperienceRetriever(ExperienceStore()),
    retriever_k=3,
)
# result["debate"], result["experience"], result["perf"]
```

### 3.4 多空辩论（单独）

```python
from src import BerkshireGraph

debate = BerkshireGraph().debate({"duan": 0.9, "buffett": 0.8, "munger": 0.4, "lilu": 0.7})
print(debate.net_stance, debate.net_score)
```

### 3.5 R/D 双循环

```python
from src.research_loop import run_rd_cycle, LLMHypothesisProposer
from src.eval_harness import run_multi_round
```

见 [textgrad_design.md](textgrad_design.md)、[rdagent_reference.md](rdagent_reference.md)。

---

## 4. 收益反馈与绩效

### 4.1 公式（简）

- `alpha = raw_return - benchmark_return`
- `realized_base = clip(0.5 + alpha × SENSITIVITY, 0, 1)`
- `master_score = clip(1 - |conviction - realized_base|, 0, 1)`

默认 `SENSITIVITY=0.5`（V10.12 校准）；覆盖：`BERKSHIRE_SENSITIVITY`。

### 4.2 perf_metrics

`tools/perf_metrics.py`：夏普、最大回撤、年化等（纯 stdlib）。

```python
from tools.perf_metrics import summarize_returns, PerfReport
```

通过 `run_with_realized_feedback(include_perf=True)` 或决策序列拼装使用。

### 4.3 决策事后「回测」说明

这是**单次或序列决策**的事后评估，不是策略回测。  
与因子 OOS、动量回测对照见 [BACKTEST.md §5](BACKTEST.md#5-决策事后绩效realized_feedback--perf_metrics)。

---

## 5. 校准工具

### 5.1 SENSITIVITY 尺度

```bash
python3 tools/calibrate_sensitivity.py universe
python3 tools/calibrate_sensitivity.py run --lookback 365 --also 182 --json
```

### 5.2 经验库 conviction

```bash
python3 tools/calibrate_conviction.py report
python3 tools/calibrate_conviction.py report --ticker AAPL --json
```

---

## 6. HTTP 服务（可选）

```bash
pip install -e '.[service]'
berkshire-serve
# 默认 0.0.0.0:8000
```

| 端点 | 方法 | 作用 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/doctor` | GET | 配置体检（无密钥） |
| `/score` | POST | 决策 + 已实现价 → 评分 |
| `/debate` | POST | 四大师分 → 多空净判断 |
| `/metrics` | GET | Prometheus 指标 |

鉴权：`BERKSHIRE_API_KEYS`（逗号分隔）；限流：`BERKSHIRE_RATE_LIMIT_PER_MIN`。

`/score` 请求体示例：

```json
{
  "ticker": "AAPL",
  "date": "2026-01-02",
  "scores": {"duan": 0.8, "buffett": 0.75, "munger": 0.7, "lilu": 0.65},
  "price_anchor": 100.0,
  "realized_price": 110.0
}
```

服务内**不主动拉行情**；调用方先取价再传入。

### 6.1 Docker 部署（可选）

```bash
docker compose up -d --build
# 或本地：pip install -e '.[service]' && berkshire-serve
```

镜像非 root + 内置 `HEALTHCHECK`；环境变量与 §7 存储路径见 `.env.example`。快速 curl：

```bash
curl -s localhost:8000/health
curl -s localhost:8000/doctor
```

---

## 7. 存储路径

| 数据 | 默认路径 | 环境变量 |
|------|----------|----------|
| 决策日志 | `~/.berkshire/decisions.jsonl` | `BERKSHIRE_DECISION_LOG` |
| 经验库 | `~/.berkshire/experiences.jsonl` | `BERKSHIRE_EXPERIENCE_LOG` |
| Run 记录 | `~/.berkshire/runs.jsonl` | `BERKSHIRE_RUN_LOG` |
| 轨迹 | `~/.qwenpaw/berkshire_traces/` | `BERKSHIRE_TRACE_DIR` |
| 价格缓存 | 内存 / 可选磁盘 | `BERKSHIRE_PRICE_CACHE_DIR` |

---

## 8. V10.26–10.28 进化 API 速查

| 版本 | 能力 | 入口 |
|------|------|------|
| V10.26 | `rerun_analysis` | `run_multi_round(..., rerun_analysis=True)`、`cycle --rerun-analysis` |
| V10.27 | 轨迹 A/B | `tools/trajectory_ab_eval.py` |
| V10.28 | 信号→Hypothesis | `run_full_cycle(factor_scan=…, limitup_scan=…)` |
| V10.29 | 多源证据 Brainstorm | `run_full_cycle(use_brainstorm=True)` |
| V10.29 | SkillForge regression gate | `run_evolution_round(regression_cases=…)` |
| V10.29.1 | 投研效果契约 + 后验周报 | `log_decision` / `posterior_weekly`；见 [RESEARCH_EFFECTIVENESS.md](RESEARCH_EFFECTIVENESS.md) |

---

## 9. LLM 与改写

| 变量 | 作用 |
|------|------|
| `BERKSHIRE_LLM_API_KEY` / `OPENAI_API_KEY` | Prompt 改写 |
| `BERKSHIRE_LLM_BASE_URL` | OpenAI 兼容网关 |
| `BERKSHIRE_LLM_MODEL` | 模型名 |

- Option B：`apply_gradient` 经 LLM 改写 prompt
- 验证门控：`validated_apply_gradient`（改写后评分不劣才接受）
- ∇_LLM：`LLMGradientGenerator` 生成批评

无 Key 时离线逻辑仍可用；e2e 见 `tests/e2e/test_llm_smoke.py`。

---

## 10. 测试与验收

```bash
python3 tools/trajectory_ab_eval.py          # V10.27 A/B（bundled fixtures）
python3 -m pytest tests/test_eval_harness_rerun.py tests/test_trajectory_ab.py -v
python3 -m pytest tests/test_v10_unit.py tests/test_v10_integration.py -v
python3 -m pytest tests/test_realized_feedback_loop.py tests/test_pipeline.py -v
python3 -m pytest tests/test_service.py -v    # 需 fastapi
python3 tests/test_v10_backtest.py            # 轨迹诊断（非 pytest）
```

```bash
python3 -m pytest tests/test_skill_forge.py tests/test_skill_forge_llm.py tests/test_skill_forge_cli.py -v
python3 src/evolution_loop_v10.py skill-evolve list
python3 tools/skill_evolve.py judge tests/fixtures/skill_forge/tasks_unlabeled.jsonl --judge-mode rule
python3 tools/skill_evolve.py evolve investment-research --judge-mode auto --dry-run
```

见 [TESTING.md](../TESTING.md) §按功能验收入口。

---

## 相关文档

- [textgrad_design.md](textgrad_design.md) — 设计深度
- [BACKTEST.md](BACKTEST.md) — 回测路线对照
- [USER_GUIDE.md](USER_GUIDE.md) §4 — 快速入口
- [PROMPT_TEMPLATES.md](PROMPT_TEMPLATES.md) — 提示模板

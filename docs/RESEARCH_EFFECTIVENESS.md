# 投研效果契约与后验 KPI

> **版本**：V10.29.1 起契约落地（当前包 `10.29.2`）  
> 把「写得好」变成「可证伪的对错」。  
> 导航：[docs/README.md](README.md) | 引擎：[ENGINE.md](ENGINE.md) | 使用：[USER_GUIDE.md](USER_GUIDE.md) §4.4

---

## 1. 为什么需要这一层

四大师报告、TextGrad、SkillForge 默认优化的是**过程与文案**。  
投研效果层强制：

1. 每次正式研究落一条 **`DecisionRecord`**
2. 到 `horizon_days` 后算 **方向命中 / 校准误差**
3. 经验库被测试污染时 **可归档清空**，避免假 alpha 绑架校准

---

## 2. 决策契约（最小字段）

| 字段 | 必填 | 说明 |
|------|:----:|------|
| `ticker` / `date` / `price_anchor` | ✅ | 标的、决策日、锚点价 |
| `scores` | ✅ | 四大师 0~1（或 CLI `--stance` 统一） |
| `thesis` | ✅ | 一句话逻辑 |
| `kill_condition` | ✅ | 论点失效条件 |
| `action` | ✅ | `buy`/`add`/`hold`/`reduce`/`exit`/`watch` |
| `horizon_days` | ✅ | 后验日历日窗口（默认 20） |
| `depth` / `skill` | 建议 | lite/standard/deep；来源技能名 |

缺 `thesis` / `kill_condition` / `action` / `horizon_days` → `is_research_complete=False`。

路径：`BERKSHIRE_DECISION_LOG`（默认 `~/.berkshire/decisions.jsonl`）。

---

## 3. 工具与命令

```bash
# 落盘
python3 tools/log_decision.py append \
  --ticker NVDA --date 2026-07-06 --price 198 --stance 0.88 \
  --thesis "CUDA 护城河" --kill "份额下滑" --action hold --horizon 20

python3 tools/log_decision.py list
python3 tools/log_decision.py gaps          # 有缺口则 exit 1

# 持仓种子（与 thesis-tracker 对齐）
python3 tools/seed_portfolio_decisions.py --from-json data/portfolio_decision_seeds.json

# 后验周报（离线 price map 键 = TICKER|到期日）
python3 tools/posterior_weekly.py report --as-of 2026-07-26 \
  --prices '{"NVDA|2026-07-26":205}' --json

python3 tools/posterior_weekly.py report --network   # 可选真实行情

# 经验库污染清理
python3 tools/archive_experiences.py --dry-run
python3 tools/archive_experiences.py --reset --reason "test pollution"
```

| 模块 | 路径 |
|------|------|
| 记录模型 | `src/decision_log.py` |
| 后验聚合 | `src/posterior_report.py` |
| CLI | `tools/log_decision.py`、`posterior_weekly.py`、`seed_portfolio_decisions.py`、`archive_experiences.py` |
| 种子数据 | `data/portfolio_decision_seeds.json` |
| 技能收尾 | `skills/investment-research.md`、`docs/action-card.md` |

---

## 4. KPI 定义

| KPI | 定义 |
|-----|------|
| **契约完整率** | `is_research_complete` 条数 / 总决策 |
| **方向命中率** | stance≥0.6 且 ret>0，或 stance≤0.4 且 ret<0；中性区不计入分母 |
| **平均\|校准误差\|** | mean(\|mean_stance − realized_base\|) |
| **到期缺价数** | 已到期但无法取价的条数 |

`realized_base` 公式见 [ENGINE.md](ENGINE.md) / `realized_feedback.py`（默认 SENSITIVITY=0.5，可用环境变量覆盖）。

---

## 5. 推荐工作流

```text
研究 (investment-research)
  → financial_rigor + report_audit
  → 行动卡
  → log_decision.py append          ← 契约硬门
  → thesis-tracker / state 更新
  → （horizon 后）posterior_weekly
  → 只对「高 conviction + 负 alpha」做 SkillForge
```

**禁止**：用重复测试 experiences（同一 ticker、同一 alpha）宣称投资能力提升。

---

## 6. 验收与 E2E

```bash
# 单元 + CLI
pytest tests/test_posterior_report.py -v

# 离线 E2E（CI 默认跑，无网络）
pytest tests/e2e/test_research_effectiveness_e2e.py -v

# 手工冒烟
python3 tools/log_decision.py gaps
python3 tools/posterior_weekly.py report --as-of $(date +%F) \
  --prices '{"AAPL|2026-01-21":110}'
```

| 测试文件 | 覆盖 |
|----------|------|
| `tests/test_posterior_report.py` | 契约字段、命中规则、CLI 单测 |
| `tests/e2e/test_research_effectiveness_e2e.py` | 子进程全链路 + API 反馈闭环 |

真实 LLM E2E 仍见 `tests/e2e/test_llm_smoke.py`（需 API Key，默认 skip）。

---

## 7. 与回测 / 引擎的边界

| 能力 | 文档 |
|------|------|
| 单笔决策收益反馈 TextGrad | [ENGINE.md](ENGINE.md)、[BACKTEST.md](BACKTEST.md) §5 |
| 组合级净值 / IR（可选扩展） | `tools/perf_metrics.py`、[qlib_evaluation.md](qlib_evaluation.md) |
| **研究是否完整 + 方向是否对** | **本文** |

因子 OOS、动量回测 **不替代** 本层的「研报决策后验」。

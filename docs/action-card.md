# 结构化行动卡（Action Card）

借鉴 [ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) 的 Portfolio Manager 输出形态，但**保持 berkshire-ai 的研报导向**：给出可执行、可回看的结论，而非自动交易指令。

所有深度研报（`investment-research`、`investment-team`）与组合审视（`portfolio-review`）在正文末尾**必须**附上本行动卡。

**投研效果契约**：行动卡写完后，必须用 `tools/log_decision.py append` 落一条 `DecisionRecord`（`thesis` / `kill_condition` / `action` / `horizon_days` / 四大师 `scores`）。无落盘记录的报告视为未完成。后验周报：`./scripts/weekly-posterior.sh` 或 `tools/posterior_weekly.py report --network`。

字段映射建议：

| 行动卡 | DecisionRecord |
|--------|----------------|
| 综合立场 / 多空净判断 | `scores` 或 `--stance`（**须与 action 带宽一致**，见下表） |
| 操作建议 | `action`：新建仓→`buy`，加仓→`add`，持有→`hold`，减仓→`reduce`，清仓→`exit`，仅观察→`watch` |
| 论点失效条件 | `kill_condition` |
| 看多逻辑第 1 条（压缩） | `thesis` |
| 持有期限 | `horizon_days`（事件驱动可 20；1–3 年可 60–90 仅作后验窗，非持有上限） |
| 基准（建议） | `benchmark` + `benchmark_anchor`（美 `SPY`，A `000300`，港 `HSI`） |

### action ↔ mean_stance 带宽（硬门）

`mean_stance = mean(scores)`。不一致则 `is_research_complete=False`，`gaps` 含 `action_stance:*`。

| action | mean_stance |
|--------|-------------|
| `buy` / `add` | ≥ 0.70 |
| `hold` | ≤ 0.80 |
| `reduce` / `exit` | ≤ 0.55 |
| `watch` | ∈ [0.45, 0.75] |

`python3 tools/log_decision.py bands` 打印完整表。生产落盘建议 `--strict`。

---

## 模板（复制到报告末尾）

```markdown
## 行动卡（Action Card）

| 字段 | 内容 |
|------|------|
| **标的** | {代码} {公司名} |
| **信息丰富度** | A / B / C |
| **综合立场** | 强烈看好 / 看好 / 中性 / 谨慎 / 回避 |
| **多空净判断** | bullish / bearish / neutral（可由 `BerkshireGraph.debate()` 的 `net_stance`/`net_score` 佐证，中性区 \|net\|<0.15） |
| **操作建议** | 新建仓 / 加仓 / 持有 / 减仓 / 清仓 / 仅观察 |
| **建议仓位区间** | 新建仓：0–3% / 3–5% / 5–8%（或「不加仓，维持 X%」） |
| **目标价区间** | {悲观} – {中性} – {乐观}（币种） |
| **持有期限** | 3年+ / 1–3年 / 事件驱动（说明事件） |
| **置信度** | 高 / 中 / 低（区分 AI 分析置信度 vs 投资确定性） |

### 看多逻辑（≤3 条）
1. 
2. 
3. 

### 看空逻辑（≤3 条）
1. 
2. 
3. 

### 关键风险（Top 3）
1. 
2. 
3. 

### 催化剂
- **加仓信号**：
- **减仓/卖出信号**：

### 论点失效条件（若出现则重新审视）
- 

### 下次审视
- 日期或事件：{财报日 / 政策节点 / 季度组合回顾}

### 组合 risk_flags（若已运行 portfolio_risk / portfolio_scan --holdings）
- {severity} {code}: {message}
- （无则写「未检查」或「通过」）
```

---

## 立场与仓位对照（参考）

与 `stock_screener` 信号分级对齐，供扫描工具与人工结论互证：

| 扫描信号 | 典型立场 | 新建仓参考上限 |
|----------|----------|----------------|
| `BUY_8%` | 强烈看好 | 8% |
| `BUY_5%` | 看好 | 5% |
| `BUY_3%` | 试探 | 3% |
| `WATCH` | 仅观察 | 0%（需补基本面） |
| `PASS` / `SKIP` | 回避或无关 | 0% |

**注意**：仓位是上限参考，须结合 `portfolio-review` 的组合集中度、相关性与机会成本再定最终比例。

---

## 组合层面（portfolio-review 专用）

在单标的行动卡之外，组合报告末尾追加：

```markdown
## 组合行动摘要

| 动作 | 标的 | 当前占比 | 建议占比 | 理由 |
|------|------|:-------:|:-------:|------|
| 加仓 | | | | |
| 减仓 | | | | |
| 清仓 | | | | |
| 新建仓 | | | | |

**组合健康度**：优秀 / 良好 / 需调整 / 问题严重  
**当前最应做的一件事**：  
**最大组合风险**：
```

---

## 工具联动

- 扫描 watchlist 生成信号草案：`python3 tools/portfolio_scan.py --json`
- 组合风险检查：`python3 tools/portfolio_risk.py --holdings '{"NVDA":25,"CASH":15}' --json`
- 扫描 + 风险一并输出：`python3 tools/portfolio_scan.py --json --holdings '{"NVDA":25,"CASH":15}'`
- 研究队列同步：`python3 tools/thesis_queue.py --json`（或 `--run-scan` 联网合并扫描）
- A股数据（多源降级，全失败不抛崩）：`python3 tools/data_sources.py daily <code>`
- 行动卡 / 组合周报多通道交付：`python3 tools/notify.py send --title "..." --file reports/x.md`（Telegram/飞书/本地兜底，零配置只落地）
- 多空净判断佐证：`BerkshireGraph().debate({"duan":..,"buffett":..,"munger":..,"lilu":..})` → `net_stance`
- 单标的深度研究后，用行动卡固化结论；扫描信号仅作**候选池**，不可替代研报与 `report_audit` 准出。

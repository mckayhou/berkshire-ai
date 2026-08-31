---
name: berkshire-capital-flow
description: |
  A 股资金行为快照：股东户数、融资融券、大宗、龙虎榜、机构持仓、北向。
  调用 tools/capital_flow.py；缺失模块如实标记，禁止伪装。
version: 10.29.3
---

# 资金行为：筹码与杠杆快照（A 股）

对 $ARGUMENTS（A 股代码，如 `600519`）跑资金行为六模块。

这是 **Deep Research / Thesis Tracker / news-pulse 的输入**，不是下单信号，也不是 PDF 产品里的 Streamlit 看板或流向预测模型。

## 何时用

- 用户问「谁在买」「筹码集中了没」「北向/融资/龙虎榜」
- `investment-research` 做到市场/资金面，或 thesis 红线涉及筹码/杠杆
- `news-pulse` 任务 4 需要机构/大宗/融资异常的**数字**而不是印象

非 A 股：本工具不适用。美股用 13F，港股用港股通公开数据，不要拿本 CLI 硬套。

## 执行

```bash
python3 tools/capital_flow.py score {代码} --json
# 单模块
python3 tools/capital_flow.py holders {代码} --json
python3 tools/capital_flow.py margin {代码} --json
python3 tools/capital_flow.py block {代码} --json
python3 tools/capital_flow.py lhb {代码} --json
python3 tools/capital_flow.py inst {代码} --json
python3 tools/capital_flow.py north {代码} --json
```

数据源：东方财富公开 datacenter（curl，零依赖）。某模块空数据或 HTTP 失败 → `ok: false` + `reason`，**不得用 LLM 知识填数字**。

## 怎么读分数

综合分 = 成功模块的算术平均（0–100）。**机构**口径是东财「前十大股东合计占比」，不是基金持仓明细；北向若只有一期则标记缺失、不编变动。

| 分 | 信号 |
|----|------|
| ≥65 | 偏多（集中 / 杠杆升温 / 机构或北向加仓） |
| 36–64 | 中性 |
| ≤35 | 偏空 |

旗标（如「筹码快速集中」「游资主导买入」）必须原文抄进报告「资金面」小节，并标明 as_of 日期。

## 写入研报的纪律

1. 列出 **n_modules / 6**，缺失模块写「未取到」，不要补故事。
2. 资金面不能替代生意质量与估值；`financial_rigor` / `terminal_value` / `report_audit` 仍按 Deep Research 准出。
3. 若资金面与论文冲突（例如 thesis 看多但北向+机构同时减持），在 Thesis Tracker 红线里记一条，**不要自动改 action**。
4. 落盘：不单独为资金行为建 DecisionRecord；跟主研究一次 `log_decision`。

## 完成后检查

- [ ] `score --json` 跑过，或每个失败模块有 reason
- [ ] 报告写了综合分、信号、旗标、日期
- [ ] 未把「偏多」写成买入建议

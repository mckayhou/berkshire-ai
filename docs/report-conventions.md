# 报告输出规范（report conventions）

> 本文件移植自 upstream 的 `CLAUDE.md` 报告方法论，适配本 fork（OpenClaw/QwenPaw）。
> 所有 Skill（investment-research / investment-team / earnings-review 等）输出报告时都应遵循此规范。

## 报告目录结构

所有报告按**公司名**建文件夹，公司相关的所有报告放在对应文件夹内；行业/主题/组合类报告放 `reports/` 根目录：

```
reports/
├── AI产业研究/                 — AI产业链全景研究（置顶）
│   ├── AI五层蛋糕-产业全景研究-YYYYMMDD.md
│   └── AI五层蛋糕-公众号-YYYYMMDD.md
├── 腾讯/                       — 腾讯所有研究报告
│   ├── 腾讯-research-YYYYMMDD.md
│   ├── 腾讯-earnings-2025Q4.md
│   ├── 腾讯-management-YYYYMMDD.md
│   └── 腾讯-thesis.md
├── 核电-industry-YYYYMMDD.md   — 行业报告放根目录
├── AI算力-funnel-YYYYMMDD.md    — 漏斗筛选报告放根目录
├── AI-轮动判断-YYYYMMDD.md      — 主题级综合判断报告放根目录
├── portfolio-latest.md         — 组合报告放根目录（持续更新）
└── 多公司对比-checklist-YYYYMMDD.md — 多公司报告放根目录
```

## 报告命名规范

| Skill | 文件命名格式 | 示例 |
|------|---------|------|
| investment-team | `{公司名}/` 目录内含4个视角+最终报告 | `reports/拼多多/最终报告.md` |
| investment-research | `{公司名}-research-{YYYYMMDD}.md` | `reports/腾讯/腾讯-research-20260408.md` |
| investment-checklist | `{公司名}-checklist-{YYYYMMDD}.md` | `reports/腾讯/腾讯-checklist-20260408.md` |
| industry-research | `{行业名}-industry-{YYYYMMDD}.md`（根目录） | `reports/核电-industry-20260409.md` |
| industry-funnel | `{行业名}-funnel-{YYYYMMDD}.md`（根目录） | `reports/AI算力-funnel-20260509.md` |
| private-company-research | `{公司名}-private-{YYYYMMDD}.md` | `reports/字节跳动/字节跳动-private-20260408.md` |
| earnings-review | `{公司名}-earnings-{期间}.md` | `reports/腾讯/腾讯-earnings-2025Q4.md` |
| earnings-team | `{公司名}/` 目录内含4个大师视角+研究底稿+公众号文章+读者评审 | `reports/腾讯/腾讯-earnings-2025Q4.md`（公众号定稿） |
| thesis-tracker | `{公司名}-thesis.md`（长期维护） | `reports/腾讯/腾讯-thesis.md` |
| portfolio-review | `portfolio-latest.md`（根目录，持续更新） | `reports/portfolio-latest.md` |
| management-deep-dive | `{公司名}-management-{YYYYMMDD}.md` | `reports/腾讯/腾讯-management-20260409.md` |

## investment-team 文件结构

```
reports/{公司名}/
├── README.md                         — 研究框架概览+核心结论
├── 01-商业模式分析-段永平视角.md
├── 02-财务估值分析-巴菲特视角.md
├── 03-行业竞争分析-芒格视角.md
├── 04-风险管理层评估-李录视角.md
└── 最终报告.md                       — Team Lead 综合报告
```

## 投研分析核心原则（最高优先级）

- **客观、客观、客观**——所有投研分析必须基于事实和数据，严禁主观臆断
- 严格区分"事实"与"观点"：事实用数据支撑，观点必须明确标注为"观点"或"推测"
- **不预设立场**：不预设看多或看空，先摆数据、再推逻辑、最后得结论。结论必须从数据中自然推出
- 禁止使用"我认为"、"我觉得"、"显然"等主观表述，改用"数据显示"、"证据表明"、"根据XX来源"
- **呈现正反两面**：每个核心判断都必须附带反面论据（"但另一方面..."），让读者自己权衡
- 对不确定的事情诚实说"不确定"或"数据不足"，不要用推测填充确定性

## 报告语言与风格

- 所有报告使用**中文**
- 风格：直接、犀利、不说废话
- 数据必须标注来源，关键数据至少2个来源交叉验证（参见 `skills/financial-data.md`）
- 估计值必须注明"估计"
- 评分使用★符号（★1-5），不含半星
- 穿插巴菲特/芒格/段永平/李录的语录点评

## 数据严谨性注意事项

- 市值必须用工具校验：`python3 tools/financial_rigor.py verify-market-cap`（独立来源总股本，禁止用"市值/股价"反推自证）
- 货币单位要明确（港币/人民币/美元），防止混淆
- PE/ROE 等指标用 `tools/financial_rigor.py` 精确计算，禁止心算
- 报告写完后用 `tools/report_audit.py` 做 15% 随机抽检准出

## 行动卡（Action Card）

深度研报与组合审视报告**末尾必须**附上结构化行动卡，模板见 [`docs/action-card.md`](action-card.md)：
- 立场、操作建议、建议仓位区间、目标价、风险与催化剂
- 组合报告使用其中的「组合行动摘要」专节

扫描工具 `portfolio_scan.py` 可生成候选信号草案，但不能替代行动卡与 `report_audit` 准出。

# Agent 技能目录（SKILLS）

> `skills/` 下 18 个独立 Agent 指令 + **AnySearch 检索 skill**，可直接作为 OpenClaw `SKILL.md` 使用。  
> Meta-skill 总入口：[config/skill.md](../config/skill.md) | 导航：[docs/README.md](README.md)

---

## 安装到 OpenClaw / QwenPaw

```bash
./update-platforms.sh
```

手动：
- 单文件：复制 `skills/xxx.md` → `~/.openclaw/workspace/skills/berkshire-xxx/SKILL.md`
- 目录 skill：同步 `skills/anysearch/` 整目录（含 `SKILL.md` + `scripts/`；**勿提交** `.env`）

---

## 技能一览

| 技能文件 | 用途 | 典型触发语 |
|----------|------|------------|
| [anysearch-web.md](../skills/anysearch-web.md) + [anysearch/](../skills/anysearch/) | **实时检索**（AnySearch；Tavily 补充） | 「搜一下腾讯 PE」「anysearch」 |
| [investment-research.md](../skills/investment-research.md) | **单标的**四大师深度研究 | 「对腾讯做四大师投资研究」 |
| [investment-team.md](../skills/investment-team.md) | **多 Agent 并行**团队研究 | 「investment-team 研究 NVDA」 |
| [investment-checklist.md](../skills/investment-checklist.md) | 研究检查清单 | 「按 checklist 检查这篇研报」 |
| [financial-data.md](../skills/financial-data.md) | **数据源规范**（各技能必须引用） | 「这个数据从哪来」 |
| [thesis-tracker.md](../skills/thesis-tracker.md) | 论文状态跟踪 / TRIGGERED；**须 log_decision 落盘** | 「更新 thesis 状态」 |
| [portfolio-review.md](../skills/portfolio-review.md) | 组合审视 | 「portfolio review」 |
| [earnings-review.md](../skills/earnings-review.md) | 单公司财报季分析 | 「Q4 earnings review」 |
| [earnings-team.md](../skills/earnings-team.md) | 财报季多 Agent 团队 | 「earnings-team」 |
| [news-pulse.md](../skills/news-pulse.md) | 新闻脉冲 / 事件驱动 | 「news pulse」 |
| [industry-research.md](../skills/industry-research.md) | 行业深度 | 「半导体行业研究」 |
| [industry-funnel.md](../skills/industry-funnel.md) | 行业漏斗筛选 | 「industry funnel」 |
| [quality-screen.md](../skills/quality-screen.md) | 质量因子筛选 | 「quality screen」 |
| [bottleneck-hunter.md](../skills/bottleneck-hunter.md) | 产业链瓶颈 | 「bottleneck hunter」 |
| [management-deep-dive.md](../skills/management-deep-dive.md) | 管理层深度 | 「管理层尽调」 |
| [private-company-research.md](../skills/private-company-research.md) | 非上市公司 | 「private company」 |
| [deep-company-series.md](../skills/deep-company-series.md) | 系列深度报告 | 「deep company series」 |
| [wechat-article.md](../skills/wechat-article.md) | 微信文章分析 | 「分析这篇公众号」 |
| [dyp-ask.md](../skills/dyp-ask.md) | 段永平式提问 | 「dyp ask」 |

---

## 技能 ↔ 工具映射

研究类技能执行时，Agent 应调用 `tools/`（见 [USER_GUIDE.md](USER_GUIDE.md)）：

| 阶段 | 推荐工具 |
|------|----------|
| 数据获取 | `anysearch-web` / `skills/anysearch/`（AnySearch Skill）, `data_sources.py`, `ashare_data.py`, `src/tavily_search.py`（Tavily+AnySearch hybrid） |
| 数字验证 | `financial_rigor.py`（**必须**） |
| **研究收尾落盘** | `log_decision.py append`（**必须**；`--strict` 校验 action↔stance） |
| action↔stance 带宽 | `log_decision.py bands` / `gaps` |
| 后验周报 | `posterior_weekly.py report` 或 `./scripts/weekly-posterior.sh` |
| 到期反馈→经验 | `feedback_due_decisions.py`（或 weekly-posterior `--feedback-apply`） |
| 历史 stance 修复 | `repair_decision_stances.py` |
| 报告准出 | `report_audit.py` |
| 组合上下文 | `portfolio_scan.py`, `portfolio_risk.py` |
| A 股候选 | `factor_screener_bridge`, `limitup_screener_bridge` |
| 待办同步 | `thesis_queue.py` |
| 交付 | `notify.py`, `report_html.py` |

---

## 四大师并行结构

`investment-team` / `earnings-team` / `news-pulse` 保留 **team-lead + 4 专业子 Agent**：

| 大师 | 视角 |
|------|------|
| 段永平 | 生意本质 |
| 巴菲特 | 护城河与估值 |
| 芒格 | 逆向与风险 |
| 李录 | 文明与趋势 |

OpenClaw：`sessions_spawn`；QwenPaw：loop_engine 并行角色。  
降级：多会话顺序模拟。

---

## 与量化栈的关系

| 技能域 | 量化工具 |
|--------|----------|
| 定性投研 | 四大师 + TextGrad（主链路） |
| A 股量化候选 | [QUANT.md](QUANT.md) 筛选桥 → `thesis_queue` |
| 策略回测 | [BACKTEST.md](BACKTEST.md)（非技能内置） |

技能**不替代** `financial_rigor` 与 `report_audit`。

**技能进化（SkillForge）**：[SKILL_EVOLUTION.md](SKILL_EVOLUTION.md) — 从 bad-case / audit 打回驱动 `skills/*.md` 版本化迭代。

---

## 报告规范

- 目录与命名：[report-conventions.md](report-conventions.md)
- 行动卡：[action-card.md](action-card.md)
- 提示模板：[PROMPT_TEMPLATES.md](PROMPT_TEMPLATES.md)

---

## 相关文档

- [config/skill.md](../config/skill.md) — V10 meta-skill 变更史
- [USER_GUIDE.md](USER_GUIDE.md) §12 — Agent 使用
- [ENGINE.md](ENGINE.md) — 进化引擎

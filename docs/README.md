# Berkshire AI 文档中心

> 从这里开始。按你的角色选一条路径，避免在 README / USER_GUIDE / 设计文档之间来回跳。

---

## 我该读哪份？

| 你想… | 读这份 | 预计时间 |
|--------|--------|----------|
| **第一次上手、跑通一条链路** | [USER_GUIDE.md](USER_GUIDE.md) §1–§2 | 15 min |
| **查某个工具的命令** | [tools/README.md](../tools/README.md) | 按需 |
| **做回测（因子/OOS/动量/引擎）** | [BACKTEST.md](BACKTEST.md) | 10 min |
| **A 股量化全流程** | [QUANT.md](QUANT.md) | 20 min |
| **TextGrad 引擎 / API / 服务** | [ENGINE.md](ENGINE.md) | 20 min |
| **跑测试、CI、冒烟** | [TESTING.md](../TESTING.md) | 10 min |
| **选 Agent 技能** | [SKILLS.md](SKILLS.md) | 5 min |
| **写研究报告** | [report-conventions.md](report-conventions.md) + [action-card.md](action-card.md) | 10 min |
| **理解架构与设计** | [textgrad_design.md](textgrad_design.md) | 30 min |

---

## 文档地图

```text
docs/README.md          ← 你在这里（导航）
├── USER_GUIDE.md       全功能使用（工作流导向）
├── BACKTEST.md         回测专题（5 条路线对照）
├── QUANT.md            A 股量化专题
├── ENGINE.md           TextGrad 引擎专题
├── SKILLS.md           18 个 Agent 技能目录
├── quant_data_fusion.md  三库融合与数据边界
├── textgrad_design.md    引擎设计（深度）
├── action-card.md        组合行动卡模板
├── report-conventions.md 报告规范
├── ROADMAP.md            路线图
└── tdx_mcp_tool_design.md 通达信 MCP（不实施，备忘）

仓库根目录
├── README.md           项目总览
├── TESTING.md          测试与验收
├── tools/README.md     工具 CLI 逐项说明
├── config/skill.md     Meta-skill（Agent 总入口）
└── VERSION_HISTORY.md  版本历史
```

---

## 按场景的快速路径

### 场景 A：A 股因子研究（macOS，无 Windows）

```text
1. QUANT.md §数据准备
2. pip install -e '.[factor-mining]'
3. ashare_factor_mining train → oos
4. factor_screener_bridge → thesis_queue
5. BACKTEST.md §1 解读 OOS 报告
```

### 场景 B：四大师投研 + 报告准出

```text
1. SKILLS.md → investment-research
2. USER_GUIDE.md §9 financial_rigor + report_audit
3. report-conventions.md
4. notify.py 交付
```

### 场景 C：组合审视与待办

```text
1. portfolio_scan → action-card.md
2. portfolio_risk
3. thesis_queue（可合并 factor/limitup 扫描）
4. thesis-tracker skill
```

### 场景 D：引擎自进化

```text
1. ENGINE.md
2. evolution_loop_v10.py status / cycle
3. TESTING.md §引擎验收
4. textgrad_design.md（深入）
```

---

## 功能 ↔ 文档对照（完整）

| 功能域 | 使用文档 | 测试文档 | 设计/边界 |
|--------|----------|----------|-----------|
| 金融严谨性 | USER_GUIDE §9, tools/README | TESTING §test_tools_financial_rigor | — |
| 报告质检 | USER_GUIDE §9 | TESTING §test_tools_report_audit | report-conventions |
| A 股数据 | USER_GUIDE §5, QUANT §1 | test_tools_data_sources | quant_data_fusion |
| 因子挖掘 | QUANT §2, BACKTEST §1 | test_ashare_alphagpt | quant_data_fusion |
| 打板评分 | QUANT §3 | test_limitup_scoring | tdx_mcp（不实施） |
| CSV 动量筛选 | QUANT §4 | test_quant_data_fusion | quant_data_fusion |
| 研究队列 | USER_GUIDE §8 | test_tools_thesis_queue | — |
| 组合扫描/风险 | USER_GUIDE §7 | test_tools_portfolio_* | action-card |
| 美股动量回测 | BACKTEST §3 | 手工冒烟 | — |
| TextGrad 引擎 | ENGINE.md | test_v10_*, test_pipeline | textgrad_design |
| 收益反馈/绩效 | ENGINE §4, BACKTEST §5 | test_realized_feedback_loop | textgrad_design |
| 引擎轨迹回测 | BACKTEST §4 | test_v10_backtest | — |
| HTTP 服务 | ENGINE §6 | test_service | — |
| 推送 | USER_GUIDE §11 | test_tools_notify | — |
| Agent 技能 | SKILLS.md | — | config/skill.md |
| 外部 quant skills | QUANT §6 | — | quant_data_fusion §7 |

---

## 维护约定

- **USER_GUIDE**：工作流与入口命令；细节下沉到专题文档。
- **tools/README**：每个 CLI 的参数与示例（与代码同步）。
- **专题文档**（BACKTEST / QUANT / ENGINE）：深度说明，避免 USER_GUIDE 过长。
- 改 Python 工具后：更新 tools/README + 相关专题 + `graphify update .`。

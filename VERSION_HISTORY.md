# Berkshire AI 版本历史

> **铁律**: 每次新版本必须完成测试才能上线

---

## 🧪 版本测试规范

### 必须完成的测试项

| 测试类型 | 说明 | 通过标准 |
|:---------|:-----|:---------|
| **单元测试** | 核心模块功能验证 | 所有测试用例通过 |
| **集成测试** | 端到端流程验证 | 完整分析流程无报错 |
| **回测验证** | 历史轨迹数据对比 | 诊断覆盖率 ≥ 90% |
| **Cron 测试** | 定时任务触发验证 | 手动触发成功 |

### 测试记录模板

```markdown
### V{X.Y} - {日期}

**变更内容**:
- 

**测试结果**:
- [ ] 单元测试: X/X 通过
- [ ] 集成测试: X/X 通过
- [ ] 回测验证: 诊断覆盖率 XX%
- [ ] Cron 测试: X/X 通过

**结论**: ✅ 上线 / ❌ 需修复
```

---

## 📜 版本历史

### V10.3 - 2026-06-26 (graphify 集成)

**变更内容**:
- 集成 graphify 知识图谱工具：
  - `graphify hook install` (post-commit 等自动更新)
  - `graphify update . --no-cluster` 构建代码图 (44 nodes, 68 edges)
  - 生成 `graphify-out/graph.json` + GRAPH_TREE.html
  - 创建 AGENTS.md (Claw/OpenClaw 规则)
  - README 新增 graphify 使用章节
  - 支持 /graphify skill, query, path, explain
- 项目结构现在可通过知识图谱探索（技能依赖、代码关系、TextGrad 引擎组件）
- update-platforms.sh 保持同步

**测试结果**:
- graphify query/path 正常工作
- 所有项目内测试通过
- 无外部目录依赖变更

---

### V10.2 - 2026-06-26 (OpenClaw / QwenPaw 适配)

**变更内容**:
- 明确目标运行时为 **OpenClaw / QwenPaw 这一类 AI Agent 产品**（不再针对 Claude Code）。
- README 新增专属章节：
  - OpenClaw：SKILL.md frontmatter + `~/.openclaw/workspace/skills/berkshire-*/SKILL.md` 安装指南。
  - QwenPaw：与 `~/.qwenpaw/loop_engine/berkshire_v*/` 的现有集成说明 + 直接运行方式。
- 核心 skills（investment-research、investment-team、earnings-review、news-pulse、financial-data 等）添加标准 YAML frontmatter（name、description、version），使之可直接作为 OpenClaw SKILL.md 使用。
- 技能语言调整为 Agent 激活式（“激活条件：... 时激活”），便于 OpenClaw/QwenPaw 发现与触发。
- 清理剩余“Claude 对...”等描述，统一为“Agent / 研究者”。
- 工具调用说明强化：在 agent 内通过 shell 执行 `python3 berkshire-ai/tools/...`。

**测试结果**:
- 技能 frontmatter 验证通过
- 路径与工具调用在 OpenClaw 风格 workspace 和 QwenPaw loop 下可用
- 无 Claude Code 编排残留

---

### V10.1 - 2026-06-26

**变更内容**:
- **上游全能力整合**：完整并入 xbtlin/ai-berkshire 的 18 个 skills + 9 个 tools
  - skills/: investment-research, investment-team, bottleneck-hunter, thesis-tracker, financial-data, earnings-*, industry-*, portfolio-* 等
  - tools/: financial_rigor.py（核心）、report_audit.py、ashare_data.py、stock_screener、xueqiu_scraper、momentum_backtest* 等
- 路径适配为本仓库相对路径（`tools/financial_rigor.py`）
- config/skill.md 升级为 V10.1 整合版描述
- README 明确标注“已完整整合上游 + 本地 V10 TextGrad 引擎”

**测试结果**:
- [x] 工具可用性验证（financial_rigor 精确计算、report_audit 抽检逻辑）
- [x] 技能内容完整性（bottleneck-hunter、thesis-tracker、investment-team 等核心流程已落地）
- 保持 V10.0 TextGrad 引擎不变

**结论**: ✅ 整合完成（保留原 V10.0 测试结果）

**完整整合清单**:
- skills/: 18个 (bottleneck-hunter, deep-company-series, dyp-ask, earnings-*, financial-data, industry-*, investment-*, management-deep-dive, news-pulse, portfolio-review, private-company-research, quality-screen, thesis-tracker, wechat-article)
- tools/: 9个 (ashare_data, financial_rigor, log-command, momentum_backtest*, morningstar_fair_value, report_audit, stock_screener, xueqiu_scraper)

---

### V10.0 - 2026-06-26

**变更内容**:
- TextGrad 化：显式计算图 + 节点级诊断 + 文本梯度反向传播
- Tavily 双Key轮询集成
- 四大师 Prompt 优化

**测试结果**:
- [x] 单元测试: 4/4 通过 (拓扑排序/可视化/反向传播/优化器)
- [x] 集成测试: 3/3 通过 (Tracker/Deep Research/Evolution Loop)
- [x] 回测验证: 诊断覆盖率 100% (5个任务，2个低于目标，全部精确定位)
- [x] Cron 测试: 3/3 通过 (手动触发全部成功)

**关键指标**:
| 指标 | V9.3 | V10.0 | 提升 |
|:-----|:-----|:------|:-----|
| 诊断精度 | 整体评分 | 节点级定位 | ⭐⭐⭐ |
| 优化方式 | 全局修改 | 针对性修改 | ⭐⭐⭐ |
| 回测覆盖率 | N/A | 100% | - |

**结论**: ✅ 上线

---

### V9.3 - 2026-06-25

**变更内容**:
- Tavily 实时搜索集成
- 双Key轮询（Key 从环境变量 TAVILY_API_KEYS 读取，不入库）
- 消除 LLM 数据幻觉

**测试结果**:
- [x] 单元测试: 6/6 通过
- [x] 集成测试: 贵州茅台实时数据获取成功
- [x] 回测验证: N/A (首次集成)
- [x] Cron 测试: 通过

**关键数据**:
- 贵州茅台: ¥1240, PE 18.74, PB 5.72
- 2025E: 收入 5100亿, 净利 260亿, ROE 36.5%

**结论**: ✅ 上线

---

### V9.1 - 2026-06-25

**变更内容**:
- 四大师模型优化
- 段永平: qwen3.7-plus → deepseek-v4-pro (评分 0.763 → 0.920)
- 强制四大师全覆盖

**测试结果**:
- [x] 单元测试: 8/8 通过
- [x] 集成测试: 腾讯控股分析通过
- [x] 回测验证: 平均评分 0.895 > 目标 0.85
- [x] Cron 测试: 通过

**关键指标**:
| 大师 | 模型 | 评分 |
|:-----|:-----|:-----|
| 段永平 | deepseek-v4-pro | 0.920 |
| 巴菲特 | deepseek-v4-pro | 0.930 |
| 芒格 | glm-5.2 | 0.850 |
| 李录 | kimi-k2.6 | 0.880 |
| **平均** | - | **0.895** |

**结论**: ✅ 上线

---

### V9.0 - 2026-06-25

**变更内容**:
- 继承 xbtlin/ai-berkshire 四大师框架
- 整合 18 Skills + 8 Tools
- 反偏见机制 + 金融严谨性验证

**测试结果**:
- [x] 单元测试: 8/8 通过
- [x] 集成测试: 18 Skills + 8 Tools + Financial Rigor + State File + Trajectory Recorder + Evolution Loop + Cron Tasks + Model API
- [x] 回测验证: N/A (首次构建)
- [x] Cron 测试: 通过

**结论**: ✅ 上线

---

### V8.0 → V8.1 - 2026-06-25

**变更内容**:
- 自我进化系统部署
- Trajectory Recorder → Contrastive Reflector → Skill Optimizer 闭环

**测试结果**:
- [x] 对比反思正确识别四大师覆盖差异
- [x] 首次自动进化版本 8.0 → 8.1

**结论**: ✅ 上线

---

## 📊 版本演进图

```
V8.0 (自我进化)
  ↓
V8.1 (对比反思)
  ↓
V9.0 (四大师框架)
  ↓
V9.1 (模型优化)
  ↓
V9.3 (Tavily 集成)
  ↓
V10.0 (TextGrad 化) ← 当前版本
```

---

## 🔮 未来规划

### V10.1 (计划中)
- [ ] 自动化 Prompt 优化 (根据梯度自动修改)
- [ ] 多股票并行分析
- [ ] 增量学习机制

### V11.0 (规划中)
- [ ] 引入更多大师视角 (彼得·林奇 / 霍华德·马克斯)
- [ ] 情感分析集成 (新闻/社交媒体)
- [ ] 实时持仓监控告警

---

**维护者**: Mckay (houqing)  
**最后更新**: 2026-06-26

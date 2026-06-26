# Berkshire AI - 四大师并行投研系统（已完整整合上游）

> **完整整合自** [xbtlin/ai-berkshire](https://github.com/xbtlin/ai-berkshire)（原始四大师框架 + 18 Skills + 9 Tools + 反偏见 + 金融严谨性 + 大量实战报告）
> 
> 叠加本地 **V10 TextGrad 自进化引擎**（显式计算图 + 节点级文本梯度反向传播 + 针对性优化）

**当前状态**：上游全能力 + V10 引擎已并入本仓库。**V10.2 重点适配 OpenClaw / QwenPaw 风格 Agent 运行时**。

**重要**：用户明确说明 **不在 Claude Code 中使用**，而是在 **OpenClaw / QwenPaw 这一类 AI Agent 产品/运行时**中使用。

- **多 Agent 并行运行方式完整保留并适配**：investment-team、news-pulse、earnings-team 等技能里的“team-lead + 4 个专业子 Agent 并发研究”结构完整保留（这是上游四大师并行的核心价值）。只是把 Claude Code 的 TeamCreate/TaskCreate/SendMessage 等语法，换成了：
  - OpenClaw：sessions_spawn、ACP 子代理、ACP 消息 / sessions_send 通信。
  - QwenPaw：loop_engine 的并行角色实例或 harness 多 agent 调度。
  - 降级方案：当平台不支持轻松 spawn 并行子 agent 时，用手动多个会话或强模型顺序模拟。
- **OpenClaw**：将 skills 作为标准 `SKILL.md` 安装到 agent workspace（支持 frontmatter + 详细行为指令 + 如何 spawn 子 agent）。
- **QwenPaw**：作为 loop_engine 的一部分运行（berkshire-ai 的 evolution_loop_v10 直接集成在 `~/.qwenpaw/loop_engine/` 下）。
- 所有 skills 已清理为**独立可移植的 Agent 指令模板**（无 Claude Code Team/Task 编排），但**多 agent 团队运行的流程和价值保留**。

## 🎯 核心理念

**四大师并行视角**:
- **段永平**: 生意本质 (Duan Yongping - Business Essence)
- **巴菲特**: 护城河估值 (Warren Buffett - Moat & Valuation)
- **芒格**: 逆向风险 (Charlie Munger - Inversion & Risk)
- **李录**: 文明趋势 (Li Lu - Civilization Trends)

**TextGrad 自进化**: 借鉴 Nature 2025 论文，实现节点级诊断 + 文本梯度反向传播

## 📊 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Berkshire AI V10.0                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 0: 输入 (ticker, tavily_query, date_anchor)         │
│      ↓                                                      │
│  Layer 1: 数据获取 (Tavily 双Key轮询)                      │
│      ↓                                                      │
│  Layer 2: 四大师分析 (段永平/巴菲特/芒格/李录)             │
│      ↓                                                      │
│  Layer 3: 财务验证 (financial_rigor.py)                    │
│      ↓                                                      │
│  Layer 4: 输出 (final_report)                              │
│                                                             │
│  ← TextGrad 反向传播 (节点级诊断 + 梯度优化)              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始（整合后）

### OpenClaw 中使用（推荐方式）

OpenClaw 技能格式：目录 + `SKILL.md`（带 YAML frontmatter）。

推荐使用项目自带的更新脚本（推荐）：
```bash
cd ~/Documents/Github/berkshire-ai
./update-platforms.sh
```
这会自动把所有 skills 和 tools 同步到 OpenClaw（和 QwenPaw）。

手动方式（一次性）：
```bash
mkdir -p ~/.openclaw/workspace/skills/berkshire-investment-research
cp berkshire-ai/skills/investment-research.md ~/.openclaw/workspace/skills/berkshire-investment-research/SKILL.md
# 同理其他...
```

所有 SKILL.md 顶部已包含兼容 frontmatter（name / description / version 10.2），OpenClaw agent 会自动发现并在匹配场景时激活。

工具调用：技能内会指导 agent 执行 `python3 ~/Documents/Github/berkshire-ai/tools/financial_rigor.py ...`（或使用 update 后 v8 里的相对路径）。

示例触发：对 agent 说“对腾讯做四大师投资研究”或“运行 berkshire investment research on 0700.HK”。

还有一个总入口技能：`berkshire`（激活后可列出所有子技能）。

### QwenPaw 中使用

berkshire-ai 已经深度集成到 QwenPaw：

- 核心 runner：`src/evolution_loop_v10.py` 放在 `~/.qwenpaw/loop_engine/berkshire_v8/`（或当前版本目录）。
- 技能模板作为 prompt 组件被 loop 加载（见 `config/skill.md` 和 loop 内的 PROMPT_TEMPLATES 引用）。
- 状态/轨迹/反射：写入 `~/.qwenpaw/berkshire_state.md`、`~/.qwenpaw/berkshire_traces/` 等。
- 直接运行：
```bash
python3 ~/.qwenpaw/loop_engine/berkshire_v8/evolution_loop_v10.py --ticker 600519 --company 贵州茅台
```

如果要手动加载单个技能提示，可在 QwenPaw 的上下文或 skill_pool 中引用 `berkshire-ai/skills/*.md`。

### 其他环境（通用）

- 直接把 `skills/xxx.md` 内容作为系统提示或 user message 喂给任何支持工具调用的 agent（Grok、Qwen、Claude 等）。
- 结合本地 Python 工具链使用（推荐把 `tools/` 加入 PATH 或在调用前 cd 到 berkshire-ai 目录）。

### 使用 TextGrad V10 进化引擎

```bash
python3 src/evolution_loop_v10.py --ticker 600519 --company 贵州茅台
```

### Agent 内工具调用（OpenClaw / QwenPaw 推荐）

Agent 技能会指导你使用 shell / 集成工具执行：

```bash
# 金融严谨性验证（必须用于任何关键数字）
python3 berkshire-ai/tools/financial_rigor.py verify-market-cap --price 510 --shares 9.11e9 --reported 4.65e12 --currency HKD
python3 berkshire-ai/tools/financial_rigor.py cross-validate --field revenue --values '123.4 123.5' --sources 'macrotrends aastocks'

# 报告 15% 随机抽检 + 准出判决
python3 berkshire-ai/tools/report_audit.py extract --report reports/腾讯-2025Q4.md
python3 berkshire-ai/tools/report_audit.py verdict --results '{...}' --report reports/xxx.md
```

**重要**：在 OpenClaw/QwenPaw 中，确保 berkshire-ai 目录对 agent 可见（workspace 挂载或 git clone），或在 skill 描述中写明绝对路径。

所有工具位于 `./tools/`（Decimal 精确计算、Benford 检验、三情景估值等）。

## 🕸️ Knowledge Graph (graphify)

本项目已集成 [graphify](https://graphify.dev) 用于代码/技能结构理解。

- Hook 已安装 (post-commit 等自动更新)
- Graph: `graphify-out/graph.json`（graphify 对**整个代码库**构建的知识图谱；节点/边数量随代码演进而变化，以 `graphify-out/manifest.json` 实际为准）
- 注意：此处的 graphify 代码图 ≠ TextGrad 引擎的 `BerkshireGraph`（后者是固定的 18 个变量节点 / 5 层投研计算图，见 `src/graph.py`）
- 使用方式（在支持的 AI 助手中）：
  - `/graphify` 激活 skill
  - `graphify query "项目核心组件?"`
  - `graphify path "evolution_loop" "financial_rigor"`
  - `graphify explain "BerkshireGraph"`
  - 更新: `graphify update .` (代码仅, 无 LLM 成本)
- AGENTS.md 中有集成规则。
- 适合探索技能依赖、代码关系、投资框架结构。

安装/更新: `./update-platforms.sh` 会同步 graphify-out (如果需要)。

## 📁 项目结构（已整合上游）

```
berkshire-ai/
├── README.md                    # 本文件（整合说明）
├── VERSION_HISTORY.md
├── src/                         # TextGrad V10 自进化引擎（本地核心）
│   ├── evolution_loop_v10.py
│   └── tavily_search.py
├── skills/                      # ★ 完整上游 18 个技能（已并入，OpenClaw 兼容）
│   ├── investment-research.md   # 带 frontmatter，可直接作为 SKILL.md 使用
│   ├── investment-team.md
│   ├── earnings-review.md
│   ├── news-pulse.md
│   ├── financial-data.md        # 数据源规范（所有技能必须引用）
│   └── ... (其他 13 个)
│   # OpenClaw 安装示例见上方“OpenClaw 中使用”章节
├── tools/                       # ★ 完整上游工具链（已并入）
│   ├── financial_rigor.py       # 精确市值/估值/交叉验证（核心）
│   ├── report_audit.py          # 报告数据抽检（15%）
│   ├── ashare_data.py
│   └── ... (stock_screener, xueqiu_scraper, momentum backtests, etc.)
├── config/
│   ├── skill.md                 # V10.1 整合版 meta-skill
│   └── state.md
├── docs/
│   └── textgrad_design.md
├── graphify-out/                # 知识图谱 (graphify) - 用于项目结构查询、代码/技能关系
├── tests/
└── traces/ / reflections/       # 运行时
```

## 📚 文档导航

| 文档 | 内容 |
|---|---|
| [README_EN.md](README_EN.md) | English version |
| [TESTING.md](TESTING.md) | 测试指南 + 最近一次全量 E2E 报告 |
| [tools/README.md](tools/README.md) | 9 个工具的 CLI 用法目录 |
| [docs/report-conventions.md](docs/report-conventions.md) | 报告目录/命名规范、投研核心原则 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 路线图（含本 fork 实现状态） |
| [docs/textgrad_design.md](docs/textgrad_design.md) | TextGrad V10 引擎设计 |
| [LICENSE](LICENSE) | MIT（fork 自 xbtlin/ai-berkshire，保留原作者版权） |

## 🧪 测试

```bash
pip install -r requirements.txt pytest
python3 -m pytest tests/ -v -rs      # 单元 + 集成（无 key/无网时相关用例自动 skip）
python3 tests/test_v10_backtest.py   # 回测诊断覆盖率
```

完整 E2E 步骤与最近一次结果见 [TESTING.md](TESTING.md)。

## 🔄 版本规范

**铁律**: 每次新版本必须完成以下测试才能上线：

1. **单元测试**: 核心模块功能验证
2. **集成测试**: 端到端流程验证
3. **回测验证**: 历史轨迹数据对比
4. **Cron 测试**: 定时任务触发验证

详见 [VERSION_HISTORY.md](VERSION_HISTORY.md)

## 📊 当前版本

**V10.1** (2026-06-26)
- ✅ TextGrad 化 (节点级诊断 + 梯度反向传播)
- ✅ Tavily 双Key轮询 (2000次/月)
- ✅ 四大师全覆盖 (100%)
- ✅ 回测诊断覆盖率 100%
- ✅ **上游全能力整合**：完整 skills/ (18个) + tools/ (9个) from xbtlin/ai-berkshire 并入 (已规范化路径引用)

## 🔗 相关链接

- 原始框架: [xbtlin/ai-berkshire](https://github.com/xbtlin/ai-berkshire)
- TextGrad 论文: [arXiv:2406.07496](https://arxiv.org/abs/2406.07496)
- QwenPaw: [内部系统]

## 📝 维护者

- Mckay (houqing)
- 最后更新: 2026-06-26 (full upstream skills+tools integrated)

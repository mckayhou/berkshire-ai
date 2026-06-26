# Berkshire AI - 四大师并行投研系统

> 继承自 xbtlin/ai-berkshire，融合 TextGrad 自进化机制

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

## 🚀 快速开始

### 运行投研分析

```bash
# 使用 Deep Research (每周五 18:00 自动执行)
qwenpaw cron run 5bb93208-3036-4ced-922b-961c26ef1566

# 使用 Thesis Tracker (每日 08:30 自动执行)
qwenpaw cron run 03c4ebc8-cb78-4d17-ae49-4138d4b8c389

# 使用 Evolution Loop (每周五 20:00 自动执行)
qwenpaw cron run 99ac7a57-4e3f-4cb2-bace-f0b7cc37c143
```

### 手动执行分析

```bash
# 贵州茅台分析
python3 src/evolution_loop_v10.py --ticker 600519 --company 贵州茅台

# 腾讯控股分析
python3 src/evolution_loop_v10.py --ticker 0700.HK --company 腾讯控股
```

## 📁 项目结构

```
berkshire-ai/
├── README.md                    # 本文件
├── VERSION_HISTORY.md           # 版本历史与测试记录
├── src/                         # 核心代码
│   ├── evolution_loop_v10.py    # V10.0 TextGrad 化引擎
│   ├── tavily_search.py         # Tavily 双Key轮询
│   └── prompt_templates.py      # 四大师 Prompt 模板
├── tests/                       # 测试套件
│   ├── test_v10_e2e.py          # V10.0 端到端测试
│   └── test_backtest.py         # 历史轨迹回测
├── docs/                        # 文档
│   ├── textgrad_design.md       # TextGrad 设计文档
│   └── backtest_reports/        # 回测报告
├── config/                      # 配置
│   ├── skill.md                 # SKILL.md 技能定义
│   └── state.md                 # 状态文件
├── traces/                      # 轨迹记录
└── reflections/                 # 反思报告
```

## 🔄 版本规范

**铁律**: 每次新版本必须完成以下测试才能上线：

1. **单元测试**: 核心模块功能验证
2. **集成测试**: 端到端流程验证
3. **回测验证**: 历史轨迹数据对比
4. **Cron 测试**: 定时任务触发验证

详见 [VERSION_HISTORY.md](VERSION_HISTORY.md)

## 📊 当前版本

**V10.0** (2026-06-26)
- ✅ TextGrad 化 (节点级诊断 + 梯度反向传播)
- ✅ Tavily 双Key轮询 (2000次/月)
- ✅ 四大师全覆盖 (100%)
- ✅ 回测诊断覆盖率 100%

## 🔗 相关链接

- 原始框架: [xbtlin/ai-berkshire](https://github.com/xbtlin/ai-berkshire)
- TextGrad 论文: [arXiv:2406.07496](https://arxiv.org/abs/2406.07496)
- QwenPaw: [内部系统]

## 📝 维护者

- Mckay (houqing)
- 最后更新: 2026-06-26

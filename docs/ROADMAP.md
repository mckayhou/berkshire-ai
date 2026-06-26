# berkshire-ai Roadmap

> 本路线图源自 upstream（xbtlin/ai-berkshire），并标注本 fork（OpenClaw/QwenPaw 适配版）的实现状态。
> 状态图例：✅ 已实现 · 🟡 部分实现 · ⬜ 未开始

## P0：近期（1-2个月）

### A股数据源接入 — ✅ 已实现
- 已通过 `tools/ashare_data.py` 接入腾讯财经 / 东方财富，覆盖 A 股行情、财务、估值、搜索
- 真正的市值/估值校验由 `tools/financial_rigor.py` 完成（独立来源总股本，避免循环论证）
- 现有 Skill 无需改动，数据层扩展即可

## P1：中期（3-6个月）

### HTML 报告输出 — ⬜ 未开始
- 在 Markdown 基础上增加 HTML 报告格式
- 支持暗色模式、导航栏、图表可视化
- 提升报告传播性和阅读体验

### 多档深度模式 — ⬜ 未开始
- `lite`：5分钟速判，快速给出估值区间和核心结论
- `standard`：当前默认模式，完整多Agent研究
- `deep`：增加更多交叉验证和历史类比，机构级深度

### 多股横向对比 — 🟡 部分实现
- `skills/investment-checklist.md` 已支持多公司清单对比
- 待补：2-4 只股票同维度横向对决矩阵、同行业估值对标的标准化输出

## P2：长期（6个月+）

### 测试覆盖 — 🟡 部分实现
- 已有 `tests/test_v10_unit.py` / `tests/test_v10_integration.py` / `tests/test_v10_backtest.py`
- 集成测试已改为 `assert` + 无 key 时 `skip`（不再"永远通过"）
- 待补：`financial_rigor.py` 等工具的单元测试、Skill 输出回归测试

### 组合级分析 — 🟡 部分实现
- `skills/portfolio-review.md` 提供持仓组合健康度评估
- 待补：行业/地域集中度量化、相关性风险检测（可结合 `data/` 的相关性数据集）

## 本 fork 专属方向（upstream 无）

### TextGrad V10 自进化引擎 — 🟡 设计 + 雏形
- `src/graph.py` + `src/optimizer.py`：BerkshireGraph 计算图 + TextualGradientDescent 文本梯度优化
- `src/evolution_loop_v10.py`：进化循环入口（当前为演示雏形）
- 设计文档：`docs/textgrad_design.md`
- 待补：`reflect` / `optimize` / `status` 命令的完整实现（详见 `config/skill.md` 进化引擎章节的 `[规划]` 标记）

### 多运行时部署 — ✅ 已实现
- `update-platforms.sh` 同步 skills/tools 到 OpenClaw、QwenPaw 运行时

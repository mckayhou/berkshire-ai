# berkshire-ai Roadmap

> 本路线图源自 upstream（xbtlin/ai-berkshire），并标注本 fork（OpenClaw/QwenPaw 适配版）的实现状态。
> 状态图例：✅ 已实现 · 🟡 部分实现 · ⬜ 未开始

## P0：近期（1-2个月）

### A股数据源接入 — ✅ 已实现
- 已通过 `tools/ashare_data.py` 接入腾讯财经 / 东方财富
- 市值/估值校验由 `tools/financial_rigor.py` 完成

### 组合工具接线 — ✅ V10.10
- `data/holdings.example.json` → 本地 `data/holdings.json`（gitignore）
- `portfolio-review` / `news-pulse` 强制引用 `portfolio_risk` + `portfolio_scan`
- `scripts/portfolio-weekly.sh`：scan → thesis_queue 周度工作流

## P1：中期（3-6个月）

### HTML 报告输出 — ⬜ 未开始
- Markdown → HTML，暗色模式、导航、图表

### 多档深度模式 — ✅ V10.9
- `lite` / `standard` / `deep`（`skills/investment-research.md`）

### 多股横向对比 — 🟡 部分实现
- `investment-checklist` 有多公司清单
- 待补：2–4 只标准化对决矩阵工具或模板

## P2：长期（6个月+）

### 测试覆盖 — 🟡 部分实现
- 125+ pytest（引擎、financial_rigor、report_audit、网络层、portfolio_*、thesis_queue）
- GitHub Actions CI（`.github/workflows/test.yml`）
- 待补：Skill 输出回归（golden 行动卡/报告片段）

### 组合级分析 — 🟡 部分实现（V10.9–10.10）
- `portfolio_risk.py`：集中度、现金、主题、相关性 CSV
- `portfolio_scan` + `risk_flags`；`portfolio-review` 已接线
- 待补：地域/货币暴露规则、压力测试半自动化

## 本 fork 专属方向

### TextGrad V10 自进化引擎 — 🟡 设计 + 雏形
- `src/graph.py` + `src/optimizer.py`：结构化 `Gradient`，非 Option B 全自动进化
- 待补：`reflect` / `optimize` CLI 完整化（见 `config/skill.md`）

### 多运行时部署 — ✅ 已实现
- `update-platforms.sh` 同步 skills/tools

### ai-hedge-fund 吸收 — ✅ PM/Risk 层（V10.8–10.10）
- 行动卡、`portfolio_scan`、`portfolio_risk`、`thesis_queue`；不采纳自动交易图

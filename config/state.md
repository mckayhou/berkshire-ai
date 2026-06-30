# Berkshire AI - Global State & Thesis Tracker
> Last Updated: 2026-06-30 | Loop Engine: Active (L2 - Assisted) | **Version: V10.16**（生产化硬化 档C：结构化日志/run_id/LLM 成本埋点 observability + 服务边界 service(FastAPI) + 提示注入防护 sanitize；生产化三档 A→B→C 全部落地）

## 1. Active Portfolio Theses (活着的投资逻辑)
| Ticker | Thesis | Confidence | Last Check | Next Trigger | Status |
|--------|--------|------------|------------|--------------|--------|
| AVGO | HBM/CoWoS 需求持续增长，PE 回归 57-60x 合理 | B+ | 2026-06-26 | Price > $400 OR PE > 65x | ⚠️ Watch (6/4 急跌15%，麦格理下调至中性，担忧谷歌自研芯片) |
| PDD | 海外 Temu 增长放缓，但国内利润释放支撑底部 | C | 2026-06-26 | Q2 Revenue < Consensus -5% | ❌ TRIGGERED (Q1营收低于预期，欧盟罚款Temu，需重新评估) |
| 600900 | 水电公用事业化，防御底仓 | A | 2026-06-26 | Dividend Yield < 3% | 🛡️ Hold (无重大公告，6/23临时股东会，稳定) |
| 0700.HK | AI+游戏双轮驱动，估值合理 | A- | 2026-06-26 | 观察中 | 📈 Accumulate (6/10回购5.01亿港元，股价465.6 HKD +2.74%) |

## 2. Pending Research Queue (待研究队列)
* *(Triggered by News/Market Movers)*
- [x] **PDD**: ~~Check CoWoS capacity constraints vs H20 demand~~ → **已触发**: Q1 营收低于预期 + 欧盟罚款，需重新评估投资逻辑 (2026-06-26)
- [ ] **AVGO**: 关注 Q2 财报，验证 AI 半导体增长是否如管理层指引 (2026-06-26)
- [ ] **NVDA**: Check CoWoS capacity constraints vs H20 demand (Triggered by News: Supply chain rumor)
- [ ] **AAPL**: Vision Pro sales impact on Services revenue (Triggered by Event: WWDC)

## 3. Evolution Log & Historical Gaps (进化日志与历史盲区)
> *Auto-updated by Loop E when a thesis fails or succeeds significantly.*

| Date | Issue | Lesson Learned | Applied To Skill |
|------|-------|----------------|------------------|
| 2026-06-30 | **V10.15 - 生产化硬化 档B（让自进化真正成立）** | 「能改 prompt」≠「改得更好」：`src/prompt_validation.py` 验证门控（改写后评分，只有不劣于旧版+min_improvement 才接受否则回滚，杜绝漂移）；`NetworkPriceProvider` 经 data_sources 接真实行情（缓存+非交易日回退）替换 mock；`src/eval_harness.py` 多轮迭代 `run_multi_round` + 离线回归证明「单调不退化且收敛」。 | `src/prompt_validation.py`, `src/realized_feedback.py`, `src/eval_harness.py` |
| 2026-06-30 | **V10.14 - 生产化硬化 档A** | 工程门禁可信化：`pyproject.toml`（ruff/mypy/pytest/coverage 集中配置 + extras）；CI 升级（py3.10-3.12 矩阵 + ruff + mypy(src) + 覆盖率门 45% + pip-audit + gitleaks + Dependabot）；`src/config.py` 中心配置 + `.env.example` + 启动自检 doctor（不泄密钥）。 | `pyproject.toml`, `.github/*`, `src/config.py` |
| 2026-06-30 | **V10.13 - 变量真实改写（Option B）** | 把文本梯度真正落到 Prompt：新增 `src/prompt_optimizer.py`（`LLMClient`/`StaticLLMClient`/`OpenAICompatibleLLMClient` + `apply_gradient`）；`TextualGradientDescent(graph, llm=...)` 注入 LLM 后 `step()` 真实改写未达标 prompt 变量的 `value`，失败优雅降级、不注入则向后兼容。 | `src/prompt_optimizer.py`, `src/optimizer.py` |
| 2026-06-30 | **V10.12 - SENSITIVITY 尺度校准** | 用真实历史行情（27 标的）校准收益反馈映射 `realized_base = clip(0.5 + alpha*SENSITIVITY, 0, 1)`：旧默认 2.5 使约 78% 样本贴边过饱和、丢失区分度，校准为 0.5；新增 `tools/calibrate_sensitivity.py` 与单测，可用 `BERKSHIRE_SENSITIVITY` 覆盖。 | `src/realized_feedback.py`, `tools/calibrate_sensitivity.py` |
| 2026-06-30 | **V10.11 - 收益反馈闭环 + 多空辩论** | 吸收 TradingAgents：决策落盘（`decision_log`）→ 真实收益算 alpha（`realized_feedback`）→ 各大师校准评分喂回 `backward()`；并加显式多空对抗（`debate`）。把"反思"变成可微 reward。 | `src/*` v10.11 |
| 2026-06-30 | **V10.11 - A股多源降级 + 多通道推送** | 吸收 JusticePlutus：数据走 `native→tushare→efinance→akshare→baostock→yfinance` 降级链全失败不抛崩；报告经 Telegram/飞书/本地兜底交付，零配置只落地。 | `tools/data_sources.py`, `tools/notify.py` |
| 2026-06-26 | **Tracker V10.0 - PDD 触发器命中** | Q1 营收低于预期 + 欧盟罚款 Temu，触发 "Q2 Revenue < Consensus -5%" 条件。需重新评估投资逻辑。 | `thesis-tracker` v10.0 |
| 2026-06-26 | **Tracker V10.0 - AVGO 风险信号** | 6/4 急跌 15%，麦格理下调至中性，担忧谷歌自研芯片影响 ASIC 市场份额。需关注 Q2 财报验证。 | `thesis-tracker` v10.0 |
| 2026-06-25 | **V10.0 - TextGrad 化** | 借鉴 Nature 2025 论文，实现显式计算图 + 节点级诊断 + 文本梯度反向传播。诊断精度从整体评分提升到节点级定位。**Cron 任务已升级**: `99ac7a57` (每周五 20:00) | `investment-research` v10.0 |
| 2026-06-25 | **V9.3 - Tavily 实时搜索集成** | 消除 LLM 数据幻觉，所有财务数据必须来自实时搜索。**双 Key 轮询**，预期评分提升 +3.9% | `investment-research` v9.3 |
| 2026-06-25 | **E2E Test 8/8 PASS (100%)** | 全链路验证通过：18 Skills + 8 Tools + 4 Masters + Evolution Loop + Polyglot MAS | `e2e_test.py` |
| 2026-06-25 | **V9.0 - 继承 ai-berkshire** | 整合四大师并行框架 (Buffett/Munger/Duan/Li Lu) + 反偏见机制 + 金融严谨性工具 | `investment-research` v9.0 |
| 2026-06-25 | Contrastive Reflection (AVGO) | 2 optimizations applied. Avg score: 0.85 | `investment-research` v8.1 |
| 2026-06-25 | V8.0 Self-Evolving | Added Contrastive Reflection + Skill Optimizer | `investment-research` v8.0 |
| 2026-06-25 | V7.3 Tri-Engine | Qwen + GLM-5.2 + DeepSeek-V4-Pro | `investment-research` v7.3 |
| 2026-06-25 | LLM Hallucinated Math in DCF | `financial_rigor.py` is MANDATORY. No mental math allowed. | `investment-research` v2.0 |
| 2026-06-25 | JSON Output Failures | Enhanced Pydantic defaults and retry logic. | `investment-research` v3.0 |
| 2026-06-25 | Stateless Analysis | Agent now remembers gaps from previous reports via State File. | `investment-research` v4.0 |
| 2026-06-25 | Macro Blindspot | Agent often ignores Fed rate hike impact on Tech valuation. Added "Macro Stress Test" to Phase B. | `investment-research` v5.0 |

## 4. Market Regime Context (市场环境上下文)
* **Current Regime**: High Rates, AI Capex Boom, China Stimulus Watch.
* **Risk Level**: Medium-High.
* **Agent Behavior Adjustment**: Be more conservative on PE expansion for Tech; Focus on Cash Flow.

## 5. Tool & Script Context (For Agent Execution)

### 核心工具
| 工具 | 路径 | 功能 |
|:-----|:-----|:-----|
| **Financial Rigor** | `tools/financial_rigor.py` | 市值/估值/交叉验证/三情景 |
| **Report Audit** | `tools/report_audit.py` | 报告数据抽检 (15%随机抽样) |
| **Portfolio Scan** | `tools/portfolio_scan.py` | watchlist 扫描 + 行动卡草案 |
| **Portfolio Risk** | `tools/portfolio_risk.py` | 组合集中度/主题/相关性检查 |
| **Thesis Queue** | `tools/thesis_queue.py` | state.md + 扫描 → 研究待办 |
| **A-Share Data** | `tools/ashare_data.py` | A股数据获取（行情/财务/估值/日线） |
| **Data Sources** | `tools/data_sources.py` | A股多源降级数据层（全失败不抛崩） |
| **Notify** | `tools/notify.py` | 多通道交付（Telegram/飞书/本地兜底） |
| **Stock Screener** | `tools/stock_screener.py` | 股票筛选 |
| **Xueqiu Scraper** | `tools/xueqiu_scraper.py` | 雪球数据抓取 |
| **Morningstar FV** | `tools/morningstar_fair_value.py` | 晨星公允价值榜单 |

### Skills (18个 - 继承自 ai-berkshire)
| 类别 | Skills |
|:-----|:-------|
| **投研核心** | `investment-research`, `investment-team`, `investment-checklist` |
| **财报分析** | `earnings-review`, `earnings-team` |
| **行业研究** | `industry-research`, `industry-funnel`, `quality-screen` |
| **组合管理** | `portfolio-review`, `thesis-tracker` |
| **深度分析** | `management-deep-dive`, `bottleneck-hunter`, `deep-company-series` |
| **数据工具** | `financial-data`, `news-pulse` |
| **特色** | `dyp-ask` (段永平问答), `wechat-article`, `private-company-research` |

### 路径汇总
| 数据 | 路径 |
|:-----|:-----|
| 仓库根目录 | `berkshire-ai/`（本仓库） |
| Skills | `skills/` |
| Tools | `tools/` |
| State File | `config/state.md`（本文件） |
| 行动卡模板 | `docs/action-card.md` |
| Watchlist | `data/watchlist.json` |
| 持仓模板 | `data/holdings.example.json` → 复制为 `data/holdings.json` |
| 周度脚本 | `scripts/portfolio-weekly.sh` |

## 6. 四大师分析框架 (V9.0 核心)

| 角色 | 大师 | 分析框架 | 核心追问 |
|:-----|:-----|:---------|:---------|
| **生意分析师** | 段永平 | 商业模式 & 护城河 | "这门生意好在哪？如果只能用一句话描述，是什么？" |
| **财务分析师** | 巴菲特 | 财务报表 & 估值 | "10年后这条护城河还在吗？什么能摧毁它？" |
| **行业研究员** | 芒格 | 行业格局 & 竞争 | "我最可能在哪里犯错？聪明人为什么会不买？" |
| **风险评估师** | 李录 | 风险 & 管理层 | "站在20年后回看，这是'时代的标准石油'还是'昙花一现'？" |

### 模型分配 (Polyglot MAS)
| 角色 | 模型 | 引擎 |
|:-----|:-----|:-----|
| 生意分析师 (段永平) | `qwen3.7-plus` | 阿里云 |
| 财务分析师 (巴菲特) | `deepseek-v4-pro` | 火山引擎 |
| 行业研究员 (芒格) | `glm-5.2` | 火山引擎 |
| 风险评估师 (李录) | `kimi-k2.6` | 火山引擎 |

## 7. 反偏见机制 (必须执行)

### 信息丰富度评级
| 等级 | 特征 | 应对策略 |
|:-----|:-----|:---------|
| A级 | 上市多年、券商覆盖多 | 重点做反面检验，避免共识过强 |
| B级 | 上市1-3年、覆盖有限 | 推算数据标注置信度 |
| C级 | 刚上市/冷门股 | 用第一性原理提问，不追求报告完整性 |

### 偏见自查清单
- [ ] 我的"确定性"感受是来自生意本质，还是来自资料数量？
- [ ] 如果把这家公司的资料量减少一半，我的结论会变吗？
- [ ] AI输出的分析是否与市场共识高度雷同？
- [ ] 是否存在"公开资料很少但生意本质极好"的可能性被低估了？

## 8. 金融严谨性验证 (必须使用工具)

```bash
# 市值验算（仓库根目录执行）
python3 tools/financial_rigor.py verify-market-cap \
  --price {股价} --shares {总股本} --reported {报告市值} --currency {币种}

# 估值验算
python3 tools/financial_rigor.py verify-valuation \
  --price {股价} --eps {EPS} --bvps {每股净资产}

# 三情景估值
python3 tools/financial_rigor.py three-scenario \
  --price {股价} --eps {EPS} --shares {股本亿} \
  --growth {乐观} {中性} {悲观} \
  --pe {乐观PE} {中性PE} {悲观PE}

# 数据交叉验证
python3 tools/financial_rigor.py cross-validate \
  --field {字段名} --values '{"来源1": 数值, "来源2": 数值}' --unit {单位}

# 研究队列
python3 tools/portfolio_scan.py --json --quiet --holdings-file data/holdings.json
python3 tools/thesis_queue.py --json
./scripts/portfolio-weekly.sh --suggest-md
```

## 9. Cron 任务 (V10.0)

| ID | 任务 | 调度 | 状态 |
|:---|:-----|:-----|:-----|
| `03c4ebc8` | Thesis Tracker | 每日 08:30 | ✅ 已测试 |
| `5bb93208` | Deep Research | 每周五 18:00 | ✅ 已测试 |
| `99ac7a57` | Evolution Loop | 每周五 20:00 | ✅ 已测试 |
| — | Portfolio Weekly | 每周一 09:00（建议） | 运行 `./scripts/portfolio-weekly.sh --suggest-md` |

**注意**: 旧的 V9.0 任务 (`84e90130`, `3ea0b79b`) 已于 2026-06-26 删除。

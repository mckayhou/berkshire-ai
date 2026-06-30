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

### V10.11 - 2026-06-30 (已实现收益反馈闭环 + 多空辩论 · A股多源降级数据层 + 多通道推送)

**变更内容**:

A) 分析脑 — 已实现收益反馈闭环 + 多空对抗辩论（吸收自 TradingAgents）
- 新增 `src/decision_log.py`：决策快照 JSONL 持久化（`DecisionRecord`），路径环境变量 `BERKSHIRE_DECISION_LOG`（默认 `~/.berkshire/decisions.jsonl`），复用 `MASTERS` 单一来源校验大师评分
- 新增 `src/realized_feedback.py`：已实现收益 → 评分转换器。`raw_return`/`alpha`；`realized_base=clip(0.5+alpha*SENSITIVITY,0,1)`（默认 `SENSITIVITY=2.5`）；`master_score=clip(1-|conviction-realized_base|,0,1)`；价格通过可注入/可 mock 的 `PriceProvider`/`StaticPriceProvider` 获取（核心不连网络）
- 新增 `src/debate.py`：多空对抗辩论。`net_score∈[-1,1]`，中性区 `NET_MARGIN=0.15`，结构化 `DebateResult`（控制流读 `net_stance`/`ok`，不解析文本）
- 修改 `src/graph.py`：新增 `BerkshireGraph.debate()`（Layer 2 与输出之间的一步）
- 修改 `src/evolution_loop_v10.py`：新增 `run_with_realized_feedback(...)`（收益→评分→backward 闭环，附带辩论净判断），保留 `run_example()`
- 修改 `src/__init__.py`：导出上述新符号
- 新增 `tests/test_realized_feedback_loop.py`

B) 数据/交付层 — A股多源降级数据层 + 多通道推送（吸收自 JusticePlutus）
- 新增 `tools/data_sources.py`：A股数据多源降级链 `native→tushare→efinance→akshare→baostock→yfinance`（可用 `--sources` / `BERKSHIRE_DATA_SOURCES` 覆盖排序）；覆盖 daily/quote/fundamentals；全部失败返回 `ok=False`+attempts 而不抛崩；可插拔 `DataSource` 适配器；tushare 增强源需 `BERKSHIRE_ENABLE_TUSHARE=1`+`TUSHARE_TOKEN`，其余源 import 守卫缺库自动跳过
- 新增 `tools/notify.py`：多通道交付。Telegram（`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`，超长拆分）、飞书（`FEISHU_WEBHOOK`+可选 `FEISHU_SECRET`，卡片→文本回退+加签+长消息拆分）、本地兜底（`BERKSHIRE_NOTIFY_DIR`，默认 `reports/notifications`）；零配置只落地不报错；用系统 curl 零依赖
- 修改 `tools/ashare_data.py`：新增 `fetch_daily()` + `daily` 子命令
- 修改 `tools/README.md`、`requirements.txt`（标注可选库）、`.gitignore`（忽略 `reports/notifications/`）
- 新增 `tests/test_tools_data_sources.py`、`tests/test_tools_notify.py`

**测试结果**: 183 通过（`python3 -m pytest tests/ -q`，0 失败）

**结论**: ✅ 上线

---

### V10.10 - 2026-06-27 (接线：holdings + portfolio-review + 周度脚本)

**变更内容**:
- `data/holdings.example.json`；`portfolio_risk`/`portfolio_scan` 自动读 `data/holdings.json`
- `scripts/portfolio-weekly.sh`：scan → thesis_queue 一键工作流
- `portfolio-review`：强制 `portfolio_risk` + scan；`news-pulse`：Pending Queue 模板
- `docs/ROADMAP.md` 同步 V10.9–10.10 状态

**测试结果**: 128 通过

**结论**: ✅ 上线

---

### V10.9 - 2026-06-27 (Risk Manager + 研究队列 + CI + lite 深度)

**变更内容**:
- 新增 `tools/portfolio_risk.py`：组合集中度、现金、主题暴露、可选相关性告警
- 新增 `tools/thesis_queue.py`：解析 `config/state.md` + 合并 `portfolio_scan` → `research_now` 优先级
- `portfolio_scan.py`：`--holdings` / `--proposed` 输出 `risk_flags`
- `skills/investment-research.md`：lite / standard / deep 三档深度
- `docs/action-card.md`：risk_flags 字段；`thesis-tracker` 队列同步流程
- `config/state.md`：工具路径改为仓库内 `tools/`
- GitHub Actions：`pytest tests/`（`.github/workflows/test.yml`）
- 新增离线单测：`test_tools_portfolio_risk.py`、`test_tools_thesis_queue.py`

**测试结果**: 125 通过

**结论**: ✅ 上线

---

### V10.8 - 2026-06-26 (吸收 ai-hedge-fund：行动卡 + portfolio_scan)

**变更内容**:
- 新增 `docs/action-card.md`：结构化行动卡模板（立场/仓位/目标价/风险/催化剂），研报与组合报告末尾必附
- 新增 `tools/portfolio_scan.py`：watchlist 扫描 + 行动卡草案输出（`--json`/`--group`/`--top`），借鉴 PM 层但保持研报导向
- Skills 接入：`investment-research`、`investment-team`（PM 汇总 7½）、`portfolio-review`（扫描候选池）
- 文档：`report-conventions`、`tools/README`、`README` 导航更新
- 新增 6 个离线单测 `tests/test_tools_portfolio_scan.py`

**测试结果**: 113 通过

**结论**: ✅ 上线

---

### V10.7 - 2026-06-26 (网络层加固：瞬时错误重试 + 18 个离线网络测试)

**变更内容**:
- **`src/tavily_search.py`**：`search()` 增加瞬时错误重试——超时 / 连接错误（`httpx.TimeoutException`/`TransportError`）/ 5xx 网关错误（500/502/503/504）指数退避（封顶 4s）后重试；429 维持切 Key；其它错误立即返回。删除从未使用的死参数 `_retries`，改为 `max_retries`
- **`tools/ashare_data.py`**：`_curl()` 增加重试（默认 2 次）+ 显式 `subprocess.TimeoutExpired` 处理，最终失败抛 `ConnectionError`（原先超时会直接冒泡）
- **`tools/morningstar_fair_value.py`**：`fetch_page()` 增加重试 + 超时/空响应/**非 JSON**（被限流/拦截）处理，最终失败抛 `ConnectionError`（原先非 JSON 会 `JSONDecodeError` 崩溃）
- **新增 18 个离线网络测试** `tests/test_tools_network.py`（monkeypatch httpx/subprocess，零真实网络）：
  - tavily：`_load_keys` 多/单/空、无 key 抛错、Key 轮询、瞬时重试成功、5xx 重试耗尽、429 切 Key、4xx 立即 error、结果解析+截断+error 透传
  - ashare：`_curl` 成功/GBK 回退/超时重试/持续失败抛错
  - morningstar：`fetch_page` 成功/非 JSON 重试/持续超时抛错

**测试结果**:
- 全量: 107 通过（带 Tavily key 时 0 跳过；无 key 时 1 跳过）
- lint: 无错误；graphify 图已更新

**结论**: ✅ 上线

---

### V10.6 - 2026-06-26 (工具层加固：离线单测 + 3 处健壮性/正确性修复)

**变更内容**:
- **新增离线单元测试 76 个**（无网络、无外部依赖，3 个文件）：
  - `tests/test_tools_financial_rigor.py`：精确十进制计算（exact/fmt_number/市值/估值/交叉验证/Benford）+ AST 安全求值器的**安全边界**（拒绝 `__import__`/属性/函数调用/自由变量/lambda/列表字面量/超大幂）
  - `tests/test_tools_report_audit.py`：数据点提取/标签过滤/抽样确定性/偏差判定/准出打回判决
  - `tests/test_tools_misc.py`：`ashare_data`（代码前缀转换/腾讯行情解析/脏输入格式化）、`stock_screener`（动量信号 `check_momentum`/分级 `grade_signal`）、`morningstar`（星级渲染/ticker 提取）
- **健壮性/正确性修复（3 处）**：
  1. `report_audit.render_verdict`（**正确性 bug**）：单一来源偏差超阈值此前被软化为"⚠️ 警告"并仍判 **PASS/准出**——对审计工具是危险默认。现修复为：单来源完全取决于该来源（超阈值即 **FAIL/打回**）；双来源维持"皆过=通过 / 皆错=不通过 / 一过一错=警告"
  2. `financial_rigor.cross_validate`（**崩溃**）：空来源字典此前因对空列表取中位数 `IndexError`；现返回 `{consensus: None, all_consistent: False}` 并提示
  3. `financial_rigor.safe_arith_eval`（**资源耗尽防护**）：幂运算指数 >1000 直接拒绝，防止 `9**99999` 类表达式吃满 CPU/内存
- CLI 三处修复均已 e2e 验证（巨幂拒绝 / 空交叉验证 / 单源 30% 偏差判 FAIL）

**测试结果**:
- 全量: 88 通过 / 1 跳过（Tavily 无 key skip）
- lint: 无错误；graphify 图已更新

**结论**: ✅ 上线

---

### V10.5 - 2026-06-26 (TextGrad 引擎清理：去重 + 结构化梯度)

**变更内容**:
- **四大师单一来源**：`src/graph.py` 新增 `Master` dataclass + `MASTERS` 常量，派生 `MASTER_PREFIXES`/`ROLE_NAMES`/`MASTER_CHECKS`；变量/边/反向传播/诊断全部从 `MASTERS` 派生，节点命名收敛到 `analysis_node`/`prompt_node`/`model_node`。消除散落在 4 处的硬编码大师列表——新增大师只需改一处。
- **去 emoji 字符串耦合（控制流结构化）**：新增 `Gradient` dataclass（`ok`/`score`/`issues`/`text`）。`backward()` 返回类型 `Dict[str, str]` → `Dict[str, Gradient]`。
  - `optimizer.step()` 判定从 `"❌" not in gradient` 改为 `gradient.ok`，并记录结构化 `issues`
  - 测试/回测消费方 `"❌" in g` → `not g.ok`
  - `Gradient` 保留 `__str__`/`__contains__` 仅用于展示兼容，不参与任何控制流
  - `evolution_loop_v10.py` 通过 `__all__` 对外导出 `Gradient`/`Master`/`MASTERS`
- **零行为回归**：example runner 仍为 18 nodes / 7 updates，回测覆盖率不变
- **文档同步**：`docs/textgrad_design.md` 更新为「实现现状 + Option B」两段——新增实现状态表、修正与代码脱节的旧片段（`failure_trace`→`scores`、返回 str→`Gradient`、`"❌" in grad`→`.ok`）、补 `MASTERS`/`Gradient` 真实片段、Phase 勾选实际进度
- **新增测试**：`test_masters_single_source` / `test_gradient_is_structured` / `test_optimizer_reads_ok_field`（守护单一来源 + 结构化契约）
- 为将来走 B（LLM 驱动自进化）铺路：`Gradient.issues` 已结构化，未来填入 LLM 批评意见时消费方无需改动

**测试结果**:
- 单元 + 集成测试: 12 通过 / 1 跳过（Tavily 无 key skip；单元由 5→8 用例）
- 回测验证: 诊断覆盖率 100%
- 进化引擎 example: Graph 18 nodes / Updates 7（与重构前一致）
- lint: 无错误；graphify 图已更新

**结论**: ✅ 上线

---

### V10.4 - 2026-06-26 (upstream 对齐 + 全量 E2E + 文档完善)

**变更内容**:
- **与 upstream 对齐**（能力/治理/文档层）：
  - `skills/private-company-research.md` 重写为 upstream 完整 6 子 Agent 框架（商业模式/财务侦探/竞争/风险治理/技术IP/替代数据），并适配 OpenClaw/QwenPaw 多 Agent 编排（1108 行）
  - 新增 `LICENSE`(MIT)、`README_EN.md`、`docs/ROADMAP.md`、`docs/report-conventions.md`、`assets/architecture.mmd`+`.png`
  - 带入 `data/`（5 个 csv/json，供 stock_screener/morningstar 用）+ 2 份样例报告（RocketLab、赛力斯）
  - 未并入 upstream 的 2084 份历史报告与个人实盘记录（属原作者作品/私人数据）
- **全量 E2E 测试**（详见 TESTING.md）：单元/集成/回测/进化引擎 + 9 个工具全部跑通
- **Bug 修复**：`tools/morningstar_fair_value.py` 增加 argparse（`--help` 不再触发 84 秒抓取；新增 `--max-pages`/`--top`），星级渲染容错（`_stars()`）
- **文档完善**：新增 `TESTING.md`、`tools/README.md`；README 增加文档导航 + 测试章节，修复一处游离代码围栏

**测试结果**:
- 单元 + 集成测试: 9 通过 / 1 跳过（Tavily 在受限网络下 skip，有网时通过真实 API）
- 回测验证: 诊断覆盖率 100%
- 工具 E2E: financial_rigor(6子命令+安全)/report_audit/ashare_data(4)/momentum×2/stock_screener/morningstar/tavily 全部通过；xueqiu CLI 验证（全量需登录态）

**结论**: ✅ 上线

---

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

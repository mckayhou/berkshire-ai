# 测试指南与 E2E 报告（TESTING）

本文件说明如何对 berkshire-ai 进行端到端（E2E）测试，并记录最近一次全量 E2E 的结果。

## 环境要求

- Python ≥ 3.11（实测 3.14.6）
- 依赖：`pip install -r requirements.txt`（仅 `httpx`）+ `pytest`
- 可选：`playwright`（仅 `xueqiu_scraper.py` 需要，且需登录态）
- 环境变量：`TAVILY_API_KEYS`（逗号分隔多个 key，供 `src/tavily_search.py` 使用）
- 网络：A股/美股/Morningstar/Tavily 工具需要外网

## 一键自测

```bash
# 1) 单元 + 集成测试（无网络/无 key 时相关用例自动 skip，不会"假通过"）
python3 -m pytest tests/ -v -rs

# 2) 回测脚本（自进化引擎诊断覆盖率）
python3 tests/test_v10_backtest.py

# 3) 进化引擎入口
python3 src/evolution_loop_v10.py --ticker 600519 --company 贵州茅台
```

## 工具 E2E 冒烟（逐个）

```bash
# 离线（无需网络）
python3 tools/financial_rigor.py verify-market-cap --price 510 --shares 9.11e9 --reported 4.65e12 --currency HKD
python3 tools/financial_rigor.py three-scenario --price 510 --eps 23.5 --shares 91.1 --growth 0.15 0.10 0.05 --pe 25 20 15
python3 tools/report_audit.py extract --report reports/RocketLab/RKLB-investment-research.md --dry-run

# 在线（需网络）
python3 tools/ashare_data.py quote 600519
python3 tools/momentum_backtest.py
python3 tools/stock_screener.py
python3 tools/morningstar_fair_value.py --max-pages 1 --top 5   # 快速冒烟，不抓全量
python3 src/tavily_search.py test                                # 需 TAVILY_API_KEYS

# 需登录态（浏览器 + cookie）
python3 tools/xueqiu_scraper.py --user-id <ID> --keywords 拼多多,PDD --output /tmp/out.md
```

## 最近一次 E2E 结果（2026-06-26，Python 3.14.6）

| 组件 | 命令 | 结果 |
|---|---|---|
| 单元+集成测试 | `pytest tests/` | ✅ 88 passed, 1 skipped（含 76 个工具层离线单测：financial_rigor 精确计算+AST 安全边界、report_audit 提取/抽样/判决、ashare_data/stock_screener/morningstar 纯函数；Tavily 用例在无网下 skip）|
| 回测脚本 | `test_v10_backtest.py` | ✅ 诊断覆盖率 100% |
| 进化引擎 | `evolution_loop_v10.py` | ✅ Graph created 18 nodes, Updates needed 7 |
| 计算图/优化器 | `graph.py` / `optimizer.py` | ✅ 由单元测试覆盖（拓扑排序/反向传播/优化器）|
| financial_rigor | 6 个子命令 + 恶意表达式 | ✅ 全部通过；`calc` 用 AST 安全求值，拒绝 `__import__(...)` |
| report_audit | `extract` / `verdict` | ✅ 抽样、准出/打回判决均正确 |
| ashare_data | `quote/financials/valuation/search` | ✅ 实时数据；市值"反推"已正确标注为仅供参考 |
| momentum_backtest / v2 | 全量运行 | ✅ 实时 Yahoo 数据，跑完无崩溃 |
| stock_screener | 全量运行 | ✅ 读取 `data/fundamentals.json`、`data/watchlist.json` |
| morningstar_fair_value | `--max-pages 1 --top 5` 与全量 | ✅ 抓取 6108 只股票；星级渲染已做容错 |
| tavily_search | `test` | ✅ 真实 API 返回腾讯行情/财务 |
| xueqiu_scraper | `--help` | ✅ CLI 正常（全量运行需登录 cookie，未在 CI 覆盖）|

### 本轮修复

- `tools/morningstar_fair_value.py`：
  - 之前 `--help` 会触发 84 秒全量抓取（无参数解析）→ 增加 `argparse`，支持 `--max-pages` / `--top`，`--help` 秒回；
  - 星级渲染 `int(star_rating)` 对浮点字符串会崩溃 → 改用 `_stars()` 容错（int/float/str/None 均安全）。

## 已知限制

- `xueqiu_scraper.py` 需要 Playwright 浏览器 + 雪球登录态，不在自动化测试范围内。
- 在线工具依赖第三方接口（Yahoo / Morningstar / 腾讯 / 东方财富 / Tavily），偶发限流/鉴权失败属环境问题；集成测试遇到此类错误会 `skip` 而非 `fail`。
- `financial_rigor.py benford` 需样本量 ≥ 50 才给出可靠结论（样本不足会明确提示）。

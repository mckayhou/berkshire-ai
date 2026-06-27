# tools/ — 工具链说明

投研流程中由 Agent 通过 shell 调用的辅助工具。所有命令均以仓库根目录为工作目录运行（`python3 tools/xxx.py ...`）。

| 工具 | 作用 | 需要网络 | 额外依赖 |
|---|---|:---:|---|
| `financial_rigor.py` | 金融数据严谨性验证（核心） | 否 | 无 |
| `report_audit.py` | 研究报告数据抽检 / 准出判决 | 否 | 无 |
| `ashare_data.py` | A股行情/财务/估值/搜索 | 是 | curl |
| `momentum_backtest.py` | 动量+价值回测（NVDA/AMD/MU） | 是 | curl |
| `momentum_backtest_v2.py` | 回测 v2（框架验证版） | 是 | curl |
| `stock_screener.py` | 动量+价值实时筛选 | 是 | curl, `data/*.json` |
| `portfolio_scan.py` | watchlist 扫描 + 结构化行动卡草案（JSON） | 是 | curl, 复用 stock_screener |
| `portfolio_risk.py` | 组合风险检查（集中度/现金/主题/相关性） | 否 | 可选 `data/correlation_*.csv` |
| `thesis_queue.py` | state.md + 扫描信号 → 研究待办队列 | 否* | `config/state.md` |
| `holdings` 数据 | `data/holdings.example.json` | 否 | 复制为 `data/holdings.json`（本地，不提交） |
| `morningstar_fair_value.py` | Morningstar 公允价值榜单 | 是 | curl |
| `xueqiu_scraper.py` | 雪球用户时间线抓取 | 是 | playwright + 登录态 |
| `log-command.sh` | 命令日志辅助脚本 | 否 | bash |

> 提示：任何报告中的关键数字都应先经 `financial_rigor.py` 校验、发布前用 `report_audit.py` 抽检。

---

## financial_rigor.py（核心，离线）

精确十进制计算，杜绝心算/浮点误差。

```bash
# 市值验算（需独立来源总股本）
python3 tools/financial_rigor.py verify-market-cap --price 510 --shares 9.11e9 --reported 4.65e12 --currency HKD
# 估值指标（PE/盈利收益率/PB/ROE）
python3 tools/financial_rigor.py verify-valuation --price 510 --eps 23.5 --bvps 120
# 多源交叉验证（values 为 JSON 字典）
python3 tools/financial_rigor.py cross-validate --field revenue --values '{"年报": 7518, "Yahoo": 7500}' --unit 亿
# 三情景估值
python3 tools/financial_rigor.py three-scenario --price 510 --eps 23.5 --shares 91.1 --growth 0.15 0.10 0.05 --pe 25 20 15
# Benford 造假检测（样本≥50）
python3 tools/financial_rigor.py benford --values '[1234,2345,...]'
# 安全计算器（AST 求值，拒绝任意代码执行）
python3 tools/financial_rigor.py calc --expr '510 * 9.11e9'
```

## report_audit.py（离线）

```bash
# Step1 提取数据点并随机抽样 15%
python3 tools/report_audit.py extract --report reports/腾讯/腾讯-research-YYYYMMDD.md
#   预览不核验：加 --dry-run；自定义抽样比例：--ratio 0.2
# Step2 人工/Agent 对清单逐项取两个独立来源数值
# Step3 输入核验结果，输出准出/打回
python3 tools/report_audit.py verdict --report 腾讯-research.md --results '[{"id":1,"label":"营收","reported_value":7518,"unit":"亿","fetched_value":7518,"fetched_source":"macrotrends","fetched_value2":7500,"fetched_source2":"stockanalysis"}]'
```

## ashare_data.py（在线）

```bash
python3 tools/ashare_data.py quote 600519        # 实时行情
python3 tools/ashare_data.py financials 600519   # 近5年核心财务
python3 tools/ashare_data.py valuation 600519    # 估值指标
python3 tools/ashare_data.py search 茅台          # 搜索代码
```
注：`valuation` 的"推算总股本"是由市值/股价反推，仅供参考；真实市值校验请用 `financial_rigor.py verify-market-cap`。

## momentum_backtest.py / momentum_backtest_v2.py（在线）

标的与时间窗为脚本内置（NVDA/AMD/MU），直接运行：
```bash
python3 tools/momentum_backtest.py
python3 tools/momentum_backtest_v2.py
```

## stock_screener.py（在线）

读取 `data/watchlist.json` 与 `data/fundamentals.json` 做动量+价值筛选：
```bash
python3 tools/stock_screener.py
python3 tools/stock_screener.py --update NVDA   # 更新某标的基本面
```

## portfolio_scan.py（在线，PM 层扫描）

在 `stock_screener` 基础上输出**结构化行动卡草案**（立场 + 建议仓位上限），供 Agent 或组合审视使用；非交易指令。模板见 `docs/action-card.md`。
```bash
python3 tools/portfolio_scan.py                    # 全 watchlist
python3 tools/portfolio_scan.py --group us_ai_chip hk_internet
python3 tools/portfolio_scan.py NVDA MU            # 指定标的
python3 tools/portfolio_scan.py --json --top 5     # JSON + 只列前 5 个买入信号
python3 tools/portfolio_scan.py --json --holdings '{"NVDA":25,"0700.HK":20,"CASH":15}'
```

## portfolio_risk.py（离线，Risk Manager 层）

检查单票/前三集中度、现金占比、watchlist 主题暴露；可选读取 `data/correlation_3stocks_2021-2026.csv` 做高相关告警。

```bash
python3 tools/portfolio_risk.py --holdings '{"NVDA":45,"CASH":55}' --json
python3 tools/portfolio_risk.py --holdings-file portfolio.json --proposed MU 5
```

## thesis_queue.py（离线*，队列同步）

解析 `config/state.md` §1/§2，合并 `portfolio_scan` 买入信号，输出 `research_now` 优先级列表。`--run-scan` 会联网。

```bash
python3 tools/thesis_queue.py --json
python3 tools/thesis_queue.py --from-scan scan.json --suggest-md
```

## morningstar_fair_value.py（在线）

```bash
python3 tools/morningstar_fair_value.py                      # 抓全量(~6000只)并存 CSV 到 data/
python3 tools/morningstar_fair_value.py --max-pages 1 --top 5  # 快速冒烟
```

## xueqiu_scraper.py（在线，需登录）

```bash
python3 tools/xueqiu_scraper.py --user-id <雪球用户ID> --keywords 拼多多,PDD,黄峥 --output /tmp/pdd.md
```
需 `pip install playwright && playwright install chromium`，并提供登录态（`--state-path`，默认 `/tmp/xueqiu_state.json`）。

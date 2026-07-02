# tools/ — 工具链说明

投研流程中由 Agent 通过 shell 调用的辅助工具。所有命令均以仓库根目录为工作目录运行（`python3 tools/xxx.py ...`）。

| 工具 | 作用 | 需要网络 | 额外依赖 |
|---|---|:---:|---|
| `financial_rigor.py` | 金融数据严谨性验证（核心） | 否 | 无 |
| `report_audit.py` | 研究报告数据抽检 / 准出判决 | 否 | 无 |
| `ashare_data.py` | A股行情/财务/估值/搜索/日线 | 是 | curl |
| `data_sources.py` | A股数据**多源降级链**（可插拔适配器） | 是* | curl（内置源）；可选 tushare/efinance/akshare/baostock/yfinance |
| `calibrate_sensitivity.py` | 用真实历史行情**校准** `realized_feedback` 的 `SENSITIVITY` | 是* | 可选 yfinance/akshare/tushare（核心数学离线） |
| `notify.py` | **多通道交付**（Telegram/飞书/本地兜底） | 是* | curl；零配置时只落地本地，不报错 |
| `momentum_backtest.py` | 动量+价值回测（NVDA/AMD/MU） | 是 | curl |
| `momentum_backtest_v2.py` | 回测 v2（框架验证版） | 是 | curl |
| `ashare_factor_mining.py` | A股自动因子挖掘（AlphaGPT times.py 移植） | 是* | `pip install '.[factor-mining]'` |
| `factor_screener_bridge.py` | 已训练公式 → 多标的打分 → thesis_queue JSON | 否* | `pip install '.[factor-mining]'`；优先本地 CSV |
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
python3 tools/ashare_data.py daily 600519 --limit 60  # 近 N 日日线（东方财富 K线）
python3 tools/ashare_data.py search 茅台          # 搜索代码
```
注：`valuation` 的"推算总股本"是由市值/股价反推，仅供参考；真实市值校验请用 `financial_rigor.py verify-market-cap`。

## ashare_factor_mining.py（实验性，需 PyTorch）

移植自 [AlphaGPT times.py](https://github.com/imbue-bit/AlphaGPT/blob/main/times.py)：用 Transformer + REINFORCE 在 A 股/ETF 日线上自动搜索可解释因子公式。

```bash
pip install '.[factor-mining]'
python3 tools/ashare_factor_mining.py train --code 511260 --steps 400
python3 tools/ashare_factor_mining.py train --code 600519 --steps 100 --plot
python3 tools/ashare_factor_mining.py decode --tokens '[0,6,1,7]'
python3 tools/ashare_factor_mining.py oos --formula data/alphagpt/best_ashare_formula.json
```

数据：优先 `data/alphagpt/{code}_ohlcv.parquet` 缓存 → `data_sources.daily` → `ashare_data.fetch_daily`；可选 `TUSHARE_TOKEN` 拉更长历史。

输出：`BERKSHIRE_DATA_DIR/alphagpt/best_ashare_formula.json`（公式 token + 可读字符串）。

## factor_screener_bridge.py（实验性，需已训练公式）

```bash
# 训练基准公式（可转债 ETF 511260）
python3 tools/ashare_factor_mining.py train --code 511260 --steps 200

# 用公式扫描本地 CSV 内全部标的
python3 tools/factor_screener_bridge.py --json -o data/alphagpt/factor_scan.json

# 在线扫描指定代码
python3 tools/factor_screener_bridge.py --codes 600519,000001 --source online --json

# 并入研究待办
python3 tools/thesis_queue.py --from-factor-scan data/alphagpt/factor_scan.json --suggest-md
python3 tools/thesis_queue.py --run-factor-scan --factor-codes 600519,511260 --json
```

## data_sources.py（在线，多源降级链）

A股数据获取的**统一降级层**：按优先级依次尝试数据源，任一源失败/为空自动降级到
下一个；**全部失败返回明确的 `ok=False` 结构，绝不抛崩主流程**。覆盖 `daily`（日线）、
`quote`（实时行情）、`fundamentals`（基本面）。

**默认优先级链**（可用 `--sources` 或 `BERKSHIRE_DATA_SOURCES` 覆盖/排序）：

```
native(内置,零依赖) → tushare(增强,需开关+token) → efinance → akshare → baostock → yfinance
```

```bash
python3 tools/data_sources.py sources                  # 列出各源可用状态（不联网）
python3 tools/data_sources.py daily 600519 --limit 60  # 日线（走降级链）
python3 tools/data_sources.py quote 600519             # 实时行情
python3 tools/data_sources.py fundamentals 600519      # 基本面字段
python3 tools/data_sources.py daily 600519 --json --sources efinance,native
```

**可选依赖与开关（import 守卫，缺库自动跳过该源）：**

| 源 | 需要 | 启用条件 | 关闭方式 |
|---|---|---|---|
| `native` | 仅 curl | 始终启用（零配置可用） | `BERKSHIRE_DISABLE_NATIVE=1` |
| `tushare` | `pip install tushare` | `BERKSHIRE_ENABLE_TUSHARE=1` **且** `TUSHARE_TOKEN` | 默认关闭（零侵入） |
| `efinance` | `pip install efinance` | 装库即启用 | `BERKSHIRE_DISABLE_EFINANCE=1` |
| `akshare` | `pip install akshare` | 装库即启用 | `BERKSHIRE_DISABLE_AKSHARE=1` |
| `baostock` | `pip install baostock` | 装库即启用 | `BERKSHIRE_DISABLE_BAOSTOCK=1` |
| `yfinance` | `pip install yfinance` | 装库即启用 | `BERKSHIRE_DISABLE_YFINANCE=1` |

> 设计范式（吸收自 JusticePlutus）：「增强源」`tushare` 是可选层——开关关闭就**完全不
> 初始化、不导入、不请求**；开关开但缺 token 只记 warning 回退；缺库的源被 import 守卫
> 静默跳过。**零配置时只用内置 `native` 源，行为与改造前一致。**

新增数据源 = 继承 `DataSource`、实现 `enabled()` 与 `daily/quote/fundamentals` 之一，
再注册进 `_REGISTRY` / `_DEFAULT_ORDER` 即可（可插拔适配器）。

## calibrate_sensitivity.py（在线*，SENSITIVITY 尺度校准）

用真实历史日线对 `src/realized_feedback.py` 的 `SENSITIVITY` 做 **data-only 尺度校准**：
在真实观测到的 alpha 分布上选一个 `SENSITIVITY`，让 `realized_base = clip(0.5 +
alpha·S)` 用满 [0,1] 区间而不过度饱和。**核心数学（目标函数 + 搜索）离线、有单测**；
真实取数走 CLI（需联网）。详见 `docs/textgrad_design.md`「SENSITIVITY 尺度校准」。

目标函数（对肥尾稳健）：`J(S) = |spread(p10..p90 of realized_base; S) − 0.80|`，让中位
80% 决策映射到 `realized_base∈[0.1,0.9]`，极端尾部有意留给饱和。搜索 = 网格扫描记录
`J(S)` 曲线 → 黄金分割在 bracket 内细化收敛。

```bash
# 汇总标的（不联网，看 watchlist+holdings 去重结果与市场/yf 代码）
python3 tools/calibrate_sensitivity.py universe

# 联网取数 + 校准 + 报告（主窗 365 天，附 182 天对照）
pip install yfinance akshare tushare
python3 tools/calibrate_sensitivity.py run --lookback 365 --also 182
python3 tools/calibrate_sensitivity.py run --json --out reports/sensitivity.txt
```

**数据源（按市场）：** 美股直接代码（基准 `^GSPC`）；港股 `XXXX.HK`（基准 `^HSI`）；
A股 走 `tushare→akshare→yfinance(.SS/.SZ)` 降级，基准沪深300。

| 用途 | 环境变量 | 说明 |
|---|---|---|
| A股增强源 Tushare | `BERKSHIRE_ENABLE_TUSHARE=1` + `TUSHARE_TOKEN` | **仅作环境变量**，切勿写进文件/提交/日志；报告里用 `<redacted>` |
| 覆盖引擎灵敏度 | `BERKSHIRE_SENSITIVITY` | 不改代码即可覆盖 `realized_feedback` 默认 `SENSITIVITY`（默认 0.5） |

> 校准结论（V10.12，27 标的真实日线）：旧默认 2.5 使 ~78% 的 realized_base 被 clip 到
> 0/1；推荐 **0.5**（12m≈0.41 / 6m≈0.68 的稳健折中），已更新为新默认，保留 env 覆盖。
> Tushare 免费 token 无 `daily`/`index_daily` 接口权限时自动降级到 akshare，不阻断。

## notify.py（在线*，多通道交付）

报告 / 信号的**多通道推送**。全部走环境变量配置，**零配置时只把内容落到本地文件、不报错**
（行为不变）；任一通道未配置即静默跳过；单通道异常不影响其它通道与主流程。

```bash
python3 tools/notify.py channels                            # 查看通道状态
python3 tools/notify.py send --title "标题" --text "正文"
python3 tools/notify.py send --title "组合周报" --file reports/x.md
cat reports/x.md | python3 tools/notify.py send --title "周报"
python3 tools/notify.py send --title "x" --text "y" --channels feishu --local
```

**通道与环境变量：**

| 通道 | 环境变量 | 说明 |
|---|---|---|
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | 超 3800 字自动拆分多条 |
| 飞书自定义机器人 | `FEISHU_WEBHOOK`，可选 `FEISHU_SECRET` | **优先卡片，失败回退纯文本**；超 3000 字自动拆分；配 secret 自动加签 |
| 本地兜底 | `BERKSHIRE_NOTIFY_DIR`（默认 `reports/notifications`） | 始终可用；无远程通道或全部失败时落地 Markdown |

> 切勿把真实 token/webhook 写进代码或提交，统一用环境变量（`.env` 已被 `.gitignore` 忽略）。

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

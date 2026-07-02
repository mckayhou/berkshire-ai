# Quant Data Fusion — 三库调研与 berkshire-ai V10.24 融合决策

> 调研对象（仅作参考，**未整库 fork**）：
> - [henrylin99/tdx_quant](https://github.com/henrylin99/tdx_quant) — pytdx parquet 管道 + 指标 + 选股 + 通达信 MCP
> - [bzcsk2/daily_stock_data](https://github.com/bzcsk2/daily_stock_data) — cron CSV/Postgres 多源 A 股采集
> - [imbue-bit/AlphaGPT](https://github.com/imbue-bit/AlphaGPT) — 加密 meme 因子挖掘 + Solana 实盘（**非 A 股 qlib 栈**）

---

## 1. 各项目实际能力（去营销版）

### tdx_quant

| 维度 | 事实 |
|------|------|
| 定位 | 个人/研究用 **pytdx 历史数据管道** + pandas 技术指标 + 声明式选股 + 静态前端 |
| 市场 | **沪深主板 6 位代码**；`snapshot("AAPL")` 走 exhq 属边缘能力 |
| 存储 | Hive 分区 **parquet**（`daily/ts_code=000001.SZ/data.parquet` 等） |
| 实时 | 通达信 **MCP HTTP**（概念/涨停/资金流），需 `TDX_API_KEY`，与 pytdx 独立 |
| 依赖 | pytdx、pandas、pyarrow、numpy；MCP 需 httpx |
| 失败策略 | 下载层 **fail-fast**（连接/空数据直接 raise） |

### daily_stock_data

| 维度 | 事实 |
|------|------|
| 定位 | **A 股** cron 采集脚本集合，默认 CSV，可选 PostgreSQL |
| 市场 | **仅 A 股**（README、`DATA_SOURCES.md` 全文无 HK/US 采集脚本） |
| 存储 | `DATA_DIR/daily_ohlcv.csv` 等；`symbol` 为 baostock 风格 `sh.600000` |
| 数据源 | Tushare → TickFlow → baostock 日线降级；pytdx 做除权/财务/板块/逐笔/F10 |
| 依赖 | baostock、tushare、pytdx、easyquotation 等（见 requirements.txt） |
| 运维 | `bin/run_*.sh` + `cron.example`，`Asia/Shanghai` 时区 |

**纠错**：「daily_stock_data 支持 A 股/HK/US 日线自动抓取」**不成立**。仓库明确写 A-share only；无港股/美股日线采集任务。

### AlphaGPT

| 维度 | 事实 |
|------|------|
| 定位 | **Solana 链上 meme 币** 因子公式自动生成（Transformer）+ 回测评分 + Jupiter 下单 |
| 与 qlib | **不使用 qlib**；核心为 PyTorch + Postgres + Birdeye/DexScreener |
| A 股 | `times.py` 实验脚本可选用 tushare，**非主链路** |
| 输出 | `best_meme_strategy.json` 公式 token 序列，供 strategy_manager 消费 |
| 契合 berkshire | **低** — 域（加密自动交易）与 TextGrad 定性投研正交 |

---

## 2. 横向对比

| 能力 | berkshire-ai (V10.24 前) | tdx_quant | daily_stock_data | AlphaGPT |
|------|--------------------------|-----------|------------------|----------|
| 运行时取数 | ✅ 多源降级链（curl/HTTP） | ✅ pytdx 实时 | ❌ 偏离线 cron | ❌ 链上 API |
| 本地历史 | ❌ | ✅ parquet | ✅ CSV/PG | ✅ PG OHLCV |
| 技术指标 | 工具层零散 | ✅ 完整注册表 | ❌ | ✅ 因子 DSL |
| 选股 | stock_screener (US curl) | ✅ 多周期 screener | ❌ | ✅ 公式信号 |
| 定性投研 | ✅ 四大师 + TextGrad | ❌ | ❌ | ❌ |
| 失败策略 | **ok=False 优雅降级** | fail-fast | 脚本级日志 | 实盘风控 |
| HK/US | yfinance 兜底 | 边缘 | **不支持** | 不支持 |

---

## 3. V10.24 采纳 vs 仅参考

### ✅ 已采纳（P0）

| 切口 | 实现 | 来源灵感 |
|------|------|----------|
| 本地 CSV 数据源 | `LocalCsvSource` — 读 `BERKSHIRE_DATA_DIR/daily_ohlcv.csv` | daily_stock_data 落盘格式 |
| 可选 pytdx 实时源 | `PytdxSource` — `BERKSHIRE_ENABLE_PYTDX=1` | tdx_quant pytdx 层 |
| 本地选股桥接 | `tools/quant_screener_bridge.py` → thesis_queue JSON | tdx_quant screener 思路（简化版，stdlib CSV） |
| 环境变量文档 | `.env.example` 增补 | 三库凭证模式 |
| 可选 extra | `pip install .[quant]` → pytdx、pyarrow | 重依赖隔离 |

### 📋 仅文档 / 边界（P1–P2，未进核心依赖）

| 项 | 说明 |
|----|------|
| tdx_quant 全管道 | 不迁入 `scripts/data_pipeline/`；指标/选股见 `quant_screener_bridge` 参考层 |
| daily_stock_data cron | 不内嵌；推荐外部 clone + cron，共享 `BERKSHIRE_DATA_DIR` |
| 通达信 MCP | 不封装进 core；可用 `TDX_API_KEY` + 外部 tdx_mcp 脚本 |
| AlphaGPT times.py A股逻辑 | ✅ `tools/ashare_factor_mining.py` + `tools/ashare_alphagpt/`（可选 `[factor-mining]`） |
| 因子筛选 → thesis_queue | ✅ `tools/factor_screener_bridge.py` + `thesis_queue.py --from-factor-scan` |
| 打板五维评分 → thesis_queue | ✅ `tools/limitup_screener_bridge.py` + `limitup_scoring.py`（参考 [TDX-MCP-LHDB-Agent](https://github.com/adambbhe/TDX-MCP-LHDB-Agent)） |
| 通达信 TQ 实盘 MCP | **不实施**（无 Windows）；备忘见 `docs/tdx_mcp_tool_design.md` |
| AlphaGPT 加密主栈 | **明确不做** Solana 实盘 / meme 训练栈并入 core |
| tdx_quant 指标全集 | 不复制 `indicators/`；动量筛选用 bridge 内最小逻辑 |

### ⬜ 明确不做（ROADMAP 对齐）

- qlib / CoSTEER / 多 trace Web viewer 直依赖
- AlphaGPT 训练栈、Solana 执行层并入 berkshire-ai
- 将 daily_stock_data 或 tdx_quant 整库 vendor 进本仓库
- TDX-MCP-LHDB-Agent 整库 vendor（仅采纳评分逻辑）；**Windows 实盘/MCP 不实施**

---

## 4. 推荐使用方式

```text
┌─────────────────────┐     cron      ┌──────────────────────┐
│ daily_stock_data    │ ────────────► │ BERKSHIRE_DATA_DIR/    │
│ (外部 clone)        │   CSV/PG      │ daily_ohlcv.csv        │
└─────────────────────┘               │ daily/ts_code=…/       │
┌─────────────────────┐     parquet     └──────────┬───────────┘
│ tdx_quant           │ ─────────────────────────►│
│ (外部 clone)        │                           │
└─────────────────────┘                           ▼
                                    ┌─────────────────────────┐
                                    │ BERKSHIRE_ENABLE_LOCAL_ │
                                    │ DATA=1                  │
                                    │ LocalCsvSource          │
                                    └──────────┬──────────────┘
                                               │
                    ┌──────────────────────────┼──────────────────┐
                    ▼                          ▼                  ▼
         data_sources.py              quant_screener_bridge   factor_screener_bridge
         (降级链)                      (动量候选 JSON)         (AlphaGPT 因子 JSON)
                    limitup_screener_bridge (五维打板 JSON)
                                               │                  │
                                               └────────┬─────────┘
                                                        ▼
                                               thesis_queue.py
                                               (--from-scan / --from-factor-scan / --from-limitup-scan)
```

**试用（零外部 cron）**：`BERKSHIRE_ENABLE_PYTDX=1` + `pip install .[quant]`，走实时 pytdx（主机可用性不稳定，建议作补充源）。

---

## 5. 风险与运维

| 风险 | 缓解 |
|------|------|
| pytdx 主机失效 | 降级链自动跳过；优先本地 parquet/CSV |
| parquet 布局 | V10.24 仅 CSV；tdx parquet 由外部工具消费 |
| 合规 / 再分发 | 用户自行确认上游 ToS；本层只读本地已落盘数据 |
| AlphaGPT 域错配 | 文档边界 + 默认关闭；勿与 A 股 TextGrad 混为一谈 |

---

## 6. 环境变量速查

| 变量 | 作用 |
|------|------|
| `BERKSHIRE_DATA_DIR` | 本地数据根目录（含 `daily_ohlcv.csv`） |
| `BERKSHIRE_ENABLE_LOCAL_DATA` | `1` 启用 `LocalCsvSource` |
| `BERKSHIRE_ENABLE_PYTDX` | `1` 启用实时 pytdx 源 |
| `BERKSHIRE_PYTDX_HOST` / `PORT` | pytdx 行情主机（可选） |
| `TDX_API_KEY` | 通达信 MCP（外部 tdx_quant 脚本用，本仓库不内置） |
| `BERKSHIRE_ALPHAGPT_REPO` | 外部 AlphaGPT 加密仓库路径（默认不用） |
| `BERKSHIRE_ENABLE_ALPHAGPT` | `1` 允许 subprocess 调外部 AlphaGPT CLI |
| `BERKSHIRE_ALPHAGPT_CODE` | 训练标的（默认 `511260`） |
| `BERKSHIRE_ALPHAGPT_STEPS` / `BATCH` / `MAX_LEN` | 训练超参 |
| `BERKSHIRE_ALPHAGPT_SCORE_MIN` | 因子筛选最低 score（默认 0） |
| `BERKSHIRE_LIMITUP_SCORE_MIN` | 打板五维评分最低分（默认 60） |
| `BERKSHIRE_LIMITUP_MIN_BARS` | 打板评分最少 K 线根数（默认 22） |
| `WENCAI_COOKIE` | 问财选股 Cookie（`pywencai` skill；见 `.env.example`） |

详见 [.env.example](../.env.example)。

---

## 7. finance-quant-skills 增量技能（V10.25）

来源：[lzwme/finance-quant-skills](https://github.com/lzwme/finance-quant-skills)（MIT）。**刻意未安装**与 `data_sources.py` / AkTools MCP 重叠的 `akshare`、`tushare`、`baostock`、`equity-researcher`。

| Skill | 路径 | 用途 | 前置条件 |
|-------|------|------|----------|
| `qmt-docs` | `.agents/skills/qmt-docs` | QMT API 离线文档 + 聚宽迁移 | 无 |
| `joinquant-docs` | `.agents/skills/joinquant-docs` | 聚宽策略/API 离线文档 | 无 |
| `miniqmt` | `.agents/skills/miniqmt` | XtQuant 行情与实盘下单脚本 | 本地 MiniQMT 客户端 |
| `backtrader` | `.agents/skills/backtrader` | 事件驱动回测教学 | `pip install backtrader` |
| `rqalpha` | `.agents/skills/rqalpha` | 米筐 A 股/期货回测 | `pip install rqalpha` |
| `pywencai` | `.agents/skills/pywencai` | 问财自然语言选股 | `WENCAI_COOKIE` |

**安装 / 更新**（项目根目录）：

```bash
npx skills add lzwme/finance-quant-skills \
  --skill qmt-docs --skill joinquant-docs --skill miniqmt \
  --skill backtrader --skill rqalpha --skill pywencai \
  --agent cursor --copy -y
npx skills update   # 后续升级
```

锁文件：`skills-lock.json`。恢复：`npx skills experimental_install`。

**同步到 OpenClaw / QwenPaw**：`./update-platforms.sh`（berkshire skills → OpenClaw；quant skills → OpenClaw + `berkshire_v8/quant-skills/`）。

**典型组合**（与 berkshire 主链路互补，不替代四大师投研）：

- 选股验证：`pywencai` → `tools/data_sources.py` 拉日线 → `backtrader` 回测
- 聚宽→QMT 迁移：`joinquant-docs` + `qmt-docs`（`joinquant-migration.md`）
- 实盘边界：`miniqmt`（需客户端）；数据仍走现有降级链

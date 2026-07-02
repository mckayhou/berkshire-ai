# A 股量化指南（QUANT）

> 数据准备 → 因子挖掘 → 筛选桥接 → 研究队列。  
> 回测验收见 [BACKTEST.md](BACKTEST.md) §1。导航：[docs/README.md](README.md)

---

## 1. 数据准备

### 1.1 目录与环境

```bash
export BERKSHIRE_DATA_DIR=./data
mkdir -p data/alphagpt
```

### 1.2 本地 CSV（筛选 / 动量 / 打板必备）

路径：`$BERKSHIRE_DATA_DIR/daily_ohlcv.csv`

| 列 | 说明 |
|----|------|
| `time` 或 `date` | 日期 |
| `symbol` | baostock 风格 `sh.600519` / `sz.000001` |
| `open`, `high`, `low`, `close` | OHLC |
| `volume` | 成交量 |

**来源**：

- 外部 [daily_stock_data](https://github.com/bzcsk2/daily_stock_data) cron 落盘（推荐）
- 或 `python3 tools/data_sources.py daily 600519 --limit 2000` 手工拼接

启用本地数据源：

```bash
export BERKSHIRE_ENABLE_LOCAL_DATA=1
```

### 1.3 实时 / 在线补充

```bash
python3 tools/data_sources.py daily 600519 --limit 60
python3 tools/ashare_data.py daily 600519 --limit 60
export BERKSHIRE_ENABLE_PYTDX=1   # 可选 pip install -e '.[quant]'
```

边界与三库融合：[quant_data_fusion.md](quant_data_fusion.md)。

---

## 2. AlphaGPT 因子挖掘

### 2.1 安装

```bash
pip install -e '.[factor-mining]'
```

### 2.2 命令一览

| 子命令 | 作用 |
|--------|------|
| `train` | Transformer + REINFORCE 搜索公式 |
| `decode` | token → 可读公式 |
| `oos` | **样本外回测报告** |
| `screen` | 多标的打分（同 factor_screener_bridge） |

```bash
# 训练
python3 tools/ashare_factor_mining.py train --code 511260 --steps 400

# 样本外（回测验收）
python3 tools/ashare_factor_mining.py oos \
  --formula data/alphagpt/best_ashare_formula.json --code 511260

# 解码
python3 tools/ashare_factor_mining.py decode --tokens '[0,6,1,7]'
```

训练数据链：parquet 缓存 → `data_sources` → `ashare_data`。

### 2.3 输出文件

`data/alphagpt/best_ashare_formula.json`：

```json
{
  "formula_tokens": [0, 6, 1],
  "formula": "MUL(RET, ...)",
  "best_score": 1.23
}
```

### 2.4 与回测的关系

- `train`：训练集上内嵌 Sortino 奖励（不单独出报告）
- `oos`：测试集策略表现 → 见 [BACKTEST.md §1.3](BACKTEST.md#13-样本外回测重点看这个)

---

## 3. 五维打板评分

**定位**：盘后/日线级**选股评分**，非实时竞价、**无内置历史收益回测**。

```bash
python3 tools/limitup_screener_bridge.py --json -o data/limitup_scan.json
python3 tools/limitup_screener_bridge.py --codes 600519,000001 --min-score 70 --json
python3 tools/limitup_screener_bridge.py --auction-min 2 --auction-max 7 --top 20 --json
```

### 3.1 五维权重

| 维度 | 权重 | 要点 |
|------|------|------|
| 信号强度 | 25% | 封涨停、接近涨停等 |
| 价格位置 | 20% | MA5/10/20 多头 |
| 量能质量 | 20% | 成交额、量比 |
| 动能指标 | 20% | 涨幅 |
| 风控指标 | 15% | ST、低价、高开过猛 |

### 3.2 与 TDX 原项目差异

移植自 [TDX-MCP-LHDB-Agent](https://github.com/adambbhe/TDX-MCP-LHDB-Agent)；用**日线收盘代理**实盘快照。  
Windows 通达信实盘层**不实施**：见 [tdx_mcp_tool_design.md](tdx_mcp_tool_design.md)。

### 3.3 若要回测打板规则

`limitup` 出候选 → 自写 backtrader 买卖逻辑 → 用 CSV 日线。见 [BACKTEST.md §6](BACKTEST.md#6-打板评分limitup与回测)。

---

## 4. 本地 CSV 动量突破

纯 stdlib，无 torch：

```bash
python3 tools/quant_screener_bridge.py --json
python3 tools/quant_screener_bridge.py --codes 600519,000001 --lookback 20 --vol-mult 1.5 --json
```

逻辑：收盘创 `lookback` 日新高 + 成交量 > 均量 × `vol_mult`。

---

## 5. 筛选桥接 → 研究队列

### 5.1 三条桥

| 桥 | 输出 signal | 命令 |
|----|-------------|------|
| 因子 | `alphagpt_factor` | `factor_screener_bridge.py --json` |
| 打板 | `limitup_scoring` | `limitup_screener_bridge.py --json` |
| 动量 | `momentum_breakout` | `quant_screener_bridge.py --json` |

### 5.2 factor_screener 参数

```bash
python3 tools/factor_screener_bridge.py --json -o data/factor_scan.json
python3 tools/factor_screener_bridge.py --codes 600519,000001 --source online --json
python3 tools/factor_screener_bridge.py --min-score 0.1 --top 30 --json
```

| `--source` | 行为 |
|------------|------|
| `auto` | 优先 CSV；有 `--codes` 且无 CSV 则在线 |
| `csv` | 仅 CSV |
| `online` | 必须 `--codes` |

### 5.3 并入 thesis_queue

```bash
python3 tools/thesis_queue.py --from-factor-scan data/factor_scan.json --suggest-md
python3 tools/thesis_queue.py --from-limitup-scan data/limitup_scan.json --json
python3 tools/thesis_queue.py --run-factor-scan --json
python3 tools/thesis_queue.py --run-limitup-scan --json
```

### 5.4 因子 + 打板叠加（Python）

```python
from ashare_alphagpt.screener import run_screen, enrich_with_limitup_scores

factor = run_screen(source="csv", min_score=0.0)
combined = enrich_with_limitup_scores(factor, min_limitup_score=60)
```

---

## 6. 外部 quant skills（backtrader / rqalpha / 问财）

不替代本仓库核心工具；与主链路**互补**。

```bash
npx skills add lzwme/finance-quant-skills \
  --skill backtrader --skill rqalpha --skill pywencai \
  --agent cursor --copy -y
```

| Skill | 用途 |
|-------|------|
| `backtrader` | 事件驱动回测 |
| `rqalpha` | 米筐式 A 股回测 |
| `pywencai` | 问财选股（需 `WENCAI_COOKIE`） |
| `qmt-docs` / `miniqmt` | QMT（需 Windows 客户端） |

详见 [quant_data_fusion.md §7](quant_data_fusion.md)。

---

## 7. 环境变量

| 变量 | 默认 | 作用 |
|------|------|------|
| `BERKSHIRE_DATA_DIR` | `./data` | 数据根目录 |
| `BERKSHIRE_ENABLE_LOCAL_DATA` | off | 启用 LocalCsvSource |
| `BERKSHIRE_ENABLE_PYTDX` | off | pytdx 实时源 |
| `BERKSHIRE_ALPHAGPT_CODE` | 511260 | 训练默认标的 |
| `BERKSHIRE_ALPHAGPT_STEPS` | 400 | 训练步数 |
| `BERKSHIRE_ALPHAGPT_SCORE_MIN` | 0.0 | 因子筛选最低分 |
| `BERKSHIRE_ALPHAGPT_MIN_BARS` | 80 | 最少 K 线根数 |
| `BERKSHIRE_LIMITUP_SCORE_MIN` | 60 | 打板最低分 |
| `BERKSHIRE_LIMITUP_MIN_BARS` | 22 | 打板最少 K 线 |

完整列表：[.env.example](../.env.example)、[USER_GUIDE.md §13](USER_GUIDE.md#13-环境变量速查)。

---

## 8. 推荐日更工作流

```bash
# 1. 确保 CSV 更新（外部 cron 或手工）
export BERKSHIRE_DATA_DIR=./data

# 2. 并行跑筛选（按需要选）
python3 tools/limitup_screener_bridge.py --json -o data/limitup_scan.json
python3 tools/factor_screener_bridge.py --json -o data/factor_scan.json
python3 tools/quant_screener_bridge.py --json -o data/quant_scan.json

# 3. 合并研究待办
python3 tools/thesis_queue.py --from-limitup-scan data/limitup_scan.json --suggest-md

# 4. 因子周期性重训 + OOS
python3 tools/ashare_factor_mining.py train --code 511260 --steps 400
python3 tools/ashare_factor_mining.py oos --formula data/alphagpt/best_ashare_formula.json
```

---

## 相关文档

- [BACKTEST.md](BACKTEST.md) — 回测路线
- [USER_GUIDE.md](USER_GUIDE.md) — 全功能入口
- [tools/README.md](../tools/README.md) — CLI 细节
- [TESTING.md](../TESTING.md) — `test_limitup_scoring`, `test_factor_*`, `test_quant_*`

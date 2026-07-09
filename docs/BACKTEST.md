# 回测指南（BACKTEST）

> 「回测」在本仓库里有 **5 种不同含义**。先选对路线，再看命令。  
> 导航：[docs/README.md](README.md) | A 股量化：[QUANT.md](QUANT.md) | 引擎：[ENGINE.md](ENGINE.md)

---

## 0. 一分钟选型

| 你想验证… | 用这条路线 | 有历史收益曲线？ |
|-----------|------------|:----------------:|
| 挖出的 **A 股因子公式** 样本外表现 | §1 `train` + `oos` | ✅ |
| **美股** 动量+价值框架（NVDA/AMD/MU） | §3 `momentum_backtest*` | ✅ |
| **四大师决策** 事后对错 / 绩效 | §5 `run_with_realized_feedback` | 单次决策 |
| **研报决策后验 KPI**（命中率/校准/契约） | [RESEARCH_EFFECTIVENESS.md](RESEARCH_EFFECTIVENESS.md) + `posterior_weekly.py` | 批量决策表 |
| **TextGrad** 对历史轨迹的诊断质量 | §4 `test_v10_backtest` 或 §4.1 `trajectory_ab_eval` | ❌（非交易） |
| **打板 / limitup 评分规则** | §6 需自建 backtrader | 仓库未内置 |
| **完整事件驱动** A 股策略 | §2 backtrader / rqalpha | 需自写策略 |

---

## 1. A 股因子回测（AlphaGPT）

**定位**：训练时用 Sortino 类奖励在训练集上选公式；**样本外**用 `oos` 看测试集表现。  
**不是**：全市场多标的组合回测、也不是打板策略回测。

### 1.1 安装

```bash
pip install -e '.[factor-mining]'
```

### 1.2 训练（内嵌训练集回测）

```bash
python3 tools/ashare_factor_mining.py train --code 511260 --steps 400
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--code` | 511260 | 训练用单标的（ETF/股票 6 位代码） |
| `--steps` | 400 | REINFORCE 迭代步数 |
| `--batch` | 1024 | 每步采样公式数 |
| `--max-len` | 8 | 公式最大 token 长度 |
| `--cost` | 0.0005 | 单边交易成本率 |
| `--start` | env | 数据起始 YYYYMMDD |
| `--train-end` | env | 训练/测试切分点 |
| `--test-end` | env | 数据结束日 |
| `--no-oos` | off | 训练结束跳过自动 OOS |
| `--plot` | off | 保存训练曲线图 |

环境变量见 [QUANT.md §7](QUANT.md#7-环境变量)。

输出：`$BERKSHIRE_DATA_DIR/alphagpt/best_ashare_formula.json`。

**训练集回测**在 `tools/ashare_alphagpt/backtest.py::backtest_sortino` 中完成，给 miner 提供奖励信号；不单独出报告。

### 1.3 样本外回测（重点看这个）

```bash
python3 tools/ashare_factor_mining.py oos \
  --formula data/alphagpt/best_ashare_formula.json \
  --code 511260
```

**报告字段**（`tools/ashare_alphagpt/oos.py`）：

| 字段 | 含义 |
|------|------|
| Test Period | 测试区间（`train-end` 之后 ~ `test-end`） |
| Ann. Return | 年化收益（open-to-open 口径） |
| Ann. Volatility | 年化波动 |
| Sharpe Ratio | 夏普 |
| Max Drawdown | 最大回撤 |
| Calmar Ratio | 年化收益 / 最大回撤 |
| Total Return | 测试期总收益 |

### 1.4 训练 vs OOS vs 筛选

| 步骤 | 命令 | 作用 |
|------|------|------|
| 训练集回测 | `train` 内部 | 选公式，防过拟合靠切分 + OOS |
| 样本外回测 | `oos` | **策略表现验收** |
| 多标的打分 | `factor_screener_bridge` | 用公式筛票，**不是回测** |

### 1.5 最小验收

```bash
pip install -e '.[factor-mining]'
python3 tools/ashare_factor_mining.py train --code 511260 --steps 200
python3 tools/ashare_factor_mining.py oos --formula data/alphagpt/best_ashare_formula.json
python3 -m pytest tests/test_ashare_alphagpt.py tests/test_factor_screener_bridge.py -v
```

---

## 2. 事件驱动回测（backtrader / rqalpha）

**berkshire 核心仓库没有**统一 backtrader CLI；仅通过 [quant_data_fusion.md §7](quant_data_fusion.md) 引用外部 skill。

### 2.1 推荐数据准备

```bash
export BERKSHIRE_DATA_DIR=./data
# daily_ohlcv.csv：time,symbol,open,high,low,close,volume
python3 tools/data_sources.py daily 600519 --limit 2000 --json  # 或外部 cron 落盘
```

### 2.2 安装 skill 文档

```bash
npx skills add lzwme/finance-quant-skills \
  --skill backtrader --skill rqalpha --agent cursor --copy -y
pip install backtrader   # 或 rqalpha
```

### 2.3 典型组合

```text
pywencai 选股 → data_sources 拉日线 → 自写 backtrader Strategy → 回测报告
```

打板 / limitup 候选 → 在 backtrader 里实现买卖规则 → 用 CSV 日线回测。

---

## 3. 美股动量回测（演示）

内置标的：**NVDA / AMD / MU**；区间约 2022–2025；Yahoo Finance。

```bash
python3 tools/momentum_backtest.py
python3 tools/momentum_backtest_v2.py
```

- 需外网
- 验证「动量发现 + 价值验证」框架，与 A 股因子栈无关
- 无 CLI 参数；改标的需编辑脚本

---

## 4. TextGrad 轨迹「回测」（诊断覆盖率）

**不是交易回测。** 用历史 Agent 轨迹验证计算图能否识别需改进节点。

```bash
# 需轨迹目录（默认 ~/.qwenpaw/berkshire_traces/*.json）
python3 tests/test_v10_backtest.py
```

| 项 | 说明 |
|----|------|
| 输入 | `berkshire_traces/*.json` |
| 输出 | 诊断覆盖率等指标 |
| pytest | **不在** pytest 集合内，单独脚本 |

详见 [TESTING.md §11 FAQ](../TESTING.md#11-已知限制与排错)。

### 4.1 离线 A/B（V10.27，推荐发版门控）

不依赖 `~/.qwenpaw/berkshire_traces`，使用 bundled fixtures：

```bash
python3 tools/trajectory_ab_eval.py
python3 tools/trajectory_ab_eval.py --tasks tests/fixtures/trajectories/sample_tasks.json --json
```

| 项 | 说明 |
|----|------|
| 对比 | V9.3 整体均分 vs V10 节点诊断覆盖率 vs V10.26 `rerun_analysis` 进化 Δ |
| 通过 | exit 0 当诊断覆盖率 ≥ 90% |
| pytest | `tests/test_trajectory_ab.py` |

---

## 5. 决策事后绩效（realized_feedback + perf_metrics）

针对 **单次四大师决策**：用已实现价格算 alpha → 校准各大师评分。

### 5.1 Python API

```python
from src import DecisionRecord, run_with_realized_feedback
from src.realized_feedback import StaticPriceProvider

d = DecisionRecord(
    ticker="600519", date="2026-01-02",
    scores={"duan": 0.9, "buffett": 0.8, "munger": 0.6, "lilu": 0.7},
    price_anchor=1500.0, benchmark="000300", benchmark_anchor=3800.0,
)
provider = StaticPriceProvider({
    ("600519", "2026-03-31"): 1650.0,
    ("000300", "2026-03-31"): 3900.0,
})
result = run_with_realized_feedback(
    d, realized_date="2026-03-31", price_provider=provider,
    persist=True, include_perf=True,
)
# result["perf"] → 夏普、回撤等摘要（tools/perf_metrics.py）
```

### 5.2 HTTP 服务

```bash
pip install -e '.[service]'
berkshire-serve   # 或 python -m uvicorn ...
# POST /score  body: ticker, scores, price_anchor, realized_price, ...
```

见 [ENGINE.md §6](ENGINE.md#6-http-服务可选)。

### 5.3 灵敏度校准

```bash
python3 tools/calibrate_sensitivity.py run --lookback 365 --json
```

校准 `BERKSHIRE_SENSITIVITY`（收益→评分映射），见 [ENGINE.md §5](ENGINE.md#5-校准工具)。

---

## 6. 打板评分（limitup）与回测

| 能力 | 命令 | 是否回测 |
|------|------|:--------:|
| 五维打板评分筛选 | `limitup_screener_bridge.py` | ❌ 仅选股 |
| 历史收益验证 | 需 §2 backtrader 自建 | 自行实现 |

`limitup_screener_bridge` 用日线**代理**涨停/竞价信号，适合盘后研究队列，**不能**替代策略历史回测。  
筛选用法见 [QUANT.md §3](QUANT.md#3-五维打板评分)。

---

## 7. 对照总表

| 路线 | 入口 | 文档 | 测试 |
|------|------|------|------|
| 因子 OOS | `ashare_factor_mining oos` | 本文 §1, QUANT §2 | test_ashare_alphagpt |
| 美股动量 | `momentum_backtest.py` | 本文 §3 | 手工冒烟 |
| 轨迹诊断（离线） | `trajectory_ab_eval.py` | 本文 §4.1 | test_trajectory_ab |
| 轨迹诊断（live traces） | `test_v10_backtest.py` | 本文 §4 | TESTING FAQ |
| 决策绩效 | `run_with_realized_feedback` | ENGINE §4 | test_realized_feedback_loop |
| backtrader | 自写策略 | quant_data_fusion §7 | — |
| 打板 | limitup 筛选 + backtrader | QUANT §3, 本文 §6 | test_limitup_scoring |

---

## 相关文档

- [QUANT.md](QUANT.md) — 数据与筛选
- [ENGINE.md](ENGINE.md) — 引擎与 API
- [TESTING.md](../TESTING.md) — 自动化测试
- [tools/README.md](../tools/README.md) — CLI 参数

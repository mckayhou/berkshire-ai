#!/usr/bin/env python3
"""
本地绩效指标库（借鉴 Qlib risk_analysis 口径，纯 stdlib 零依赖）。

为什么需要它
--------------------------------------------------
现状 `tools/momentum_backtest*` 与 `src/realized_feedback` 只产出「点对点总收益率%」，
没有任何**风险调整指标**（年化、波动、夏普/信息比率、最大回撤）。这是「证明自进化
真的赚钱」缺的最后一块拼图。本模块借 [microsoft/qlib] `risk_analysis` 的**指标定义
与口径**（借口径，不借包）：

- 累计收益用**求和**口径（对齐 Qlib「避免指数级失真」），另留 compound 备选；
- 年化收益 = mean(returns) × periods；
- 年化波动 = std(returns) × √periods；
- 信息比率/夏普 = mean / std × √periods；
- 最大回撤 = 累计净值的峰谷最大跌幅。

工程约束（与本项目一致）
--------------------------------------------------
- 纯函数 + 标准库，**零第三方依赖**，完全离线可单测；
- 接 `decision_log` 决策快照 + **可注入/可 mock 的 PriceProvider**（鸭子类型，仅需
  `.get_price(ticker, date)`）拼净值/超额曲线，不在本模块发起任何网络；
- 边界（空序列/单点/零波动）返回明确值，绝不抛异常崩链路。
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence

DEFAULT_PERIODS = 252  # 日频年化基数（A股/美股约 250~252 交易日）


# ---------------------------------------------------------------------------
# 基础统计（纯函数，输入 list[float]）
# ---------------------------------------------------------------------------
def returns_from_prices(prices: Sequence[float]) -> List[float]:
    """价格序列 → 简单（算术）收益序列。长度 < 2 返回 []。"""
    out: List[float] = []
    for prev, cur in zip(prices, list(prices)[1:]):
        if prev is None or cur is None or float(prev) == 0.0:
            continue
        out.append((float(cur) - float(prev)) / float(prev))
    return out


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: Sequence[float]) -> float:
    """样本标准差（ddof=1，与 pandas/Qlib 默认一致）。n<2 返回 0.0。"""
    n = len(xs)
    if n < 2:
        return 0.0
    mu = _mean(xs)
    var = sum((x - mu) ** 2 for x in xs) / (n - 1)
    return math.sqrt(var)


def cumulative_return(returns: Sequence[float], method: str = "sum") -> float:
    """累计收益。默认 **sum**（对齐 Qlib，避免指数级失真）；method='compound' 为累乘。"""
    if not returns:
        return 0.0
    if method == "compound":
        acc = 1.0
        for r in returns:
            acc *= (1.0 + r)
        return acc - 1.0
    return float(sum(returns))


def annualized_return(returns: Sequence[float], periods: int = DEFAULT_PERIODS) -> float:
    """年化收益 = mean(returns) × periods（加法口径，对齐 Qlib）。"""
    return _mean(returns) * periods


def volatility(returns: Sequence[float], periods: int = DEFAULT_PERIODS) -> float:
    """年化波动 = std(returns) × √periods。"""
    return _std(returns) * math.sqrt(periods)


def sharpe(returns: Sequence[float], rf: float = 0.0, periods: int = DEFAULT_PERIODS) -> float:
    """夏普比率 = mean(excess) / std(excess) × √periods。零波动返回 0.0。

    rf 为**每期**无风险利率（默认 0）。
    """
    if len(returns) < 2:
        return 0.0
    excess = [r - rf for r in returns]
    sd = _std(excess)
    if sd == 0.0:
        return 0.0
    return _mean(excess) / sd * math.sqrt(periods)


def information_ratio(
    returns: Sequence[float],
    benchmark: Sequence[float],
    periods: int = DEFAULT_PERIODS,
) -> float:
    """信息比率 = mean(超额) / std(超额) × √periods。逐元素对齐取较短长度。"""
    n = min(len(returns), len(benchmark))
    if n < 2:
        return 0.0
    excess = [returns[i] - benchmark[i] for i in range(n)]
    sd = _std(excess)
    if sd == 0.0:
        return 0.0
    return _mean(excess) / sd * math.sqrt(periods)


def max_drawdown(series: Sequence[float], *, is_nav: bool = False) -> float:
    """最大回撤（≤0；无回撤返回 0.0）。

    - is_nav=False（默认）：把 `series` 当作收益序列，按**求和**口径构造累计净值后算回撤；
    - is_nav=True：把 `series` 当作净值水平直接算峰谷回撤。
    """
    if not series:
        return 0.0
    if is_nav:
        nav = list(series)
    else:
        nav = []
        acc = 0.0
        for r in series:
            acc += r
            nav.append(acc)
    peak = nav[0]
    mdd = 0.0
    for v in nav:
        if v > peak:
            peak = v
        dd = v - peak  # ≤ 0（加法净值口径下为绝对跌幅）
        if dd < mdd:
            mdd = dd
    return mdd


def win_rate(returns: Sequence[float]) -> float:
    """胜率 = 正收益期数 / 总期数。空序列返回 0.0。"""
    if not returns:
        return 0.0
    return sum(1 for r in returns if r > 0) / len(returns)


# ---------------------------------------------------------------------------
# 汇总报告
# ---------------------------------------------------------------------------
@dataclass
class PerfReport:
    """一段收益序列的标准绩效指标（控制流读字段，不解析文本）。"""

    n: int
    periods: int
    cumulative_return: float
    annualized_return: float
    volatility: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    # 相对基准（仅 has_benchmark 时有意义）
    has_benchmark: bool = False
    benchmark_cumulative: float = 0.0
    excess_cumulative: float = 0.0          # CAR：累计超额（求和口径）
    information_ratio: float = 0.0
    annualized_excess: float = 0.0          # 年化超额（≈ alpha）
    # 含成本口径（cost>0 时与不含口径不同）
    cost: float = 0.0
    net_cumulative_return: float = 0.0
    net_annualized_return: float = 0.0
    net_sharpe: float = 0.0

    extra: Dict[str, float] = field(default_factory=dict)


def risk_analysis(
    returns: Sequence[float],
    benchmark: Optional[Sequence[float]] = None,
    *,
    cost: float = 0.0,
    periods: int = DEFAULT_PERIODS,
    rf: float = 0.0,
) -> PerfReport:
    """一次性产出 Qlib 风格的全套绩效指标。

    Args:
        returns: 标的（策略）每期收益序列。
        benchmark: 基准每期收益序列（可选）；给出则附超额/IR/年化超额。
        cost: **每期**成本（如单边费率摊到每期），用于「含成本」口径；默认 0。
        periods: 年化基数（日频 252）。
        rf: 每期无风险利率（夏普用）。

    空序列返回全 0 的报告（不崩）。
    """
    rets = [float(r) for r in (returns or [])]
    report = PerfReport(
        n=len(rets),
        periods=periods,
        cumulative_return=cumulative_return(rets, "sum"),
        annualized_return=annualized_return(rets, periods),
        volatility=volatility(rets, periods),
        sharpe=sharpe(rets, rf, periods),
        max_drawdown=max_drawdown(rets),
        win_rate=win_rate(rets),
        cost=cost,
    )

    if benchmark is not None:
        bench = [float(b) for b in benchmark]
        m = min(len(rets), len(bench))
        excess = [rets[i] - bench[i] for i in range(m)]
        report.has_benchmark = True
        report.benchmark_cumulative = cumulative_return(bench, "sum")
        report.excess_cumulative = cumulative_return(excess, "sum")
        report.information_ratio = information_ratio(rets, bench, periods)
        report.annualized_excess = annualized_return(excess, periods)

    # 含成本口径：逐期扣减成本
    net = [r - cost for r in rets]
    report.net_cumulative_return = cumulative_return(net, "sum")
    report.net_annualized_return = annualized_return(net, periods)
    report.net_sharpe = sharpe(net, rf, periods)

    return report


# ---------------------------------------------------------------------------
# 桥接：decision_log 决策快照 + 可注入 PriceProvider → 绩效报告
# ---------------------------------------------------------------------------
def price_path_from_provider(ticker: str, dates: Sequence[str], provider) -> List[float]:
    """用可注入 provider（鸭子类型：`.get_price(ticker, date)`）取一条价格路径。

    取价失败（KeyError 等）的日期被跳过，不崩；返回成功取到的价格序列（按入参顺序）。
    """
    path: List[float] = []
    for d in dates:
        try:
            path.append(float(provider.get_price(ticker, d)))
        except Exception:  # noqa: BLE001 - 单点取价失败跳过，不影响整体
            continue
    return path


def analyze_price_path(
    prices: Sequence[float],
    benchmark_prices: Optional[Sequence[float]] = None,
    *,
    cost: float = 0.0,
    periods: int = DEFAULT_PERIODS,
) -> PerfReport:
    """价格路径（及可选基准路径）→ 收益序列 → 绩效报告。"""
    rets = returns_from_prices(prices)
    bench = returns_from_prices(benchmark_prices) if benchmark_prices is not None else None
    return risk_analysis(rets, bench, cost=cost, periods=periods)


def analyze_decision(
    decision,
    eval_dates: Sequence[str],
    provider,
    *,
    cost: float = 0.0,
    periods: int = DEFAULT_PERIODS,
) -> PerfReport:
    """单条决策快照（鸭子类型，需 `.ticker/.price_anchor/.benchmark/.benchmark_anchor`）
    + 后续若干评估日的 provider 取价 → 该持仓的净值曲线绩效。

    以决策锚点为 t0，eval_dates 为后续观测点，构造价格路径；若决策含基准锚点，
    同步构造基准路径并算超额。任意一侧取价不足 2 点 → 该侧指标为 0（不崩）。
    """
    path = [float(decision.price_anchor)] + price_path_from_provider(
        decision.ticker, eval_dates, provider
    )
    bench_path: Optional[List[float]] = None
    if getattr(decision, "benchmark", None) and getattr(decision, "benchmark_anchor", None):
        bench_path = [float(decision.benchmark_anchor)] + price_path_from_provider(
            decision.benchmark, eval_dates, provider
        )
    return analyze_price_path(path, bench_path, cost=cost, periods=periods)


# ---------------------------------------------------------------------------
# 渲染（JSON / Markdown）
# ---------------------------------------------------------------------------
def to_json(report: PerfReport) -> Dict[str, object]:
    """结构化 JSON（dict）。"""
    return asdict(report)


def render_markdown(report: PerfReport) -> str:
    """人读 Markdown 表（含/不含成本两行；有基准时附超额）。"""
    lines = [
        "| 指标 | 值 |",
        "|---|---|",
        f"| 样本期数 | {report.n} |",
        f"| 累计收益(求和) | {report.cumulative_return:+.4f} |",
        f"| 年化收益 | {report.annualized_return:+.4f} |",
        f"| 年化波动 | {report.volatility:.4f} |",
        f"| 夏普 | {report.sharpe:.3f} |",
        f"| 最大回撤 | {report.max_drawdown:+.4f} |",
        f"| 胜率 | {report.win_rate:.2%} |",
    ]
    if report.has_benchmark:
        lines += [
            f"| 基准累计 | {report.benchmark_cumulative:+.4f} |",
            f"| 累计超额(CAR) | {report.excess_cumulative:+.4f} |",
            f"| 信息比率(IR) | {report.information_ratio:.3f} |",
            f"| 年化超额(α) | {report.annualized_excess:+.4f} |",
        ]
    if report.cost > 0:
        lines += [
            f"| 累计收益(含成本) | {report.net_cumulative_return:+.4f} |",
            f"| 年化收益(含成本) | {report.net_annualized_return:+.4f} |",
            f"| 夏普(含成本) | {report.net_sharpe:.3f} |",
        ]
    return "\n".join(lines)

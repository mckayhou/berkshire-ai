#!/usr/bin/env python3
"""
已实现收益 → 评分 转换器（反馈闭环的核心）。

借鉴 TradingAgents：跑完一笔决策后，事后用真实价格算出
  - raw return（标的自身涨跌幅）
  - alpha（相对基准的超额收益）
并把它映射成 0~1 的"各大师评分"，喂回 BerkshireGraph.backward()，
替代原来硬编码的 {"duan":0.92,...}。

映射规则（明确、可测、确定性）
--------------------------------------------------
1) 收益锚定的"真相分" realized_base ∈ [0,1]：
       realized_base = clip(0.5 + alpha * SENSITIVITY, 0, 1)
   - alpha = 0      → 0.5（与基准持平，中性）
   - alpha = +1/SENS 的一半 → 越接近 1（决策被市场证明正确）
   - alpha 为负     → 越接近 0（决策被证伪）

2) 每位大师的"校准分"（reward）：
       master_score = clip(1 - |conviction - realized_base|, 0, 1)
   conviction 即决策当时该大师的信心分。
   - 信心与真相一致（看多且涨 / 看空且跌）→ 高分（无需优化）
   - 信心与真相背离（高信心却被证伪）→ 低分（触发 TextGrad 优化其 prompt）

这套规则把"反思"变成可微的 reward：奖励校准良好的大师，
惩罚系统性过度自信/过度保守的大师，正是 backward() 想要的信号。

工程约束：价格通过可注入/可 mock 的 PriceProvider 获取，核心不连网络。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

try:
    from graph import MASTER_PREFIXES
    from decision_log import DecisionRecord
except ImportError:  # pragma: no cover - 包内导入回退
    from .graph import MASTER_PREFIXES
    from .decision_log import DecisionRecord


# 基线灵敏度。该值由 tools/calibrate_sensitivity.py 用真实历史行情做「尺度校准」
# 得出：让 realized_base = clip(0.5 + alpha*SENSITIVITY) 对真实观测到的 alpha 分布
# 用满 [0,1] 区间而不过度饱和（详见 docs/textgrad_design.md「SENSITIVITY 尺度校准」）。
#
# 校准结论（27 个标的真实日线，2025-2026）：旧默认 2.5 严重过饱和——~78% 的
# realized_base 被 clip 到 0/1。在「中位 80% 决策映射到 realized_base∈[0.1,0.9]」
# 目标下，12 个月窗最优 ≈0.41、6 个月窗最优 ≈0.68；取稳健折中 0.5（直觉：±100%
# 的相对超额收益即为最大信号，0.5 ± alpha*0.5 触达 [0,1] 边界）。
# 环境变量 BERKSHIRE_SENSITIVITY 可在不改代码的前提下覆盖（零侵入）。
ENV_SENSITIVITY = "BERKSHIRE_SENSITIVITY"
_BASE_SENSITIVITY = 0.5


def _resolve_default_sensitivity() -> float:
    """默认灵敏度：环境变量 BERKSHIRE_SENSITIVITY 优先，否则用校准基线。

    仅接受正数；非法/非正值静默回退到基线，绝不抛错（零侵入）。
    """
    raw = os.environ.get(ENV_SENSITIVITY, "").strip()
    if raw:
        try:
            val = float(raw)
            if val > 0:
                return val
        except ValueError:
            pass
    return _BASE_SENSITIVITY


# alpha = +(0.5/SENSITIVITY) 时 realized_base 达到 1.0（强烈正反馈）
DEFAULT_SENSITIVITY = _resolve_default_sensitivity()


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


# ---------------------------------------------------------------------------
# 价格来源：可注入/可 mock 的接口（核心引擎不硬连网络）
# ---------------------------------------------------------------------------
class PriceProvider:
    """价格来源抽象接口。实现 get_price(ticker, date) -> float。"""

    def get_price(self, ticker: str, date: str) -> float:  # pragma: no cover - 抽象
        raise NotImplementedError


class StaticPriceProvider(PriceProvider):
    """用内存字典提供价格，便于测试/回放（不连网络）。

    prices: {(TICKER, "YYYY-MM-DD"): price}
    """

    def __init__(self, prices: Dict[Tuple[str, str], float]):
        self._prices = {(str(t).strip().upper(), d): float(p) for (t, d), p in prices.items()}

    def get_price(self, ticker: str, date: str) -> float:
        key = (str(ticker).strip().upper(), date)
        if key not in self._prices:
            raise KeyError(f"无价格数据: {key}")
        return self._prices[key]


@dataclass
class ReturnStats:
    """一次已实现收益的结构化结果（控制流读字段，不解析文本）。"""

    ticker: str
    raw_return: float            # 标的涨跌幅
    benchmark_return: float      # 基准涨跌幅（无基准记 0.0）
    alpha: float                 # raw_return - benchmark_return
    realized_base: float         # 收益锚定的真相分 ∈ [0,1]
    has_benchmark: bool


def compute_returns(
    decision: DecisionRecord,
    realized_price: float,
    benchmark_realized_price: Optional[float] = None,
    sensitivity: float = DEFAULT_SENSITIVITY,
) -> ReturnStats:
    """由决策锚点 + 后续价格计算 raw return / alpha / realized_base。"""
    if realized_price is None or float(realized_price) <= 0:
        raise ValueError(f"realized_price 必须为正数: {realized_price}")
    raw_return = (float(realized_price) - decision.price_anchor) / decision.price_anchor

    has_benchmark = (
        decision.benchmark_anchor is not None and benchmark_realized_price is not None
    )
    if has_benchmark:
        if float(benchmark_realized_price) <= 0:
            raise ValueError("benchmark_realized_price 必须为正数")
        benchmark_return = (
            float(benchmark_realized_price) - decision.benchmark_anchor
        ) / decision.benchmark_anchor
    else:
        benchmark_return = 0.0

    alpha = raw_return - benchmark_return
    realized_base = _clip01(0.5 + alpha * sensitivity)

    return ReturnStats(
        ticker=decision.ticker,
        raw_return=raw_return,
        benchmark_return=benchmark_return,
        alpha=alpha,
        realized_base=realized_base,
        has_benchmark=has_benchmark,
    )


def realized_scores(
    decision: DecisionRecord,
    realized_price: float,
    benchmark_realized_price: Optional[float] = None,
    sensitivity: float = DEFAULT_SENSITIVITY,
) -> Tuple[Dict[str, float], ReturnStats]:
    """把已实现收益映射成 {prefix: score}（喂给 graph.backward）。

    返回 (scores, stats)。对缺失 conviction 的大师，conviction 视为 0.5（中性）。
    """
    stats = compute_returns(
        decision, realized_price, benchmark_realized_price, sensitivity
    )
    scores: Dict[str, float] = {}
    for prefix in MASTER_PREFIXES:
        conviction = decision.scores.get(prefix, 0.5)
        scores[prefix] = _clip01(1.0 - abs(conviction - stats.realized_base))
    return scores, stats


def realized_scores_via_provider(
    decision: DecisionRecord,
    realized_date: str,
    provider: PriceProvider,
    sensitivity: float = DEFAULT_SENSITIVITY,
) -> Tuple[Dict[str, float], ReturnStats]:
    """通过 PriceProvider 拉取 realized_date 的价格后再映射（可 mock）。"""
    realized_price = provider.get_price(decision.ticker, realized_date)
    benchmark_realized_price = None
    if decision.benchmark and decision.benchmark_anchor is not None:
        benchmark_realized_price = provider.get_price(decision.benchmark, realized_date)
    return realized_scores(
        decision, realized_price, benchmark_realized_price, sensitivity
    )

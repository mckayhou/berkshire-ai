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

import json
import os
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

try:
    from .decision_log import DecisionRecord
    from .graph import MASTER_PREFIXES
except ImportError:  # pragma: no cover - flat PYTHONPATH=src
    from decision_log import DecisionRecord
    from graph import MASTER_PREFIXES


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


def _norm_date(value: object) -> Optional[str]:
    """把各源日期统一成 'YYYY-MM-DD'（可按字典序比较 = 按时间比较）。

    兼容 '20240105' / '2024-01-05' / '2024-01-05 00:00:00' 等；无法解析返回 None。
    """
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) < 8:
        return None
    y, m, d = digits[0:4], digits[4:6], digits[6:8]
    return f"{y}-{m}-{d}"


ENV_PRICE_CACHE_DIR = "BERKSHIRE_PRICE_CACHE_DIR"
ENV_PRICE_CACHE_TTL = "BERKSHIRE_PRICE_CACHE_TTL"  # 秒，默认 86400（1 天）
_DEFAULT_CACHE_TTL = 86400
DailyFetcher = Callable[[str, int], dict]


def _default_daily_fetcher(code: str, limit: int) -> dict:
    """默认取数：惰性接入 tools/data_sources（多源降级链）。

    src/ 不在导入期硬依赖 tools/，仅在真正取数时才尝试导入；不可用时返回
    ok=False 的明确结构（与 data_sources.fetch 失败结构一致），不抛 ImportError。
    """
    try:
        import os as _os
        import sys as _sys

        _tools = _os.path.join(_os.path.dirname(__file__), "..", "tools")
        if _tools not in _sys.path:
            _sys.path.insert(0, _tools)
        import data_sources  # type: ignore
    except Exception as e:  # noqa: BLE001 - 缺 tools/ 路径或库 → 优雅失败
        return {"ok": False, "data": None, "error": f"data_sources 不可用: {e}"}
    return data_sources.daily(code, limit=limit)


class NetworkPriceProvider(PriceProvider):
    """接真实行情的价格源：经 tools/data_sources 多源降级链取日线，内存缓存。

    设计（与既有工程约束一致）：
    - **可注入 fetcher**：默认走 data_sources.daily（native→tushare→…→yfinance 降级链）；
      测试传入 mock fetcher 即可完全离线。
    - **内存缓存**：每个 ticker 的整条日线只取一次，构建 {date: close} 映射，
      一次 run 内多次 get_price 不重复取数。
    - **非交易日回退**：请求日无 bar 时，回退到该日**之前最近的交易日**收盘价
      （周末/节假日/停牌常见）。可用 fallback_to_prior=False 关闭。
    - 整段无数据 → 抛 KeyError（与 StaticPriceProvider 行为一致，让调用方可感知）。
    """

    def __init__(
        self,
        *,
        fetcher: Optional[DailyFetcher] = None,
        sources: Optional[list] = None,
        limit: int = 250,
        fallback_to_prior: bool = True,
        disk_cache_dir: Optional[str] = None,
        disk_cache_ttl: Optional[int] = None,
    ):
        self._fetcher: DailyFetcher = fetcher or _default_daily_fetcher
        self._sources = sources
        self._limit = limit
        self._fallback_to_prior = fallback_to_prior
        self._cache: Dict[str, Dict[str, float]] = {}
        self._disk_cache_dir = disk_cache_dir or os.environ.get(ENV_PRICE_CACHE_DIR, "").strip() or None
        raw_ttl = disk_cache_ttl
        if raw_ttl is None:
            env_ttl = os.environ.get(ENV_PRICE_CACHE_TTL, "").strip()
            if env_ttl:
                try:
                    raw_ttl = int(env_ttl)
                except ValueError:
                    raw_ttl = _DEFAULT_CACHE_TTL
            else:
                raw_ttl = _DEFAULT_CACHE_TTL
        self._disk_cache_ttl = max(0, int(raw_ttl))

    def _disk_cache_file(self, ticker: str) -> Optional[str]:
        if not self._disk_cache_dir:
            return None
        key = str(ticker).strip().upper()
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        return os.path.join(self._disk_cache_dir, f"{safe}.json")

    def _load_disk_cache(self, ticker: str) -> Optional[Dict[str, float]]:
        path = self._disk_cache_file(ticker)
        if not path or not os.path.isfile(path):
            return None
        if self._disk_cache_ttl > 0:
            age = time.time() - os.path.getmtime(path)
            if age > self._disk_cache_ttl:
                return None
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return {str(k): float(v) for k, v in data.items()}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None
        return None

    def _save_disk_cache(self, ticker: str, series: Dict[str, float]) -> None:
        path = self._disk_cache_file(ticker)
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(series, fh, ensure_ascii=False)
        except OSError:
            pass

    def _series(self, ticker: str) -> Dict[str, float]:
        key = str(ticker).strip().upper()
        if key in self._cache:
            return self._cache[key]
        disk_series = self._load_disk_cache(key)
        if disk_series is not None:
            self._cache[key] = disk_series
            return disk_series
        series: Dict[str, float] = {}
        try:
            res = self._fetcher(ticker, self._limit)
        except Exception:  # noqa: BLE001 - 取数异常 → 视为空序列，不崩
            res = None
        if res and res.get("ok") and res.get("data"):
            for bar in res["data"]:
                nd = _norm_date(bar.get("date"))
                raw_close = bar.get("close")
                if nd is None or raw_close is None or raw_close == "":
                    continue
                try:
                    series[nd] = float(raw_close)
                except (TypeError, ValueError):
                    continue
        self._cache[key] = series
        if series:
            self._save_disk_cache(key, series)
        return series

    def get_price(self, ticker: str, date: str) -> float:
        series = self._series(ticker)
        if not series:
            raise KeyError(f"无价格数据（取数失败或为空）: {ticker}")
        nd = _norm_date(date)
        if nd is None:
            raise KeyError(f"非法日期: {date!r}")
        if nd in series:
            return series[nd]
        if self._fallback_to_prior:
            prior = [d for d in series if d <= nd]
            if prior:
                return series[max(prior)]
        raise KeyError(f"无 {ticker} 在 {nd}（或之前）的价格")


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
        # has_benchmark 已保证二者非空，显式断言让类型检查器收窄类型
        assert benchmark_realized_price is not None
        assert decision.benchmark_anchor is not None
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

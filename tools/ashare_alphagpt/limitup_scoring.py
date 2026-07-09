"""五维打板评分（移植自 TDX-MCP-LHDB-Agent scoring_system.py，适配本地 OHLCV）。

不依赖通达信 DLL；用日线/分钟 bar 代理竞价高开、涨停等信号。
参考：https://github.com/adambbhe/TDX-MCP-LHDB-Agent
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Sequence


class SignalType(Enum):
    NO_SIGNAL = "无信号"
    AUCTION_HIGH_OPEN = "竞价高开"
    RAPID_RISE = "快速拉升"
    NEAR_LIMIT_UP = "接近涨停"
    LIMIT_UP = "封涨停"
    STRONG_BREAKOUT = "强势突破"


@dataclass
class StockSignal:
    code: str
    name: str
    signal_type: SignalType
    current_price: float
    last_close: float
    volume: float = 0.0
    amount: float = 0.0
    high_open_ratio: float = 0.0
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    score: float = 0.0
    details: Dict = field(default_factory=dict)


class UnifiedScoringSystem:
    """五维加权评分（信号强度 / 价格位置 / 量能 / 动能 / 风控）。"""

    def __init__(self, custom_weights: Optional[Dict[str, float]] = None):
        self.default_weights = {
            "signal_strength": 25.0,
            "price_position": 20.0,
            "volume_quality": 20.0,
            "momentum": 20.0,
            "risk_control": 15.0,
        }
        self.weights = dict(custom_weights or self.default_weights)
        self._validate_weights()

    def _validate_weights(self) -> None:
        total = sum(self.weights.values())
        if not (99 <= total <= 101):
            raise ValueError(f"权重总和应为 100%，当前为 {total}%")

    def calculate_score(
        self,
        signal: StockSignal,
        kline_bars: Optional[Sequence[dict]] = None,
    ) -> float:
        signal_strength = self._score_signal_strength(signal)
        price_position = self._score_price_position(signal, kline_bars)
        volume_quality = self._score_volume_quality(signal)
        momentum = self._score_momentum(signal)
        risk_control = self._score_risk_control(signal)

        score = (
            signal_strength * self.weights["signal_strength"] / 100
            + price_position * self.weights["price_position"] / 100
            + volume_quality * self.weights["volume_quality"] / 100
            + momentum * self.weights["momentum"] / 100
            + risk_control * self.weights["risk_control"] / 100
        )
        signal.score = round(score, 1)
        signal.details["评分明细"] = {
            "总分": f"{score:.1f}",
            "信号强度": f"{signal_strength:.1f}",
            "价格位置": f"{price_position:.1f}",
            "量能质量": f"{volume_quality:.1f}",
            "动能指标": f"{momentum:.1f}",
            "风控指标": f"{risk_control:.1f}",
        }
        return score

    def _score_signal_strength(self, signal: StockSignal) -> float:
        type_scores = {
            SignalType.LIMIT_UP: 100.0,
            SignalType.NEAR_LIMIT_UP: 85.0,
            SignalType.RAPID_RISE: 70.0,
            SignalType.AUCTION_HIGH_OPEN: 60.0,
            SignalType.STRONG_BREAKOUT: 75.0,
        }
        base = type_scores.get(signal.signal_type, 0.0)
        if signal.signal_type == SignalType.LIMIT_UP:
            rise = (signal.current_price / signal.last_close - 1) * 100
            if rise >= 9.98:
                base = 100.0
            elif rise >= 9.95:
                base = 95.0
        elif signal.signal_type == SignalType.AUCTION_HIGH_OPEN:
            if signal.high_open_ratio >= 5:
                base = 70.0
            elif signal.high_open_ratio >= 3:
                base = 65.0
        return min(base, 100.0)

    def _score_price_position(
        self,
        signal: StockSignal,
        kline_bars: Optional[Sequence[dict]] = None,
    ) -> float:
        if not kline_bars:
            return 60.0 if signal.current_price > signal.last_close else 40.0

        closes = [float(b["close"]) for b in kline_bars if b.get("close")]
        if len(closes) < 21:
            return 50.0

        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10
        ma20 = sum(closes[-20:]) / 20
        signal.ma5 = round(ma5, 2)
        signal.ma10 = round(ma10, 2)
        signal.ma20 = round(ma20, 2)
        price = signal.current_price

        if price > ma5 > ma10 > ma20:
            return 100.0
        if price > ma5 > ma10:
            return 85.0
        if price > ma5:
            return 70.0
        if price > ma20:
            return 55.0
        return 35.0

    def _score_volume_quality(self, signal: StockSignal) -> float:
        if signal.amount <= 0:
            return 50.0
        if signal.signal_type == SignalType.LIMIT_UP:
            if signal.amount > 100_000_000:
                return 95.0
            if signal.amount > 50_000_000:
                return 85.0
            return 70.0
        denom = max(signal.last_close * signal.volume, 1.0)
        ratio = signal.amount / denom
        if ratio > 1.5:
            return 85.0
        if ratio > 1.0:
            return 70.0
        return 55.0

    def _score_momentum(self, signal: StockSignal) -> float:
        rise = (signal.current_price / signal.last_close - 1) * 100
        if signal.signal_type == SignalType.LIMIT_UP:
            return 95.0
        if rise >= 7:
            return 90.0
        if rise >= 5:
            return 80.0
        if rise >= 3:
            return 70.0
        if rise >= 1:
            return 60.0
        if rise >= 0:
            return 50.0
        return 30.0

    def _score_risk_control(self, signal: StockSignal) -> float:
        score = 80.0
        if "*" in signal.name:
            score -= 30.0
        if signal.current_price < 5:
            score -= 10.0
        if signal.high_open_ratio > 6:
            score -= 15.0
        if (signal.current_price / signal.last_close - 1) > 0.095:
            score -= 10.0
        return max(score, 0.0)


def _limit_up_threshold(code: str) -> float:
    """主板 10%，创业板/科创板 20%，北交所 30%（简化）。"""
    digits = code.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    if digits.startswith(("300", "301", "688")):
        return 19.5
    if digits.startswith(("8", "4")):
        return 29.5
    return 9.8


def classify_signal_from_bars(
    bars: Sequence[dict],
    *,
    code: str = "",
    auction_min_high_open: float = 2.0,
    auction_max_high_open: float = 7.0,
) -> SignalType:
    """从最近两根 bar 推断打板类信号（日线收盘代理实盘快照）。"""
    if len(bars) < 2:
        return SignalType.NO_SIGNAL

    prev = bars[-2]
    last = bars[-1]
    prev_close = float(prev.get("close", 0) or 0)
    open_ = float(last.get("open", last.get("close", 0)) or 0)
    close = float(last.get("close", 0) or 0)
    high = float(last.get("high", close) or close)
    if prev_close <= 0 or close <= 0:
        return SignalType.NO_SIGNAL

    rise_pct = (close / prev_close - 1) * 100
    high_open = (open_ / prev_close - 1) * 100
    limit_th = _limit_up_threshold(code)

    if rise_pct >= limit_th - 0.2 and close >= high * 0.998:
        return SignalType.LIMIT_UP
    if rise_pct >= limit_th * 0.7:
        return SignalType.NEAR_LIMIT_UP
    if rise_pct >= 5:
        return SignalType.RAPID_RISE
    if auction_min_high_open <= high_open <= auction_max_high_open:
        return SignalType.AUCTION_HIGH_OPEN
    if rise_pct >= 3 and close >= high * 0.99:
        return SignalType.STRONG_BREAKOUT
    return SignalType.NO_SIGNAL


def signal_from_bars(
    code: str,
    bars: Sequence[dict],
    *,
    name: str = "",
    auction_min_high_open: float = 2.0,
    auction_max_high_open: float = 7.0,
) -> Optional[StockSignal]:
    """构建 StockSignal；无有效信号时返回 None。"""
    if len(bars) < 2:
        return None

    signal_type = classify_signal_from_bars(
        bars,
        code=code,
        auction_min_high_open=auction_min_high_open,
        auction_max_high_open=auction_max_high_open,
    )
    if signal_type == SignalType.NO_SIGNAL:
        return None

    prev_close = float(bars[-2]["close"])
    last = bars[-1]
    open_ = float(last.get("open", last["close"]))
    close = float(last["close"])
    vol = float(last.get("vol", last.get("volume", 0)) or 0)
    amount = close * vol

    return StockSignal(
        code=code,
        name=name,
        signal_type=signal_type,
        current_price=close,
        last_close=prev_close,
        volume=vol,
        amount=amount,
        high_open_ratio=round((open_ / prev_close - 1) * 100, 2),
    )


def score_bars_limitup(
    code: str,
    bars: Sequence[dict],
    *,
    name: str = "",
    scorer: UnifiedScoringSystem | None = None,
    auction_min_high_open: float = 2.0,
    auction_max_high_open: float = 7.0,
) -> dict | None:
    """对单标的 OHLCV 序列打五维分；无信号返回 None。"""
    signal = signal_from_bars(
        code,
        bars,
        name=name,
        auction_min_high_open=auction_min_high_open,
        auction_max_high_open=auction_max_high_open,
    )
    if signal is None:
        return None

    sys = scorer or UnifiedScoringSystem()
    total = sys.calculate_score(signal, kline_bars=bars)
    rise_pct = round((signal.current_price / signal.last_close - 1) * 100, 2)
    return {
        "code": code,
        "name": name,
        "signal_type": signal.signal_type.value,
        "score": signal.score,
        "rise_pct": rise_pct,
        "high_open_ratio": signal.high_open_ratio,
        "amount": round(signal.amount, 0),
        "ma5": signal.ma5,
        "ma10": signal.ma10,
        "ma20": signal.ma20,
        "details": signal.details,
        "date": bars[-1].get("date", ""),
        "total_raw": round(total, 1),
    }


def _min_bars() -> int:
    return int(os.environ.get("BERKSHIRE_LIMITUP_MIN_BARS", "22"))


def _min_score() -> float:
    return float(os.environ.get("BERKSHIRE_LIMITUP_SCORE_MIN", "60"))


def run_limitup_screen(
    bars_by_symbol: dict[str, list[dict]],
    *,
    codes: list[str] | None = None,
    min_score: float | None = None,
    top_n: int | None = None,
    custom_weights: dict[str, float] | None = None,
    auction_min_high_open: float = 2.0,
    auction_max_high_open: float = 7.0,
    names: dict[str, str] | None = None,
) -> dict:
    """扫描多标的，返回 thesis_queue 友好结构。"""
    from datetime import datetime

    threshold = min_score if min_score is not None else _min_score()
    min_b = _min_bars()
    scorer = UnifiedScoringSystem(custom_weights)
    names = names or {}

    wanted: set[str] | None = None
    if codes:
        wanted = set()
        for c in codes:
            digits = c.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
            if digits.startswith(("6", "9", "5")):
                wanted.add(f"sh.{digits}")
            else:
                wanted.add(f"sz.{digits}")

    candidates: list[dict] = []
    for sym, bars in sorted(bars_by_symbol.items()):
        if wanted is not None and sym not in wanted:
            continue
        if len(bars) < min_b:
            continue
        ticker = sym.split(".")[-1] if "." in sym else sym
        hit = score_bars_limitup(
            ticker,
            bars,
            name=names.get(sym, names.get(ticker, "")),
            scorer=scorer,
            auction_min_high_open=auction_min_high_open,
            auction_max_high_open=auction_max_high_open,
        )
        if not hit or hit["score"] < threshold:
            continue
        note = (
            f"{hit['date']} {hit['signal_type']} 评分{hit['score']:.1f} "
            f"涨幅{hit['rise_pct']:+.2f}% 高开{hit['high_open_ratio']:+.2f}%"
        )
        candidates.append({
            "ticker": ticker,
            "symbol": sym,
            "signal": "limitup_scoring",
            "score": hit["score"],
            "signal_type": hit["signal_type"],
            "rise_pct": hit["rise_pct"],
            "high_open_ratio": hit["high_open_ratio"],
            "date": hit["date"],
            "note": note,
            "details": hit.get("details"),
            "thesis_queue_line": f"**{ticker}**: {note}",
        })

    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    if top_n is not None and top_n > 0:
        candidates = candidates[:top_n]

    return {
        "ok": True,
        "source": "limitup_screener_bridge",
        "scoring": "unified_5dim",
        "min_score": threshold,
        "min_bars": min_b,
        "candidates": candidates,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

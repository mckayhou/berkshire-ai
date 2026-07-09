#!/usr/bin/env python3
"""
投研后验周报核心逻辑（决策 → horizon 到期 → 方向命中 / 校准误差）。

设计目标
--------
- 吃干净的 `decisions.jsonl`，不碰被测试污染的 experiences（除非显式要求）。
- 价格经可注入 PriceProvider（测试用 Static；生产用 Network）。
- 零新依赖；控制流读字段。

KPI（与「投研效果」北极星对齐）
------------------------------
1. 方向命中率：mean_stance >= bullish_threshold 且 raw_return > 0（看多被验证）
   或 mean_stance <= bearish_threshold 且 raw_return < 0（看空被验证）
   中性区不计入命中分母（可选 skip_neutral）。
2. 校准误差：|mean_stance - realized_base|
3. 契约完整率：is_research_complete 占比
4. 到期可计样本数 / 缺价跳过数
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

try:
    from .decision_log import (
        DecisionRecord,
        incomplete_research_decisions,
        is_research_complete,
        maturity_date,
        mean_stance,
    )
    from .realized_feedback import (
        DEFAULT_SENSITIVITY,
        PriceProvider,
        ReturnStats,
        compute_returns,
    )

except ImportError:  # pragma: no cover
    from decision_log import (
        DecisionRecord,
        incomplete_research_decisions,
        is_research_complete,
        maturity_date,
        mean_stance,
    )
    from realized_feedback import (
        DEFAULT_SENSITIVITY,
        PriceProvider,
        ReturnStats,
        compute_returns,
    )
# 默认：stance >= 0.6 视为偏多；<= 0.4 视为偏空；中间中性
DEFAULT_BULLISH = 0.6
DEFAULT_BEARISH = 0.4


@dataclass
class PosteriorRow:
    """单条决策的后验结果。"""

    ticker: str
    date: str
    maturity: str
    action: str
    thesis: str
    mean_stance: Optional[float]
    price_anchor: float
    realized_price: Optional[float]
    raw_return: Optional[float]
    alpha: Optional[float]
    realized_base: Optional[float]
    abs_calibration_error: Optional[float]
    direction_hit: Optional[bool]
    complete: bool
    status: str  # due_priced | due_missing_price | not_due | incomplete
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PosteriorReport:
    """聚合周报。"""

    as_of: str
    n_decisions: int
    n_complete: int
    complete_rate: float
    n_due: int
    n_priced: int
    n_missing_price: int
    n_direction_scored: int
    direction_hits: int
    direction_hit_rate: Optional[float]
    mean_abs_calibration_error: Optional[float]
    mean_raw_return: Optional[float]
    mean_alpha: Optional[float]
    incomplete_tickers: List[str] = field(default_factory=list)
    rows: List[PosteriorRow] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["rows"] = [r.to_dict() if hasattr(r, "to_dict") else r for r in self.rows]
        return d


def _parse_day(s: str) -> datetime:
    return datetime.strptime(s[:10], "%Y-%m-%d")


def direction_hit(
    stance: Optional[float],
    raw_return: float,
    *,
    bullish: float = DEFAULT_BULLISH,
    bearish: float = DEFAULT_BEARISH,
) -> Optional[bool]:
    """方向是否正确；中性区返回 None（不计入命中率）。"""
    if stance is None:
        return None
    if stance >= bullish:
        return raw_return > 0
    if stance <= bearish:
        return raw_return < 0
    return None


def evaluate_decision(
    record: DecisionRecord,
    *,
    as_of: str,
    price_provider: Optional[PriceProvider] = None,
    realized_price: Optional[float] = None,
    benchmark_realized_price: Optional[float] = None,
    sensitivity: float = DEFAULT_SENSITIVITY,
    bullish: float = DEFAULT_BULLISH,
    bearish: float = DEFAULT_BEARISH,
) -> PosteriorRow:
    """评估单条决策相对 as_of 的后验状态。"""
    mat = maturity_date(record)
    stance = mean_stance(record)
    complete = is_research_complete(record)
    base_row = dict(
        ticker=record.ticker,
        date=record.date,
        maturity=mat or "",
        action=record.action,
        thesis=record.thesis[:120],
        mean_stance=round(stance, 4) if stance is not None else None,
        price_anchor=record.price_anchor,
        complete=complete,
    )

    if mat is None:
        return PosteriorRow(
            **base_row,  # type: ignore[arg-type]
            realized_price=None,
            raw_return=None,
            alpha=None,
            realized_base=None,
            abs_calibration_error=None,
            direction_hit=None,
            status="incomplete",
            note="缺 horizon_days",
        )

    if _parse_day(mat) > _parse_day(as_of):
        return PosteriorRow(
            **base_row,  # type: ignore[arg-type]
            realized_price=None,
            raw_return=None,
            alpha=None,
            realized_base=None,
            abs_calibration_error=None,
            direction_hit=None,
            status="not_due",
            note=f"到期日 {mat} > as_of {as_of}",
        )

    price = realized_price
    if price is None and price_provider is not None:
        try:
            price = float(price_provider.get_price(record.ticker, mat))
        except (KeyError, ValueError, TypeError) as e:
            return PosteriorRow(
                **base_row,  # type: ignore[arg-type]
                realized_price=None,
                raw_return=None,
                alpha=None,
                realized_base=None,
                abs_calibration_error=None,
                direction_hit=None,
                status="due_missing_price",
                note=str(e),
            )

    if price is None:
        return PosteriorRow(
            **base_row,  # type: ignore[arg-type]
            realized_price=None,
            raw_return=None,
            alpha=None,
            realized_base=None,
            abs_calibration_error=None,
            direction_hit=None,
            status="due_missing_price",
            note="无 realized_price 且未注入 price_provider",
        )

    bench_px = benchmark_realized_price
    if (
        bench_px is None
        and price_provider is not None
        and record.benchmark
        and record.benchmark_anchor is not None
    ):
        try:
            bench_px = float(price_provider.get_price(str(record.benchmark), mat))
        except (KeyError, ValueError, TypeError):
            bench_px = None

    stats: ReturnStats = compute_returns(
        record,
        realized_price=price,
        benchmark_realized_price=bench_px,
        sensitivity=sensitivity,
    )
    cal_err = None if stance is None else abs(stance - stats.realized_base)
    hit = direction_hit(stance, stats.raw_return, bullish=bullish, bearish=bearish)

    return PosteriorRow(
        **base_row,  # type: ignore[arg-type]
        realized_price=round(price, 6),
        raw_return=round(stats.raw_return, 6),
        alpha=round(stats.alpha, 6),
        realized_base=round(stats.realized_base, 6),
        abs_calibration_error=round(cal_err, 6) if cal_err is not None else None,
        direction_hit=hit,
        status="due_priced",
        note="",
    )


def build_posterior_report(
    records: Sequence[DecisionRecord],
    *,
    as_of: str,
    price_provider: Optional[PriceProvider] = None,
    price_map: Optional[Dict[str, float]] = None,
    sensitivity: float = DEFAULT_SENSITIVITY,
    bullish: float = DEFAULT_BULLISH,
    bearish: float = DEFAULT_BEARISH,
) -> PosteriorReport:
    """聚合多条决策后验。

    price_map 键格式：``TICKER|YYYY-MM-DD`` → 收盘价（maturity 日），优先于 provider。
    """
    price_map = price_map or {}
    rows: List[PosteriorRow] = []
    for rec in records:
        mat = maturity_date(rec)
        key = f"{rec.ticker}|{mat}" if mat else ""
        forced = price_map.get(key) if key else None
        rows.append(
            evaluate_decision(
                rec,
                as_of=as_of,
                price_provider=price_provider,
                realized_price=forced,
                sensitivity=sensitivity,
                bullish=bullish,
                bearish=bearish,
            )
        )

    n = len(rows)
    n_complete = sum(1 for r in rows if r.complete)
    priced = [r for r in rows if r.status == "due_priced"]
    due = [r for r in rows if r.status in ("due_priced", "due_missing_price")]
    missing = [r for r in rows if r.status == "due_missing_price"]
    scored = [r for r in priced if r.direction_hit is not None]
    hits = sum(1 for r in scored if r.direction_hit)
    cal_errs = [r.abs_calibration_error for r in priced if r.abs_calibration_error is not None]
    raws = [r.raw_return for r in priced if r.raw_return is not None]
    alphas = [r.alpha for r in priced if r.alpha is not None]
    incomplete = incomplete_research_decisions(records=list(records))

    def _mean(xs: List[float]) -> Optional[float]:
        return round(sum(xs) / len(xs), 6) if xs else None

    return PosteriorReport(
        as_of=as_of[:10],
        n_decisions=n,
        n_complete=n_complete,
        complete_rate=round(n_complete / n, 4) if n else 0.0,
        n_due=len(due),
        n_priced=len(priced),
        n_missing_price=len(missing),
        n_direction_scored=len(scored),
        direction_hits=hits,
        direction_hit_rate=round(hits / len(scored), 4) if scored else None,
        mean_abs_calibration_error=_mean(cal_errs),  # type: ignore[arg-type]
        mean_raw_return=_mean(raws),  # type: ignore[arg-type]
        mean_alpha=_mean(alphas),  # type: ignore[arg-type]
        incomplete_tickers=sorted({r.ticker for r in incomplete}),
        rows=rows,
    )


def format_report_markdown(report: PosteriorReport) -> str:
    """人类可读 Markdown 摘要。"""
    lines = [
        f"# 投研后验周报（as_of {report.as_of}）",
        "",
        "## KPI",
        "",
        "| 指标 | 值 |",
        "|------|-----|",
        f"| 决策条数 | {report.n_decisions} |",
        f"| 契约完整率 | {report.complete_rate:.1%} ({report.n_complete}/{report.n_decisions}) |",
        f"| 已到期 | {report.n_due} |",
        f"| 已定价后验 | {report.n_priced} |",
        f"| 缺价跳过 | {report.n_missing_price} |",
        f"| 方向命中率 | "
        f"{'n/a' if report.direction_hit_rate is None else f'{report.direction_hit_rate:.1%}'} "
        f"({report.direction_hits}/{report.n_direction_scored}) |",
        f"| 平均|校准误差| | "
        f"{'n/a' if report.mean_abs_calibration_error is None else report.mean_abs_calibration_error} |",
        f"| 平均 raw_return | "
        f"{'n/a' if report.mean_raw_return is None else report.mean_raw_return} |",
        f"| 平均 alpha | "
        f"{'n/a' if report.mean_alpha is None else report.mean_alpha} |",
        "",
    ]
    if report.incomplete_tickers:
        lines.append(
            f"**契约不完整标的**：{', '.join(report.incomplete_tickers)}  "
            f"— 用 `python3 tools/log_decision.py gaps` 查看。"
        )
        lines.append("")

    lines.extend(
        [
            "## 明细（到期已定价）",
            "",
            "| Ticker | 决策日 | 到期 | stance | ret | α | hit | action | thesis |",
            "|--------|--------|------|--------|-----|---|-----|--------|--------|",
        ]
    )
    for r in report.rows:
        if r.status != "due_priced":
            continue
        hit_s = "—" if r.direction_hit is None else ("Y" if r.direction_hit else "N")
        thesis = (r.thesis or "").replace("|", "/")[:40]
        lines.append(
            f"| {r.ticker} | {r.date} | {r.maturity} | {r.mean_stance} | "
            f"{r.raw_return} | {r.alpha} | {hit_s} | {r.action or '—'} | {thesis} |"
        )

    pending = [r for r in report.rows if r.status == "not_due"]
    if pending:
        lines.extend(["", f"## 未到期（{len(pending)}）", ""])
        for r in pending[:20]:
            lines.append(f"- {r.ticker} {r.date} → {r.maturity}（{r.note}）")

    missing = [r for r in report.rows if r.status == "due_missing_price"]
    if missing:
        lines.extend(["", f"## 到期但缺价（{len(missing)}）", ""])
        for r in missing[:20]:
            lines.append(f"- {r.ticker} maturity={r.maturity}: {r.note}")

    lines.append("")
    return "\n".join(lines)

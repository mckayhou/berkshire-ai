"""Score A-share symbols with a mined AlphaGPT formula."""

from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

from .config import MiningConfig
from .data_engine import AshareDataEngine
from .decode import decode_formula
from .formula_store import load_formula
from .vm import FormulaVM

_TOOLS = Path(__file__).resolve().parent.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))


def _data_dir() -> Path:
    return Path(os.environ.get("BERKSHIRE_DATA_DIR", "./data")).expanduser()


def _csv_path() -> Path:
    return _data_dir() / "daily_ohlcv.csv"


def _min_bars() -> int:
    return int(os.environ.get("BERKSHIRE_ALPHAGPT_MIN_BARS", "80"))


def _code_digits(code: str) -> str:
    return code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")


def _baostock_symbol(code: str) -> str:
    c = _code_digits(code)
    if c.startswith(("6", "9", "5")):
        return f"sh.{c}"
    return f"sz.{c}"


def load_csv_ohlcv_by_symbol(path: Path) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym = (row.get("symbol") or "").strip().lower()
            if not sym:
                continue
            t = (row.get("time") or row.get("date") or "")[:10]
            if not t:
                continue
            try:
                buckets[sym].append({
                    "date": t,
                    "open": float(row.get("open", 0) or 0),
                    "high": float(row.get("high", 0) or 0),
                    "low": float(row.get("low", 0) or 0),
                    "close": float(row.get("close", 0) or 0),
                    "vol": float(row.get("volume", row.get("vol", 0)) or 0),
                })
            except (TypeError, ValueError):
                continue
    for sym in buckets:
        buckets[sym].sort(key=lambda r: r["date"])
    return buckets


def score_bars(
    bars: list[dict],
    formula_tokens: list[int],
    *,
    device=None,
) -> dict | None:
    """Score one symbol's OHLCV bars; returns None if insufficient data."""
    import torch

    min_b = _min_bars()
    if len(bars) < min_b:
        return None

    dates = [r["date"] for r in bars]
    open_ = np.array([r["open"] for r in bars], dtype=np.float32)
    high = np.array([r["high"] for r in bars], dtype=np.float32)
    low = np.array([r["low"] for r in bars], dtype=np.float32)
    close = np.array([r["close"] for r in bars], dtype=np.float32)
    vol = np.array([r["vol"] for r in bars], dtype=np.float32)

    dev = device or torch.device("cpu")
    eng = AshareDataEngine.from_ohlcv_arrays(
        trade_dates=dates,
        open_=open_,
        high=high,
        low=low,
        close=close,
        vol=vol,
        device=dev,
    )
    vm = FormulaVM(eng.feat_data)
    factor = vm.solve_one(formula_tokens)
    if factor is None:
        return None

    raw = float(factor[-1].item())
    score = float(torch.tanh(factor[-1]).item())
    return {
        "date": dates[-1],
        "raw_signal": round(raw, 4),
        "score": round(score, 4),
        "direction": "long" if score > 0.05 else ("short" if score < -0.05 else "neutral"),
    }


def score_symbol_online(
    code: str,
    formula_tokens: list[int],
    *,
    daily_limit: int | None = None,
    device=None,
) -> dict | None:
    """Fetch daily bars then score (network)."""
    import torch

    cfg = MiningConfig(
        index_code=_code_digits(code),
        daily_limit=daily_limit or MiningConfig().daily_limit,
        start_date="20180101",
    )
    dev = device or torch.device("cpu")
    try:
        eng = AshareDataEngine(cfg).load(device=dev)
    except Exception:
        return None
    if eng.feat_data.shape[-1] < _min_bars():
        return None
    vm = FormulaVM(eng.feat_data)
    factor = vm.solve_one(formula_tokens)
    if factor is None:
        return None
    raw = float(factor[-1].item())
    score = float(torch.tanh(factor[-1]).item())
    return {
        "date": eng.dates[-1] if eng.dates else "",
        "raw_signal": round(raw, 4),
        "score": round(score, 4),
        "direction": "long" if score > 0.05 else ("short" if score < -0.05 else "neutral"),
    }


def run_screen(
    *,
    formula_path: Path | str | None = None,
    formula_tokens: list[int] | None = None,
    codes: list[str] | None = None,
    source: str = "auto",
    min_score: float | None = None,
    top_n: int | None = None,
) -> dict:
    """Screen symbols; prefers local CSV, falls back to online per-symbol fetch."""
    import torch

    if formula_tokens is None:
        loaded = load_formula(formula_path)
        formula_tokens = loaded["formula_tokens"]
        formula_str = loaded.get("formula") or decode_formula(formula_tokens)
        best_score = loaded.get("best_score")
    else:
        formula_str = decode_formula(formula_tokens)
        best_score = None

    threshold = min_score
    if threshold is None:
        threshold = float(os.environ.get("BERKSHIRE_ALPHAGPT_SCORE_MIN", "0.0"))

    csv_path = _csv_path()
    use_csv = source in ("auto", "csv") and csv_path.is_file()
    candidates: list[dict] = []
    errors: list[str] = []

    if use_csv:
        by_sym = load_csv_ohlcv_by_symbol(csv_path)
        if codes:
            wanted = {_baostock_symbol(c) for c in codes}
            by_sym = {k: v for k, v in by_sym.items() if k in wanted}
        dev = torch.device("cpu")
        for sym, bars in sorted(by_sym.items()):
            hit = score_bars(bars, formula_tokens, device=dev)
            if not hit:
                continue
            if hit["score"] < threshold and threshold > 0:
                continue
            ticker = sym.split(".")[-1] if "." in sym else sym
            note = (
                f"{hit['date']} 因子信号 {hit['score']:+.3f} "
                f"({hit['direction']}) formula={formula_str[:60]}"
            )
            candidates.append({
                "ticker": ticker,
                "symbol": sym,
                "signal": "alphagpt_factor",
                "score": hit["score"],
                "raw_signal": hit["raw_signal"],
                "direction": hit["direction"],
                "date": hit["date"],
                "note": note,
                "thesis_queue_line": f"**{ticker}**: {note}",
            })
        data_source = "local_csv"
    elif source == "csv":
        return {
            "ok": False,
            "error": f"daily_ohlcv.csv not found at {csv_path}",
            "candidates": [],
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }
    else:
        if not codes:
            return {
                "ok": False,
                "error": "online screen requires --codes",
                "candidates": [],
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            }
        dev = torch.device("cpu")
        for code in codes:
            c = _code_digits(code)
            try:
                hit = score_symbol_online(c, formula_tokens, device=dev)
            except Exception as e:
                errors.append(f"{c}: {e}")
                continue
            if not hit:
                errors.append(f"{c}: insufficient data or invalid formula")
                continue
            if hit["score"] < threshold and threshold > 0:
                continue
            note = (
                f"{hit['date']} 因子信号 {hit['score']:+.3f} "
                f"({hit['direction']}) formula={formula_str[:60]}"
            )
            candidates.append({
                "ticker": c,
                "symbol": _baostock_symbol(c),
                "signal": "alphagpt_factor",
                "score": hit["score"],
                "raw_signal": hit["raw_signal"],
                "direction": hit["direction"],
                "date": hit["date"],
                "note": note,
                "thesis_queue_line": f"**{c}**: {note}",
            })
        data_source = "online"

    candidates.sort(key=lambda x: abs(x.get("score", 0)), reverse=True)
    if top_n is not None and top_n > 0:
        candidates = candidates[:top_n]

    return {
        "ok": True,
        "source": "factor_screener_bridge",
        "data_source": data_source,
        "formula": formula_str,
        "formula_tokens": formula_tokens,
        "train_best_score": best_score,
        "min_score": threshold,
        "candidates": candidates,
        "errors": errors,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

#!/usr/bin/env python3
"""本地 CSV 动量筛选 → thesis_queue 友好 JSON（V10.24 quant fusion）。

读取 BERKSHIRE_DATA_DIR/daily_ohlcv.csv（daily_stock_data 格式），
用纯 stdlib 做简化动量筛选，输出可供 thesis_queue / Cron 消费的候选列表。

用法：
  python3 tools/quant_screener_bridge.py
  python3 tools/quant_screener_bridge.py --json
  python3 tools/quant_screener_bridge.py --codes 600519,000001 --lookback 20
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "tools") not in sys.path:
    sys.path.insert(0, str(_REPO / "tools"))

from data_sources import _baostock_symbol, _code_digits  # noqa: E402


def _data_dir() -> Path:
    return Path(os.environ.get("BERKSHIRE_DATA_DIR", "./data")).expanduser()


def _csv_path() -> Path:
    return _data_dir() / "daily_ohlcv.csv"


def load_daily_by_symbol(path: Path) -> dict[str, list[dict]]:
    """按 symbol 聚合日线，每 symbol 按 date 升序。"""
    buckets: dict[str, list[dict]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym = (row.get("symbol") or "").strip().lower()
            if not sym:
                continue
            t = (row.get("time") or row.get("date") or "")[:10]
            close = row.get("close")
            vol = row.get("volume")
            if not t or close in (None, ""):
                continue
            try:
                c = float(close)
                v = float(vol) if vol not in (None, "") else 0.0
            except (TypeError, ValueError):
                continue
            buckets[sym].append({"date": t, "close": c, "volume": v})
    for sym in buckets:
        buckets[sym].sort(key=lambda r: r["date"])
    return buckets


def _ticker_from_symbol(symbol: str) -> str:
    """sh.600000 → 600519 风格展示代码。"""
    s = symbol.lower()
    if s.startswith(("sh.", "sz.", "bj.")):
        return s[3:]
    return _code_digits(symbol) or symbol


def screen_momentum(
    bars: list[dict],
    *,
    lookback: int = 20,
    vol_mult: float = 1.5,
) -> dict | None:
    """简化动量：收盘创 lookback 日新高且放量。"""
    if len(bars) < lookback + 1:
        return None
    window = bars[-(lookback + 1):]
    last = window[-1]
    prev = window[:-1]
    high_close = max(r["close"] for r in prev)
    avg_vol = sum(r["volume"] for r in prev) / len(prev) if prev else 0.0
    if last["close"] <= high_close:
        return None
    if avg_vol > 0 and last["volume"] < avg_vol * vol_mult:
        return None
    pct = (last["close"] - prev[-1]["close"]) / prev[-1]["close"] * 100 if prev else 0.0
    return {
        "close": last["close"],
        "date": last["date"],
        "breakout_pct": round(pct, 2),
        "volume_ratio": round(last["volume"] / avg_vol, 2) if avg_vol else None,
    }


def run_screen(
    *,
    codes: list[str] | None = None,
    lookback: int = 20,
    vol_mult: float = 1.5,
) -> dict:
    path = _csv_path()
    if not path.is_file():
        return {
            "ok": False,
            "error": f"daily_ohlcv.csv not found at {path}",
            "candidates": [],
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }

    by_sym = load_daily_by_symbol(path)
    if codes:
        wanted = {_baostock_symbol(c) for c in codes}
        by_sym = {k: v for k, v in by_sym.items() if k in wanted}

    candidates = []
    for sym, bars in sorted(by_sym.items()):
        hit = screen_momentum(bars, lookback=lookback, vol_mult=vol_mult)
        if not hit:
            continue
        ticker = _ticker_from_symbol(sym)
        note = (
            f"{hit['date']} 突破{lookback}日高点 "
            f"收盘{hit['close']} 量比{hit.get('volume_ratio')} "
            f"(local CSV screener)"
        )
        candidates.append({
            "ticker": ticker,
            "symbol": sym,
            "signal": "momentum_breakout",
            "note": note,
            "thesis_queue_line": f"**{ticker}**: {note}",
            **hit,
        })

    candidates.sort(key=lambda c: c.get("breakout_pct") or 0, reverse=True)
    return {
        "ok": True,
        "source": "quant_screener_bridge",
        "data_dir": str(_data_dir()),
        "lookback": lookback,
        "candidates": candidates,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="本地 CSV 动量筛选 → thesis_queue JSON")
    parser.add_argument("--codes", help="逗号分隔代码，默认扫描 CSV 内全部")
    parser.add_argument("--lookback", type=int, default=20, help="突破回看天数")
    parser.add_argument("--vol-mult", type=float, default=1.5, help="放量倍数阈值")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    codes = None
    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]

    result = run_screen(codes=codes, lookback=args.lookback, vol_mult=args.vol_mult)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if not result.get("ok"):
        print(f"❌ {result.get('error')}")
        sys.exit(1)

    print(f"✅ {len(result['candidates'])} 候选 (lookback={args.lookback})")
    for c in result["candidates"][:20]:
        print(f"  {c['ticker']}: {c['note']}")


if __name__ == "__main__":
    main()

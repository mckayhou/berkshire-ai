#!/usr/bin/env python3
"""投研后验周报 CLI。

读 decisions.jsonl → 对已到期决策算方向命中 / 校准误差。

用法
----
    # 离线：用 price map（键 TICKER|YYYY-MM-DD）
    python3 tools/posterior_weekly.py report \\
      --as-of 2026-07-09 \\
      --prices '{"AAPL|2026-01-21":110,"MSFT|2026-01-21":420}'

    # 在线：NetworkPriceProvider（多源降级）
    python3 tools/posterior_weekly.py report --network

    # JSON
    python3 tools/posterior_weekly.py report --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from typing import Dict, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from decision_log import default_log_path, load_decisions  # noqa: E402
from posterior_report import (  # noqa: E402
    build_posterior_report,
    format_report_markdown,
)
from realized_feedback import NetworkPriceProvider, StaticPriceProvider  # noqa: E402


def _load_price_map(raw: Optional[str], path: Optional[str]) -> Dict[str, float]:
    data: Dict[str, float] = {}
    if path:
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
        if not isinstance(obj, dict):
            raise SystemExit("--prices-file 必须是 JSON 对象")
        data.update({str(k): float(v) for k, v in obj.items()})
    if raw:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise SystemExit("--prices 必须是 JSON 对象")
        data.update({str(k): float(v) for k, v in obj.items()})
    return data


def cmd_report(args: argparse.Namespace) -> int:
    as_of = args.as_of or date.today().isoformat()
    records = load_decisions(args.log)
    price_map = _load_price_map(args.prices, args.prices_file)

    provider = None
    if args.network:
        provider = NetworkPriceProvider()
    elif price_map:
        # StaticPriceProvider 键是 (ticker, date)；maturity 日已在 map 里用 TICKER|date
        static: Dict = {}
        for k, v in price_map.items():
            if "|" not in k:
                continue
            tkr, d = k.split("|", 1)
            static[(tkr.strip().upper(), d.strip()[:10])] = float(v)
        # 也允许直接用 Static 喂 map 之外的：evaluate 优先 price_map
        provider = StaticPriceProvider(static) if static else None

    report = build_posterior_report(
        records,
        as_of=as_of,
        price_provider=provider,
        price_map=price_map,
        bullish=args.bullish,
        bearish=args.bearish,
    )

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"决策日志: {args.log or default_log_path()}")
        print(format_report_markdown(report))

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            if args.json:
                json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
            else:
                f.write(format_report_markdown(report))
        print(f"已写入 {args.out}", file=sys.stderr)

    # 退出码：有到期缺价 → 2；契约完整率过低 → 1（仅 --strict）
    if report.n_missing_price > 0 and args.strict:
        return 2
    if args.strict and report.n_decisions and report.complete_rate < args.min_complete:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="投研后验周报")
    p.add_argument("--log", default=None, help="覆盖 BERKSHIRE_DECISION_LOG")
    sub = p.add_subparsers(dest="cmd", required=True)

    rp = sub.add_parser("report", help="生成后验周报")
    rp.add_argument("--as-of", default=None, help="YYYY-MM-DD，默认今天")
    rp.add_argument("--prices", default=None, help='JSON map "TICKER|YYYY-MM-DD": price')
    rp.add_argument("--prices-file", default=None, help="同上，从文件读")
    rp.add_argument("--network", action="store_true", help="用 NetworkPriceProvider 取价")
    rp.add_argument("--bullish", type=float, default=0.6)
    rp.add_argument("--bearish", type=float, default=0.4)
    rp.add_argument("--json", action="store_true")
    rp.add_argument("--out", default=None, help="写入文件")
    rp.add_argument("--strict", action="store_true", help="缺价/完整率不达标时非 0 退出")
    rp.add_argument("--min-complete", type=float, default=0.9, help="--strict 时完整率门槛")
    rp.set_defaults(func=cmd_report)
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

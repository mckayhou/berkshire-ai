#!/usr/bin/env python3
"""五维打板评分筛选 → thesis_queue 友好 JSON。

移植自 TDX-MCP-LHDB-Agent 的 UnifiedScoringSystem，用本地 daily_ohlcv.csv
代理竞价/涨停信号（无需 Windows 通达信 DLL）。

用法：
  python3 tools/limitup_screener_bridge.py --json
  python3 tools/limitup_screener_bridge.py --codes 600519,000001 --min-score 70
  python3 tools/thesis_queue.py --from-limitup-scan limitup_scan.json --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "tools") not in sys.path:
    sys.path.insert(0, str(_REPO / "tools"))


def main() -> None:
    parser = argparse.ArgumentParser(description="五维打板评分 → thesis_queue JSON")
    parser.add_argument("--codes", help="逗号分隔代码；省略则扫描 CSV 内全部")
    parser.add_argument("--min-score", type=float, help="最低评分，默认 BERKSHIRE_LIMITUP_SCORE_MIN")
    parser.add_argument("--top", type=int, help="只保留 Top N")
    parser.add_argument("--auction-min", type=float, default=2.0, help="竞价高开下限 %%")
    parser.add_argument("--auction-max", type=float, default=7.0, help="竞价高开上限 %%")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("-o", "--output", help="写入 JSON 文件")
    args = parser.parse_args()

    from ashare_alphagpt.screener import run_limitup_screen_from_csv

    codes = None
    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]

    result = run_limitup_screen_from_csv(
        codes=codes,
        min_score=args.min_score,
        top_n=args.top,
        auction_min_high_open=args.auction_min,
        auction_max_high_open=args.auction_max,
    )

    if args.output:
        Path(args.output).write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if args.json or args.output:
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if not result.get("ok"):
            print(f"❌ {result.get('error')}")
            sys.exit(1)
        print(f"✅ {len(result['candidates'])} 打板候选 (min_score={result.get('min_score')})")
        for c in result["candidates"][:20]:
            print(
                f"  {c['ticker']}: {c['score']:.1f} "
                f"{c['signal_type']} — {c['note'][:70]}"
            )


if __name__ == "__main__":
    main()

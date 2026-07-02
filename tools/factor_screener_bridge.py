#!/usr/bin/env python3
"""AlphaGPT 因子筛选 → thesis_queue 友好 JSON（V10.25）。

用已训练的公式（data/alphagpt/best_ashare_formula.json）对 A 股标的打分排序，
输出可供 thesis_queue / Cron 消费的研究候选。

用法：
  pip install '.[factor-mining]'
  python3 tools/ashare_factor_mining.py train --code 511260 --steps 200
  python3 tools/factor_screener_bridge.py --json
  python3 tools/factor_screener_bridge.py --codes 600519,000001,511260 --source online
  python3 tools/thesis_queue.py --from-factor-scan factor_scan.json --json
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
    parser = argparse.ArgumentParser(description="AlphaGPT 因子筛选 → thesis_queue JSON")
    parser.add_argument("--formula", help="公式 JSON 路径，默认 data/alphagpt/best_ashare_formula.json")
    parser.add_argument("--codes", help="逗号分隔代码；省略则扫描 CSV 内全部")
    parser.add_argument("--source", choices=["auto", "csv", "online"], default="auto",
                        help="auto=优先本地 CSV，否则 online 需 --codes")
    parser.add_argument("--min-score", type=float, help="最低 |score| 阈值，默认 BERKSHIRE_ALPHAGPT_SCORE_MIN")
    parser.add_argument("--top", type=int, help="只保留 Top N")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("-o", "--output", help="写入 JSON 文件")
    args = parser.parse_args()

    try:
        import torch  # noqa: F401
    except ImportError:
        print("Missing PyTorch: pip install '.[factor-mining]'", file=sys.stderr)
        sys.exit(1)

    from ashare_alphagpt.screener import run_screen

    codes = None
    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]

    result = run_screen(
        formula_path=args.formula,
        codes=codes,
        source=args.source,
        min_score=args.min_score,
        top_n=args.top,
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
        print(f"✅ {len(result['candidates'])} 候选 | formula: {result.get('formula', '')[:70]}")
        for c in result["candidates"][:20]:
            print(f"  {c['ticker']}: score={c['score']:+.3f} {c['direction']} — {c['note'][:60]}")
        if result.get("errors"):
            print(f"  ⚠️ {len(result['errors'])} 跳过/失败")


if __name__ == "__main__":
    main()

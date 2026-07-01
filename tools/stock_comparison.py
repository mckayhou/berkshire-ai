#!/usr/bin/env python3
"""2–4 只标的横向对决矩阵（标准化对比）。

从 decision_log / experience_store 或 CLI 输入生成 Markdown 矩阵，可选输出 HTML。

用法：
  python3 tools/stock_comparison.py AAPL MSFT GOOGL
  python3 tools/stock_comparison.py --from-decisions --limit 4 --html out.html
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

_TOOLS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_TOOLS)
sys.path.insert(0, os.path.join(_REPO, "src"))

from decision_log import load_decisions  # noqa: E402
from experience_store import ExperienceStore  # noqa: E402
from graph import MASTER_PREFIXES, ROLE_NAMES  # noqa: E402

try:
    import report_html
except ImportError:
    sys.path.insert(0, _TOOLS)
    import report_html  # noqa: E402


def _latest_decision_per_ticker(tickers: List[str]) -> Dict[str, dict]:
    want = {t.strip().upper() for t in tickers}
    latest: Dict[str, dict] = {}
    for d in reversed(load_decisions()):
        if d.ticker in want and d.ticker not in latest:
            latest[d.ticker] = {
                "date": d.date,
                "scores": dict(d.scores),
                "price_anchor": d.price_anchor,
            }
    return latest


def _latest_alpha(tickers: List[str]) -> Dict[str, Optional[float]]:
    want = {t.strip().upper() for t in tickers}
    out: Dict[str, Optional[float]] = {t: None for t in want}
    for exp in reversed(ExperienceStore().load()):
        if exp.ticker in want and out[exp.ticker] is None:
            out[exp.ticker] = float(exp.alpha)
    return out


def build_matrix(tickers: List[str]) -> str:
    if not (2 <= len(tickers) <= 4):
        raise ValueError("需要 2–4 只标的")
    tickers = [t.strip().upper() for t in tickers]
    decisions = _latest_decision_per_ticker(tickers)
    alphas = _latest_alpha(tickers)
    lines = [
        "# 多股对决矩阵",
        "",
        f"> 生成时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "| 维度 | " + " | ".join(tickers) + " |",
        "|------|" + "|".join(["------"] * len(tickers)) + "|",
    ]
    # 决策日期
    lines.append(
        "| 最近决策日 | "
        + " | ".join(decisions.get(t, {}).get("date", "—") for t in tickers)
        + " |"
    )
    lines.append(
        "| 价格锚点 | "
        + " | ".join(
            f"{decisions[t]['price_anchor']:.2f}" if t in decisions else "—"
            for t in tickers
        )
        + " |"
    )
    lines.append(
        "| 最近 alpha | "
        + " | ".join(
            f"{alphas[t]:+.3f}" if alphas.get(t) is not None else "—"
            for t in tickers
        )
        + " |"
    )
    for prefix in MASTER_PREFIXES:
        name = ROLE_NAMES.get(prefix, prefix)
        cells = []
        for t in tickers:
            sc = decisions.get(t, {}).get("scores", {}).get(prefix)
            cells.append(f"{sc:.2f}" if sc is not None else "—")
        lines.append(f"| {name} 信心 | " + " | ".join(cells) + " |")
    # 综合
    avg_cells = []
    for t in tickers:
        sc = decisions.get(t, {}).get("scores", {})
        if sc:
            avg_cells.append(f"{sum(sc.values())/len(sc):.2f}")
        else:
            avg_cells.append("—")
    lines.append("| 平均信心 | " + " | ".join(avg_cells) + " |")
    lines.extend(["", "## 解读提示", "", "- 信心高但 alpha 为负 → 过度自信风险", "- 多股同主题高相关 → 组合共振", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="2–4 股对决矩阵")
    parser.add_argument("tickers", nargs="*", help="标的代码（2–4 个）")
    parser.add_argument("--from-decisions", action="store_true", help="取最近 4 只有决策记录的标的")
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--html", help="同时输出 HTML 路径")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.from_decisions:
        seen = []
        for d in reversed(load_decisions()):
            if d.ticker not in seen:
                seen.append(d.ticker)
            if len(seen) >= args.limit:
                break
        tickers = seen[: max(2, min(4, len(seen)))]
    else:
        tickers = args.tickers

    if len(tickers) < 2:
        parser.error("需要至少 2 只标的（传入或 --from-decisions）")

    md = build_matrix(tickers[:4])
    if args.json:
        print(json.dumps({"tickers": tickers[:4], "markdown": md}, ensure_ascii=False, indent=2))
    else:
        print(md)
    if args.html:
        with open(args.html, "w", encoding="utf-8") as fh:
            fh.write(report_html.render_html(md, title="Stock Comparison"))
        print(f"HTML → {args.html}", file=sys.stderr)


if __name__ == "__main__":
    main()

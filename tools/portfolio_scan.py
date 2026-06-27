#!/usr/bin/env python3
"""Portfolio scan — watchlist 扫描 + 结构化信号输出。

借鉴 ai-hedge-fund 的「多标的 + Portfolio Manager」体验，但输出为
**研究向行动卡草案**（非交易指令），与 stock_screener 分级对齐。

用法：
  python3 tools/portfolio_scan.py              # 扫描 data/watchlist.json 全部
  python3 tools/portfolio_scan.py --group us_ai_chip
  python3 tools/portfolio_scan.py NVDA MU      # 指定标的
  python3 tools/portfolio_scan.py --json       # JSON（供 Agent 消费）
  python3 tools/portfolio_scan.py --top 5      # 只展示前 N 个买入信号

依赖：复用 stock_screener 的动量+价值逻辑；需要网络（Yahoo curl）。
"""

import argparse
import json
import os
import sys
from datetime import datetime

_TOOLS = os.path.dirname(os.path.abspath(__file__))
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from stock_screener import (  # noqa: E402
    DEFAULT_WATCHLIST,
    WATCHLIST_FILE,
    scan_ticker,
)

# 与 stock_screener 分级一致；供 PM 层参考上限
POSITION_HINTS = {
    "BUY_8%": {"stance": "强烈看好", "action": "新建仓/加仓", "max_position_pct": 8},
    "BUY_5%": {"stance": "看好", "action": "新建仓/加仓", "max_position_pct": 5},
    "BUY_3%": {"stance": "试探", "action": "新建仓", "max_position_pct": 3},
    "WATCH": {"stance": "仅观察", "action": "观察", "max_position_pct": 0},
    "PASS": {"stance": "回避", "action": "不操作", "max_position_pct": 0},
    "SKIP": {"stance": "无信号", "action": "跳过", "max_position_pct": 0},
}


def load_watchlist(groups: list[str] | None = None) -> dict[str, list[str]]:
    """加载 watchlist；groups 为空则返回全部分组。"""
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, encoding="utf-8") as f:
            wl = json.load(f)
    else:
        wl = dict(DEFAULT_WATCHLIST)

    if not groups:
        return wl

    missing = [g for g in groups if g not in wl]
    if missing:
        raise ValueError(f"未知 watchlist 分组: {', '.join(missing)}")
    return {g: wl[g] for g in groups}


def flatten_tickers(wl: dict[str, list[str]]) -> list[tuple[str, str]]:
    """(ticker, group) 列表，去重保留首次分组。"""
    seen = set()
    out = []
    for group, tickers in wl.items():
        for t in tickers:
            key = t.upper()
            if key not in seen:
                seen.add(key)
                out.append((key, group))
    return out


def build_signal_record(ticker: str, group: str, scan_result: dict) -> dict:
    """将 scan_ticker 结果转为结构化行动卡草案。"""
    grade = scan_result["grade"]
    hint = POSITION_HINTS.get(grade, POSITION_HINTS["SKIP"])
    m = scan_result.get("momentum") or {}
    v = scan_result.get("value")

    rec = {
        "ticker": ticker,
        "group": group,
        "grade": grade,
        "stance": hint["stance"],
        "suggested_action": hint["action"],
        "max_position_pct": hint["max_position_pct"],
        "reason": scan_result.get("reason", ""),
        "advice": scan_result.get("advice", ""),
        "price": m.get("close"),
        "date": m.get("date"),
        "pct_30d": m.get("pct_30d"),
        "vol_ratio": m.get("vol_ratio"),
        "value_score": v.get("score") if v else None,
        "value_max": v.get("max") if v else None,
        "fund_label": v.get("fund_label", "") if v else "",
        "independent_pass": v.get("independent_pass") if v else False,
        "note": "扫描信号草案，须结合深度研报与组合审视后定稿（见 docs/action-card.md）",
    }
    return rec


def run_scan(tickers_with_group: list[tuple[str, str]], verbose: bool = True) -> list[dict]:
    results = []
    for ticker, group in tickers_with_group:
        raw = scan_ticker(ticker, verbose=verbose)
        if raw:
            results.append(build_signal_record(ticker, group, raw))
    return results


def summarize(results: list[dict], risk_result: dict | None = None) -> dict:
    buy = [r for r in results if r["grade"].startswith("BUY")]
    watch = [r for r in results if r["grade"] == "WATCH"]
    buy.sort(key=lambda x: x["max_position_pct"], reverse=True)
    out = {
        "scanned": len(results),
        "buy_count": len(buy),
        "watch_count": len(watch),
        "buy_signals": buy,
        "watch_signals": watch,
        "timestamp": datetime.now().isoformat(),
    }
    if risk_result is not None:
        out["risk_flags"] = risk_result.get("flags", [])
        out["risk_ok"] = risk_result.get("ok", True)
        out["risk_metrics"] = risk_result.get("metrics", {})
    return out


def print_human_summary(summary: dict, top: int | None = None):
    print(f"\n{'='*70}")
    print(f"  Portfolio Scan — 行动卡草案  {summary['timestamp'][:10]}")
    print(f"  扫描有效标的: {summary['scanned']}  |  买入信号: {summary['buy_count']}  |  观察: {summary['watch_count']}")
    print(f"{'='*70}\n")

    buys = summary["buy_signals"]
    if top:
        buys = buys[:top]

    if buys:
        print("  🎯 买入信号（按建议仓位上限排序）")
        print(f"  {'代码':<10} {'分组':<14} {'立场':<8} {'仓位上限':>6}  {'现价':>8}  理由")
        print(f"  {'-'*10} {'-'*14} {'-'*8} {'-'*6}  {'-'*8}  {'-'*20}")
        for r in buys:
            px = f"${r['price']}" if r.get("price") else "—"
            print(
                f"  {r['ticker']:<10} {r['group']:<14} {r['stance']:<8} "
                f"{r['max_position_pct']:>5}%  {px:>8}  {r['reason'][:40]}"
            )
        print("\n  → 深度研究: skills/investment-research 或 investment-team")
        print("  → 组合核对: skills/portfolio-review")
        print("  → 行动卡模板: docs/action-card.md")
    else:
        print("  当前无买入级信号。")

    if summary["watch_signals"]:
        print(f"\n  👀 观察（需补基本面 fundamentals.json）: {len(summary['watch_signals'])} 个")
        for r in summary["watch_signals"][:10]:
            print(f"     {r['ticker']:<10} {r['group']:<14} 30日+{r.get('pct_30d')}% — stock_screener.py --update {r['ticker']}")

    if summary.get("risk_flags"):
        print("\n  ⚠️  组合 risk_flags（portfolio_risk）:")
        for f in summary["risk_flags"]:
            icon = "❌" if f["severity"] == "fail" else "⚠️"
            print(f"     {icon} {f['message']}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Watchlist 扫描 + 结构化行动卡草案（非交易指令）",
    )
    parser.add_argument("tickers", nargs="*", help="指定标的（默认扫描 watchlist 全部）")
    parser.add_argument("--group", nargs="+", help="只扫描 watchlist 中的分组，如 us_ai_chip")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--top", type=int, default=None, help="人类可读模式下只列前 N 个买入信号")
    parser.add_argument("--quiet", action="store_true", help="扫描时不打印逐标的行")
    parser.add_argument(
        "--holdings",
        help="可选：当前组合 JSON，如 '{\"NVDA\":25,\"CASH\":15}'，用于 risk_flags",
    )
    parser.add_argument(
        "--proposed",
        nargs=2,
        metavar=("TICKER", "PCT"),
        help="模拟对某标的加仓后的风险（需配合 --holdings）",
    )
    args = parser.parse_args()

    if args.tickers:
        pairs = [(t.upper(), "manual") for t in args.tickers]
    else:
        wl = load_watchlist(args.group)
        pairs = flatten_tickers(wl)
        if not pairs:
            print("⚠️  watchlist 为空，请编辑 data/watchlist.json")
            sys.exit(1)

    print(f"\n  扫描 {len(pairs)} 个标的 …")
    results = run_scan(pairs, verbose=not args.quiet)

    risk_result = None
    if args.holdings:
        from portfolio_risk import check_holdings, parse_holdings  # noqa: E402
        h = parse_holdings(json.loads(args.holdings))
        proposed = (args.proposed[0], float(args.proposed[1])) if args.proposed else None
        # 模拟：将最高优先级买入信号作为加仓建议（若无 --proposed）
        if proposed is None and results:
            buys = [r for r in results if r["grade"].startswith("BUY")]
            if buys:
                top = buys[0]
                proposed = (top["ticker"], float(top["max_position_pct"]))
        risk_result = check_holdings(h, proposed=proposed)

    summary = summarize(results, risk_result)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_human_summary(summary, top=args.top)


if __name__ == "__main__":
    main()

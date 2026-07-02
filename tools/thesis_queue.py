#!/usr/bin/env python3
"""投资论点队列同步 — 解析 config/state.md + portfolio_scan 信号，输出待办。

将 TRIGGERED 论文、扫描买入信号与 Pending Queue 对齐，供 Agent / Cron 消费。
默认不自动改写 state.md（避免误覆盖）；--suggest-md 输出可粘贴的 Markdown。

用法：
  python3 tools/thesis_queue.py                    # 读 config/state.md
  python3 tools/thesis_queue.py --json
  python3 tools/thesis_queue.py --from-scan scan.json
  python3 tools/thesis_queue.py --run-scan --quiet  # 联网扫描后合并（慢）
  python3 tools/thesis_queue.py --suggest-md       # 打印建议追加的队列条目
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_STATE = os.path.join(_REPO, "config", "state.md")
_TOOLS = os.path.join(_REPO, "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)


def parse_active_theses(text: str) -> list[dict]:
    """解析 §1 Active Portfolio Theses 表格行。"""
    rows = []
    in_section = False
    for line in text.splitlines():
        if line.startswith("## 1."):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section or not line.strip().startswith("|"):
            continue
        if "Ticker" in line or line.strip().startswith("|---"):
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 6:
            continue
        ticker, thesis, conf, last, trigger, status = parts[:6]
        rows.append({
            "ticker": ticker,
            "thesis": thesis,
            "confidence": conf,
            "last_check": last,
            "next_trigger": trigger,
            "status": status,
            "triggered": "TRIGGERED" in status.upper() or "❌" in status,
            "watch": "⚠️" in status or "Watch" in status,
        })
    return rows


def parse_pending_queue(text: str) -> list[dict]:
    """解析 §2 Pending Research Queue 列表项。"""
    items = []
    in_section = False
    for line in text.splitlines():
        if line.startswith("## 2."):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        m = re.match(r"^- \[(x| )\]\s+\*\*([^:*]+)\*\*:?\s*(.*)$", line.strip())
        if m:
            done = m.group(1) == "x"
            items.append({
                "ticker": m.group(2).strip(),
                "note": m.group(3).strip(),
                "done": done,
            })
    return items


def load_state(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return {
        "theses": parse_active_theses(text),
        "queue": parse_pending_queue(text),
        "path": path,
    }


def queue_tickers(queue: list[dict]) -> set[str]:
    return {_norm(q["ticker"]) for q in queue if not q.get("done")}


def _norm(t: str) -> str:
    return t.strip().upper().replace(" ", "")


def merge_limitup_scan_suggestions(
    limitup_scan: dict,
    existing_queue: set[str],
    existing_theses: set[str],
) -> list[dict]:
    """从 limitup_screener_bridge 结果生成研究建议。"""
    out = []
    for c in limitup_scan.get("candidates", []):
        t = _norm(c.get("ticker", ""))
        if not t or t in existing_queue or t in existing_theses:
            continue
        score = float(c.get("score", 0))
        priority = int(min(100, score))
        if priority < 60:
            continue
        out.append({
            "ticker": c.get("ticker", t),
            "source": "limitup_screener",
            "priority": priority,
            "suggested_note": c.get("note", "")[:120],
            "action": "investment-research 验证打板信号 + 基本面/题材逻辑",
            "score": score,
            "signal_type": c.get("signal_type"),
        })
    out.sort(key=lambda x: -x["priority"])
    return out


def merge_factor_scan_suggestions(
    factor_scan: dict,
    existing_queue: set[str],
    existing_theses: set[str],
) -> list[dict]:
    """从 factor_screener_bridge 结果生成研究建议。"""
    out = []
    for c in factor_scan.get("candidates", []):
        t = _norm(c.get("ticker", ""))
        if not t or t in existing_queue or t in existing_theses:
            continue
        score = abs(float(c.get("score", 0)))
        priority = int(min(100, score * 100))
        if priority < 5:
            continue
        out.append({
            "ticker": c.get("ticker", t),
            "source": "factor_screener",
            "priority": priority,
            "suggested_note": c.get("note", "")[:120],
            "action": "investment-research 验证 AlphaGPT 因子信号 + fundamentals",
            "score": c.get("score"),
            "direction": c.get("direction"),
        })
    out.sort(key=lambda x: -x["priority"])
    return out


def merge_scan_suggestions(
    scan_summary: dict,
    existing_queue: set[str],
    existing_theses: set[str],
) -> list[dict]:
    """从 portfolio_scan 结果生成研究建议（未在队列且非仅观察）。"""
    out = []
    for sig in scan_summary.get("buy_signals", []):
        t = _norm(sig["ticker"])
        if t in existing_queue:
            continue
        reason = f"portfolio_scan {sig['grade']}: {sig.get('reason', '')[:80]}"
        priority = sig.get("max_position_pct", 0)
        out.append({
            "ticker": sig["ticker"],
            "source": "portfolio_scan",
            "priority": priority,
            "suggested_note": reason,
            "action": "investment-research 或 investment-team 深度研究",
        })
    for sig in scan_summary.get("watch_signals", []):
        t = _norm(sig["ticker"])
        if t in existing_queue or t in existing_theses:
            continue
        out.append({
            "ticker": sig["ticker"],
            "source": "portfolio_scan",
            "priority": 0,
            "suggested_note": "动量触发，需补充 fundamentals.json",
            "action": f"stock_screener.py --update {sig['ticker']}",
        })
    out.sort(key=lambda x: -x["priority"])
    return out


def build_action_plan(
    state: dict,
    scan_summary: dict | None = None,
    factor_scan: dict | None = None,
    limitup_scan: dict | None = None,
) -> dict:
    theses = state["theses"]
    queue = state["queue"]
    pending_tickers = queue_tickers(queue)
    thesis_tickers = {_norm(t["ticker"]) for t in theses}

    triggered = [t for t in theses if t["triggered"]]
    watch = [t for t in theses if t["watch"] and not t["triggered"]]

    scan_suggestions = []
    if scan_summary:
        scan_suggestions = merge_scan_suggestions(
            scan_summary, pending_tickers, thesis_tickers,
        )

    factor_suggestions = []
    if factor_scan and factor_scan.get("ok"):
        factor_suggestions = merge_factor_scan_suggestions(
            factor_scan, pending_tickers, thesis_tickers,
        )
        scan_suggestions.extend(factor_suggestions)

    limitup_suggestions = []
    if limitup_scan and limitup_scan.get("ok"):
        limitup_suggestions = merge_limitup_scan_suggestions(
            limitup_scan, pending_tickers, thesis_tickers,
        )
        scan_suggestions.extend(limitup_suggestions)

    # 研究优先级：TRIGGERED 论文 > 新 BUY 信号 > Watch 论文
    research_now = []
    for t in triggered:
        research_now.append({
            "ticker": t["ticker"],
            "source": "thesis_triggered",
            "priority": 100,
            "reason": t["status"],
            "action": "thesis-tracker 重新评估 + investment-research 深度重研",
        })
    for s in scan_suggestions:
        if s["priority"] > 0:
            research_now.append({
                "ticker": s["ticker"],
                "source": s["source"],
                "priority": s["priority"],
                "reason": s["suggested_note"],
                "action": s["action"],
            })
    for t in watch:
        research_now.append({
            "ticker": t["ticker"],
            "source": "thesis_watch",
            "priority": 10,
            "reason": t["status"],
            "action": "thesis-tracker 季度检查",
        })

    research_now.sort(key=lambda x: -x["priority"])

    return {
        "timestamp": datetime.now().isoformat(),
        "state_file": state["path"],
        "triggered_theses": triggered,
        "watch_theses": watch,
        "pending_queue_open": [q for q in queue if not q["done"]],
        "scan_suggestions": scan_suggestions,
        "factor_suggestions": factor_suggestions,
        "limitup_suggestions": limitup_suggestions,
        "research_now": research_now,
    }


def format_suggest_md(plan: dict) -> str:
    lines = ["## 建议追加到 Pending Research Queue", ""]
    for item in plan["scan_suggestions"]:
        if item["priority"] <= 0:
            continue
        src = item.get("source", "portfolio_scan")
        lines.append(
            f"- [ ] **{item['ticker']}**: {item['suggested_note']} "
            f"(来源: {src}, {datetime.now().strftime('%Y-%m-%d')})"
        )
    if len(lines) == 2:
        lines.append("- （无新买入信号需入队）")
    lines.append("")
    lines.append("## 需立即研究（TRIGGERED / 高优先级）")
    lines.append("")
    for item in plan["research_now"][:10]:
        lines.append(f"- **{item['ticker']}** [{item['source']}] — {item['reason'][:100]}")
        lines.append(f"  - 建议: {item['action']}")
    return "\n".join(lines)


def print_human(plan: dict):
    print("=" * 70)
    print("  Thesis Queue — 研究待办同步")
    print("=" * 70)
    print(f"  状态文件: {plan['state_file']}")
    print(f"  TRIGGERED 论文: {len(plan['triggered_theses'])}  |  "
          f"Watch: {len(plan['watch_theses'])}  |  "
          f"开放队列项: {len(plan['pending_queue_open'])}")
    if plan["scan_suggestions"]:
        print(f"  扫描新建议: {len(plan['scan_suggestions'])}")
    print()
    if plan["research_now"]:
        print("  📋 建议优先处理（Top 10）")
        for i, item in enumerate(plan["research_now"][:10], 1):
            print(f"  {i:>2}. {item['ticker']:<10} [{item['source']}]  {item['reason'][:55]}")
    else:
        print("  ✅ 无紧急研究待办")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="state.md + portfolio_scan 研究队列同步")
    parser.add_argument("--state", default=DEFAULT_STATE, help="state.md 路径")
    parser.add_argument("--from-scan", help="portfolio_scan --json 输出文件")
    parser.add_argument("--from-factor-scan", help="factor_screener_bridge --json 输出文件")
    parser.add_argument("--from-limitup-scan", help="limitup_screener_bridge --json 输出文件")
    parser.add_argument("--run-factor-scan", action="store_true",
                        help="运行 factor_screener_bridge（需已训练公式 + 本地 CSV 或 --factor-codes）")
    parser.add_argument("--run-limitup-scan", action="store_true",
                        help="运行 limitup_screener_bridge（需本地 CSV）")
    parser.add_argument("--limitup-codes", help="--run-limitup-scan 限定代码列表")
    parser.add_argument("--factor-codes", help="--run-factor-scan 在线模式代码列表")
    parser.add_argument("--run-scan", action="store_true", help="联网运行 portfolio_scan")
    parser.add_argument("--quiet", action="store_true", help="--run-scan 时静默扫描")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--suggest-md", action="store_true", help="输出可粘贴的 Markdown 建议")
    args = parser.parse_args()

    if not os.path.exists(args.state):
        print(f"❌ 状态文件不存在: {args.state}", file=sys.stderr)
        sys.exit(1)

    state = load_state(args.state)
    scan_summary = None
    factor_scan = None
    limitup_scan = None

    if args.from_scan:
        with open(args.from_scan, encoding="utf-8") as f:
            scan_summary = json.load(f)
    elif args.from_factor_scan:
        with open(args.from_factor_scan, encoding="utf-8") as f:
            factor_scan = json.load(f)
    elif args.from_limitup_scan:
        with open(args.from_limitup_scan, encoding="utf-8") as f:
            limitup_scan = json.load(f)
    elif args.run_factor_scan:
        try:
            import torch  # noqa: F401
            from ashare_alphagpt.screener import run_screen

            codes = None
            if args.factor_codes:
                codes = [c.strip() for c in args.factor_codes.split(",") if c.strip()]
            source = "online" if codes else "auto"
            factor_scan = run_screen(codes=codes, source=source)
        except Exception as e:
            print(f"❌ factor scan failed: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.run_limitup_scan:
        try:
            from ashare_alphagpt.screener import run_limitup_screen_from_csv

            codes = None
            if args.limitup_codes:
                codes = [c.strip() for c in args.limitup_codes.split(",") if c.strip()]
            limitup_scan = run_limitup_screen_from_csv(codes=codes)
        except Exception as e:
            print(f"❌ limitup scan failed: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.run_scan:
        from portfolio_scan import (  # noqa: E402
            flatten_tickers,
            load_watchlist,
            run_scan,
            summarize,
        )
        wl = load_watchlist()
        pairs = flatten_tickers(wl)
        results = run_scan(pairs, verbose=not args.quiet)
        scan_summary = summarize(results)

    plan = build_action_plan(state, scan_summary, factor_scan, limitup_scan)

    if args.suggest_md:
        print(format_suggest_md(plan))
    elif args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print_human(plan)


if __name__ == "__main__":
    main()

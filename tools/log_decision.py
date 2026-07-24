#!/usr/bin/env python3
"""投研决策落盘 CLI（投研效果契约）。

正式研究报告完成后，必须追加一条 DecisionRecord，否则无法做后验 KPI。

用法
----
    # 追加一条完整研究决策
    python3 tools/log_decision.py append \\
      --ticker NVDA --date 2026-07-06 --price 120 \\
      --scores '{"duan":0.88,"buffett":0.90,"munger":0.82,"lilu":0.85}' \\
      --thesis "AI 算力核心 + CUDA 护城河" \\
      --kill "PE>40 或 份额<75%" \\
      --action hold --horizon 20 --depth standard --skill investment-research

    # 列表 / 契约缺口
    python3 tools/log_decision.py list
    python3 tools/log_decision.py gaps
    python3 tools/log_decision.py list --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from decision_log import (  # noqa: E402
    ACTION_STANCE_BANDS,
    DEFAULT_HORIZON_DAYS,
    DecisionRecord,
    action_stance_gaps,
    append_decision,
    default_log_path,
    format_action_stance_rule,
    incomplete_research_decisions,
    is_research_complete,
    load_decisions,
    maturity_date,
    mean_stance,
    research_gaps,
)
from graph import MASTER_PREFIXES  # noqa: E402


def _parse_scores(raw: str) -> Dict[str, float]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise SystemExit("--scores 必须是 JSON 对象")
    return {str(k): float(v) for k, v in data.items()}


def _uniform_scores(stance: float) -> Dict[str, float]:
    s = max(0.0, min(1.0, float(stance)))
    return {p: s for p in MASTER_PREFIXES}


def cmd_append(args: argparse.Namespace) -> int:
    if args.scores:
        scores = _parse_scores(args.scores)
    elif args.stance is not None:
        scores = _uniform_scores(args.stance)
    else:
        raise SystemExit("必须提供 --scores JSON 或 --stance 0~1")

    rec = DecisionRecord(
        ticker=args.ticker,
        date=args.date,
        scores=scores,
        price_anchor=args.price,
        benchmark=args.benchmark or None,
        benchmark_anchor=args.benchmark_price,
        note=args.note or "",
        horizon_days=args.horizon,
        thesis=args.thesis or "",
        kill_condition=args.kill or "",
        action=args.action or "",
        depth=args.depth or "",
        skill=args.skill or "",
    )
    gaps = research_gaps(rec)
    stance_gaps = action_stance_gaps(rec)
    # 默认仍落盘（保留审计轨迹）；--strict 时遇缺口拒绝写入
    if args.strict and gaps:
        print(
            json.dumps(
                {
                    "ok": False,
                    "rejected": True,
                    "ticker": rec.ticker,
                    "date": rec.date,
                    "mean_stance": mean_stance(rec),
                    "gaps": gaps,
                    "action_stance_rule": format_action_stance_rule(rec.action),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 3

    path = append_decision(rec, path=args.log)
    print(json.dumps(
        {
            "ok": True,
            "path": path,
            "ticker": rec.ticker,
            "date": rec.date,
            "maturity": maturity_date(rec),
            "mean_stance": mean_stance(rec),
            "research_complete": is_research_complete(rec),
            "gaps": gaps,
            "action_stance_rule": format_action_stance_rule(rec.action),
        },
        ensure_ascii=False,
        indent=2,
    ))
    if gaps:
        hint = ""
        if stance_gaps:
            hint = (
                f" action↔stance 须满足: {format_action_stance_rule(rec.action)}"
                f"（见 ACTION_STANCE_BANDS）。"
            )
        print(
            f"警告: 契约不完整，缺 {gaps}。{hint}"
            "后验 KPI 仍可记方向，但 complete_rate 会扣分。",
            file=sys.stderr,
        )
        return 2
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    rows = load_decisions(args.log)
    if args.ticker:
        t = args.ticker.strip().upper()
        rows = [r for r in rows if r.ticker == t]
    payload = []
    for r in rows:
        ms = mean_stance(r)
        payload.append(
            {
                "ticker": r.ticker,
                "date": r.date,
                "maturity": maturity_date(r),
                "action": r.action,
                "mean_stance": round(ms, 4) if ms is not None else None,
                "price_anchor": r.price_anchor,
                "complete": is_research_complete(r),
                "gaps": research_gaps(r),
                "thesis": r.thesis[:80],
                "kill_condition": r.kill_condition[:80],
                "depth": r.depth,
                "skill": r.skill,
            }
        )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"决策日志: {args.log or default_log_path()}  n={len(payload)}")
        for p in payload:
            flag = "OK" if p["complete"] else "GAP"
            print(
                f"[{flag}] {p['ticker']:10} {p['date']} → {p['maturity'] or '?':10} "
                f"act={p['action'] or '-':6} stance={p['mean_stance']}  {p['thesis'][:40]}"
            )
    return 0


def cmd_gaps(args: argparse.Namespace) -> int:
    rows = incomplete_research_decisions(args.log)
    payload = [
        {
            "ticker": r.ticker,
            "date": r.date,
            "gaps": research_gaps(r),
            "mean_stance": mean_stance(r),
            "action": r.action,
            "action_stance_rule": format_action_stance_rule(r.action),
            "thesis": r.thesis,
        }
        for r in rows
    ]
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"契约不完整: {len(payload)} 条")
        print(
            "action↔stance 带宽: "
            + ", ".join(
                f"{a}→{format_action_stance_rule(a)}"
                for a in ("buy", "add", "hold", "reduce", "exit", "watch")
            )
        )
        for p in payload:
            ms = p["mean_stance"]
            ms_s = f"{ms:.3f}" if isinstance(ms, float) else "-"
            print(
                f"  {p['ticker']} {p['date']}: act={p['action'] or '-'} "
                f"stance={ms_s} 缺 {p['gaps']}"
            )
    return 0 if not payload else 1


def cmd_bands(_args: argparse.Namespace) -> int:
    """打印 action↔mean_stance 带宽表（给 Agent / 人工对照）。"""
    rows = [
        {"action": a, "rule": format_action_stance_rule(a), "band": ACTION_STANCE_BANDS[a]}
        for a in ("buy", "add", "hold", "reduce", "exit", "watch")
    ]
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="DecisionRecord 落盘 / 列表 / 契约缺口")
    p.add_argument("--log", default=None, help="覆盖 BERKSHIRE_DECISION_LOG")
    sub = p.add_subparsers(dest="cmd", required=True)

    ap = sub.add_parser("append", help="追加一条决策")
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--price", type=float, required=True, help="price_anchor")
    ap.add_argument("--scores", default=None, help='JSON 如 {"duan":0.8,...}')
    ap.add_argument("--stance", type=float, default=None, help="四大师统一 stance（无 scores 时）")
    ap.add_argument("--thesis", default="")
    ap.add_argument("--kill", default="", dest="kill", help="kill_condition / 失效条件")
    ap.add_argument(
        "--action",
        default="",
        choices=["", "buy", "add", "hold", "reduce", "exit", "watch"],
    )
    ap.add_argument("--horizon", type=int, default=DEFAULT_HORIZON_DAYS)
    ap.add_argument("--depth", default="", choices=["", "lite", "standard", "deep"])
    ap.add_argument("--skill", default="investment-research")
    ap.add_argument("--benchmark", default="")
    ap.add_argument("--benchmark-price", type=float, default=None)
    ap.add_argument("--note", default="")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="契约/action↔stance 有缺口时拒绝落盘（exit 3）",
    )
    ap.set_defaults(func=cmd_append)

    lp = sub.add_parser("list", help="列出决策")
    lp.add_argument("--ticker", default=None)
    lp.add_argument("--json", action="store_true")
    lp.set_defaults(func=cmd_list)

    gp = sub.add_parser("gaps", help="列出契约不完整记录（含 action↔stance）")
    gp.add_argument("--json", action="store_true")
    gp.set_defaults(func=cmd_gaps)

    bp = sub.add_parser("bands", help="打印 action↔mean_stance 带宽表")
    bp.set_defaults(func=cmd_bands)

    return p


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

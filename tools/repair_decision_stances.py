#!/usr/bin/env python3
"""修复决策日志中 action↔mean_stance 越界记录（不伪造收益，只校正契约一致性）。

默认 **clip**：保留 action，按比例/平移缩放 scores，使 mean_stance 落入带宽。
可选 **remap-action**：保留 scores，把 action 改成与 stance 相容的最近操作。

用法
----
    # 干跑（默认）
    python3 tools/repair_decision_stances.py
    python3 tools/repair_decision_stances.py --json

    # 写回（先备份 .bak-stance-repair.<ts>）
    python3 tools/repair_decision_stances.py --apply
    python3 tools/repair_decision_stances.py --apply --strategy remap-action

设计约束
--------
- 只改 scores 或 action + note 审计后缀；不改 price/thesis/date。
- 缺 thesis/kill/action/horizon 的字段缺口不在此工具范围（仍用 log_decision gaps）。
- 零新依赖；可注入 --log。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from decision_log import (  # noqa: E402
    ACTION_STANCE_BANDS,
    DecisionRecord,
    action_stance_gaps,
    default_log_path,
    format_action_stance_rule,
    is_research_complete,
    load_decisions,
    mean_stance,
    research_gaps,
)

STRATEGIES = ("clip", "remap-action")


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _target_mean_for_action(action: str, current: float) -> Optional[float]:
    """越界时把 mean 拉到带宽内侧边界；已在带宽内返回 None。"""
    action = (action or "").strip().lower()
    band = ACTION_STANCE_BANDS.get(action)
    if not band:
        return None
    lo, hi = band
    if lo is not None and current < lo - 1e-12:
        return float(lo)
    if hi is not None and current > hi + 1e-12:
        return float(hi)
    return None


def scale_scores_to_mean(
    scores: Dict[str, float],
    target: float,
) -> Dict[str, float]:
    """平移 + 必要时等比缩放，使均值尽量贴近 target（clip 到 [0,1]）。"""
    if not scores:
        return scores
    keys = list(scores.keys())
    vals = [float(scores[k]) for k in keys]
    cur = sum(vals) / len(vals)
    target = _clip01(target)
    if abs(cur - target) < 1e-12:
        return {k: float(scores[k]) for k in keys}

    # 1) 平移
    delta = target - cur
    shifted = [_clip01(v + delta) for v in vals]
    mean_s = sum(shifted) / len(shifted)
    if abs(mean_s - target) < 1e-6:
        return {k: round(shifted[i], 6) for i, k in enumerate(keys)}

    # 2) 相对中点缩放（处理触边后均值仍偏）
    mid = 0.5
    centered = [v - mid for v in shifted]
    # 目标：mid + scale * centered 的均值 = target
    # mean(mid + scale*c) = mid + scale*mean(c) = target
    mc = sum(centered) / len(centered)
    if abs(mc) < 1e-12:
        # 全被 clip 成常数 → 直接填 target
        return {k: round(target, 6) for k in keys}
    scale = (target - mid) / mc
    scaled = [_clip01(mid + scale * c) for c in centered]
    # 3) 若仍有误差，最后一次微调平移（允许轻微触边损失）
    mean_sc = sum(scaled) / len(scaled)
    fix = target - mean_sc
    final = [_clip01(v + fix) for v in scaled]
    return {k: round(final[i], 6) for i, k in enumerate(keys)}


def suggest_action_for_stance(stance: float) -> str:
    """按 stance 选一个「自然」action（用于 remap-action）。

    区间（与带宽相容，取中位偏好）:
      ≥0.80 → add（高信心应体现为加仓/买入侧）
      ≥0.70 → hold
      ≥0.55 → watch
      ≥0.45 → hold（中性偏持有；也可用 watch，hold 更中性）
      else  → reduce
    """
    s = float(stance)
    if s >= 0.80:
        return "add"
    if s >= 0.70:
        return "hold"
    if s >= 0.55:
        return "watch"
    if s >= 0.45:
        return "hold"
    return "reduce"


def plan_repair(
    record: DecisionRecord,
    *,
    strategy: str = "clip",
) -> Optional[Dict[str, Any]]:
    """若记录仅有 action_stance 缺口（或夹杂可忽略），返回修复计划；否则 None。

    返回 None 表示无需/无法用本工具修（无 stance 缺口，或缺核心字段）。
    """
    gaps = research_gaps(record)
    stance_gaps = action_stance_gaps(record)
    if not stance_gaps:
        return None

    # 有字段级缺口时仍可修 stance，但标记 partial
    field_gaps = [g for g in gaps if not str(g).startswith("action_stance:")]
    ms = mean_stance(record)
    if ms is None:
        return None

    before_scores = dict(record.scores)
    before_action = record.action
    after_scores = dict(before_scores)
    after_action = before_action
    detail = ""

    if strategy == "clip":
        target = _target_mean_for_action(before_action, ms)
        if target is None:
            return None
        after_scores = scale_scores_to_mean(before_scores, target)
        detail = (
            f"clip scores mean {ms:.4f}→{sum(after_scores.values())/len(after_scores):.4f} "
            f"for action={before_action} ({format_action_stance_rule(before_action)})"
        )
    elif strategy == "remap-action":
        after_action = suggest_action_for_stance(ms)
        # 若建议 action 仍越界（理论上不应），再 clip
        tmp = DecisionRecord(
            ticker=record.ticker,
            date=record.date,
            scores=after_scores,
            price_anchor=record.price_anchor,
            action=after_action,
            thesis=record.thesis or "x",
            kill_condition=record.kill_condition or "x",
            horizon_days=record.horizon_days or 20,
        )
        if action_stance_gaps(tmp):
            t2 = _target_mean_for_action(after_action, ms)
            if t2 is not None:
                after_scores = scale_scores_to_mean(after_scores, t2)
        detail = f"remap action {before_action!r}→{after_action!r} (stance={ms:.4f})"
    else:
        raise ValueError(f"未知 strategy: {strategy}")

    trial = DecisionRecord(
        ticker=record.ticker,
        date=record.date,
        scores=after_scores,
        price_anchor=record.price_anchor,
        benchmark=record.benchmark,
        benchmark_anchor=record.benchmark_anchor,
        note=record.note,
        analyses=record.analyses,
        trace_id=record.trace_id,
        hypothesis_id=record.hypothesis_id,
        created_at=record.created_at,
        horizon_days=record.horizon_days,
        thesis=record.thesis,
        kill_condition=record.kill_condition,
        action=after_action,
        depth=record.depth,
        skill=record.skill,
    )
    # 审计 note
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    audit = f"[stance-repair {stamp} {strategy}] {detail}"
    note = (record.note or "").strip()
    trial.note = f"{note} | {audit}" if note else audit

    after_ms = mean_stance(trial)
    return {
        "ticker": record.ticker,
        "date": record.date,
        "strategy": strategy,
        "before_action": before_action,
        "after_action": after_action,
        "before_mean_stance": round(ms, 6),
        "after_mean_stance": round(after_ms, 6) if after_ms is not None else None,
        "before_scores": before_scores,
        "after_scores": after_scores,
        "before_gaps": gaps,
        "after_gaps": research_gaps(trial),
        "after_complete": is_research_complete(trial),
        "field_gaps_remaining": field_gaps,
        "detail": detail,
        "record": trial,
    }


def repair_all(
    records: List[DecisionRecord],
    *,
    strategy: str = "clip",
) -> Tuple[List[DecisionRecord], List[Dict[str, Any]]]:
    """返回 (新列表, 计划列表)。未改动的记录原样保留。"""
    out: List[DecisionRecord] = []
    plans: List[Dict[str, Any]] = []
    for rec in records:
        plan = plan_repair(rec, strategy=strategy)
        if plan is None:
            out.append(rec)
            continue
        plans.append({k: v for k, v in plan.items() if k != "record"})
        out.append(plan["record"])
    return out, plans


def write_decisions(path: str, records: List[DecisionRecord]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")


def backup_log(path: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bak = f"{path}.bak-stance-repair.{ts}"
    shutil.copy2(path, bak)
    return bak


def cmd_main(args: argparse.Namespace) -> int:
    path = args.log or default_log_path()
    if not os.path.isfile(path):
        print(f"决策日志不存在: {path}", file=sys.stderr)
        return 2

    records = load_decisions(path)
    new_rows, plans = repair_all(records, strategy=args.strategy)

    payload = {
        "path": path,
        "strategy": args.strategy,
        "n_total": len(records),
        "n_planned": len(plans),
        "plans": plans,
        "apply": bool(args.apply),
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"决策日志: {path}")
        print(f"策略: {args.strategy}  总条数={len(records)}  待修={len(plans)}")
        if not plans:
            print("无 action↔stance 越界，无需修复。")
        for p in plans:
            print(
                f"  {p['ticker']:10} {p['date']}  "
                f"{p['before_action']}→{p['after_action']}  "
                f"stance {p['before_mean_stance']:.4f}→{p['after_mean_stance']}  "
                f"complete={p['after_complete']}  {p['detail']}"
            )
            if p["after_gaps"]:
                print(f"    after_gaps={p['after_gaps']}")

    if not plans:
        return 0

    if not args.apply:
        print("[dry-run] 不加 --apply 不写盘。", file=sys.stderr)
        return 0

    bak = backup_log(path)
    write_decisions(path, new_rows)
    print(f"已备份 → {bak}", file=sys.stderr)
    print(f"已写回 → {path}（{len(plans)} 条已修）", file=sys.stderr)

    # 写盘后复核
    left = [r for r in load_decisions(path) if action_stance_gaps(r)]
    if left:
        print(f"警告: 仍有 {len(left)} 条 stance 缺口", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="修复 DecisionRecord action↔stance 越界")
    p.add_argument("--log", default=None, help="覆盖 BERKSHIRE_DECISION_LOG")
    p.add_argument(
        "--strategy",
        choices=STRATEGIES,
        default="clip",
        help="clip=保留 action 调 scores；remap-action=保留 scores 调 action",
    )
    p.add_argument("--apply", action="store_true", help="写回 JSONL（默认 dry-run）")
    p.add_argument("--json", action="store_true")
    return p


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(cmd_main(args))


if __name__ == "__main__":
    raise SystemExit(main())

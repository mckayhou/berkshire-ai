#!/usr/bin/env python3
"""对已到期 DecisionRecord 批量跑 realized feedback → 沉淀 Experience。

把「后验能定价」推进到「经验库可学习」：扫描 maturity≤as_of 的决策，
取价 → run_with_realized_feedback → experiences.jsonl（按 ticker+date+maturity 去重）。

用法
----
    # 干跑
    python3 tools/feedback_due_decisions.py
    python3 tools/feedback_due_decisions.py --as-of 2026-07-24 --json

    # 写经验（备份 experiences；不改 decisions）
    python3 tools/feedback_due_decisions.py --apply

    # 离线价图（键 TICKER|YYYY-MM-DD，与 posterior_weekly 相同）
    python3 tools/feedback_due_decisions.py --apply --offline \\
      --prices '{"TSM|2026-07-19":398.37}'

设计
----
- 默认 dry-run；--apply 才写 experiences。
- 去重键：(ticker, date, maturity)。经验 tags 含 ``mat:YYYY-MM-DD``。
- 价格：--prices 优先，否则 NetworkPriceProvider（含 Yahoo chart 回退）。
- 不重复 append decision。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from decision_log import (  # noqa: E402
    DecisionRecord,
    default_log_path as default_decision_log,
    load_decisions,
    maturity_date,
    mean_stance,
)
from experience_store import (  # noqa: E402
    ExperienceStore,
    classify_verdict,
    default_log_path as default_experience_log,
    experience_from_stats,
)
from realized_feedback import (  # noqa: E402
    NetworkPriceProvider,
    PriceProvider,
    StaticPriceProvider,
    realized_scores_via_provider,
)


def _today() -> str:
    return date.today().isoformat()


def _parse_day(s: str) -> str:
    return str(s).strip()[:10]


def maturity_tag(mat: str) -> str:
    return f"mat:{_parse_day(mat)}"


def load_price_map(raw: Optional[str], path: Optional[str]) -> Dict[str, float]:
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


def build_price_provider(
    price_map: Dict[str, float],
    *,
    network: bool,
) -> PriceProvider:
    static: Dict[Tuple[str, str], float] = {}
    for k, v in price_map.items():
        if "|" not in k:
            continue
        tkr, d = k.split("|", 1)
        static[(tkr.strip().upper(), d.strip()[:10])] = float(v)

    if static and not network:
        return StaticPriceProvider(static)

    if network:
        inner = NetworkPriceProvider()
        if not static:
            return inner

        class PreferMapProvider(PriceProvider):
            def get_price(self, ticker: str, date: str) -> float:
                key = (str(ticker).strip().upper(), _parse_day(date))
                if key in static:
                    return static[key]
                return inner.get_price(ticker, date)

        return PreferMapProvider()

    return StaticPriceProvider(static)


def existing_mat_keys(store: ExperienceStore) -> Set[Tuple[str, str, str]]:
    """(ticker, decision_date, maturity) 已有经验。"""
    keys: Set[Tuple[str, str, str]] = set()
    for exp in store.load():
        mats = [
            str(t).split(":", 1)[1][:10]
            for t in (exp.tags or [])
            if str(t).startswith("mat:")
        ]
        d = exp.date[:10]
        t = exp.ticker
        if mats:
            for m in mats:
                keys.add((t, d, m))
        else:
            # 旧经验无 mat tag：记为 maturity=""，仅精确匹配空键时跳过
            keys.add((t, d, ""))
    return keys


def has_experience(
    keys: Set[Tuple[str, str, str]],
    ticker: str,
    date: str,
    mat: str,
) -> bool:
    t, d, m = ticker.upper(), date[:10], mat[:10]
    if (t, d, m) in keys:
        return True
    # 兼容：仅当存在「无 mat 的旧经验」且调用方愿意把其视为同一决策时
    # 这里：旧经验 (t,d,"") 只跳过「无法区分 horizon」的重复刷写——
    # 若同 ticker+date 有多条不同 maturity 决策，旧经验不阻塞带 mat 的新写入。
    # 但若旧经验就是该 mat 的反馈（人工刚跑过），用户应先给旧经验打 tag。
    # 为防 TSM 重复：若 (t,d,"") 存在且 keys 里没有其他 mat for (t,d)，则 skip。
    legacy = (t, d, "") in keys
    if not legacy:
        return False
    other_mats = [k for k in keys if k[0] == t and k[1] == d and k[2]]
    return not other_mats  # 仅有 legacy、无任何 mat → 视为已覆盖该 date


@dataclass
class FeedbackPlan:
    ticker: str
    date: str
    maturity: str
    action: str
    mean_stance: Optional[float]
    status: str
    alpha: Optional[float] = None
    realized_base: Optional[float] = None
    verdict: Optional[str] = None
    lesson: str = ""
    realized_price: Optional[float] = None
    price_date: str = ""
    note: str = ""
    horizon_days: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def iter_candidates(
    records: Sequence[DecisionRecord],
    *,
    as_of: str,
    keys: Set[Tuple[str, str, str]],
    include_not_due: bool,
) -> List[Tuple[FeedbackPlan, Optional[DecisionRecord], str]]:
    """返回 (初步 plan, record|None, price_date)。"""
    as_of_d = _parse_day(as_of)
    out: List[Tuple[FeedbackPlan, Optional[DecisionRecord], str]] = []
    for rec in records:
        mat = maturity_date(rec)
        ms = mean_stance(rec)
        base_kw = dict(
            ticker=rec.ticker,
            date=rec.date[:10],
            maturity=mat or "",
            action=rec.action or "",
            mean_stance=round(ms, 6) if ms is not None else None,
            horizon_days=rec.horizon_days,
        )
        if not mat:
            out.append((FeedbackPlan(**base_kw, status="error", note="无 maturity"), None, ""))
            continue
        if mat > as_of_d and not include_not_due:
            out.append((FeedbackPlan(**base_kw, status="not_due"), None, ""))
            continue
        if has_experience(keys, rec.ticker, rec.date, mat):
            out.append(
                (FeedbackPlan(**base_kw, status="skip_existing", note="experiences 已有"), None, "")
            )
            continue
        price_date = mat if mat <= as_of_d else as_of_d
        out.append(
            (
                FeedbackPlan(**base_kw, status="pending", price_date=price_date),
                rec,
                price_date,
            )
        )
    return out


def run_one(
    rec: DecisionRecord,
    *,
    price_date: str,
    provider: PriceProvider,
    apply: bool,
    store: ExperienceStore,
) -> FeedbackPlan:
    mat = maturity_date(rec) or price_date
    ms = mean_stance(rec)
    plan = FeedbackPlan(
        ticker=rec.ticker,
        date=rec.date[:10],
        maturity=mat,
        action=rec.action or "",
        mean_stance=round(ms, 6) if ms is not None else None,
        status="pending",
        price_date=price_date,
        horizon_days=rec.horizon_days,
    )
    try:
        px = float(provider.get_price(rec.ticker, price_date))
    except Exception as e:  # noqa: BLE001
        plan.status = "skip_incomplete_price"
        plan.note = f"缺价 {price_date}: {e}"
        return plan
    plan.realized_price = px

    try:
        scores, stats = realized_scores_via_provider(
            rec, price_date, provider
        )
    except Exception as e:  # noqa: BLE001
        # 无基准时仍可用标的价
        try:
            from realized_feedback import realized_scores

            scores, stats = realized_scores(rec, px)
        except Exception as e2:  # noqa: BLE001
            plan.status = "error"
            plan.note = f"评分失败: {e}; {e2}"
            return plan

    plan.alpha = float(stats.alpha)
    plan.realized_base = float(stats.realized_base)
    plan.verdict = classify_verdict(float(stats.alpha))
    plan.lesson = (
        f"{rec.ticker} α={stats.alpha:+.3f} rb={stats.realized_base:.3f} "
        f"px={px:.4f}@{price_date}"
    )

    if not apply:
        plan.status = "would_write"
        return plan

    tags = [maturity_tag(mat), "source:feedback_due"]
    if rec.horizon_days is not None:
        tags.append(f"horizon:{int(rec.horizon_days)}")
    if rec.action:
        tags.append(f"action:{rec.action}")
    exp = experience_from_stats(
        rec,
        stats,
        lesson=plan.lesson,
        tags=tags,
        hypothesis_id=getattr(rec, "hypothesis_id", None),
    )
    try:
        store.append(exp)
    except Exception as e:  # noqa: BLE001
        plan.status = "error"
        plan.note = f"写入经验失败: {e}"
        return plan
    plan.status = "written"
    plan.note = f"scores_keys={list(scores)}"
    return plan


def run_feedback_pass(
    *,
    as_of: str,
    decision_log: Optional[str] = None,
    experience_log: Optional[str] = None,
    price_map: Optional[Dict[str, float]] = None,
    network: bool = True,
    apply: bool = False,
    include_not_due: bool = False,
    provider: Optional[PriceProvider] = None,
) -> Dict[str, Any]:
    records = load_decisions(decision_log)
    store = ExperienceStore(path=experience_log)
    keys = existing_mat_keys(store)
    prov = provider or build_price_provider(price_map or {}, network=network)

    bak = ""
    if apply and os.path.isfile(store.path):
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        bak = f"{store.path}.bak-feedback.{ts}"
        try:
            shutil.copy2(store.path, bak)
        except OSError:
            bak = ""

    results: List[FeedbackPlan] = []
    for plan0, rec, price_date in iter_candidates(
        records,
        as_of=as_of,
        keys=keys,
        include_not_due=include_not_due,
    ):
        if rec is None:
            results.append(plan0)
            continue
        plan = run_one(
            rec, price_date=price_date, provider=prov, apply=apply, store=store
        )
        results.append(plan)
        if plan.status == "written":
            keys.add((plan.ticker, plan.date, plan.maturity))

    return {
        "as_of": as_of,
        "decision_log": decision_log or default_decision_log(),
        "experience_log": experience_log or default_experience_log(),
        "apply": apply,
        "backup": bak or None,
        "n_decisions": len(records),
        "n_would_write": sum(1 for p in results if p.status == "would_write"),
        "n_written": sum(1 for p in results if p.status == "written"),
        "n_skip_existing": sum(1 for p in results if p.status == "skip_existing"),
        "n_skip_price": sum(1 for p in results if p.status == "skip_incomplete_price"),
        "n_not_due": sum(1 for p in results if p.status == "not_due"),
        "n_error": sum(1 for p in results if p.status == "error"),
        "plans": [p.to_dict() for p in results],
    }


def _print_human(summary: Dict[str, Any]) -> None:
    print(f"as_of={summary['as_of']}  apply={summary['apply']}")
    print(
        f"decisions={summary['n_decisions']}  "
        f"written={summary['n_written']} would={summary['n_would_write']}  "
        f"skip_existing={summary['n_skip_existing']} "
        f"skip_price={summary['n_skip_price']}  "
        f"not_due={summary['n_not_due']} err={summary['n_error']}"
    )
    if summary.get("backup"):
        print(f"experiences backup: {summary['backup']}")
    for p in summary["plans"]:
        if p["status"] == "not_due":
            continue
        alpha = p.get("alpha")
        a_s = f"α={alpha:+.4f}" if isinstance(alpha, (int, float)) else ""
        print(
            f"  [{p['status']:22}] {p['ticker']:10} {p['date']}→{p['maturity']}  "
            f"act={p['action'] or '-':6} stance={p.get('mean_stance')}  "
            f"{a_s} {p.get('verdict') or ''}  {p.get('note') or ''}"
        )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="到期决策 → realized feedback → experiences")
    p.add_argument("--as-of", default=None, help="YYYY-MM-DD，默认今天")
    p.add_argument("--log", default=None, help="决策日志路径")
    p.add_argument("--experience-log", default=None, help="经验库路径")
    p.add_argument("--prices", default=None, help='JSON "TICKER|date": price')
    p.add_argument("--prices-file", default=None)
    p.add_argument("--offline", action="store_true", help="仅用 --prices，不联网")
    p.add_argument("--apply", action="store_true", help="写入 experiences")
    p.add_argument("--include-not-due", action="store_true", help="包含未到期（调试）")
    p.add_argument("--json", action="store_true")
    return p


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    as_of = args.as_of or _today()
    price_map = load_price_map(args.prices, args.prices_file)
    if args.offline and not price_map:
        print("offline 模式需要 --prices 或 --prices-file", file=sys.stderr)
        return 2

    summary = run_feedback_pass(
        as_of=as_of,
        decision_log=args.log,
        experience_log=args.experience_log,
        price_map=price_map,
        network=not args.offline,
        apply=bool(args.apply),
        include_not_due=bool(args.include_not_due),
    )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        _print_human(summary)
        if not args.apply and summary["n_would_write"]:
            print("[dry-run] 加 --apply 写入 experiences", file=sys.stderr)
    return 1 if summary["n_error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

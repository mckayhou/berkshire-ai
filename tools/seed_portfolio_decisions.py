#!/usr/bin/env python3
"""从 thesis-tracker 活持仓补录 DecisionRecord 种子。

对应 ~/.qwenpaw/berkshire_state.md 中的 Active Portfolio Theses（可改 --from-json）。
默认不覆盖已有同 ticker+date；--force 仍追加（不去重删除）。

用法
----
    python3 tools/seed_portfolio_decisions.py --dry-run
    python3 tools/seed_portfolio_decisions.py
    python3 tools/seed_portfolio_decisions.py --from-json data/portfolio_decision_seeds.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from decision_log import (  # noqa: E402
    DecisionRecord,
    append_decision,
    default_log_path,
    load_decisions,
)
from graph import MASTER_PREFIXES  # noqa: E402

# 与 2026-07-07 state 对齐的默认种子（价格锚点为当时备注近似值，后验需自行刷新）
DEFAULT_SEEDS: List[Dict[str, Any]] = [
    {
        "ticker": "NVDA",
        "date": "2026-07-06",
        "price_anchor": 198.0,
        "stance": 0.88,
        "action": "hold",
        "horizon_days": 20,
        "depth": "standard",
        "skill": "thesis-tracker",
        "thesis": "AI 算力核心基础设施，CUDA 生态护城河宽",
        "kill_condition": "PE > 40x OR 份额 < 75%",
        "note": "seed from berkshire_state 2026-07-07 Hold",
        "benchmark": "SPX",
    },
    {
        "ticker": "AVGO",
        "date": "2026-07-06",
        "price_anchor": 362.0,
        "stance": 0.72,
        "action": "watch",
        "horizon_days": 20,
        "depth": "standard",
        "skill": "thesis-tracker",
        "thesis": "HBM/CoWoS 需求持续；AI 芯片 $100B 目标未上调需观察",
        "kill_condition": "Price > $400 OR PE > 65x",
        "note": "seed from berkshire_state Watch",
        "benchmark": "SPX",
    },
    {
        "ticker": "PDD",
        "date": "2026-07-06",
        "price_anchor": 110.0,
        "stance": 0.45,
        "action": "reduce",
        "horizon_days": 20,
        "depth": "deep",
        "skill": "thesis-tracker",
        "thesis": "海外 Temu 放缓；国内利润支撑底部，但 Q2 触发重评",
        "kill_condition": "Q2 Revenue < Consensus -5%（已 TRIGGERED，需重新评估逻辑）",
        "note": "seed TRIGGERED — 立场偏谨慎，非新建仓",
        "benchmark": "SPX",
    },
    {
        "ticker": "600900",
        "date": "2026-07-06",
        "price_anchor": 27.05,
        "stance": 0.80,
        "action": "hold",
        "horizon_days": 60,
        "depth": "lite",
        "skill": "thesis-tracker",
        "thesis": "水电公用事业化，防御底仓",
        "kill_condition": "Dividend Yield < 3%",
        "note": "seed defensive sleeve",
        "benchmark": "000300",
    },
    {
        "ticker": "0700.HK",
        "date": "2026-07-06",
        "price_anchor": 447.20,
        "stance": 0.84,
        "action": "add",
        "horizon_days": 40,
        "depth": "standard",
        "skill": "thesis-tracker",
        "thesis": "AI+游戏双轮驱动，估值相对合理",
        "kill_condition": "下一财报显著 miss 或机构逻辑破裂",
        "note": "seed Accumulate HK$447.20",
        "benchmark": "HSI",
    },
]


def _scores(stance: float) -> Dict[str, float]:
    # 略微分化：芒格更保守 -0.05，巴菲特 +0.02（仍 clip 到 [0,1]）
    base = float(stance)
    raw = {
        "duan": base,
        "buffett": min(1.0, base + 0.02),
        "munger": max(0.0, base - 0.05),
        "lilu": base,
    }
    return {p: raw[p] for p in MASTER_PREFIXES}


def seeds_from_json(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SystemExit("seed JSON 必须是对象数组")
    return data


def to_record(item: Dict[str, Any]) -> DecisionRecord:
    if "scores" in item and item["scores"]:
        scores = {str(k): float(v) for k, v in item["scores"].items()}
    else:
        scores = _scores(float(item.get("stance", 0.7)))
    return DecisionRecord(
        ticker=str(item["ticker"]),
        date=str(item["date"]),
        scores=scores,
        price_anchor=float(item["price_anchor"]),
        benchmark=item.get("benchmark"),
        benchmark_anchor=item.get("benchmark_anchor"),
        note=str(item.get("note") or ""),
        horizon_days=int(item.get("horizon_days") or 20),
        thesis=str(item.get("thesis") or ""),
        kill_condition=str(item.get("kill_condition") or ""),
        action=str(item.get("action") or ""),
        depth=str(item.get("depth") or ""),
        skill=str(item.get("skill") or "thesis-tracker"),
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="补录持仓 DecisionRecord 种子")
    p.add_argument("--log", default=None)
    p.add_argument("--from-json", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true", help="即使已有同 ticker+date 也追加")
    args = p.parse_args(argv)

    items = seeds_from_json(args.from_json) if args.from_json else DEFAULT_SEEDS
    existing = load_decisions(args.log)
    existing_keys = {(r.ticker, r.date) for r in existing}

    written = 0
    skipped = 0
    for item in items:
        rec = to_record(item)
        key = (rec.ticker, rec.date)
        if key in existing_keys and not args.force:
            print(f"SKIP 已存在 {key}")
            skipped += 1
            continue
        if args.dry_run:
            print(
                f"DRY  {rec.ticker} {rec.date} act={rec.action} "
                f"stance~{item.get('stance')} thesis={rec.thesis[:40]}"
            )
            written += 1
            continue
        path = append_decision(rec, path=args.log)
        print(f"OK   {rec.ticker} {rec.date} → {path}")
        written += 1
        existing_keys.add(key)

    print(
        f"完成: written={written} skipped={skipped} log={args.log or default_log_path()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

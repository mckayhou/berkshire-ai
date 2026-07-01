#!/usr/bin/env python3
"""用经验库历史数据校准各大师「信心 vs 已实现真相」的系统性偏差。

背景
----
V10.22 的 `quality_scorer.build_experience_quality_fn` 用 |stance - realized_base|
的均值估计 prompt 质量。本工具把同一批 Experience 做成**可读的校准报告**：

  bias(prefix) = mean(stance - realized_base)

  bias > 0 → 该大师历史上系统性过度自信（信心高于事后真相）
  bias < 0 → 系统性过度谨慎

并给出建议的 per-master 校准偏移（供人工审阅或写入 BERKSHIRE_CONVICTION_OFFSET JSON）。

用法
----
    python3 tools/calibrate_conviction.py report
    python3 tools/calibrate_conviction.py report --ticker AAPL
    python3 tools/calibrate_conviction.py report --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

# 经验库在 src/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from experience_store import Experience, ExperienceStore  # noqa: E402
from graph import MASTER_PREFIXES  # noqa: E402


@dataclass
class ConvictionCalibration:
    """单大师校准统计。"""

    prefix: str
    n: int
    mean_bias: float
    mean_abs_error: float
    suggested_offset: float

    def to_dict(self) -> Dict:
        return {
            "prefix": self.prefix,
            "n": self.n,
            "mean_bias": round(self.mean_bias, 4),
            "mean_abs_error": round(self.mean_abs_error, 4),
            "suggested_offset": round(self.suggested_offset, 4),
        }


def filter_experiences(
    experiences: List[Experience],
    *,
    ticker: Optional[str] = None,
    min_n: int = 1,
) -> List[Experience]:
    rows = list(experiences)
    if ticker:
        tkr = str(ticker).strip().upper()
        rows = [e for e in rows if e.ticker == tkr]
    return rows if len(rows) >= min_n else []


def calibrate_conviction(
    experiences: List[Experience],
    *,
    min_samples: int = 1,
) -> List[ConvictionCalibration]:
    """按大师汇总信心偏差；样本不足的大师仍返回 n=0。"""
    sums: Dict[str, float] = {p: 0.0 for p in MASTER_PREFIXES}
    abs_sums: Dict[str, float] = {p: 0.0 for p in MASTER_PREFIXES}
    counts: Dict[str, int] = {p: 0 for p in MASTER_PREFIXES}

    for exp in experiences:
        rb = float(exp.realized_base)
        for prefix, stance in (exp.stances or {}).items():
            if prefix not in counts:
                continue
            s = float(stance)
            sums[prefix] += s - rb
            abs_sums[prefix] += abs(s - rb)
            counts[prefix] += 1

    out: List[ConvictionCalibration] = []
    for prefix in MASTER_PREFIXES:
        n = counts[prefix]
        if n < min_samples:
            out.append(
                ConvictionCalibration(prefix, n, 0.0, 0.5, 0.0)
            )
            continue
        mean_bias = sums[prefix] / n
        mean_abs = abs_sums[prefix] / n
        # 建议偏移：把信心向 realized_base 方向拉回（减过度自信）
        out.append(
            ConvictionCalibration(
                prefix=prefix,
                n=n,
                mean_bias=mean_bias,
                mean_abs_error=mean_abs,
                suggested_offset=-mean_bias,
            )
        )
    return out


def render_report(
    rows: List[ConvictionCalibration],
    *,
    ticker: Optional[str] = None,
    total_experiences: int = 0,
) -> str:
    title = "Conviction 校准报告"
    if ticker:
        title += f" ({ticker})"
    lines = [
        title,
        "=" * 56,
        f"经验条数: {total_experiences}",
        "",
        f"{'大师':<10} {'样本':>6} {'平均偏差':>10} {'|误差|':>10} {'建议偏移':>10}",
        "-" * 56,
    ]
    for r in rows:
        if r.n == 0:
            lines.append(f"{r.prefix:<10} {'—':>6} {'—':>10} {'—':>10} {'—':>10}")
            continue
        bias_s = f"{r.mean_bias:+.3f}"
        lines.append(
            f"{r.prefix:<10} {r.n:>6} {bias_s:>10} "
            f"{r.mean_abs_error:>10.3f} {r.suggested_offset:>+10.3f}"
        )
    lines.append("-" * 56)
    lines.append("偏差 = mean(stance - realized_base)；建议偏移 = -偏差")
    return "\n".join(lines)


def offsets_dict(rows: List[ConvictionCalibration]) -> Dict[str, float]:
    return {
        r.prefix: r.suggested_offset
        for r in rows
        if r.n > 0
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="经验库 conviction 校准")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("report", help="输出校准报告")
    p.add_argument("--ticker", help="仅统计该标的")
    p.add_argument("--min-samples", type=int, default=1, help="每大师最少样本")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()
    if args.command != "report":
        parser.print_help()
        return 1

    store = ExperienceStore()
    exps = filter_experiences(store.load(), ticker=args.ticker)
    rows = calibrate_conviction(exps, min_samples=args.min_samples)

    if args.json:
        payload = {
            "ticker": args.ticker,
            "n_experiences": len(exps),
            "masters": [r.to_dict() for r in rows],
            "offsets": offsets_dict(rows),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_report(rows, ticker=args.ticker, total_experiences=len(exps)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

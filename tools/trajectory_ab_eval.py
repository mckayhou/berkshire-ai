#!/usr/bin/env python3
"""历史轨迹 A/B 评测 CLI（V10.27）。

用法：
  python3 tools/trajectory_ab_eval.py
  python3 tools/trajectory_ab_eval.py --tasks tests/fixtures/trajectories/sample_tasks.json --json
  python3 tools/trajectory_ab_eval.py --no-evolution
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))

from trajectory_ab import load_tasks, render_ab_report, run_ab_report  # noqa: E402

DEFAULT_TASKS = _REPO / "tests" / "fixtures" / "trajectories" / "sample_tasks.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="TextGrad V9.3 vs V10 A/B 轨迹评测")
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS, help="tasks JSON 路径")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--no-evolution", action="store_true", help="跳过 V10.26 进化段")
    args = parser.parse_args()

    if not args.tasks.is_file():
        print(f"❌ tasks file not found: {args.tasks}", file=sys.stderr)
        sys.exit(1)

    tasks = load_tasks(args.tasks)
    report = run_ab_report(tasks, include_evolution=not args.no_evolution)

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_ab_report(report))

    # 与 test_v10_backtest 一致：覆盖率 ≥ 90% 为通过
    ok = report.diagnosis_coverage_pct >= 90.0
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

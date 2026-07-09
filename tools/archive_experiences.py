#!/usr/bin/env python3
"""归档 / 重置经验库（清理测试污染的 experiences）。

典型场景：experiences.jsonl 被同一 ticker、同一 alpha 重复刷写，
校准报告与 quality_fn 被绑架 → 先 archive 再从干净决策后验重建。

用法
----
    # 干跑：只统计
    python3 tools/archive_experiences.py --dry-run

    # 归档并清空（推荐）
    python3 tools/archive_experiences.py --reset --reason "remove AAPL test pollution"

    # 仅归档，保留原文件
    python3 tools/archive_experiences.py --reason "backup before clean slate"
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import List, Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from experience_store import DEFAULT_LOG_PATH, ENV_LOG_PATH  # noqa: E402


def _path(override: Optional[str]) -> str:
    return override or os.environ.get(ENV_LOG_PATH, DEFAULT_LOG_PATH)


def _load_lines(path: str) -> List[str]:
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [ln for ln in f.read().splitlines() if ln.strip()]


def _stats(lines: List[str]) -> Tuple[int, Counter, Counter]:
    tickers: Counter = Counter()
    alphas: Counter = Counter()
    for ln in lines:
        try:
            o = json.loads(ln)
        except json.JSONDecodeError:
            continue
        tickers[str(o.get("ticker", "?")).upper()] += 1
        a = o.get("alpha")
        if a is not None:
            alphas[round(float(a), 4)] += 1
    return len(lines), tickers, alphas


def cmd_run(args: argparse.Namespace) -> int:
    path = _path(args.path)
    lines = _load_lines(path)
    n, tickers, alphas = _stats(lines)
    print(f"经验库: {path}")
    print(f"条数: {n}")
    print(f"tickers: {tickers.most_common(10)}")
    print(f"alpha 分布 top: {alphas.most_common(5)}")

    if n == 0:
        print("空文件，无需归档。")
        return 0

    # 污染启发式：单 ticker 占比 ≥ 90% 且 单一 alpha 占比 ≥ 90%
    top_t, top_tc = tickers.most_common(1)[0] if tickers else ("?", 0)
    top_a, top_ac = alphas.most_common(1)[0] if alphas else (None, 0)
    polluted = n >= 5 and top_tc / n >= 0.9 and (top_ac / n >= 0.9 if n else False)
    if polluted:
        print(
            f"⚠️  疑似测试污染：{top_t} 占 {top_tc}/{n}，"
            f"alpha={top_a} 占 {top_ac}/{n}"
        )
    else:
        print("未触发自动污染启发式（仍可手动 --reset）。")

    if args.dry_run:
        print("[dry-run] 不写盘。")
        return 0

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = f"{path}.archive.{ts}"
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    shutil.copy2(path, archive)
    meta = {
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "source": path,
        "archive": archive,
        "reason": args.reason or "",
        "n": n,
        "tickers": dict(tickers),
        "polluted_heuristic": polluted,
    }
    with open(archive + ".meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"已归档 → {archive}")

    if args.reset:
        open(path, "w", encoding="utf-8").close()
        print(f"已清空 → {path}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="归档 experiences.jsonl")
    p.add_argument("--path", default=None, help="覆盖 BERKSHIRE_EXPERIENCE_LOG")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--reset", action="store_true", help="归档后清空原文件")
    p.add_argument("--reason", default="")
    args = p.parse_args(argv)
    return cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())

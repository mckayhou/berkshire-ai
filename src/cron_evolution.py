#!/usr/bin/env python3
"""
Cron 自动进化任务（对齐 config/state.md 定时表）。

任务类型：
  thesis-tracker  — 每日 08:30：扫描持仓论文队列
  portfolio-weekly — 每周：组合扫描 + 风险检查
  evolution-loop  — 每周五 20:00：对有经验的标的 reflect + optimize
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from .decision_log import load_decisions
    from .experience_store import ExperienceStore
    from .reflect import reflect_ticker
    from .run_recorder import RunRecord, RunRecorder
    from .trace_recorder import record_trace
except ImportError:  # pragma: no cover - flat PYTHONPATH=src
    from decision_log import load_decisions
    from experience_store import ExperienceStore
    from reflect import reflect_ticker
    from run_recorder import RunRecord, RunRecorder
    from trace_recorder import record_trace

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOLS = os.path.join(_REPO_ROOT, "tools")
_SCRIPTS = os.path.join(_REPO_ROOT, "scripts")
DEFAULT_HOLDINGS = os.path.join(_REPO_ROOT, "data", "holdings.json")


@dataclass
class CronResult:
    task: str
    ok: bool
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


def _run_py(args: List[str], *, cwd: Optional[str] = None) -> tuple[int, str]:
    cmd = [sys.executable, *args]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd or _REPO_ROOT,
        timeout=300,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def _tickers_from_holdings() -> List[str]:
    if not os.path.isfile(DEFAULT_HOLDINGS):
        return []
    try:
        with open(DEFAULT_HOLDINGS, encoding="utf-8") as fh:
            raw = json.load(fh)
        return [
            str(k).strip().upper()
            for k in raw
            if str(k).upper() not in ("CASH", "现金") and not str(k).startswith("_")
        ]
    except (json.JSONDecodeError, OSError):
        return []


def _tickers_with_experiences(min_count: int = 1) -> List[str]:
    by_ticker: Dict[str, int] = {}
    for exp in ExperienceStore().load():
        by_ticker[exp.ticker] = by_ticker.get(exp.ticker, 0) + 1
    return [t for t, n in by_ticker.items() if n >= min_count]


def run_thesis_tracker() -> CronResult:
    """Thesis Tracker：thesis_queue + portfolio_scan。"""
    errors: List[str] = []
    details: Dict[str, Any] = {}
    code, out = _run_py([os.path.join(_TOOLS, "thesis_queue.py"), "--json"])
    details["thesis_queue_exit"] = code
    if out:
        details["thesis_queue"] = out[:2000]
    if code != 0:
        errors.append("thesis_queue failed")
    if os.path.isfile(DEFAULT_HOLDINGS):
        code2, out2 = _run_py([
            os.path.join(_TOOLS, "portfolio_scan.py"),
            "--json", "--quiet", "--holdings-file", DEFAULT_HOLDINGS,
        ])
        details["portfolio_scan_exit"] = code2
        if out2:
            details["portfolio_scan"] = out2[:2000]
        if code2 != 0:
            errors.append("portfolio_scan failed")
    record_trace("PORTFOLIO", "checker", notes="cron thesis-tracker")
    return CronResult("thesis-tracker", not errors, details, errors)


def run_portfolio_weekly() -> CronResult:
    """组合周度：portfolio-weekly.sh + portfolio_risk。"""
    script = os.path.join(_SCRIPTS, "portfolio-weekly.sh")
    errors: List[str] = []
    details: Dict[str, Any] = {}
    if os.path.isfile(script):
        code, out = _run_py([script, "--suggest-md"])
        details["weekly_exit"] = code
        if out:
            details["weekly"] = out[:2000]
        if code != 0:
            errors.append("portfolio-weekly failed")
    if os.path.isfile(DEFAULT_HOLDINGS):
        code2, out2 = _run_py([
            os.path.join(_TOOLS, "portfolio_risk.py"),
            "--holdings-file", DEFAULT_HOLDINGS, "--json",
        ])
        details["risk_exit"] = code2
        if out2:
            try:
                details["risk"] = json.loads(out2)
            except json.JSONDecodeError:
                details["risk_raw"] = out2[:1000]
    record_trace("PORTFOLIO", "pm", notes="cron portfolio-weekly")
    return CronResult("portfolio-weekly", not errors, details, errors)


def run_evolution_loop(*, optimize: bool = True) -> CronResult:
    """Evolution Loop：对有经验的标的 reflect（+ 可选 optimize）。"""
    tickers = _tickers_with_experiences(min_count=1)
    if not tickers:
        tickers = list({d.ticker for d in load_decisions()})[:5]
    details: Dict[str, Any] = {"tickers": tickers, "reflect": {}, "optimize": {}}
    errors: List[str] = []
    evo_script = os.path.join(_REPO_ROOT, "src", "evolution_loop_v10.py")

    for tkr in tickers:
        try:
            rep = reflect_ticker(tkr)
            details["reflect"][tkr] = rep.to_dict()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"reflect {tkr}: {exc}")
        if optimize:
            code, out = _run_py([evo_script, "optimize", tkr, "--rounds", "1"])
            details["optimize"][tkr] = {"exit": code, "output": out[:500]}
            if code != 0:
                errors.append(f"optimize {tkr} exit {code}")
        record_trace(tkr, "evolution", notes="cron evolution-loop")

    try:
        RunRecorder().append(
            RunRecord(
                run_id="",
                event="cron_evolution",
                ticker=None,
                metrics={"tickers": len(tickers), "errors": len(errors)},
                note="evolution-loop",
            )
        )
    except OSError:
        pass

    return CronResult("evolution-loop", not errors, details, errors)


def run_cron(task: str) -> CronResult:
    """分发 Cron 任务。"""
    key = task.strip().lower().replace("_", "-")
    if key in ("thesis-tracker", "thesis", "daily"):
        return run_thesis_tracker()
    if key in ("portfolio-weekly", "weekly", "portfolio"):
        return run_portfolio_weekly()
    if key in ("evolution-loop", "evolution", "friday"):
        return run_evolution_loop()
    if key == "all":
        results = [run_thesis_tracker(), run_portfolio_weekly(), run_evolution_loop()]
        ok = all(r.ok for r in results)
        return CronResult("all", ok, {"subtasks": [r.task for r in results]})
    raise ValueError(f"未知 cron 任务: {task!r}")

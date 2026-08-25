#!/usr/bin/env python3
"""离线冒烟：Deep Research 最小依赖 CLI 能启动、help 完整、关键子命令不崩。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=str(TOOLS.parent),
    )


def test_smoke_terminal_value_help_lists_audit():
    r = _run(str(TOOLS / "terminal_value.py"), "-h")
    assert r.returncode == 0, r.stderr
    out = r.stdout + r.stderr
    for token in ("pe", "irr", "audit", "table", "sweep"):
        assert token in out


def test_smoke_financial_rigor_market_cap():
    r = _run(
        str(TOOLS / "financial_rigor.py"),
        "verify-market-cap",
        "--price", "510",
        "--shares", "9.11e9",
        "--reported", "4.65e12",
        "--currency", "HKD",
    )
    assert r.returncode == 0, r.stderr + r.stdout


def test_smoke_financial_rigor_calc():
    r = _run(str(TOOLS / "financial_rigor.py"), "calc", "--expr", "510 * 9.11e9")
    assert r.returncode == 0, r.stderr + r.stdout


def test_smoke_report_audit_dry_run(tmp_path):
    md = tmp_path / "s.md"
    md.write_text("# 冒烟\n\n营业收入：100 亿元\n", encoding="utf-8")
    r = _run(str(TOOLS / "report_audit.py"), "extract", "--report", str(md), "--dry-run")
    assert r.returncode == 0, r.stderr + r.stdout
    assert "抽检" in r.stdout or "营业收入" in r.stdout


def test_smoke_skill_files_present():
    root = TOOLS.parent
    assert (root / "skills" / "thesis-tracker.md").is_file()
    assert (root / "skills" / "investment-research.md").is_file()
    assert (root / "skills" / "financial-data.md").is_file()
    ir = (root / "skills" / "investment-research.md").read_text(encoding="utf-8")
    tt = (root / "skills" / "thesis-tracker.md").read_text(encoding="utf-8")
    fd = (root / "skills" / "financial-data.md").read_text(encoding="utf-8")
    assert "terminal_value.py" in ir
    assert "log_decision.py" in ir
    assert "log_decision.py" in tt
    assert "thesis_queue.py" in tt
    assert "股价与复权" in fd
    assert "tavily" in fd.lower() or "Tavily" in fd
    assert (root / "tools" / "terminal_value.py").is_file()

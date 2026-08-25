#!/usr/bin/env python3
"""离线 E2E：Deep Research 最小依赖集。

模拟一篇含十年折现数字的研报准出链：
  financial_rigor → terminal_value audit/pe/irr → report_audit extract+verdict → log_decision

不依赖网络 / LLM。CI 默认必跑。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

BERKSHIRE_DIR = Path(__file__).resolve().parents[2]
SRC = BERKSHIRE_DIR / "src"
TOOLS = BERKSHIRE_DIR / "tools"


def _env(tmp: Path) -> dict:
    env = os.environ.copy()
    env["BERKSHIRE_DECISION_LOG"] = str(tmp / "decisions.jsonl")
    env["BERKSHIRE_EXPERIENCE_LOG"] = str(tmp / "experiences.jsonl")
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _run(script: Path, *args: str, env: dict, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(BERKSHIRE_DIR),
        env=env,
    )


def test_e2e_deep_research_minpack_gate(tmp_path: Path) -> None:
    env = _env(tmp_path)

    r = _run(
        TOOLS / "financial_rigor.py",
        "verify-valuation",
        "--price", "80",
        "--eps", "5",
        "--bvps", "20",
        env=env,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "PE" in r.stdout or "16" in r.stdout

    r = _run(
        TOOLS / "financial_rigor.py",
        "three-scenario",
        "--price", "80",
        "--eps", "5",
        "--shares", "10",
        "--growth", "0.15", "0.10", "0.05",
        "--pe", "20", "16", "12",
        "--years", "3",
        env=env,
    )
    assert r.returncode == 0, r.stderr + r.stdout

    r = _run(
        TOOLS / "terminal_value.py",
        "audit",
        "--currency", "CNY",
        "--r", "0.08",
        "--roic", "0.20",
        "--g", "0.005,0.015,0.02",
        "--rf", "0.017",
        "--beta", "1.0",
        "--discrete-risks", "监管重击:尾部档",
        env=env,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "准出" in r.stdout

    r = _run(
        TOOLS / "terminal_value.py",
        "pe",
        "--roic", "0.20",
        "--g", "0.015",
        "--r", "0.08",
        env=env,
    )
    assert r.returncode == 0, r.stderr + r.stdout

    r = _run(
        TOOLS / "terminal_value.py",
        "irr",
        "--profit", "100",
        "--mcap", "1600",
        "--pe", "13.85",
        "--years", "10",
        "--payout", "0.01",
        env=env,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "IRR" in r.stdout

    report = tmp_path / "E2E-deep-research.md"
    report.write_text(
        """# E2E 深度研究

营业收入：1234 亿元
净利润：200 亿元
市盈率：16 x
终值 PE：13.8 x
十年 IRR：4.2%
""",
        encoding="utf-8",
    )
    r = _run(
        TOOLS / "report_audit.py",
        "extract",
        "--report",
        str(report),
        "--seed",
        "1",
        env=env,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "fetched_value" in r.stdout

    start = r.stdout.find("[")
    end = r.stdout.rfind("]") + 1
    assert start >= 0 and end > start
    sampled = json.loads(r.stdout[start:end])
    for item in sampled:
        item["fetched_value"] = item["reported_value"]
        item["fetched_source"] = "e2e-self"
        item["fetched_value2"] = item["reported_value"]
        item["fetched_source2"] = "e2e-self-2"

    r = _run(
        TOOLS / "report_audit.py",
        "verdict",
        "--results",
        json.dumps(sampled, ensure_ascii=False),
        "--report",
        str(report),
        "--output-json",
        env=env,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    brace = r.stdout.rfind("{")
    assert brace >= 0, r.stdout
    verdict = json.loads(r.stdout[brace:])
    assert verdict["verdict"] == "PASS"

    r = _run(
        TOOLS / "log_decision.py",
        "append",
        "--ticker", "E2EDR",
        "--date", "2026-08-25",
        "--price", "80",
        "--stance", "0.75",
        "--thesis", "E2E 十年折现准出",
        "--kill", "r-g 分母跌破 5pct",
        "--action", "hold",
        "--horizon", "20",
        "--depth", "deep",
        "--skill", "investment-research",
        env=env,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    payload = json.loads(r.stdout)
    assert payload["ok"] is True
    assert payload["research_complete"] is True
    assert payload.get("depth") == "deep" or "deep" in r.stdout

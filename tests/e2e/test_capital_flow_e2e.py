#!/usr/bin/env python3
"""资金行为 e2e：离线注入 + 可选真网。

离线必跑。真网失败 skip，不红 CI。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BERKSHIRE_DIR = Path(__file__).resolve().parents[2]
TOOLS = BERKSHIRE_DIR / "tools"
sys.path.insert(0, str(TOOLS))

import capital_flow as cf  # noqa: E402


def test_e2e_offline_score_json_chain() -> None:
    def holders(_c):
        return [
            {"HOLDER_TOTAL_NUM": 80_000, "END_DATE": "2026-06-30"},
            {"HOLDER_TOTAL_NUM": 100_000, "END_DATE": "2026-03-31"},
        ]

    def flow(_c):
        return [{"DATE": "2026-08-31", "MAIN_NET": -1e7, "MAIN_PCT": -1.2}] * 3

    result = cf.analyze(
        "600519",
        fetchers={
            "holders": holders,
            "margin": lambda c: [],
            "block": lambda c: [],
            "lhb": lambda c: [],
            "inst": lambda c: [],
            "north": lambda c: [],
            "flow": flow,
        },
    )
    assert result["ok"] is True
    assert result["n_modules"] == 2
    assert "holders" in result["modules"]
    assert result["modules"]["flow"]["ok"] is True


def test_e2e_live_score_cli() -> None:
    proc = subprocess.run(
        [sys.executable, str(TOOLS / "capital_flow.py"), "score", "600519", "--json"],
        capture_output=True,
        text=True,
        timeout=90,
        cwd=str(BERKSHIRE_DIR),
        env=os.environ.copy(),
    )
    if proc.returncode not in (0, 1):
        pytest.skip(f"capital_flow CLI 异常: {proc.stderr[:200]}")
    text = proc.stdout.strip()
    if not text.startswith("{"):
        pytest.skip("无 JSON 输出（网络/接口失败）")
    payload = json.loads(text)
    assert payload.get("code") == "600519"
    assert "modules" in payload
    assert set(payload["modules"]) >= {"holders", "margin", "flow", "north"}

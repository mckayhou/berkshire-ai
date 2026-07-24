#!/usr/bin/env python3
"""twstock_data.py offline unit tests (no network)."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

_spec = importlib.util.spec_from_file_location("twstock_data", TOOLS / "twstock_data.py")
assert _spec and _spec.loader
tw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tw)


def test_token_env(monkeypatch, tmp_path):
    monkeypatch.delenv("FINMIND_TOKEN", raising=False)
    monkeypatch.setattr(tw, "_TOKEN_FILE", str(tmp_path / "missing.txt"))
    assert tw._token() is None

    monkeypatch.setenv("FINMIND_TOKEN", "  abc  ")
    assert tw._token() == "abc"

    monkeypatch.delenv("FINMIND_TOKEN", raising=False)
    tok = tmp_path / "finmind_token.txt"
    tok.write_text("file-token\n", encoding="utf-8")
    monkeypatch.setattr(tw, "_TOKEN_FILE", str(tok))
    assert tw._token() == "file-token"


def test_cli_help_exits_zero(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["twstock_data.py", "--help"])
    with pytest.raises(SystemExit) as ei:
        tw.main()
    assert ei.value.code == 0


def test_module_has_expected_commands():
    # public CLI surface used by skills/financial-data.md
    src = (TOOLS / "twstock_data.py").read_text(encoding="utf-8")
    for cmd in ("quote", "valuation", "financials", "revenue", "dividend", "search"):
        assert cmd in src

#!/usr/bin/env python3
"""离线单元测试：tools/terminal_value.py（Copaw Deep Research 终值工具）。"""
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import terminal_value as tv  # noqa: E402

CLI = os.path.join(os.path.dirname(__file__), "..", "tools", "terminal_value.py")


def test_exit_pe_gordon():
    pe, retention, numerator, spread = tv.exit_pe(0.20, 0.02, 0.08)
    assert retention == pytest.approx(0.10)
    assert numerator == pytest.approx(0.90)
    assert spread == pytest.approx(0.06)
    assert pe == pytest.approx(15.0)


def test_exit_pe_invalid_when_g_ge_r():
    pe, _, _, spread = tv.exit_pe(0.20, 0.10, 0.08)
    assert pe is None
    assert spread == pytest.approx(-0.02)


def test_irr_from_terminal_roundtrip():
    irr = tv.irr_from_terminal(100.0, 1000.0, 15.0, years=10, payout=0.0)
    assert irr == pytest.approx((1.5) ** 0.1 - 1.0)


def test_audit_cli_pass():
    proc = subprocess.run(
        [
            sys.executable,
            CLI,
            "audit",
            "--currency",
            "CNY",
            "--r",
            "0.08",
            "--roic",
            "0.20",
            "--g",
            "0.005,0.015,0.02",
            "--rf",
            "0.017",
            "--beta",
            "1.0",
            "--discrete-risks",
            "监管重击:尾部档",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "准出" in proc.stdout


def test_audit_cli_rejects_risk_in_discount_rate():
    proc = subprocess.run(
        [
            sys.executable,
            CLI,
            "audit",
            "--currency",
            "CNY",
            "--r",
            "0.08",
            "--roic",
            "0.20",
            "--g",
            "0.005,0.015,0.02",
            "--rf",
            "0.017",
            "--discrete-risks",
            "退市:折现率",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 1
    assert "打回" in proc.stdout or "C3" in proc.stdout

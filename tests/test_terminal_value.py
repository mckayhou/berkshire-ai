#!/usr/bin/env python3
"""离线单元测试：tools/terminal_value.py（Copaw Deep Research 终值工具）。"""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import terminal_value as tv  # noqa: E402

CLI = os.path.join(os.path.dirname(__file__), "..", "tools", "terminal_value.py")


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, CLI, *args],
        capture_output=True,
        text=True,
        timeout=15,
    )


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


def test_irr_adds_payout():
    base = tv.irr_from_terminal(100.0, 1000.0, 15.0, years=10, payout=0.0)
    with_div = tv.irr_from_terminal(100.0, 1000.0, 15.0, years=10, payout=0.02)
    assert with_div == pytest.approx(base + 0.02)


def test_rescale_irr_identity():
    assert tv.rescale_irr(0.10, 15.0, 15.0, 0.02) == pytest.approx(0.10)


def test_warn_spread_tags():
    assert tv.warn_spread(0.0) == "✗失效"
    assert tv.warn_spread(-0.01) == "✗失效"
    assert "窄" in tv.warn_spread(0.03)
    assert tv.warn_spread(0.06) == ""


def test_load_companies_preset_and_file(tmp_path):
    preset = tv.load_companies(None)
    assert "腾讯" in preset
    cfg = tmp_path / "cos.json"
    cfg.write_text(
        json.dumps({"测试": {"roic": 0.2, "g": [0.01, 0.02, 0.03], "p": [0.3, 0.5, 0.2], "irr10": [1, 5, 9], "k": 0.0}}),
        encoding="utf-8",
    )
    loaded = tv.load_companies(str(cfg))
    assert loaded["测试"]["roic"] == 0.2
    assert loaded["测试"]["g"] == (0.01, 0.02, 0.03)


def test_evaluate_and_summarize_preset():
    spec = tv.PRESET["腾讯"]
    rows = tv.evaluate(spec, r=0.10, g_shift=0.0)
    assert len(rows) == 3
    assert all(r["pe"] is not None for r in rows)
    mean, sd, ratio = tv.summarize(rows, spec["p"], rf=0.017)
    assert mean is not None and sd is not None


def test_pe_cli():
    proc = _run("pe", "--roic", "0.20", "--g", "0.02", "--r", "0.08")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "15.0" in proc.stdout or "15.0x" in proc.stdout


def test_irr_cli():
    proc = _run("irr", "--profit", "100", "--mcap", "1000", "--pe", "15", "--years", "10")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "IRR" in proc.stdout


def test_audit_cli_pass():
    proc = _run(
        "audit",
        "--currency", "CNY",
        "--r", "0.08",
        "--roic", "0.20",
        "--g", "0.005,0.015,0.02",
        "--rf", "0.017",
        "--beta", "1.0",
        "--discrete-risks", "监管重击:尾部档",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "准出" in proc.stdout


def test_audit_cli_rejects_risk_in_discount_rate():
    proc = _run(
        "audit",
        "--currency", "CNY",
        "--r", "0.08",
        "--roic", "0.20",
        "--g", "0.005,0.015,0.02",
        "--rf", "0.017",
        "--discrete-risks", "退市:折现率",
    )
    assert proc.returncode == 1
    assert "打回" in proc.stdout or "C3" in proc.stdout


def test_audit_c1_rejects_usd_r_on_cny():
    proc = _run(
        "audit",
        "--currency", "CNY",
        "--r", "0.10",
        "--roic", "0.20",
        "--g", "0.005,0.015,0.02",
        "--rf", "0.017",
    )
    assert proc.returncode == 1
    assert "C1" in proc.stdout


def test_audit_c2_narrow_spread_fails_without_flag():
    proc = _run(
        "audit",
        "--currency", "CNY",
        "--r", "0.06",
        "--roic", "0.20",
        "--g", "0.01,0.015,0.02",
        "--rf", "0.017",
    )
    assert proc.returncode == 1
    assert "C2" in proc.stdout


def test_audit_c2_narrow_ok_with_upside_only():
    proc = _run(
        "audit",
        "--currency", "CNY",
        "--r", "0.06",
        "--roic", "0.20",
        "--g", "0.01,0.015,0.02",
        "--rf", "0.017",
        "--upside-only",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "准出" in proc.stdout


def test_audit_beta_needs_justification():
    proc = _run(
        "audit",
        "--currency", "CNY",
        "--r", "0.08",
        "--roic", "0.20",
        "--g", "0.005,0.015,0.02",
        "--rf", "0.017",
        "--beta", "1.3",
    )
    assert proc.returncode == 1
    assert "C3" in proc.stdout


def test_audit_unknown_currency():
    proc = _run(
        "audit",
        "--currency", "JPY",
        "--r", "0.08",
        "--roic", "0.20",
        "--g", "0.01,0.02,0.03",
    )
    assert proc.returncode == 1
    assert "未知币种" in (proc.stdout + proc.stderr)

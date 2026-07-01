#!/usr/bin/env python3
"""V10.24 quant fusion：LocalCsvSource / PytdxSource / quant_screener_bridge（离线 mock）。"""
import csv
import os
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import data_sources as ds  # noqa: E402
import quant_screener_bridge as qsb  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in list(os.environ):
        if k.startswith("BERKSHIRE_"):
            monkeypatch.delenv(k, raising=False)
    yield


def _write_daily_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["time", "symbol", "open", "high", "low", "close", "volume"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def test_local_csv_disabled_by_default():
    ok, reason = ds.LocalCsvSource().enabled()
    assert ok is False
    assert "BERKSHIRE_ENABLE_LOCAL_DATA" in reason


def test_local_csv_reads_daily_ohlcv(tmp_path, monkeypatch):
    monkeypatch.setenv("BERKSHIRE_ENABLE_LOCAL_DATA", "1")
    monkeypatch.setenv("BERKSHIRE_DATA_DIR", str(tmp_path))
    rows = [
        {"time": "2026-01-01", "symbol": "sh.600519", "open": "10", "high": "11",
         "low": "9", "close": "10.5", "volume": "1000"},
        {"time": "2026-01-02", "symbol": "sh.600519", "open": "10.5", "high": "12",
         "low": "10", "close": "11.0", "volume": "1200"},
    ]
    _write_daily_csv(tmp_path / "daily_ohlcv.csv", rows)

    out = ds.LocalCsvSource().daily("600519", limit=10)
    assert len(out) == 2
    assert out[-1]["close"] == "11.0"


def test_local_csv_in_chain(tmp_path, monkeypatch):
    monkeypatch.setenv("BERKSHIRE_ENABLE_LOCAL_DATA", "1")
    monkeypatch.setenv("BERKSHIRE_DATA_DIR", str(tmp_path))
    _write_daily_csv(tmp_path / "daily_ohlcv.csv", [
        {"time": "2026-01-01", "symbol": "sz.000001", "open": "1", "high": "1",
         "low": "1", "close": "1.2", "volume": "500"},
    ])
    res = ds.daily("000001", sources=["local"], limit=5)
    assert res["ok"] is True
    assert res["source"] == "local"


def test_pytdx_disabled_by_default():
    ok, reason = ds.PytdxSource().enabled()
    assert ok is False
    assert "BERKSHIRE_ENABLE_PYTDX" in reason


def test_pytdx_enabled_missing_lib(monkeypatch):
    monkeypatch.setenv("BERKSHIRE_ENABLE_PYTDX", "1")
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "pytdx":
            raise ImportError("no pytdx")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    ok, reason = ds.PytdxSource().enabled()
    assert ok is False
    assert "not installed" in reason


def test_pytdx_daily_mocked(monkeypatch):
    monkeypatch.setenv("BERKSHIRE_ENABLE_PYTDX", "1")
    pytdx_mod = types.ModuleType("pytdx")
    hq_mod = types.ModuleType("pytdx.hq")

    class _API:
        def connect(self, host, port):
            return True

        def disconnect(self):
            pass

        def get_security_bars(self, *a, **k):
            return [
                {"datetime": "2026-01-01", "open": 1, "high": 2, "low": 1,
                 "close": 1.5, "vol": 100},
            ]

    hq_mod.TdxHq_API = _API
    pytdx_mod.hq = hq_mod
    monkeypatch.setitem(sys.modules, "pytdx", pytdx_mod)
    monkeypatch.setitem(sys.modules, "pytdx.hq", hq_mod)

    out = ds.PytdxSource().daily("600519", limit=5)
    assert len(out) == 1
    assert out[0]["close"] == 1.5


def test_screener_bridge_momentum(tmp_path, monkeypatch):
    monkeypatch.setenv("BERKSHIRE_DATA_DIR", str(tmp_path))
    # 21 天横盘后突破 + 放量
    base = []
    for i in range(20):
        base.append({
            "time": f"2026-01-{i+1:02d}",
            "symbol": "sh.600519",
            "open": "100", "high": "101", "low": "99", "close": "100",
            "volume": "1000",
        })
    base.append({
        "time": "2026-01-21",
        "symbol": "sh.600519",
        "open": "100", "high": "110", "low": "100", "close": "105",
        "volume": "3000",
    })
    _write_daily_csv(tmp_path / "daily_ohlcv.csv", base)

    result = qsb.run_screen(codes=["600519"], lookback=20, vol_mult=1.5)
    assert result["ok"] is True
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["ticker"] == "600519"
    assert "thesis_queue_line" in result["candidates"][0]


def test_screener_bridge_missing_csv(tmp_path, monkeypatch):
    monkeypatch.setenv("BERKSHIRE_DATA_DIR", str(tmp_path))
    result = qsb.run_screen()
    assert result["ok"] is False
    assert result["candidates"] == []

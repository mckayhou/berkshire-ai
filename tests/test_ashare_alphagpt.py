#!/usr/bin/env python3
"""Tests for A-share AlphaGPT factor mining (no torch required for core logic)."""

from __future__ import annotations

import json
import os
import sys

import pytest

np = pytest.importorskip("numpy")
# torch 仅训练路径需要；decode/ops 在 import 链上可能要求
pytest.importorskip("torch")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from ashare_alphagpt.config import MiningConfig  # noqa: E402
from ashare_alphagpt.data_engine import AshareDataEngine  # noqa: E402
from ashare_alphagpt.decode import decode_formula  # noqa: E402
from ashare_alphagpt.features import build_features_from_arrays, robust_norm  # noqa: E402
from ashare_alphagpt.vocab import FEATURE_COUNT, VOCAB_SIZE  # noqa: E402


def _synthetic_ohlcv(n: int = 120):
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n)).astype(np.float32)
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = close + rng.uniform(0, 1, n).astype(np.float32)
    low = close - rng.uniform(0, 1, n).astype(np.float32)
    vol = rng.uniform(1e5, 2e5, n).astype(np.float32)
    dates = [f"2024{(i // 30 + 1):02d}{(i % 30 + 1):02d}" for i in range(n)]
    return dates, open_, high, low, close, vol


def test_vocab_size():
    assert VOCAB_SIZE == FEATURE_COUNT + 11
    assert FEATURE_COUNT == 5


def test_robust_norm_bounds():
    x = np.array([1.0, 2.0, 100.0, -50.0], dtype=np.float32)
    y = robust_norm(x)
    assert y.min() >= -5
    assert y.max() <= 5


def test_decode_feature_token():
    # token 0 = RET
    assert decode_formula([0]) == "RET"


def test_decode_simple_formula():
  # Prefix order: operator first, then operands
    mul_idx = FEATURE_COUNT + 2  # MUL
    s = decode_formula([mul_idx, 0, 0])
    assert "MUL" in s
    assert "RET" in s


@pytest.fixture
def synthetic_engine():
    torch = pytest.importorskip("torch")
    dates, o, h, l, c, v = _synthetic_ohlcv(200)
    cfg = MiningConfig(train_split_ratio=0.8)
    return AshareDataEngine.from_ohlcv_arrays(
        trade_dates=dates,
        open_=o,
        high=h,
        low=l,
        close=c,
        vol=v,
        config=cfg,
        device=torch.device("cpu"),
    )


def test_engine_shapes(synthetic_engine):
    eng = synthetic_engine
    assert eng.feat_data.shape[0] == FEATURE_COUNT
    assert eng.feat_data.shape[1] == 200
    assert eng.split_idx == 160


def test_vm_execute_constant_feature(synthetic_engine):
    torch = pytest.importorskip("torch")
    from ashare_alphagpt.vm import FormulaVM

    vm = FormulaVM(synthetic_engine.feat_data)
    out = vm.solve_one([0])  # RET only
    assert out is not None
    assert out.shape == (200,)


def test_backtest_sortino_runs(synthetic_engine):
    torch = pytest.importorskip("torch")
    from ashare_alphagpt.backtest import backtest_sortino
    from ashare_alphagpt.vm import FormulaVM

    vm = FormulaVM(synthetic_engine.feat_data)
    factor = vm.solve_one([0])
    assert factor is not None
    batch = factor.unsqueeze(0)
    rewards = backtest_sortino(
        batch,
        split_idx=synthetic_engine.split_idx,
        target_oto_ret=synthetic_engine.target_oto_ret,
        cost_rate=0.0005,
    )
    assert rewards.shape == (1,)
    assert rewards[0].item() > -3


def test_oos_report(synthetic_engine):
    pytest.importorskip("torch")
    from ashare_alphagpt.oos import run_oos_check

    report = run_oos_check(synthetic_engine, [0], cost_rate=0.0005)
    assert report is not None
    assert "RET" in report.formula
    assert report.test_start


def test_miner_short_train(synthetic_engine, tmp_path, monkeypatch):
    torch = pytest.importorskip("torch")
    monkeypatch.setenv("BERKSHIRE_DATA_DIR", str(tmp_path))
    from ashare_alphagpt.miner import DeepQuantMiner

    cfg = MiningConfig(batch_size=32, train_iterations=3, max_seq_len=6)
    miner = DeepQuantMiner(synthetic_engine, cfg)
    result = miner.train(progress=False)
    assert result.best_formula_tokens is not None
    path = miner.save()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "formula_tokens" in data

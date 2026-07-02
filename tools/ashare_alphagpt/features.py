"""OHLCV → factor feature tensors (AlphaGPT times.py feature engineering)."""

from __future__ import annotations

import numpy as np
import torch

from .vocab import FEATURE_COUNT


def _rolling_mean(arr: np.ndarray, window: int) -> np.ndarray:
    out = np.full_like(arr, np.nan, dtype=np.float32)
    if window <= 0 or len(arr) < window:
        return out
    cs = np.cumsum(np.insert(arr.astype(np.float64), 0, 0.0))
    vals = (cs[window:] - cs[:-window]) / window
    out[window - 1 :] = vals.astype(np.float32)
    return out


def robust_norm(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32)
    median = np.nanmedian(x)
    mad = np.nanmedian(np.abs(x - median)) + 1e-6
    return np.clip((x - median) / mad, -5, 5).astype(np.float32)


def build_features_from_arrays(
    close: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    vol: np.ndarray,
    *,
    device: torch.device | None = None,
) -> torch.Tensor:
    """Build [FEATURE_COUNT, T] feature tensor from 1-D OHLCV arrays."""
    close = close.astype(np.float32)
    vol = vol.astype(np.float32)

    ret = np.zeros_like(close)
    ret[1:] = (close[1:] - close[:-1]) / (close[:-1] + 1e-6)

    ret5 = np.zeros_like(close)
    ret5[5:] = (close[5:] - close[:-5]) / (close[:-5] + 1e-6)

    vol_ma = _rolling_mean(vol, 20)
    vol_chg = np.zeros_like(vol)
    mask = vol_ma > 0
    vol_chg[mask] = vol[mask] / vol_ma[mask] - 1
    vol_chg = np.nan_to_num(vol_chg).astype(np.float32)

    v_ret = (ret * (vol_chg + 1)).astype(np.float32)

    ma60 = _rolling_mean(close, 60)
    trend = np.zeros_like(close)
    tmask = ma60 > 0
    trend[tmask] = close[tmask] / ma60[tmask] - 1
    trend = np.nan_to_num(trend).astype(np.float32)

    stacks = [
        robust_norm(ret),
        robust_norm(ret5),
        robust_norm(vol_chg),
        robust_norm(v_ret),
        robust_norm(trend),
    ]
    feat = torch.stack([torch.from_numpy(s) for s in stacks])
    if device is not None:
        feat = feat.to(device)
    return feat


def build_target_oto_open(open_: np.ndarray, *, device: torch.device | None = None) -> torch.Tensor:
    """Open-to-open return: buy at t+1 open, sell at t+2 open."""
    open_tensor = torch.from_numpy(open_.astype(np.float32))
    if device is not None:
        open_tensor = open_tensor.to(device)
    open_t1 = torch.roll(open_tensor, -1)
    open_t2 = torch.roll(open_tensor, -2)
    target = (open_t2 - open_t1) / (open_t1 + 1e-6)
    target[-2:] = 0.0
    return target


def assert_feature_count(feat: torch.Tensor) -> None:
    if feat.shape[0] != FEATURE_COUNT:
        raise ValueError(f"Expected {FEATURE_COUNT} features, got {feat.shape[0]}")

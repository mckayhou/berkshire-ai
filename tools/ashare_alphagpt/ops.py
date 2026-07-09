"""StackVM operators for A-share factor formulas (from AlphaGPT times.py)."""

from __future__ import annotations

import torch

__all__ = ["OPS_CONFIG", "build_op_maps"]


def _ts_delay(x: torch.Tensor, d: int) -> torch.Tensor:
    if d == 0:
        return x
    pad = torch.zeros((x.shape[0], d), device=x.device)
    return torch.cat([pad, x[:, :-d]], dim=1)


def _ts_delta(x: torch.Tensor, d: int) -> torch.Tensor:
    return x - _ts_delay(x, d)


def _ts_zscore(x: torch.Tensor, d: int) -> torch.Tensor:
    if d <= 1:
        return torch.zeros_like(x)
    b, _t = x.shape
    pad = torch.zeros((b, d - 1), device=x.device)
    x_pad = torch.cat([pad, x], dim=1)
    windows = x_pad.unfold(1, d, 1)
    mean = windows.mean(dim=-1)
    std = windows.std(dim=-1) + 1e-6
    return (x - mean) / std


def _ts_decay_linear(x: torch.Tensor, d: int) -> torch.Tensor:
    if d <= 1:
        return x
    b, _t = x.shape
    pad = torch.zeros((b, d - 1), device=x.device)
    x_pad = torch.cat([pad, x], dim=1)
    windows = x_pad.unfold(1, d, 1)
    w = torch.arange(1, d + 1, device=x.device, dtype=x.dtype)
    w = w / w.sum()
    return (windows * w).sum(dim=-1)


OPS_CONFIG: list[tuple[str, object, int]] = [
    ("ADD", lambda x, y: x + y, 2),
    ("SUB", lambda x, y: x - y, 2),
    ("MUL", lambda x, y: x * y, 2),
    ("DIV", lambda x, y: x / (y + 1e-6 * torch.sign(y)), 2),
    ("NEG", lambda x: -x, 1),
    ("ABS", lambda x: torch.abs(x), 1),
    ("SIGN", lambda x: torch.sign(x), 1),
    ("DELTA5", lambda x: _ts_delta(x, 5), 1),
    ("MA20", lambda x: _ts_decay_linear(x, 20), 1),
    ("STD20", lambda x: _ts_zscore(x, 20), 1),
    ("TS_RANK20", lambda x: _ts_zscore(x, 20), 1),
]


def build_op_maps(feature_count: int) -> tuple[dict[int, object], dict[int, int]]:
    """Map token id -> operator func / arity (offset after feature tokens)."""
    op_func = {i + feature_count: cfg[1] for i, cfg in enumerate(OPS_CONFIG)}
    op_arity = {i + feature_count: cfg[2] for i, cfg in enumerate(OPS_CONFIG)}
    return op_func, op_arity

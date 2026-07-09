"""Sortino-style reward backtest for mined factors (train split)."""

from __future__ import annotations

import torch


def backtest_sortino(
    factors: torch.Tensor,
    *,
    split_idx: int,
    target_oto_ret: torch.Tensor,
    cost_rate: float,
) -> torch.Tensor:
    """Per-formula Sortino reward on in-sample segment."""
    if factors.shape[0] == 0:
        return torch.tensor([], device=factors.device)

    target = target_oto_ret[:split_idx]
    rewards = torch.zeros(factors.shape[0], device=factors.device)

    for i in range(factors.shape[0]):
        f = factors[i, :split_idx]
        if torch.isnan(f).all() or (f == 0).all() or f.numel() == 0:
            rewards[i] = -2.0
            continue

        sig = torch.tanh(f)
        pos = torch.sign(sig)
        turnover = torch.abs(pos - torch.roll(pos, 1))
        if turnover.numel() == 0:
            rewards[i] = -2.0
            continue
        turnover[0] = 0.0

        pnl = pos * target - turnover * cost_rate
        if pnl.numel() < 10:
            rewards[i] = -2.0
            continue

        mu = pnl.mean()
        std = pnl.std() + 1e-6
        downside = pnl[pnl < 0]
        if downside.numel() > 5:
            down_std = downside.std() + 1e-6
            sortino = mu / down_std * 15.87
        else:
            sortino = mu / std * 15.87

        if mu < 0:
            sortino = -2.0
        if turnover.mean() > 0.5:
            sortino -= 1.0
        if (pos == 0).all():
            sortino = -2.0

        rewards[i] = sortino

    return torch.clamp(rewards, -3, 5)


def strict_action_mask(
    open_slots: torch.Tensor,
    step: int,
    *,
    max_seq_len: int,
    vocab_size: int,
    feature_count: int,
    device: torch.device,
) -> torch.Tensor:
    """Polish-notation validity mask for token sampling."""
    b = open_slots.shape[0]
    mask = torch.full((b, vocab_size), float("-inf"), device=device)
    remaining = max_seq_len - step

    done = open_slots == 0
    mask[done, 0] = 0.0

    active = ~done
    must_feat = open_slots >= remaining
    mask[active, :feature_count] = 0.0

    can_op = active & (~must_feat)
    if can_op.any():
        mask[can_op, feature_count:] = 0.0
    return mask

"""Reverse-polish formula solver for A-share factors."""

from __future__ import annotations

import torch

from .ops import build_op_maps
from .vocab import FEATURE_COUNT


class FormulaVM:
    """Execute token sequences into factor signals (times.py solve_one semantics)."""

    def __init__(self, feat_data: torch.Tensor):
        self.feat_data = feat_data
        self.op_func, self.op_arity = build_op_maps(FEATURE_COUNT)

    def solve_one(self, tokens: list[int]) -> torch.Tensor | None:
        stack: list[torch.Tensor] = []
        try:
            for t in reversed(tokens):
                if t < FEATURE_COUNT:
                    stack.append(self.feat_data[t])
                else:
                    arity = self.op_arity[t]
                    if len(stack) < arity:
                        raise ValueError("stack underflow")
                    args = [stack.pop() for _ in range(arity)]
                    func = self.op_func[t]
                    if arity == 2:
                        res = func(args[1], args[0])
                    else:
                        res = func(args[0])
                    if torch.isnan(res).any():
                        res = torch.nan_to_num(res)
                    stack.append(res)
            if not stack:
                return None
            final = stack[-1]
            if final.std() < 1e-4:
                return None
            return final
        except Exception:
            return None

    def solve_batch(self, token_seqs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        b = token_seqs.shape[0]
        t_len = self.feat_data.shape[-1]
        results = torch.zeros((b, t_len), device=token_seqs.device)
        valid_mask = torch.zeros(b, dtype=torch.bool, device=token_seqs.device)
        for i in range(b):
            res = self.solve_one(token_seqs[i].cpu().tolist())
            if res is not None:
                results[i] = res
                valid_mask[i] = True
        return results, valid_mask

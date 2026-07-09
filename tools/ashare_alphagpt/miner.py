"""REINFORCE training loop for A-share factor mining."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import torch
from torch.distributions import Categorical

from .backtest import backtest_sortino, strict_action_mask
from .config import MiningConfig
from .data_engine import AshareDataEngine
from .decode import decode_formula
from .model import AlphaGPTModel, default_device
from .ops import build_op_maps
from .vm import FormulaVM
from .vocab import FEATURE_COUNT, VOCAB_SIZE


@dataclass
class MiningResult:
    best_score: float = -10.0
    best_formula_tokens: list[int] | None = None
    formula_str: str = "N/A"

    def to_dict(self) -> dict:
        return {
            "best_score": self.best_score,
            "formula_tokens": self.best_formula_tokens,
            "formula": self.formula_str,
        }


@dataclass
class DeepQuantMiner:
    engine: AshareDataEngine
    config: MiningConfig = field(default_factory=MiningConfig)
    device: torch.device = field(default_factory=default_device)
    result: MiningResult = field(default_factory=MiningResult)

    def __post_init__(self) -> None:
        self.model = AlphaGPTModel(max_seq_len=self.config.max_seq_len).to(self.device)
        self.opt = torch.optim.AdamW(self.model.parameters(), lr=3e-4, weight_decay=1e-5)
        self.vm = FormulaVM(self.engine.feat_data)
        self._op_arity = build_op_maps(FEATURE_COUNT)[1]

    def train(self, *, progress: bool = True) -> MiningResult:
        try:
            from tqdm import tqdm
        except ImportError:
            tqdm = lambda x, **_: x  # noqa: E731

        iterator = tqdm(range(self.config.train_iterations), disable=not progress)
        for _ in iterator:
            self._train_step()
            if progress and hasattr(iterator, "set_postfix"):
                iterator.set_postfix({
                    "BestSortino": f"{self.result.best_score:.2f}",
                })
        self.result.formula_str = decode_formula(self.result.best_formula_tokens)
        return self.result

    def _train_step(self) -> None:
        cfg = self.config
        b = cfg.batch_size
        open_slots = torch.ones(b, dtype=torch.long, device=self.device)
        log_probs: list[torch.Tensor] = []
        tokens: list[torch.Tensor] = []
        curr_inp = torch.zeros((b, 1), dtype=torch.long, device=self.device)

        for step in range(cfg.max_seq_len):
            logits, _val = self.model(curr_inp)
            mask = strict_action_mask(
                open_slots,
                step,
                max_seq_len=cfg.max_seq_len,
                vocab_size=VOCAB_SIZE,
                feature_count=FEATURE_COUNT,
                device=self.device,
            )
            dist = Categorical(logits=logits + mask)
            action = dist.sample()
            log_probs.append(dist.log_prob(action))
            tokens.append(action)
            curr_inp = torch.cat([curr_inp, action.unsqueeze(1)], dim=1)

            is_op = action >= FEATURE_COUNT
            delta = torch.full((b,), -1, device=self.device)
            arity_tens = torch.zeros(VOCAB_SIZE, dtype=torch.long, device=self.device)
            for k, v in self._op_arity.items():
                arity_tens[k] = v
            op_delta = arity_tens[action] - 1
            delta = torch.where(is_op, op_delta, delta)
            delta[open_slots == 0] = 0
            open_slots = open_slots + delta

        seqs = torch.stack(tokens, dim=1)

        with torch.no_grad():
            f_vals, valid_mask = self.vm.solve_batch(seqs)
            valid_idx = torch.where(valid_mask)[0]
            rewards = torch.full((b,), -1.0, device=self.device)

            if len(valid_idx) > 0:
                bt_scores = backtest_sortino(
                    f_vals[valid_idx],
                    split_idx=self.engine.split_idx,
                    target_oto_ret=self.engine.target_oto_ret,
                    cost_rate=cfg.cost_rate,
                )
                rewards[valid_idx] = bt_scores
                best_sub = torch.argmax(bt_scores)
                score = bt_scores[best_sub].item()
                if score > self.result.best_score:
                    self.result.best_score = score
                    self.result.best_formula_tokens = seqs[valid_idx[best_sub]].cpu().tolist()

        adv = rewards - rewards.mean()
        loss = -(torch.stack(log_probs, dim=1).sum(dim=1) * adv).mean()

        self.opt.zero_grad()
        loss.backward()
        self.opt.step()

    def save(self, path: Path | None = None) -> Path:
        from .formula_store import save_formula

        self.result.formula_str = decode_formula(self.result.best_formula_tokens)
        return save_formula(
            self.result.best_formula_tokens or [],
            formula_str=self.result.formula_str,
            best_score=self.result.best_score,
            path=path,
        )

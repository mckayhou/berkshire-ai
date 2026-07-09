"""Small causal Transformer for formula token generation."""

from __future__ import annotations

import torch
import torch.nn as nn

from .vocab import VOCAB_SIZE


class AlphaGPTModel(nn.Module):
    """Causal Transformer policy (times.py AlphaGPT)."""

    def __init__(self, *, max_seq_len: int, d_model: int = 64, n_head: int = 4, n_layer: int = 2):
        super().__init__()
        self.max_seq_len = max_seq_len
        self.token_emb = nn.Embedding(VOCAB_SIZE, d_model)
        self.pos_emb = nn.Parameter(torch.zeros(1, max_seq_len + 1, d_model))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=n_head,
            dim_feedforward=128,
            batch_first=True,
            norm_first=True,
        )
        self.blocks = nn.TransformerEncoder(encoder_layer, num_layers=n_layer)
        self.ln_f = nn.LayerNorm(d_model)
        self.head_actor = nn.Linear(d_model, VOCAB_SIZE)
        self.head_critic = nn.Linear(d_model, 1)

    def forward(self, idx: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        _b, t = idx.size()
        x = self.token_emb(idx) + self.pos_emb[:, :t, :]
        mask = nn.Transformer.generate_square_subsequent_mask(t).to(idx.device)
        x = self.blocks(x, mask=mask, is_causal=True)
        x = self.ln_f(x)
        last = x[:, -1, :]
        return self.head_actor(last), self.head_critic(last)


def default_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")

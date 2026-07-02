"""Configuration for A-share AlphaGPT factor mining."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _data_dir() -> Path:
    return Path(os.environ.get("BERKSHIRE_DATA_DIR", "./data")).expanduser()


@dataclass
class MiningConfig:
    """Hyperparameters and paths (env-overridable)."""

    index_code: str = os.environ.get("BERKSHIRE_ALPHAGPT_CODE", "511260")
    start_date: str = os.environ.get("BERKSHIRE_ALPHAGPT_START", "20150101")
    end_date: str = os.environ.get("BERKSHIRE_ALPHAGPT_TRAIN_END", "20240101")
    test_end_date: str = os.environ.get("BERKSHIRE_ALPHAGPT_TEST_END", "20250101")

    batch_size: int = int(os.environ.get("BERKSHIRE_ALPHAGPT_BATCH", "1024"))
    train_iterations: int = int(os.environ.get("BERKSHIRE_ALPHAGPT_STEPS", "400"))
    max_seq_len: int = int(os.environ.get("BERKSHIRE_ALPHAGPT_MAX_LEN", "8"))
    cost_rate: float = float(os.environ.get("BERKSHIRE_ALPHAGPT_COST", "0.0005"))
    train_split_ratio: float = float(os.environ.get("BERKSHIRE_ALPHAGPT_SPLIT", "0.8"))
    daily_limit: int = int(os.environ.get("BERKSHIRE_ALPHAGPT_DAILY_LIMIT", "3000"))

    @property
    def cache_path(self) -> Path:
        code = self.index_code.replace(".", "_")
        return _data_dir() / "alphagpt" / f"{code}_ohlcv.parquet"

    @property
    def output_dir(self) -> Path:
        return _data_dir() / "alphagpt"

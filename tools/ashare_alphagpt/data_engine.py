"""A-share OHLCV loading for factor mining (no hardcoded API tokens)."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import MiningConfig
from .features import (
    assert_feature_count,
    build_features_from_arrays,
    build_target_oto_open,
)

_TOOLS = Path(__file__).resolve().parent.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))


@dataclass
class AshareDataEngine:
    """Load single-symbol daily bars and build feature tensors."""

    config: MiningConfig
    dates: list[str] | None = None
    feat_data: object = None
    target_oto_ret: object = None
    raw_open: object = None
    raw_close: object = None
    split_idx: int = 0
    _device: object = None

    def _device_ref(self):
        import torch

        if self._device is None:
            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return self._device

    def load(self, *, device=None) -> AshareDataEngine:
        import torch

        if device is not None:
            self._device = device
        dev = self._device_ref()

        df = self._load_ohlcv_frame()
        df = self._filter_date_range(df)

        close = np.array(df["close"], dtype=np.float32)
        open_ = np.array(df["open"], dtype=np.float32)
        high = np.array(df["high"], dtype=np.float32)
        low = np.array(df["low"], dtype=np.float32)
        vol = np.array(df["vol"], dtype=np.float32)
        self.dates = list(df["trade_date"])

        self.feat_data = build_features_from_arrays(close, open_, high, low, vol, device=dev)
        assert_feature_count(self.feat_data)

        self.target_oto_ret = build_target_oto_open(open_, device=dev)
        self.raw_open = torch.from_numpy(open_).to(dev)
        self.raw_close = torch.from_numpy(close).to(dev)
        self.split_idx = int(len(df) * self.config.train_split_ratio)
        return self

    def _filter_date_range(self, df: list[dict]) -> list[dict]:
        start = self.config.start_date
        end = self.config.test_end_date
        out = [r for r in df if start <= str(r["trade_date"]) <= end]
        out.sort(key=lambda r: r["trade_date"])
        if not out:
            raise ValueError(f"No rows in range {start}–{end} for {self.config.index_code}")
        return out

    def _load_ohlcv_frame(self) -> list[dict]:
        cache = self.config.cache_path
        if cache.is_file():
            return self._read_cache(cache)

        rows = self._fetch_remote()
        if not rows:
            raise ValueError(
                f"Failed to load OHLCV for {self.config.index_code}. "
                "Check network or set BERKSHIRE_DATA_DIR with a parquet cache."
            )
        df = self._normalize_rows(rows)
        self._write_cache(cache, df)
        return df

    def _read_cache(self, path: Path) -> list[dict]:
        try:
            import pandas as pd

            frame = pd.read_parquet(path)
            return frame.to_dict(orient="records")
        except ImportError:
            raise ValueError("parquet cache requires pyarrow/pandas: pip install '.[factor-mining]'") from None

    def _write_cache(self, path: Path, rows: list[dict]) -> None:
        try:
            import pandas as pd

            path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows).to_parquet(path, index=False)
        except Exception:
            pass

    def _fetch_remote(self) -> list[dict]:
        code = self.config.index_code.replace(".SH", "").replace(".SZ", "")
        limit = self.config.daily_limit

        try:
            import data_sources as ds

            res = ds.daily(code, limit=limit)
            if res.get("ok") and res.get("rows"):
                return self._normalize_rows(res["rows"])
        except Exception:
            pass

        try:
            import ashare_data

            rows = ashare_data.fetch_daily(code, limit=limit)
            if rows:
                return self._normalize_rows(rows)
        except Exception:
            pass

        token = os.environ.get("TUSHARE_TOKEN", "").strip()
        if token:
            try:
                import pandas as pd
                import tushare as ts

                pro = ts.pro_api(token)
                ts_code = self._tushare_code(code)
                for fn_name in ("fund_daily", "index_daily"):
                    fn = getattr(pro, fn_name, None)
                    if fn is None:
                        continue
                    try:
                        raw = fn(
                            ts_code=ts_code,
                            start_date=self.config.start_date,
                            end_date=self.config.test_end_date,
                        )
                        if raw is not None and not raw.empty:
                            return self._tushare_df_to_rows(raw)
                    except Exception:
                        continue
            except Exception:
                pass

        return []

    @staticmethod
    def _tushare_code(code: str) -> str:
        c = code.replace(".SH", "").replace(".SZ", "")
        if c.endswith((".SH", ".SZ")):
            return c
        if c.startswith(("5", "6", "9")):
            return f"{c}.SH"
        return f"{c}.SZ"

    @staticmethod
    def _tushare_df_to_rows(df) -> list[dict]:
        out = []
        for _, r in df.sort_values("trade_date").iterrows():
            out.append({
                "trade_date": str(r["trade_date"]),
                "open": float(r.get("open", 0)),
                "high": float(r.get("high", 0)),
                "low": float(r.get("low", 0)),
                "close": float(r.get("close", 0)),
                "vol": float(r.get("vol", r.get("volume", 0))),
            })
        return out

    @staticmethod
    def _normalize_rows(rows: list[dict]) -> list[dict]:
        out = []
        for r in rows:
            d = (r.get("date") or r.get("time") or r.get("trade_date") or "")[:10]
            d = d.replace("-", "")
            if not d:
                continue
            try:
                out.append({
                    "trade_date": d,
                    "open": float(r.get("open", 0)),
                    "high": float(r.get("high", 0)),
                    "low": float(r.get("low", 0)),
                    "close": float(r.get("close", 0)),
                    "vol": float(r.get("volume", r.get("vol", 0))),
                })
            except (TypeError, ValueError):
                continue
        return out

    @classmethod
    def from_ohlcv_arrays(
        cls,
        *,
        trade_dates: list[str],
        open_: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        vol: np.ndarray,
        config: MiningConfig | None = None,
        device=None,
    ) -> AshareDataEngine:
        """Construct engine from in-memory arrays (tests / offline)."""
        import torch

        cfg = config or MiningConfig()
        eng = cls(config=cfg)
        if device is not None:
            eng._device = device
        dev = eng._device_ref()

        eng.dates = [d.replace("-", "") for d in trade_dates]
        eng.feat_data = build_features_from_arrays(
            close.astype(np.float32),
            open_.astype(np.float32),
            high.astype(np.float32),
            low.astype(np.float32),
            vol.astype(np.float32),
            device=dev,
        )
        eng.target_oto_ret = build_target_oto_open(open_.astype(np.float32), device=dev)
        eng.raw_open = torch.from_numpy(open_.astype(np.float32)).to(dev)
        eng.raw_close = torch.from_numpy(close.astype(np.float32)).to(dev)
        eng.split_idx = int(len(trade_dates) * cfg.train_split_ratio)
        return eng

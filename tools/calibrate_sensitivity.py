#!/usr/bin/env python3
"""用真实历史行情对 TextGrad 引擎的 SENSITIVITY 做「尺度校准」。

背景
----
`src/realized_feedback.py` 把已实现收益映射成评分喂回 TextGrad：

    raw_return    = (realized - anchor) / anchor
    alpha         = raw_return - benchmark_return            # 相对基准的超额收益
    realized_base = clip(0.5 + alpha * SENSITIVITY, 0, 1)    # 默认 SENSITIVITY=0.5（V10.12 校准值）

我们暂时没有历史「大师 conviction」数据，无法做「信心 vs alpha」的误差校准。
所以本工具做的是**尺度校准（data-only）**：在真实观测到的 alpha 分布上选一个
SENSITIVITY，让 realized_base 用满 [0,1] 区间——既不过度饱和（多数样本被 clip
到 0/1），也不全挤在 0.5 附近。

目标函数（明确、可复现 · 对肥尾稳健）
----------------------------------
对一组观测 alpha {aᵢ}，给定 S 算出 realized_baseᵢ = clip(0.5 + aᵢ·S)。

    J(S) = | spread₁₀₋₉₀(realized_base; S) - TARGET_SPREAD |   （TARGET_SPREAD = 0.80）

其中 spread₁₀₋₉₀ = p90(realized_base) - p10(realized_base)，即 realized_base 的
中位 80% 区间宽度。我们让**中位 80% 的决策**用满约 [0.1, 0.9] 的 realized_base
区间，而把极端 ±10% 尾部（如 IPO/加密的暴涨暴跌）**有意留给饱和**。

为什么用「中位分位宽度」而非「标准差」：真实观测到的 alpha 分布严重右偏、肥尾
（少数 AI/加密/次新股一年内 +数倍），标准差会被这几个离群点主导，把 S 压到极小，
导致**典型 ±15% 的决策几乎没有反馈信号**。而极端 alpha 本就**应该**读成接近 1.0/0.0
（涨 8 倍的决策当然近乎满分），所以让尾部饱和是正确行为。基于 p10/p90 的中位
宽度对离群点稳健，只刻画「大多数决策」的尺度。

J(S) 关于 S 单峰（spread 随 S 单调递增直到饱和到 ≤1.0），因此：
  1. 先在网格上扫 J(S) 记录曲线（这就是本次的「loop」可视化）；
  2. 在含最优点的相邻网格区间用**黄金分割**细化收敛到最优 S。

我们取「最小的、达到目标 spread 的 S」，它在同等中位宽度下天然使饱和比例最低。

数据来源（可注入接口，核心逻辑不连网络）
------------------------------------
取数走 `HistoryProvider` 抽象接口（便于 mock）：
  * 美股：yfinance（直接代码），基准 ^GSPC（标普500）
  * 港股：yfinance（XXXX.HK），基准 ^HSI（恒指）
  * A 股：Tushare（需 BERKSHIRE_ENABLE_TUSHARE=1 + TUSHARE_TOKEN）兜底 akshare/
    yfinance(.SS/.SZ)，基准沪深300（tushare 000300.SH / yfinance 000300.SS）

真实校准走 CLI（需联网）：
    pip install yfinance akshare tushare
    export BERKSHIRE_ENABLE_TUSHARE=1 TUSHARE_TOKEN=<redacted>   # 仅 A 股需要
    python3 tools/calibrate_sensitivity.py run --lookback 365 --also 182

核心数学（目标函数 + 搜索）由 tests/ 用 mock 样本做单元测试，不打真实网络。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

# 默认校准目标（对肥尾稳健：刻画中位 80% 而非整体方差）
SPREAD_LO = 0.10             # 中位区间下分位
SPREAD_HI = 0.90             # 中位区间上分位
TARGET_SPREAD = 0.80         # realized_base 的目标中位 80% 宽度（≈用满 [0.1,0.9]）
SAT_EPS = 0.01               # 距 0/1 不超过该值视为「饱和」
DEFAULT_GRID = [
    0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.75, 0.9,
    1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.5, 10.0, 15.0, 20.0,
]


# ---------------------------------------------------------------------------
# 纯函数：realized_base 映射 / 统计 / 目标函数 / 搜索（全部可离线单测）
# ---------------------------------------------------------------------------
def clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def realized_base(alpha: float, sensitivity: float) -> float:
    """与 src/realized_feedback.py 完全一致的映射。"""
    return clip01(0.5 + alpha * sensitivity)


def _percentile(xs: Sequence[float], p: float) -> float:
    """线性插值分位（p ∈ [0,1]）。空序列报错。"""
    if not xs:
        raise ValueError("empty sample")
    s = sorted(xs)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return float(s[int(k)])
    return float(s[lo] * (hi - k) + s[hi] * (k - lo))


def summarize_alphas(alphas: Sequence[float]) -> Dict[str, float]:
    """观测 alpha 的分布摘要（均值/标准差/分位）。"""
    if not alphas:
        return {"n": 0}
    return {
        "n": len(alphas),
        "mean": statistics.fmean(alphas),
        "std": statistics.pstdev(alphas) if len(alphas) > 1 else 0.0,
        "min": min(alphas),
        "p05": _percentile(alphas, 0.05),
        "p25": _percentile(alphas, 0.25),
        "p50": _percentile(alphas, 0.50),
        "p75": _percentile(alphas, 0.75),
        "p95": _percentile(alphas, 0.95),
        "max": max(alphas),
    }


def realized_base_stats(
    alphas: Sequence[float], sensitivity: float, eps: float = SAT_EPS
) -> Dict[str, float]:
    """给定 S，算 realized_base 的中位宽度/标准差/饱和比例（控制流读字段）。"""
    bases = [realized_base(a, sensitivity) for a in alphas]
    n = len(bases)
    std = statistics.pstdev(bases) if n > 1 else 0.0
    sat = sum(1 for b in bases if b <= eps or b >= 1.0 - eps)
    spread = (_percentile(bases, SPREAD_HI) - _percentile(bases, SPREAD_LO)) if n else 0.0
    return {
        "sensitivity": sensitivity,
        "spread": spread,          # 主目标：p90-p10 中位宽度
        "std": std,                # 辅助报告
        "mean": statistics.fmean(bases) if n else 0.0,
        "sat_ratio": (sat / n) if n else 0.0,
        "n": n,
    }


def objective(alphas: Sequence[float], sensitivity: float,
              target_spread: float = TARGET_SPREAD) -> float:
    """目标函数 J(S) = |spread₁₀₋₉₀(realized_base; S) - target_spread|（越小越好）。"""
    return abs(realized_base_stats(alphas, sensitivity)["spread"] - target_spread)


def grid_search(
    alphas: Sequence[float],
    grid: Sequence[float] = DEFAULT_GRID,
    target_spread: float = TARGET_SPREAD,
) -> List[Dict[str, float]]:
    """在网格上扫目标函数，返回曲线 [{sensitivity,spread,std,sat_ratio,objective}]。"""
    curve = []
    for s in grid:
        st = realized_base_stats(alphas, s)
        curve.append({
            "sensitivity": s,
            "spread": st["spread"],
            "std": st["std"],
            "sat_ratio": st["sat_ratio"],
            "objective": abs(st["spread"] - target_spread),
        })
    return curve


def golden_section_min(
    alphas: Sequence[float],
    lo: float,
    hi: float,
    target_spread: float = TARGET_SPREAD,
    tol: float = 1e-3,
    max_iter: int = 100,
) -> Tuple[float, List[Dict[str, float]]]:
    """黄金分割搜索 J(S) 在 [lo,hi] 上的极小点（J 单峰），返回 (best_S, 迭代记录)。"""
    inv_phi = (math.sqrt(5.0) - 1.0) / 2.0  # 0.618...
    a, b = float(lo), float(hi)
    c = b - inv_phi * (b - a)
    d = a + inv_phi * (b - a)
    fc = objective(alphas, c, target_spread)
    fd = objective(alphas, d, target_spread)
    history: List[Dict[str, float]] = []
    it = 0
    while abs(b - a) > tol and it < max_iter:
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - inv_phi * (b - a)
            fc = objective(alphas, c, target_spread)
        else:
            a, c, fc = c, d, fd
            d = a + inv_phi * (b - a)
            fd = objective(alphas, d, target_spread)
        it += 1
        mid = (a + b) / 2.0
        history.append({
            "iter": it,
            "lo": a,
            "hi": b,
            "mid": mid,
            "objective": objective(alphas, mid, target_spread),
        })
    best = (a + b) / 2.0
    return best, history


def calibrate(
    alphas: Sequence[float],
    target_spread: float = TARGET_SPREAD,
    grid: Sequence[float] = DEFAULT_GRID,
    default_sensitivity: float = 2.5,
    tol: float = 1e-3,
) -> Dict[str, object]:
    """完整校准 loop：网格扫描 → 黄金分割细化 → 与默认值对比。

    返回结构（控制流读字段，不解析文本）：
      {
        "n", "alpha_summary",
        "grid_curve": [...],
        "gs_history": [...],
        "recommended": float,
        "recommended_stats": {spread, std, sat_ratio, ...},
        "default": float, "default_stats": {...},
        "target_spread": float,
        "improved": bool,        # 推荐值的 |spread-target| 是否显著优于默认
      }
    """
    if not alphas:
        raise ValueError("alphas 为空：没有可用于校准的 alpha 样本")

    curve = grid_search(alphas, grid, target_spread)
    # 网格最优点 + 相邻点构成黄金分割的搜索区间
    best_idx = min(range(len(curve)), key=lambda i: curve[i]["objective"])
    lo = curve[max(0, best_idx - 1)]["sensitivity"]
    hi = curve[min(len(curve) - 1, best_idx + 1)]["sensitivity"]
    if hi <= lo:  # 边界退化
        lo, hi = grid[0], grid[-1]
    recommended, gs_history = golden_section_min(alphas, lo, hi, target_spread, tol)

    rec_stats = realized_base_stats(alphas, recommended)
    def_stats = realized_base_stats(alphas, default_sensitivity)
    rec_obj = abs(rec_stats["spread"] - target_spread)
    def_obj = abs(def_stats["spread"] - target_spread)
    # 「显著更优」：目标函数至少改进 20% 且绝对差 > 0.05
    improved = (rec_obj < def_obj * 0.8) and ((def_obj - rec_obj) > 0.05)

    return {
        "n": len(alphas),
        "alpha_summary": summarize_alphas(alphas),
        "target_spread": target_spread,
        "grid_curve": curve,
        "gs_history": gs_history,
        "recommended": round(recommended, 4),
        "recommended_stats": rec_stats,
        "default": default_sensitivity,
        "default_stats": def_stats,
        "improved": improved,
    }


# ---------------------------------------------------------------------------
# 标的 / 市场分类
# ---------------------------------------------------------------------------
@dataclass
class Instrument:
    raw: str
    market: str          # us / hk / a
    yf_symbol: str       # yfinance 代码
    benchmark_key: str   # gspc / hsi / csi300


def classify(ticker: str) -> Instrument:
    """把原始代码归类到市场，并给出 yfinance 代码与基准。"""
    t = str(ticker).strip().upper()
    if t.endswith(".HK"):
        return Instrument(t, "hk", t, "hsi")
    core = t.replace(".SS", "").replace(".SZ", "").replace(".SH", "")
    if core.isdigit() and len(core) == 6:
        suffix = "SS" if core.startswith(("6", "9", "5")) else "SZ"
        return Instrument(t, "a", f"{core}.{suffix}", "csi300")
    return Instrument(t, "us", t, "gspc")


BENCHMARKS = {
    "gspc": {"yf": "^GSPC", "name": "S&P500"},
    "hsi": {"yf": "^HSI", "name": "恒生指数"},
    "csi300": {"yf": "000300.SS", "name": "沪深300", "tushare": "000300.SH"},
}


def load_universe(
    watchlist_path: str,
    holdings_path: str,
) -> List[str]:
    """汇总 watchlist + holdings 的标的（去重；忽略 CASH 与 _ 开头元字段）。"""
    tickers: List[str] = []

    def _add(x: str) -> None:
        x = str(x).strip()
        if not x or x.upper() == "CASH" or x.startswith("_"):
            return
        if x.upper() not in {t.upper() for t in tickers}:
            tickers.append(x)

    try:
        with open(watchlist_path, encoding="utf-8") as f:
            wl = json.load(f)
        for group, items in wl.items():
            if group.startswith("_"):
                continue
            if isinstance(items, list):
                for it in items:
                    _add(it)
    except FileNotFoundError:
        pass

    try:
        with open(holdings_path, encoding="utf-8") as f:
            hold = json.load(f)
        for k in hold:
            _add(k)
    except FileNotFoundError:
        pass

    return tickers


# ---------------------------------------------------------------------------
# 价格序列 → alpha（纯逻辑，可离线单测）
# ---------------------------------------------------------------------------
Series = List[Tuple[str, float]]  # [(YYYY-MM-DD, close)] 升序


def _to_date(s: str) -> date:
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


def _closest(series: Series, target: date) -> Tuple[str, float]:
    """返回日期最接近 target 的 (date, close)。"""
    if not series:
        raise ValueError("empty series")
    return min(series, key=lambda dc: abs((_to_date(dc[0]) - target).days))


def window_return(series: Series, lookback_days: int) -> Dict[str, object]:
    """以最新交易日为 realized，约 lookback_days 前最近交易日为 anchor，算涨跌幅。"""
    if len(series) < 2:
        raise ValueError("序列点数不足，无法计算窗口收益")
    series = sorted(series, key=lambda dc: _to_date(dc[0]))
    r_date, r_close = series[-1]
    target_anchor = _to_date(r_date) - timedelta(days=lookback_days)
    a_date, a_close = _closest(series, target_anchor)
    if a_close <= 0:
        raise ValueError("anchor 价格非正")
    return {
        "anchor_date": a_date,
        "anchor_close": float(a_close),
        "realized_date": r_date,
        "realized_close": float(r_close),
        "ret": float(r_close) / float(a_close) - 1.0,
    }


def compute_alpha(
    ticker_series: Series,
    benchmark_series: Optional[Series],
    lookback_days: int,
) -> Dict[str, object]:
    """由标的与基准价格序列算 alpha = raw_return - benchmark_return。"""
    tw = window_return(ticker_series, lookback_days)
    raw_return = tw["ret"]
    benchmark_return = 0.0
    has_benchmark = False
    if benchmark_series:
        ba = _closest(benchmark_series, _to_date(tw["anchor_date"]))[1]
        br = _closest(benchmark_series, _to_date(tw["realized_date"]))[1]
        if ba > 0:
            benchmark_return = float(br) / float(ba) - 1.0
            has_benchmark = True
    return {
        "raw_return": raw_return,
        "benchmark_return": benchmark_return,
        "alpha": raw_return - benchmark_return,
        "has_benchmark": has_benchmark,
        "anchor_date": tw["anchor_date"],
        "realized_date": tw["realized_date"],
    }


# ---------------------------------------------------------------------------
# 取数接口（可注入 / 可 mock）
# ---------------------------------------------------------------------------
class HistoryProvider:
    """历史日线价格抽象接口。get_series(symbol, market) -> Series（升序）。"""

    def get_series(self, symbol: str, market: str) -> Series:  # pragma: no cover
        raise NotImplementedError


class DictHistoryProvider(HistoryProvider):
    """内存字典价格源（测试/回放用，不连网络）。{symbol: Series}。"""

    def __init__(self, data: Dict[str, Series]):
        self._data = {str(k).upper(): v for k, v in data.items()}

    def get_series(self, symbol: str, market: str) -> Series:
        key = str(symbol).upper()
        if key not in self._data:
            raise KeyError(f"无价格序列: {symbol}")
        return self._data[key]


class YFinanceProvider(HistoryProvider):
    """yfinance 日线（美股/港股直接代码；A股 .SS/.SZ）。延迟导入。"""

    def __init__(self, period: str = "2y"):
        self.period = period

    def get_series(self, symbol: str, market: str) -> Series:
        import yfinance as yf  # 延迟导入：未装库时只在真实用到时报错
        # Yahoo 上海后缀是 .SS（tushare 用 .SH），统一规整
        symbol = symbol.upper().replace(".SH", ".SS")
        hist = yf.Ticker(symbol).history(period=self.period, auto_adjust=True)
        if hist is None or len(hist) == 0:
            return []
        out: Series = []
        for idx, row in hist.iterrows():
            d = getattr(idx, "date", lambda: idx)()
            out.append((str(d), float(row["Close"])))
        return out


class TushareProvider(HistoryProvider):
    """Tushare A 股日线 + 指数日线（沪深300）。需 token；延迟导入。"""

    def __init__(self, start_days: int = 500):
        self.start_days = start_days
        self._pro = None

    def _api(self):
        if self._pro is None:
            import tushare as ts
            token = os.environ.get("TUSHARE_TOKEN", "").strip()
            if not token:
                raise RuntimeError("TUSHARE_TOKEN 未设置")
            ts.set_token(token)
            self._pro = ts.pro_api(token)
        return self._pro

    @staticmethod
    def _ts_code(symbol: str) -> str:
        core = symbol.upper().replace(".SS", "").replace(".SZ", "").replace(".SH", "")
        if core.startswith(("6", "9", "5")):
            return f"{core}.SH"
        if core.startswith(("4", "8")):
            return f"{core}.BJ"
        return f"{core}.SZ"

    def get_series(self, symbol: str, market: str) -> Series:
        pro = self._api()
        start = (date.today() - timedelta(days=self.start_days)).strftime("%Y%m%d")
        end = date.today().strftime("%Y%m%d")
        is_index = symbol.upper().startswith("000300") or symbol.upper() == "000300.SH"
        if is_index:
            df = pro.index_daily(ts_code="000300.SH", start_date=start, end_date=end)
        else:
            df = pro.daily(ts_code=self._ts_code(symbol), start_date=start, end_date=end)
        if df is None or len(df) == 0:
            return []
        df = df.sort_values("trade_date")
        out: Series = []
        for _, row in df.iterrows():
            d = str(row["trade_date"])
            out.append((f"{d[:4]}-{d[4:6]}-{d[6:8]}", float(row["close"])))
        return out


class AkshareProvider(HistoryProvider):
    """akshare A 股日线兜底。延迟导入。"""

    def get_series(self, symbol: str, market: str) -> Series:
        import akshare as ak
        core = symbol.upper().replace(".SS", "").replace(".SZ", "").replace(".SH", "")
        # 指数（如沪深300 000300）走指数接口
        if core in ("000300", "399300"):
            df = ak.stock_zh_index_daily(symbol="sh000300")
            if df is None or len(df) == 0:
                return []
            return [(str(r["date"]), float(r["close"])) for _, r in df.iterrows()]
        df = ak.stock_zh_a_hist(symbol=core, period="daily", adjust="qfq")
        if df is None or len(df) == 0:
            return []
        out: Series = []
        for _, row in df.iterrows():
            out.append((str(row["日期"]), float(row["收盘"])))
        return out


class ChainProvider(HistoryProvider):
    """按市场选择取数链：A 股 tushare→akshare→yfinance(.SS/.SZ)；美港股 yfinance。

    任一源失败/为空自动降级；记录每个标的实际命中的源。
    """

    def __init__(self):
        self.yf = YFinanceProvider()
        self.tushare = TushareProvider()
        self.akshare = AkshareProvider()
        self.last_source: Dict[str, str] = {}

    def _try(self, name: str, fn) -> Optional[Series]:
        try:
            s = fn()
            if s:
                return s
        except Exception as e:  # noqa: BLE001 - 降级不崩
            sys.stderr.write(f"[calibrate] {name} 失败: {type(e).__name__}: {e}\n")
        return None

    def get_series(self, symbol: str, market: str) -> Series:
        if market == "a":
            enable_ts = os.environ.get("BERKSHIRE_ENABLE_TUSHARE", "").strip().lower() in (
                "1", "true", "yes", "on")
            if enable_ts:
                s = self._try("tushare", lambda: self.tushare.get_series(symbol, market))
                if s:
                    self.last_source[symbol] = "tushare"
                    return s
            s = self._try("akshare", lambda: self.akshare.get_series(symbol, market))
            if s:
                self.last_source[symbol] = "akshare"
                return s
            s = self._try("yfinance", lambda: self.yf.get_series(symbol, market))
            if s:
                self.last_source[symbol] = "yfinance"
                return s
            return []
        s = self._try("yfinance", lambda: self.yf.get_series(symbol, market))
        if s:
            self.last_source[symbol] = "yfinance"
            return s
        return []


# ---------------------------------------------------------------------------
# 端到端：取数 → 算 alpha 样本（联网，走可注入 provider）
# ---------------------------------------------------------------------------
def collect_alpha_samples(
    tickers: Sequence[str],
    provider: HistoryProvider,
    lookback_days: int,
) -> Dict[str, object]:
    """对每个标的取数算 alpha，返回 alpha 列表 + 覆盖/未覆盖明细。"""
    # 先把各市场基准序列拉好（每市场只取一次）
    bench_cache: Dict[str, Optional[Series]] = {}

    def _bench(market_key: str) -> Optional[Series]:
        if market_key not in bench_cache:
            spec = BENCHMARKS[market_key]
            bm = "csi300" if market_key == "csi300" else market_key
            sym = spec.get("tushare") if (market_key == "csi300" and isinstance(provider, (TushareProvider, ChainProvider))) else spec["yf"]
            # ChainProvider/Tushare 对 csi300 走指数接口；其余走 yf 代码
            market = "a" if market_key == "csi300" else ("hk" if market_key == "hsi" else "us")
            try:
                bench_cache[market_key] = provider.get_series(sym, market) or None
            except Exception as e:  # noqa: BLE001
                sys.stderr.write(f"[calibrate] 基准 {market_key} 取数失败: {e}\n")
                bench_cache[market_key] = None
        return bench_cache[market_key]

    alphas: List[float] = []
    covered: List[Dict[str, object]] = []
    uncovered: List[Dict[str, str]] = []

    for tk in tickers:
        inst = classify(tk)
        try:
            series = provider.get_series(inst.yf_symbol, inst.market)
        except Exception as e:  # noqa: BLE001
            uncovered.append({"ticker": tk, "reason": f"{type(e).__name__}: {e}"})
            continue
        if not series or len(series) < 2:
            uncovered.append({"ticker": tk, "reason": "无足够日线数据"})
            continue
        bench = _bench(inst.benchmark_key)
        try:
            res = compute_alpha(series, bench, lookback_days)
        except Exception as e:  # noqa: BLE001
            uncovered.append({"ticker": tk, "reason": f"算 alpha 失败: {e}"})
            continue
        alphas.append(res["alpha"])
        covered.append({
            "ticker": tk,
            "market": inst.market,
            "alpha": res["alpha"],
            "raw_return": res["raw_return"],
            "benchmark_return": res["benchmark_return"],
            "has_benchmark": res["has_benchmark"],
            "anchor_date": res["anchor_date"],
            "realized_date": res["realized_date"],
        })

    return {"alphas": alphas, "covered": covered, "uncovered": uncovered}


# ---------------------------------------------------------------------------
# 报告渲染
# ---------------------------------------------------------------------------
def render_report(
    samples: Dict[str, object],
    calib: Dict[str, object],
    lookback_days: int,
    extra: Optional[Dict[str, object]] = None,
) -> str:
    lines: List[str] = []
    a = lines.append
    a("=" * 68)
    a(f"SENSITIVITY 尺度校准报告（lookback={lookback_days} 天）")
    a("=" * 68)
    covered = samples["covered"]
    uncovered = samples["uncovered"]
    a(f"覆盖标的: {len(covered)}  未覆盖: {len(uncovered)}")
    if uncovered:
        a("未覆盖清单:")
        for u in uncovered:
            a(f"  - {u['ticker']}: {u['reason']}")
    s = calib["alpha_summary"]
    a("")
    a("观测 alpha 分布:")
    a(f"  n={s.get('n')} mean={s.get('mean'):+.4f} std={s.get('std'):.4f}")
    a(f"  分位 p05={s.get('p05'):+.4f} p25={s.get('p25'):+.4f} "
      f"p50={s.get('p50'):+.4f} p75={s.get('p75'):+.4f} p95={s.get('p95'):+.4f}")
    a(f"  min={s.get('min'):+.4f} max={s.get('max'):+.4f}")
    a("")
    a(f"目标函数 J(S) = |spread(p10..p90 of realized_base) - {calib['target_spread']}|")
    rec = calib["recommended"]
    rs = calib["recommended_stats"]
    ds = calib["default_stats"]
    a(f"推荐 SENSITIVITY = {rec}")
    a(f"  推荐值: spread={rs['spread']:.4f} std={rs['std']:.4f} "
      f"sat_ratio={rs['sat_ratio']:.3f}")
    a(f"  默认 {calib['default']}: spread={ds['spread']:.4f} std={ds['std']:.4f} "
      f"sat_ratio={ds['sat_ratio']:.3f}")
    a(f"  是否显著更优: {'是' if calib['improved'] else '否（与默认相当，建议保留默认）'}")
    a("")
    a("网格曲线 J(S)（spread 随 S 单调上升直到饱和）:")
    curve = calib["grid_curve"]
    for row in curve:
        bar = "#" * int(row["spread"] * 40)
        a(f"  S={row['sensitivity']:5.2f} spread={row['spread']:.3f} "
          f"sat={row['sat_ratio']:.2f} J={row['objective']:.3f} {bar}")
    if extra:
        a("")
        a("稳健性对照（不同回看窗）:")
        for label, ex in extra.items():
            exrec = ex["recommended"]
            a(f"  {label}: 推荐 S={exrec} (n={ex['n']}, "
              f"spread@rec={ex['recommended_stats']['spread']:.3f})")
    a("=" * 68)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv: Optional[Sequence[str]] = None) -> int:
    root = _repo_root()
    parser = argparse.ArgumentParser(
        description="SENSITIVITY 尺度校准（真实历史行情）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="联网取数 + 校准 + 报告")
    p_run.add_argument("--watchlist", default=os.path.join(root, "data", "watchlist.json"))
    p_run.add_argument("--holdings", default=os.path.join(root, "data", "holdings.example.json"))
    p_run.add_argument("--lookback", type=int, default=365, help="主回看窗(天)")
    p_run.add_argument("--also", type=int, default=182, help="对照回看窗(天)，0 关闭")
    p_run.add_argument("--target-spread", type=float, default=TARGET_SPREAD,
                       help="realized_base 的目标中位80%%宽度(p10..p90)")
    p_run.add_argument("--json", action="store_true", help="输出原始 JSON")
    p_run.add_argument("--out", default="", help="把报告写入文件")

    p_uni = sub.add_parser("universe", help="只打印汇总标的（不联网）")
    p_uni.add_argument("--watchlist", default=os.path.join(root, "data", "watchlist.json"))
    p_uni.add_argument("--holdings", default=os.path.join(root, "data", "holdings.example.json"))

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    if args.command == "universe":
        tickers = load_universe(args.watchlist, args.holdings)
        for t in tickers:
            print(f"{t:12} -> {classify(t).market} / {classify(t).yf_symbol}")
        print(f"共 {len(tickers)} 个标的")
        return 0

    if args.command == "run":
        tickers = load_universe(args.watchlist, args.holdings)
        if not tickers:
            print("没有可用标的（检查 watchlist/holdings 路径）", file=sys.stderr)
            return 2
        provider = ChainProvider()
        samples = collect_alpha_samples(tickers, provider, args.lookback)
        if not samples["alphas"]:
            print("BLOCKER: 没有取到任何真实 alpha 样本（联网/数据源在沙箱受限？）。"
                  "未使用任何假数据。", file=sys.stderr)
            print(json.dumps(samples, ensure_ascii=False, indent=2, default=str),
                  file=sys.stderr)
            return 3
        calib = calibrate(samples["alphas"], target_spread=args.target_spread)
        extra: Dict[str, object] = {}
        if args.also and args.also > 0:
            s2 = collect_alpha_samples(tickers, provider, args.also)
            if s2["alphas"]:
                extra[f"{args.also}d"] = calibrate(
                    s2["alphas"], target_spread=args.target_spread)
        if args.json:
            out = {"lookback": args.lookback, "samples": samples,
                   "calibration": calib, "extra": extra}
            print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        else:
            report = render_report(samples, calib, args.lookback, extra or None)
            print(report)
            if args.out:
                with open(args.out, "w", encoding="utf-8") as f:
                    f.write(report + "\n")
                print(f"\n已写入 {args.out}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""离线单元测试：SENSITIVITY 尺度校准（目标函数 + 搜索 + 取数管线）。

全部用 mock alpha 样本 / 合成价格序列，**不打真实网络**。
真实校准走 CLI（tools/calibrate_sensitivity.py run，需联网）。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import calibrate_sensitivity as cs  # noqa: E402

import realized_feedback as rf  # noqa: E402


# --------------------------- 映射与统计 ---------------------------
def test_realized_base_matches_realized_feedback():
    # 与 src/realized_feedback 的 clip(0.5+alpha*S) 完全一致
    for alpha in (-0.5, -0.1, 0.0, 0.1, 0.4):
        for s in (1.0, 2.5, 5.0):
            assert cs.realized_base(alpha, s) == pytest.approx(
                rf._clip01(0.5 + alpha * s))


def test_percentile_linear_interpolation():
    xs = [0.0, 1.0, 2.0, 3.0, 4.0]
    assert cs._percentile(xs, 0.0) == 0.0
    assert cs._percentile(xs, 1.0) == 4.0
    assert cs._percentile(xs, 0.5) == 2.0
    assert cs._percentile(xs, 0.25) == 1.0


def test_summarize_alphas_fields():
    s = cs.summarize_alphas([-0.2, -0.1, 0.0, 0.1, 0.2])
    assert s["n"] == 5
    assert s["mean"] == pytest.approx(0.0)
    assert s["min"] == -0.2 and s["max"] == 0.2
    assert s["p50"] == pytest.approx(0.0)


def test_realized_base_stats_saturation():
    # 大 alpha + 大 S → 全部饱和到 0/1
    alphas = [-0.5, 0.5] * 5
    st = cs.realized_base_stats(alphas, sensitivity=10.0)
    assert st["sat_ratio"] == pytest.approx(1.0)
    assert st["std"] == pytest.approx(0.5)  # 一半 0 一半 1
    # 极小 S → 全挤 0.5 附近，std≈0
    st2 = cs.realized_base_stats(alphas, sensitivity=0.0001)
    assert st2["std"] < 0.01
    assert st2["sat_ratio"] == pytest.approx(0.0)


# --------------------------- 目标函数单调性 ---------------------------
def test_spread_and_std_monotonic_increasing_in_S():
    alphas = [-0.15, -0.08, -0.03, 0.0, 0.04, 0.09, 0.17]
    spreads = [cs.realized_base_stats(alphas, s)["spread"] for s in (0.5, 1.0, 2.0, 4.0)]
    stds = [cs.realized_base_stats(alphas, s)["std"] for s in (0.5, 1.0, 2.0, 4.0)]
    # 未完全饱和区间，spread / std 随 S 单调不减
    assert spreads[0] < spreads[1] <= spreads[2] + 1e-9
    assert stds[0] < stds[1] < stds[2] <= stds[3] + 1e-9


def test_spread_robust_to_fat_tail_outlier():
    # 加入一个极端离群点不显著改变中位 80% 宽度（稳健性）
    base = [-0.2, -0.1, -0.05, 0.0, 0.05, 0.1, 0.2]
    sp1 = cs.realized_base_stats(base, 2.0)["spread"]
    sp2 = cs.realized_base_stats(base + [8.0], 2.0)["spread"]  # +800% 离群
    assert abs(sp1 - sp2) < 0.15
    # 而标准差会被离群点显著抬高（说明为何选 spread 而非 std）
    sd1 = cs.realized_base_stats(base, 2.0)["std"]
    sd2 = cs.realized_base_stats(base + [8.0], 2.0)["std"]
    assert sd2 > sd1


def test_objective_is_distance_to_target():
    alphas = [-0.1, 0.0, 0.1]
    st = cs.realized_base_stats(alphas, 2.0)
    assert cs.objective(alphas, 2.0, target_spread=0.80) == pytest.approx(
        abs(st["spread"] - 0.80))


# --------------------------- 搜索收敛 ---------------------------
def test_golden_section_converges_within_bracket():
    # 黄金分割用于在「含极小点的 bracket」内细化（bracket 由 calibrate 的网格给出）。
    # 在 [0.5, 1.8] 上 J 单峰，应收敛到使 spread≈0.80 的 S。
    alphas = [-0.45, -0.3, -0.18, -0.08, 0.0, 0.06, 0.14, 0.25, 0.38, 0.55]
    best, history = cs.golden_section_min(alphas, 0.5, 1.8, target_spread=0.80, tol=1e-4)
    achieved = cs.realized_base_stats(alphas, best)["spread"]
    assert achieved == pytest.approx(0.80, abs=0.03)
    # 迭代记录的目标函数应整体下降（最后一步优于第一步）
    assert history[-1]["objective"] <= history[0]["objective"]
    assert len(history) > 3


def test_calibrate_brackets_and_converges_to_target_spread():
    # 端到端 calibrate 会用网格给 bracket，避开饱和平台，收敛到目标 spread。
    alphas = [-0.45, -0.3, -0.18, -0.08, 0.0, 0.06, 0.14, 0.25, 0.38, 0.55]
    res = cs.calibrate(alphas, target_spread=0.80)
    assert res["recommended_stats"]["spread"] == pytest.approx(0.80, abs=0.03)
    assert res["recommended"] < 2.0  # 真实极小点远离 20 的边界


def test_grid_search_curve_shape():
    alphas = [-0.2, -0.1, 0.0, 0.1, 0.2]
    curve = cs.grid_search(alphas, grid=[0.5, 1.0, 2.0, 4.0, 8.0], target_spread=0.80)
    assert [r["sensitivity"] for r in curve] == [0.5, 1.0, 2.0, 4.0, 8.0]
    # spread 随 S 递增（直到饱和）
    spreads = [r["spread"] for r in curve]
    assert spreads == sorted(spreads)


def test_calibrate_end_to_end_and_compare_default():
    alphas = [-0.45, -0.3, -0.18, -0.08, 0.0, 0.06, 0.14, 0.25, 0.38, 0.55]
    res = cs.calibrate(alphas, target_spread=0.80, default_sensitivity=2.5)
    assert res["n"] == len(alphas)
    assert 0.05 <= res["recommended"] <= 20.0
    # 推荐值的目标函数不差于默认值
    rec_obj = abs(res["recommended_stats"]["spread"] - 0.80)
    def_obj = abs(res["default_stats"]["spread"] - 0.80)
    assert rec_obj <= def_obj + 1e-9
    assert isinstance(res["improved"], bool)


def test_calibrate_empty_raises():
    with pytest.raises(ValueError):
        cs.calibrate([])


# --------------------------- 市场分类 ---------------------------
def test_classify_markets():
    assert cs.classify("NVDA").market == "us"
    assert cs.classify("NVDA").benchmark_key == "gspc"
    hk = cs.classify("0700.HK")
    assert hk.market == "hk" and hk.benchmark_key == "hsi" and hk.yf_symbol == "0700.HK"
    a = cs.classify("600900")
    assert a.market == "a" and a.benchmark_key == "csi300" and a.yf_symbol == "600900.SS"
    sz = cs.classify("000001")
    assert sz.yf_symbol == "000001.SZ"


# --------------------------- 标的汇总（读真实 json，不联网） ---------------------------
def test_load_universe_dedup_and_filters(tmp_path):
    wl = tmp_path / "wl.json"
    hold = tmp_path / "hold.json"
    wl.write_text('{"g1":["NVDA","AVGO"],"hk":["0700.HK"],"_meta":["X"],"a":[]}',
                  encoding="utf-8")
    hold.write_text('{"_comment":"x","AVGO":15,"600900":10,"CASH":30}',
                    encoding="utf-8")
    tickers = cs.load_universe(str(wl), str(hold))
    assert "NVDA" in tickers and "0700.HK" in tickers and "600900" in tickers
    assert "CASH" not in tickers
    assert "X" not in tickers  # _meta 组被忽略
    # AVGO 去重只出现一次
    assert sum(1 for t in tickers if t.upper() == "AVGO") == 1


def test_load_universe_reads_repo_files():
    root = os.path.join(os.path.dirname(__file__), "..")
    tickers = cs.load_universe(
        os.path.join(root, "data", "watchlist.json"),
        os.path.join(root, "data", "holdings.example.json"),
    )
    assert "NVDA" in tickers
    assert "600900" in tickers  # 来自 holdings.example.json
    assert "0700.HK" in tickers
    assert "CASH" not in tickers


# --------------------------- 价格序列 → alpha ---------------------------
def _series(start_close, end_close, n=260):
    """合成升序日线：从 2025-01-01 起 n 个交易日，线性涨到目标。"""
    from datetime import date, timedelta
    out = []
    d = date(2025, 1, 1)
    for i in range(n):
        frac = i / (n - 1)
        close = start_close + (end_close - start_close) * frac
        out.append(((d + timedelta(days=i)).isoformat(), round(close, 4)))
    return out


def test_window_return_picks_anchor_and_realized():
    s = _series(100.0, 120.0, n=400)
    w = cs.window_return(s, lookback_days=365)
    assert w["realized_close"] == pytest.approx(120.0)
    # anchor 约在最后一日往前 365 天，收益为正
    assert w["ret"] > 0
    assert w["anchor_close"] < w["realized_close"]


def test_compute_alpha_with_benchmark():
    # 标的 +20%，基准 +5% → alpha ≈ +15%
    tkr = _series(100.0, 120.0, n=400)
    bench = _series(1000.0, 1050.0, n=400)
    res = cs.compute_alpha(tkr, bench, lookback_days=365)
    assert res["has_benchmark"] is True
    assert res["alpha"] == pytest.approx(0.15, abs=0.02)


def test_compute_alpha_without_benchmark():
    tkr = _series(100.0, 110.0, n=400)
    res = cs.compute_alpha(tkr, None, lookback_days=365)
    assert res["has_benchmark"] is False
    assert res["benchmark_return"] == 0.0
    assert res["alpha"] == res["raw_return"]


# --------------------------- 取数管线（注入 DictHistoryProvider） ---------------------------
def test_collect_alpha_samples_with_mock_provider():
    provider = cs.DictHistoryProvider({
        "NVDA": _series(100.0, 140.0, n=400),       # 美股
        "^GSPC": _series(5000.0, 5250.0, n=400),    # 标普
        "0700.HK": _series(300.0, 360.0, n=400),    # 港股
        "^HSI": _series(18000.0, 18900.0, n=400),   # 恒指
    })
    samples = cs.collect_alpha_samples(["NVDA", "0700.HK"], provider, lookback_days=365)
    assert len(samples["alphas"]) == 2
    assert samples["uncovered"] == []
    # NVDA 原始 +35% 区间，扣标普同窗 +4.5% → alpha≈+31%
    nvda = [c for c in samples["covered"] if c["ticker"] == "NVDA"][0]
    assert nvda["alpha"] == pytest.approx(0.31, abs=0.03)
    assert nvda["has_benchmark"] is True


def test_collect_alpha_samples_reports_uncovered():
    provider = cs.DictHistoryProvider({
        "NVDA": _series(100.0, 120.0, n=400),
        "^GSPC": _series(5000.0, 5100.0, n=400),
        # 600900 故意不提供 → 应进未覆盖
    })
    samples = cs.collect_alpha_samples(["NVDA", "600900"], provider, lookback_days=365)
    assert len(samples["alphas"]) == 1
    assert len(samples["uncovered"]) == 1
    assert samples["uncovered"][0]["ticker"] == "600900"


def test_render_report_smoke():
    provider = cs.DictHistoryProvider({
        "NVDA": _series(100.0, 130.0, n=400),
        "^GSPC": _series(5000.0, 5200.0, n=400),
    })
    samples = cs.collect_alpha_samples(["NVDA"], provider, lookback_days=365)
    calib = cs.calibrate(samples["alphas"] + [-0.1, 0.05, -0.2, 0.18], target_spread=0.80)
    report = cs.render_report(samples, calib, 365)
    assert "SENSITIVITY 尺度校准报告" in report
    assert "推荐 SENSITIVITY" in report


# --------------------------- env 覆盖（realized_feedback 集成） ---------------------------
def test_env_override_sensitivity(monkeypatch):
    monkeypatch.setenv(rf.ENV_SENSITIVITY, "3.7")
    assert rf._resolve_default_sensitivity() == pytest.approx(3.7)
    monkeypatch.setenv(rf.ENV_SENSITIVITY, "not_a_number")
    assert rf._resolve_default_sensitivity() == pytest.approx(rf._BASE_SENSITIVITY)
    monkeypatch.setenv(rf.ENV_SENSITIVITY, "-1")  # 非正 → 回退
    assert rf._resolve_default_sensitivity() == pytest.approx(rf._BASE_SENSITIVITY)
    monkeypatch.delenv(rf.ENV_SENSITIVITY, raising=False)
    assert rf._resolve_default_sensitivity() == pytest.approx(rf._BASE_SENSITIVITY)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

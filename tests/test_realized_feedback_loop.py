#!/usr/bin/env python3
"""离线单元测试：已实现收益反馈闭环 + 多空辩论。

覆盖：
- decision_log：JSONL 持久化 + 环境变量路径覆盖 + 单一来源校验
- realized_feedback：raw return / alpha / realized_base 与各大师校准分映射
- debate：bull/bear/净判断 结构化输出
- run_with_realized_feedback：闭环串联（直接价格 / PriceProvider / 持久化）

全部用 mock 数据，不依赖真实网络。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import debate as db  # noqa: E402
import decision_log as dl  # noqa: E402
import realized_feedback as rf  # noqa: E402
from evolution_loop_v10 import run_with_realized_feedback  # noqa: E402
from graph import MASTER_PREFIXES, SCORE_THRESHOLD  # noqa: E402


def _sample_decision(**overrides):
    base = dict(
        ticker="aapl",
        date="2026-01-01",
        scores={"duan": 0.9, "buffett": 0.8, "munger": 0.4, "lilu": 0.6},
        price_anchor=100.0,
        benchmark="SPX",
        benchmark_anchor=5000.0,
        note="unit test",
    )
    base.update(overrides)
    return dl.DecisionRecord(**base)


# --------------------------- decision_log ---------------------------
def test_decision_record_normalizes_and_validates():
    d = _sample_decision()
    assert d.ticker == "AAPL"  # 归一化大写
    assert d.price_anchor == 100.0
    assert d.created_at  # 自动补时间戳
    with pytest.raises(ValueError):
        _sample_decision(price_anchor=0)
    with pytest.raises(ValueError):
        _sample_decision(scores={"unknown_master": 0.5})  # 单一来源校验


def test_decision_log_roundtrip_with_env_override(tmp_path, monkeypatch):
    log = tmp_path / "decisions.jsonl"
    monkeypatch.setenv(dl.ENV_LOG_PATH, str(log))
    assert dl.default_log_path() == str(log)

    dl.append_decision(_sample_decision(ticker="AAPL", date="2026-01-01"))
    dl.append_decision(_sample_decision(ticker="MSFT", date="2026-02-01"))
    dl.append_decision(_sample_decision(ticker="AAPL", date="2026-03-01"))

    rows = dl.load_decisions()
    assert len(rows) == 3
    aapl = dl.decisions_for_ticker("aapl")
    assert [r.date for r in aapl] == ["2026-01-01", "2026-03-01"]  # 升序
    assert dl.latest_decision("AAPL").date == "2026-03-01"
    assert dl.latest_decision("NONE") is None


def test_load_decisions_missing_file_returns_empty(tmp_path):
    assert dl.load_decisions(str(tmp_path / "nope.jsonl")) == []


# --------------------------- realized_feedback ---------------------------
def test_compute_returns_alpha_and_base():
    d = _sample_decision(price_anchor=100.0, benchmark_anchor=5000.0)
    # 标的 +20%，基准 +5% → alpha = +15%（固定 sensitivity=2.5 测映射公式本身）
    stats = rf.compute_returns(
        d, realized_price=120.0, benchmark_realized_price=5250.0, sensitivity=2.5)
    assert stats.raw_return == pytest.approx(0.20)
    assert stats.benchmark_return == pytest.approx(0.05)
    assert stats.alpha == pytest.approx(0.15)
    # realized_base = clip(0.5 + 0.15*2.5,0,1) = 0.875
    assert stats.realized_base == pytest.approx(0.875)
    assert stats.has_benchmark is True


def test_compute_returns_clips_and_no_benchmark():
    d = _sample_decision(benchmark=None, benchmark_anchor=None)
    # 暴涨 +100% 无基准 → alpha=raw=1.0 → base clip 到 1.0（固定 sensitivity=2.5）
    stats = rf.compute_returns(d, realized_price=200.0, sensitivity=2.5)
    assert stats.has_benchmark is False
    assert stats.benchmark_return == 0.0
    assert stats.realized_base == 1.0
    # 暴跌 -60% → base clip 到 0.0
    stats2 = rf.compute_returns(d, realized_price=40.0, sensitivity=2.5)
    assert stats2.realized_base == 0.0


def test_realized_scores_rewards_calibration():
    # 标的 +20% / 基准 +5% → realized_base ≈ 0.875（决策被证明正确，固定 sensitivity=2.5）
    d = _sample_decision(scores={"duan": 0.9, "buffett": 0.85, "munger": 0.1, "lilu": 0.5})
    scores, stats = rf.realized_scores(d, 120.0, 5250.0, sensitivity=2.5)
    assert set(scores) == set(MASTER_PREFIXES)
    # buffett 信心 0.85 ≈ 真相 0.875 → 校准好，高分（应达标）
    assert scores["buffett"] >= SCORE_THRESHOLD
    # munger 信心 0.1 却大涨 → 严重背离 → 低分（触发优化）
    assert scores["munger"] < 0.3
    # 所有分都在 [0,1]
    assert all(0.0 <= v <= 1.0 for v in scores.values())


def test_realized_scores_missing_master_defaults_neutral():
    d = _sample_decision(scores={"duan": 0.5})  # 仅一个大师
    scores, stats = rf.realized_scores(d, 105.0, 5050.0)
    # 缺失的大师按 0.5 中性处理，仍输出全部四个 key
    assert set(scores) == set(MASTER_PREFIXES)


def test_static_price_provider_and_via_provider():
    d = _sample_decision()
    provider = rf.StaticPriceProvider({
        ("AAPL", "2026-06-01"): 120.0,
        ("SPX", "2026-06-01"): 5250.0,
    })
    scores, stats = rf.realized_scores_via_provider(d, "2026-06-01", provider)
    assert stats.alpha == pytest.approx(0.15)
    with pytest.raises(KeyError):
        provider.get_price("AAPL", "1999-01-01")


# --------------------------- debate ---------------------------
def test_debate_bullish():
    res = db.run_debate({"duan": 0.9, "buffett": 0.85, "munger": 0.7, "lilu": 0.8})
    assert res.net_stance == "bullish"
    assert res.ok is True
    assert res.net_score > 0
    assert len(res.bull.supporters) == 4
    assert res.bear.supporters == []


def test_debate_bearish_uses_issues():
    issues = {"munger": ["监管风险显著"], "lilu": ["趋势走弱"]}
    res = db.run_debate(
        {"duan": 0.3, "buffett": 0.2, "munger": 0.1, "lilu": 0.4},
        issues_by_master=issues,
    )
    assert res.net_stance == "bearish"
    assert res.net_score < 0
    assert "监管风险显著" in " ".join(res.bear.points)


def test_debate_neutral_balanced():
    res = db.run_debate({"duan": 0.5, "buffett": 0.5, "munger": 0.5, "lilu": 0.5})
    assert res.net_stance == "neutral"
    assert res.ok is False
    assert res.net_score == pytest.approx(0.0)


# --------------------------- closed loop ---------------------------
def test_run_with_realized_feedback_direct_price():
    d = _sample_decision(scores={"duan": 0.95, "buffett": 0.9, "munger": 0.95, "lilu": 0.9})
    # 标的暴跌 -50%，基准持平 → 高信心被证伪 → 低分 → 应产生优化更新
    out = run_with_realized_feedback(d, realized_price=50.0, benchmark_realized_price=5000.0)
    assert isinstance(out["stats"], rf.ReturnStats)
    assert out["stats"].alpha < 0
    # backward 应基于已实现收益（非硬编码）
    assert set(out["scores"]) == set(MASTER_PREFIXES)
    assert len(out["updates"]) > 0  # 高信心却大跌 → 校准差 → 触发更新
    # debate 用决策当时信心（全多）→ bullish
    assert out["debate"].net_stance == "bullish"


def test_run_with_realized_feedback_via_provider_and_persist(tmp_path, monkeypatch):
    log = tmp_path / "decisions.jsonl"
    monkeypatch.setenv(dl.ENV_LOG_PATH, str(log))
    d = _sample_decision(scores={"duan": 0.88, "buffett": 0.86, "munger": 0.84, "lilu": 0.87})
    provider = rf.StaticPriceProvider({
        ("AAPL", "2026-06-01"): 120.0,
        ("SPX", "2026-06-01"): 5250.0,
    })
    out = run_with_realized_feedback(
        d, realized_date="2026-06-01", price_provider=provider, persist=True
    )
    # 好校准（信心≈真相 0.875）→ 多数达标 → 更新很少甚至为 0
    assert out["stats"].alpha == pytest.approx(0.15)
    # 持久化生效
    assert dl.latest_decision("AAPL") is not None
    # 闭环含多空辩论
    assert out["debate"].net_stance == "bullish"


def test_run_with_realized_feedback_requires_price():
    d = _sample_decision()
    with pytest.raises(ValueError):
        run_with_realized_feedback(d)


def test_persist_also_appends_experience(tmp_path, monkeypatch):
    """persist=True 时默认同步沉淀经验（V10.20 主线接线）。"""
    dec_log = tmp_path / "decisions.jsonl"
    exp_log = tmp_path / "experiences.jsonl"
    run_log = tmp_path / "runs.jsonl"
    monkeypatch.setenv(dl.ENV_LOG_PATH, str(dec_log))
    monkeypatch.setenv("BERKSHIRE_EXPERIENCE_LOG", str(exp_log))
    monkeypatch.setenv("BERKSHIRE_RUN_LOG", str(run_log))

    import experience_store as es  # noqa: E402

    d = _sample_decision(scores={"duan": 0.95, "buffett": 0.9, "munger": 0.95, "lilu": 0.9})
    out = run_with_realized_feedback(
        d, realized_price=50.0, benchmark_realized_price=5000.0, persist=True
    )
    assert "experience" in out
    assert out["experience"].verdict == es.VERDICT_REFUTED
    assert out["experience"].ticker == "AAPL"
    rows = es.ExperienceStore(str(exp_log)).load()
    assert len(rows) == 1
    assert rows[0].alpha == pytest.approx(out["stats"].alpha)

    from run_recorder import RunRecorder  # noqa: E402

    runs = RunRecorder(str(run_log)).load()
    assert len(runs) == 1
    assert runs[0].event == "feedback"


def test_persist_experience_false_skips(tmp_path, monkeypatch):
    exp_log = tmp_path / "experiences.jsonl"
    monkeypatch.setenv("BERKSHIRE_EXPERIENCE_LOG", str(exp_log))

    import experience_store as es  # noqa: E402

    d = _sample_decision()
    out = run_with_realized_feedback(
        d,
        realized_price=120.0,
        benchmark_realized_price=5250.0,
        persist=False,
        persist_experience=False,
    )
    assert "experience" not in out
    assert es.ExperienceStore(str(exp_log)).load() == []


def test_include_perf_direct_price():
    d = _sample_decision(price_anchor=100.0, benchmark_anchor=5000.0)
    out = run_with_realized_feedback(
        d,
        realized_price=120.0,
        benchmark_realized_price=5250.0,
        include_perf=True,
    )
    assert "perf" in out
    assert out["perf"].n == 1  # 单期收益：锚点→实现价
    assert out["perf"].has_benchmark is True
    assert out["perf"].cumulative_return == pytest.approx(0.20)


def test_include_perf_via_provider():
    d = _sample_decision()
    provider = rf.StaticPriceProvider({
        ("AAPL", "2026-06-01"): 120.0,
        ("SPX", "2026-06-01"): 5250.0,
    })
    out = run_with_realized_feedback(
        d,
        realized_date="2026-06-01",
        price_provider=provider,
        include_perf=True,
    )
    assert "perf" in out
    assert out["perf"].n >= 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

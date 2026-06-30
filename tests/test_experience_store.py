#!/usr/bin/env python3
"""离线单元测试：src/experience_store.py（RAG-lite 经验沉淀 + 检索）。"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import experience_store as es  # noqa: E402


def _exp(ticker="AAPL", *, alpha=0.1, verdict=None, sector=None, tags=None, lesson="", hid=None):
    return es.Experience(
        ticker=ticker,
        date="2024-01-01",
        stances={"buffett": 0.9},
        alpha=alpha,
        realized_base=0.7,
        verdict=verdict or es.classify_verdict(alpha),
        lesson=lesson,
        sector=sector,
        tags=tags or [],
        hypothesis_id=hid,
    )


# --------------------------- Experience ---------------------------
def test_experience_normalizes_and_defaults():
    e = _exp("aapl", sector="tech", tags=["Moat", " "])
    assert e.ticker == "AAPL"
    assert e.sector == "TECH"
    assert e.tags == ["moat"]  # 去空、转小写
    assert e.created_at is not None


def test_experience_rejects_bad_verdict():
    with pytest.raises(ValueError):
        es.Experience(ticker="X", date="d", stances={}, alpha=0.0,
                      realized_base=0.5, verdict="bogus")


def test_experience_rejects_empty_ticker():
    with pytest.raises(ValueError):
        es.Experience(ticker="  ", date="d", stances={}, alpha=0.0,
                      realized_base=0.5, verdict="neutral")


def test_classify_verdict_bands():
    assert es.classify_verdict(0.05) == es.VERDICT_CONFIRMED
    assert es.classify_verdict(-0.05) == es.VERDICT_REFUTED
    assert es.classify_verdict(0.0) == es.VERDICT_NEUTRAL
    # band 内归 neutral
    assert es.classify_verdict(0.01, band=0.02) == es.VERDICT_NEUTRAL


# --------------------------- experience_from_stats（鸭子类型）---------------------------
class _Decision:
    def __init__(self):
        self.ticker = "MSFT"
        self.date = "2024-02-02"
        self.scores = {"buffett": 0.8, "munger": 0.6}


class _Stats:
    def __init__(self, alpha, realized_base):
        self.alpha = alpha
        self.realized_base = realized_base


def test_experience_from_stats_maps_fields_and_verdict():
    e = es.experience_from_stats(_Decision(), _Stats(0.12, 0.81), lesson="护城河被低估")
    assert e.ticker == "MSFT"
    assert e.date == "2024-02-02"
    assert e.stances == {"buffett": 0.8, "munger": 0.6}
    assert e.alpha == pytest.approx(0.12)
    assert e.verdict == es.VERDICT_CONFIRMED
    assert e.lesson == "护城河被低估"


# --------------------------- ExperienceStore 落盘 ---------------------------
def test_store_append_load_roundtrip(tmp_path):
    path = str(tmp_path / "exp.jsonl")
    store = es.ExperienceStore(path)
    store.append(_exp("AAPL", lesson="教训A"))
    store.append(_exp("NVDA", lesson="教训B"))
    rows = store.load()
    assert [r.ticker for r in rows] == ["AAPL", "NVDA"]
    assert rows[0].lesson == "教训A"


def test_store_load_missing_file_returns_empty(tmp_path):
    assert es.ExperienceStore(str(tmp_path / "none.jsonl")).load() == []


def test_store_load_skips_corrupted_line(tmp_path):
    path = tmp_path / "exp.jsonl"
    path.write_text('{"ticker":"AAPL","date":"d","stances":{},"alpha":0.1,'
                    '"realized_base":0.6,"verdict":"confirmed"}\n'
                    "not-json\n", encoding="utf-8")
    rows = es.ExperienceStore(str(path)).load()
    assert len(rows) == 1
    assert rows[0].ticker == "AAPL"


def test_store_env_override(monkeypatch, tmp_path):
    p = str(tmp_path / "env.jsonl")
    monkeypatch.setenv(es.ENV_LOG_PATH, p)
    assert es.default_log_path() == p


# --------------------------- KeywordExperienceRetriever ---------------------------
def test_keyword_retriever_ticker_ranks_above_sector(tmp_path):
    store = es.ExperienceStore(str(tmp_path / "e.jsonl"))
    store.append(_exp("AAPL", sector="TECH", lesson="ticker命中"))
    store.append(_exp("NVDA", sector="TECH", lesson="仅sector命中"))
    r = es.KeywordExperienceRetriever(store)
    hits = r.retrieve(ticker="AAPL", sector="TECH", k=2)
    assert hits[0].ticker == "AAPL"  # ticker 权重更高排第一


def test_keyword_retriever_no_match_returns_empty(tmp_path):
    store = es.ExperienceStore(str(tmp_path / "e.jsonl"))
    store.append(_exp("AAPL"))
    assert es.KeywordExperienceRetriever(store).retrieve(ticker="ZZZZ") == []


def test_keyword_retriever_k_limit(tmp_path):
    store = es.ExperienceStore(str(tmp_path / "e.jsonl"))
    for _ in range(5):
        store.append(_exp("AAPL"))
    assert len(es.KeywordExperienceRetriever(store).retrieve(ticker="AAPL", k=3)) == 3


def test_keyword_retriever_tag_match(tmp_path):
    store = es.ExperienceStore(str(tmp_path / "e.jsonl"))
    store.append(_exp("AAPL", tags=["overconfidence"]))
    hits = es.KeywordExperienceRetriever(store).retrieve(
        ticker="ZZZ", tags=["overconfidence"], k=3
    )
    assert len(hits) == 1


def test_keyword_retriever_failure_degrades_to_empty():
    class _BoomStore:
        def load(self):
            raise RuntimeError("boom")

    r = es.KeywordExperienceRetriever(_BoomStore())  # type: ignore[arg-type]
    assert r.retrieve(ticker="AAPL") == []  # 不抛，降级为空


# --------------------------- StaticExperienceRetriever / Protocol ---------------------------
def test_static_retriever_truncates_k():
    items = [_exp("A"), _exp("B"), _exp("C")]
    assert len(es.StaticExperienceRetriever(items).retrieve(ticker="X", k=2)) == 2


def test_retriever_protocol_isinstance():
    store = es.ExperienceStore("/tmp/none.jsonl")
    assert isinstance(es.KeywordExperienceRetriever(store), es.ExperienceRetriever)
    assert isinstance(es.StaticExperienceRetriever([]), es.ExperienceRetriever)

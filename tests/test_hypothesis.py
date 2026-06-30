#!/usr/bin/env python3
"""离线单元测试：src/hypothesis.py（显式可证伪假设对象 + 最小存储）。"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import hypothesis as hyp  # noqa: E402


def _h(ticker="AAPL", statement="护城河被低估", **kw):
    return hyp.Hypothesis(ticker=ticker, statement=statement, **kw)


# --------------------------- Hypothesis ---------------------------
def test_hypothesis_autogen_id_and_created_at():
    h = _h()
    assert h.id and len(h.id) == 12
    assert h.created_at is not None
    assert h.status == hyp.STATUS_OPEN
    assert h.proposed_by == hyp.PROPOSED_BY_SYSTEM


def test_hypothesis_normalizes_ticker():
    assert _h("aapl").ticker == "AAPL"


def test_hypothesis_rejects_empty_statement():
    with pytest.raises(ValueError):
        _h(statement="   ")


def test_hypothesis_rejects_empty_ticker():
    with pytest.raises(ValueError):
        hyp.Hypothesis(ticker=" ", statement="x")


def test_hypothesis_proposed_by_master_prefix_ok():
    assert _h(proposed_by="buffett").proposed_by == "buffett"


def test_hypothesis_rejects_unknown_proposer():
    with pytest.raises(ValueError):
        _h(proposed_by="warren")


def test_hypothesis_rejects_bad_status():
    with pytest.raises(ValueError):
        _h(status="maybe")


def test_hypothesis_roundtrip_dict():
    h = _h(reasoning="r", justification="j", falsifiable_condition="若12月ROIC不升",
           proposed_by="munger", linked_decision_id="trace-1")
    h2 = hyp.Hypothesis.from_dict(h.to_dict())
    assert h2 == h


def test_hypothesis_from_dict_ignores_unknown_keys():
    h = hyp.Hypothesis.from_dict(
        {"ticker": "AAPL", "statement": "s", "bogus": 1}
    )
    assert h.ticker == "AAPL"


# --------------------------- HypothesisStore ---------------------------
def test_store_append_load_get_for_ticker(tmp_path):
    path = str(tmp_path / "h.jsonl")
    store = hyp.HypothesisStore(path)
    h1 = _h("AAPL", id="id-aapl")
    h2 = _h("NVDA", id="id-nvda")
    store.append(h1)
    store.append(h2)
    assert [h.ticker for h in store.load()] == ["AAPL", "NVDA"]
    assert store.get("id-nvda").ticker == "NVDA"
    assert store.get("missing") is None
    assert [h.ticker for h in store.for_ticker("aapl")] == ["AAPL"]


def test_store_load_missing_returns_empty(tmp_path):
    assert hyp.HypothesisStore(str(tmp_path / "none.jsonl")).load() == []


def test_store_skips_corrupted_line(tmp_path):
    p = tmp_path / "h.jsonl"
    p.write_text('{"ticker":"AAPL","statement":"s","id":"x"}\nbroken\n', encoding="utf-8")
    rows = hyp.HypothesisStore(str(p)).load()
    assert len(rows) == 1 and rows[0].ticker == "AAPL"


def test_store_env_override(monkeypatch, tmp_path):
    p = str(tmp_path / "env.jsonl")
    monkeypatch.setenv(hyp.ENV_LOG_PATH, p)
    assert hyp.default_log_path() == p


# --------------------------- group_experiences_by_hypothesis ---------------------------
class _Exp:
    def __init__(self, hid):
        self.hypothesis_id = hid


def test_group_experiences_by_hypothesis():
    exps = [_Exp("h1"), _Exp("h1"), _Exp(None), _Exp("h2")]
    grouped = hyp.group_experiences_by_hypothesis(exps)
    assert len(grouped["h1"]) == 2
    assert len(grouped["h2"]) == 1
    assert len(grouped[""]) == 1  # 无 hypothesis_id 归入空串桶

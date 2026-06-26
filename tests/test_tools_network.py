#!/usr/bin/env python3
"""离线网络层加固测试：tavily_search / ashare_data._curl / morningstar.fetch_page

全部通过 monkeypatch 模拟 httpx / subprocess，不触真实网络。
重点验证：瞬时错误重试、超时处理、错误透传、解析正确性。
"""
import os
import sys
import types

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import tavily_search as tv          # noqa: E402
import ashare_data as ad            # noqa: E402
import morningstar_fair_value as mf  # noqa: E402


# ===========================================================================
# tavily_search
# ===========================================================================
@pytest.fixture(autouse=True)
def _reset_key_index():
    tv.TavilySearcher._key_index = 0
    yield
    tv.TavilySearcher._key_index = 0


def test_load_keys_multi(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEYS", "k1, k2 ,k3")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert tv._load_keys() == ["k1", "k2", "k3"]


def test_load_keys_single_fallback(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEYS", raising=False)
    monkeypatch.setenv("TAVILY_API_KEY", "solo")
    assert tv._load_keys() == ["solo"]


def test_load_keys_empty(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEYS", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert tv._load_keys() == []


def test_init_raises_without_keys(monkeypatch):
    # api_keys=[] 会回退到 _load_keys()，故需把环境来源也清空
    monkeypatch.setattr(tv, "_load_keys", lambda: [])
    with pytest.raises(ValueError):
        tv.TavilySearcher(api_keys=[])


def test_rotate_key():
    s = tv.TavilySearcher(api_keys=["a", "b"])
    assert s.current_key == "a"
    s._rotate_key()
    assert s.current_key == "b"
    s._rotate_key()
    assert s.current_key == "a"  # 环回


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _fake_client_factory(actions):
    """返回一个伪 httpx.Client 类，post() 依次消费 actions（异常则抛出，否则返回）。"""
    seq = list(actions)

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            act = seq.pop(0)
            if isinstance(act, Exception):
                raise act
            return act

    return _Client


def test_search_retries_transient_then_succeeds(monkeypatch):
    monkeypatch.setattr(tv.time, "sleep", lambda *_: None)
    actions = [httpx.TimeoutException("t"), _Resp(200, {"answer": "ok", "results": []})]
    monkeypatch.setattr(tv.httpx, "Client", _fake_client_factory(actions))
    s = tv.TavilySearcher(api_keys=["k"])
    res = s.search("q")
    assert res == {"answer": "ok", "results": []}


def test_search_5xx_retries_then_gives_up(monkeypatch):
    monkeypatch.setattr(tv.time, "sleep", lambda *_: None)
    actions = [_Resp(503), _Resp(503), _Resp(503)]
    monkeypatch.setattr(tv.httpx, "Client", _fake_client_factory(actions))
    s = tv.TavilySearcher(api_keys=["k"])
    res = s.search("q")
    assert "error" in res
    assert "503" in res["error"]


def test_search_429_rotates_key(monkeypatch):
    monkeypatch.setattr(tv.time, "sleep", lambda *_: None)
    actions = [_Resp(429), _Resp(200, {"answer": "after-rotate", "results": []})]
    monkeypatch.setattr(tv.httpx, "Client", _fake_client_factory(actions))
    s = tv.TavilySearcher(api_keys=["k1", "k2"])
    res = s.search("q")
    assert res["answer"] == "after-rotate"
    assert s.current_key == "k2"  # 已轮询


def test_search_non_retryable_returns_error(monkeypatch):
    monkeypatch.setattr(tv.time, "sleep", lambda *_: None)
    actions = [_Resp(400)]
    monkeypatch.setattr(tv.httpx, "Client", _fake_client_factory(actions))
    s = tv.TavilySearcher(api_keys=["k"])
    res = s.search("q")
    assert "error" in res
    assert "400" in res["error"]


def test_get_stock_data_parses_and_truncates(monkeypatch):
    s = tv.TavilySearcher(api_keys=["k"])
    monkeypatch.setattr(s, "search", lambda *a, **k: {
        "answer": "A",
        "results": [{"title": "t", "url": "u", "content": "c" * 600}],
    })
    data = s.get_stock_data("600519", "茅台")
    assert data["answer"] == "A"
    assert len(data["sources"]) == 1
    assert len(data["sources"][0]["content"]) == 500  # 截断到 500


def test_get_stock_data_propagates_error(monkeypatch):
    s = tv.TavilySearcher(api_keys=["k"])
    monkeypatch.setattr(s, "search", lambda *a, **k: {"error": "boom", "results": []})
    assert s.get_stock_data("x", "y") == {"error": "boom"}


# ===========================================================================
# ashare_data._curl
# ===========================================================================
def _ns(returncode, stdout):
    return types.SimpleNamespace(returncode=returncode, stdout=stdout)


def test_curl_success(monkeypatch):
    monkeypatch.setattr(ad.subprocess, "run", lambda *a, **k: _ns(0, b"hello"))
    assert ad._curl("http://x") == "hello"


def test_curl_gbk_fallback(monkeypatch):
    payload = "你好".encode("gbk")
    monkeypatch.setattr(ad.subprocess, "run", lambda *a, **k: _ns(0, payload))
    assert ad._curl("http://x") == "你好"


def test_curl_retries_timeout_then_success(monkeypatch):
    monkeypatch.setattr(ad.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def fake_run(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ad.subprocess.TimeoutExpired(cmd="curl", timeout=15)
        return _ns(0, b"ok")

    monkeypatch.setattr(ad.subprocess, "run", fake_run)
    assert ad._curl("http://x") == "ok"
    assert calls["n"] == 2


def test_curl_persistent_failure_raises(monkeypatch):
    monkeypatch.setattr(ad.time, "sleep", lambda *_: None)
    monkeypatch.setattr(ad.subprocess, "run", lambda *a, **k: _ns(1, b""))
    with pytest.raises(ConnectionError):
        ad._curl("http://x")


# ===========================================================================
# morningstar_fair_value.fetch_page
# ===========================================================================
def _ns_text(returncode, stdout):
    return types.SimpleNamespace(returncode=returncode, stdout=stdout)


def test_fetch_page_success(monkeypatch):
    monkeypatch.setattr(mf.subprocess, "run",
                        lambda *a, **k: _ns_text(0, '{"total": 1, "rows": []}'))
    assert mf.fetch_page(1) == {"total": 1, "rows": []}


def test_fetch_page_non_json_then_success(monkeypatch):
    monkeypatch.setattr(mf.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def fake_run(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return _ns_text(0, "<html>blocked</html>")
        return _ns_text(0, '{"rows": [1, 2]}')

    monkeypatch.setattr(mf.subprocess, "run", fake_run)
    assert mf.fetch_page(2) == {"rows": [1, 2]}
    assert calls["n"] == 2


def test_fetch_page_persistent_timeout_raises(monkeypatch):
    monkeypatch.setattr(mf.time, "sleep", lambda *_: None)

    def fake_run(*a, **k):
        raise mf.subprocess.TimeoutExpired(cmd="curl", timeout=30)

    monkeypatch.setattr(mf.subprocess, "run", fake_run)
    with pytest.raises(ConnectionError):
        mf.fetch_page(1)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

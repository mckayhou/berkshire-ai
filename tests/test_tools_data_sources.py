#!/usr/bin/env python3
"""离线测试：data_sources 多源降级层。

覆盖：
  - 降级链优先级 / 顺序解析（默认、环境变量、显式参数）
  - 缺库的源被 import 守卫优雅跳过（不抛异常）
  - 第一个成功的源即返回，后续源不再调用
  - 空结果触发降级；全失败返回明确的 ok=False 结构（不抛异常）
  - 增强源（tushare）的开关 + token 范式：关闭即零侵入
全程不触真实网络（mock 适配器 / curl）。
"""
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import data_sources as ds  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """清掉所有相关环境变量，保证默认状态可预测。"""
    for k in list(os.environ):
        if k.startswith("BERKSHIRE_") or k in ("TUSHARE_TOKEN",):
            monkeypatch.delenv(k, raising=False)
    yield


# ---------------------------------------------------------------------------
# 顺序解析
# ---------------------------------------------------------------------------
def test_default_order():
    assert ds._resolve_order() == ds._DEFAULT_ORDER


def test_order_from_env(monkeypatch):
    monkeypatch.setenv("BERKSHIRE_DATA_SOURCES", "efinance, native ,akshare")
    assert ds._resolve_order() == ["efinance", "native", "akshare"]


def test_order_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv("BERKSHIRE_DATA_SOURCES", "efinance")
    assert ds._resolve_order(["native"]) == ["native"]


def test_order_dedup_and_unknown_ignored():
    assert ds._resolve_order(["native", "native", "bogus"]) == ["native"]


# ---------------------------------------------------------------------------
# 降级链行为（用伪适配器替换注册表）
# ---------------------------------------------------------------------------
def _make_source(name, *, enabled=True, reason="", daily_impl=None):
    class _S(ds.DataSource):
        pass

    _S.name = name

    def _enabled(self):
        return enabled, reason

    def _daily(self, code, limit=250):
        if daily_impl is None:
            raise ds.NotSupported("no daily")
        return daily_impl(code, limit)

    _S.enabled = _enabled
    _S.daily = _daily
    return _S


def _patch_registry(monkeypatch, sources):
    reg = {cls.name: cls for cls in sources}
    monkeypatch.setattr(ds, "_REGISTRY", reg)
    monkeypatch.setattr(ds, "_DEFAULT_ORDER", [c.name for c in sources])


def test_chain_uses_first_success(monkeypatch):
    calls = []
    s1 = _make_source("s1", daily_impl=lambda c, l: calls.append("s1") or [{"date": "d", "close": 1}])
    s2 = _make_source("s2", daily_impl=lambda c, l: calls.append("s2") or [{"date": "d2"}])
    _patch_registry(monkeypatch, [s1, s2])

    res = ds.daily("600519")
    assert res["ok"] is True
    assert res["source"] == "s1"
    assert calls == ["s1"]  # s2 未被调用


def test_chain_falls_back_on_exception(monkeypatch):
    def boom(c, l):
        raise ConnectionError("network down")

    s1 = _make_source("s1", daily_impl=boom)
    s2 = _make_source("s2", daily_impl=lambda c, l: [{"date": "d2", "close": 2}])
    _patch_registry(monkeypatch, [s1, s2])

    res = ds.daily("600519")
    assert res["ok"] is True
    assert res["source"] == "s2"
    a1 = next(a for a in res["attempts"] if a["source"] == "s1")
    assert a1["ok"] is False
    assert "ConnectionError" in a1["error"]


def test_chain_falls_back_on_empty(monkeypatch):
    s1 = _make_source("s1", daily_impl=lambda c, l: [])
    s2 = _make_source("s2", daily_impl=lambda c, l: [{"date": "d", "close": 3}])
    _patch_registry(monkeypatch, [s1, s2])

    res = ds.daily("600519")
    assert res["source"] == "s2"
    a1 = next(a for a in res["attempts"] if a["source"] == "s1")
    assert a1["error"] == "empty result"


def test_disabled_source_skipped(monkeypatch):
    s1 = _make_source("s1", enabled=False, reason="lib not installed")
    s2 = _make_source("s2", daily_impl=lambda c, l: [{"date": "d", "close": 4}])
    _patch_registry(monkeypatch, [s1, s2])

    res = ds.daily("600519")
    assert res["source"] == "s2"
    a1 = next(a for a in res["attempts"] if a["source"] == "s1")
    assert a1["skipped"] is True


def test_all_fail_returns_error_struct_not_raise(monkeypatch):
    def boom(c, l):
        raise RuntimeError("x")

    s1 = _make_source("s1", daily_impl=boom)
    s2 = _make_source("s2", enabled=False, reason="off")
    _patch_registry(monkeypatch, [s1, s2])

    res = ds.daily("600519")
    assert res["ok"] is False
    assert res["source"] is None
    assert res["data"] is None
    assert res["error"]
    assert len(res["attempts"]) == 2


def test_unsupported_kind_returns_error():
    res = ds.fetch("balance_sheet", "600519")
    assert res["ok"] is False
    assert "unsupported kind" in res["error"]


def test_notsupported_is_skipped(monkeypatch):
    # s1 不实现 daily（默认抛 NotSupported）→ 应被当作 skip 而非 fail
    s1 = _make_source("s1", daily_impl=None)
    s2 = _make_source("s2", daily_impl=lambda c, l: [{"date": "d", "close": 5}])
    _patch_registry(monkeypatch, [s1, s2])

    res = ds.daily("600519")
    assert res["source"] == "s2"
    a1 = next(a for a in res["attempts"] if a["source"] == "s1")
    assert a1["skipped"] is True


# ---------------------------------------------------------------------------
# 增强源 tushare：开关 + token 范式
# ---------------------------------------------------------------------------
def test_tushare_disabled_by_default(monkeypatch):
    ok, reason = ds.TushareSource().enabled()
    assert ok is False
    assert "BERKSHIRE_ENABLE_TUSHARE" in reason


def test_tushare_enabled_but_missing_lib(monkeypatch):
    monkeypatch.setenv("BERKSHIRE_ENABLE_TUSHARE", "1")
    # 模拟未安装 tushare：拦截 import
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "tushare":
            raise ImportError("no tushare")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    ok, reason = ds.TushareSource().enabled()
    assert ok is False
    assert "not installed" in reason


def test_tushare_enabled_lib_present_no_token(monkeypatch):
    monkeypatch.setenv("BERKSHIRE_ENABLE_TUSHARE", "1")
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    # 注入一个假的 tushare 模块，使 import 成功
    monkeypatch.setitem(sys.modules, "tushare", types.ModuleType("tushare"))
    ok, reason = ds.TushareSource().enabled()
    assert ok is False
    assert "TUSHARE_TOKEN" in reason


def test_tushare_fully_enabled(monkeypatch):
    monkeypatch.setenv("BERKSHIRE_ENABLE_TUSHARE", "1")
    monkeypatch.setenv("TUSHARE_TOKEN", "tok")
    monkeypatch.setitem(sys.modules, "tushare", types.ModuleType("tushare"))
    ok, reason = ds.TushareSource().enabled()
    assert ok is True


# ---------------------------------------------------------------------------
# 缺库的真实源：import 守卫优雅跳过
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cls", [
    ds.EfinanceSource, ds.AkshareSource, ds.BaostockSource, ds.YFinanceSource,
])
def test_optional_lib_sources_skip_when_missing(monkeypatch, cls):
    import builtins
    real_import = builtins.__import__
    libname = cls.requires[0]

    def fake_import(name, *a, **k):
        if name == libname:
            raise ImportError(f"no {libname}")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    ok, reason = cls().enabled()
    assert ok is False
    assert "not installed" in reason


# ---------------------------------------------------------------------------
# native 源：复用 ashare_data，mock curl，不触网
# ---------------------------------------------------------------------------
def test_native_enabled_default():
    ok, reason = ds.NativeSource().enabled()
    assert ok is True


def test_native_can_be_disabled(monkeypatch):
    monkeypatch.setenv("BERKSHIRE_DISABLE_NATIVE", "1")
    ok, reason = ds.NativeSource().enabled()
    assert ok is False


def test_native_daily_parses_mocked_kline(monkeypatch):
    import ashare_data as ad
    payload = {"data": {"klines": [
        "2026-01-02,10.0,10.5,10.8,9.9,1000,1,2",
        "2026-01-03,10.5,11.0,11.2,10.4,1200,1,2",
    ]}}
    monkeypatch.setattr(ad, "_curl_json", lambda *a, **k: payload)
    res = ds.daily("600519", sources=["native"], limit=10)
    assert res["ok"] is True
    assert res["source"] == "native"
    assert len(res["data"]) == 2
    assert res["data"][0]["date"] == "2026-01-02"
    assert res["data"][-1]["close"] == "11.0"


def test_native_daily_empty_then_all_fail(monkeypatch):
    import ashare_data as ad
    monkeypatch.setattr(ad, "_curl_json", lambda *a, **k: {"data": {"klines": []}})
    res = ds.daily("600519", sources=["native"], limit=10)
    assert res["ok"] is False
    assert res["error"]


def test_source_status_no_network(monkeypatch):
    rows = ds.source_status()
    names = [r["source"] for r in rows]
    assert "native" in names
    native = next(r for r in rows if r["source"] == "native")
    assert native["enabled"] is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

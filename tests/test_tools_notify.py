#!/usr/bin/env python3
"""离线测试：notify 多通道交付层。

覆盖：
  - 零配置时只落地本地文件、不报错（delivered=False, local_file 存在）
  - 通道未配置 → 跳过；配置后走 mock 的 curl 发送
  - Telegram / 飞书 长消息自动拆分多条
  - 飞书卡片失败 → 回退纯文本
  - 飞书加签：配置 FEISHU_SECRET 时附加 timestamp/sign
  - 单通道异常不影响其它通道与主流程
全程不触真实网络（mock _curl_post_json）。
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import notify as nf  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
              "FEISHU_WEBHOOK", "FEISHU_SECRET", "BERKSHIRE_NOTIFY_DIR"):
        monkeypatch.delenv(k, raising=False)
    # 把本地兜底目录指到临时目录，避免污染仓库 reports/
    monkeypatch.setenv("BERKSHIRE_NOTIFY_DIR", str(tmp_path / "notifications"))
    yield


# ---------------------------------------------------------------------------
# 文本拆分
# ---------------------------------------------------------------------------
def test_split_short_text():
    assert nf._split_text("hello", 100) == ["hello"]


def test_split_long_text_by_lines():
    text = "\n".join(["line%d" % i for i in range(100)])
    parts = nf._split_text(text, 50)
    assert len(parts) > 1
    assert all(len(p) <= 50 for p in parts)
    assert "".join(parts) == text


def test_split_hard_break_single_long_line():
    text = "x" * 250
    parts = nf._split_text(text, 100)
    assert len(parts) == 3
    assert "".join(parts) == text


# ---------------------------------------------------------------------------
# 零配置：只落地本地
# ---------------------------------------------------------------------------
def test_zero_config_local_only(monkeypatch):
    # 确保即使有人配置了通道也不会真的发；mock 掉网络
    monkeypatch.setattr(nf, "_curl_post_json", lambda *a, **k: (0, "should not be called"))
    res = nf.notify("标题", "正文内容")
    assert res["delivered"] is False
    assert res["local_file"] is not None
    assert os.path.exists(res["local_file"])
    with open(res["local_file"], encoding="utf-8") as f:
        content = f.read()
    assert "标题" in content and "正文内容" in content
    # 两个通道都应被标记为 skipped
    assert all(c.get("skipped") for c in res["channels"])


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
def test_telegram_available(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    ok, _ = nf.telegram_available()
    assert ok is True


def test_telegram_send_success(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    captured = []

    def fake_post(url, payload, timeout=15):
        captured.append((url, payload))
        return 200, json.dumps({"ok": True})

    monkeypatch.setattr(nf, "_curl_post_json", fake_post)
    res = nf.notify("t", "body", channels=["telegram"])
    assert res["delivered"] is True
    tg = res["channels"][0]
    assert tg["ok"] is True and tg["parts"] == 1
    assert "api.telegram.org/bottok/sendMessage" in captured[0][0]
    # delivered 成功且未强制 local → 不落地
    assert res["local_file"] is None


def test_telegram_long_message_splits(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    calls = {"n": 0}

    def fake_post(url, payload, timeout=15):
        calls["n"] += 1
        return 200, "{}"

    monkeypatch.setattr(nf, "_curl_post_json", fake_post)
    long_text = "a" * (nf.TELEGRAM_LIMIT * 2 + 100)
    res = nf.send_telegram("title", long_text)
    assert res["ok"] is True
    assert res["parts"] == calls["n"] >= 3


def test_telegram_http_error(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr(nf, "_curl_post_json", lambda *a, **k: (403, "forbidden"))
    res = nf.send_telegram("t", "b")
    assert res["ok"] is False
    assert "403" in res["error"]


# ---------------------------------------------------------------------------
# 飞书
# ---------------------------------------------------------------------------
def test_feishu_card_success(monkeypatch):
    monkeypatch.setenv("FEISHU_WEBHOOK", "https://open.feishu.cn/hook/x")
    captured = []

    def fake_post(url, payload, timeout=15):
        captured.append(payload)
        return 200, json.dumps({"code": 0})

    monkeypatch.setattr(nf, "_curl_post_json", fake_post)
    res = nf.send_feishu("标题", "正文")
    assert res["ok"] is True
    assert captured[0]["msg_type"] == "interactive"  # 优先卡片


def test_feishu_card_fails_falls_back_to_text(monkeypatch):
    monkeypatch.setenv("FEISHU_WEBHOOK", "https://open.feishu.cn/hook/x")
    seq = []

    def fake_post(url, payload, timeout=15):
        seq.append(payload["msg_type"])
        if payload["msg_type"] == "interactive":
            return 200, json.dumps({"code": 9499, "msg": "card error"})
        return 200, json.dumps({"code": 0})

    monkeypatch.setattr(nf, "_curl_post_json", fake_post)
    res = nf.send_feishu("标题", "正文")
    assert res["ok"] is True
    assert res["text_fallback"] is True
    assert seq == ["interactive", "text"]


def test_feishu_sign_attached(monkeypatch):
    monkeypatch.setenv("FEISHU_WEBHOOK", "https://open.feishu.cn/hook/x")
    monkeypatch.setenv("FEISHU_SECRET", "secret123")
    captured = {}

    def fake_post(url, payload, timeout=15):
        captured.update(payload)
        return 200, json.dumps({"code": 0})

    monkeypatch.setattr(nf, "_curl_post_json", fake_post)
    nf.send_feishu("t", "b")
    assert "sign" in captured and "timestamp" in captured


def test_feishu_sign_deterministic():
    sig = nf._feishu_sign("secret", "1700000000")
    # 同输入必产生同签名（回归保护）
    assert sig == nf._feishu_sign("secret", "1700000000")
    assert isinstance(sig, str) and len(sig) > 0


def test_feishu_long_message_splits(monkeypatch):
    monkeypatch.setenv("FEISHU_WEBHOOK", "https://open.feishu.cn/hook/x")
    calls = {"n": 0}

    def fake_post(url, payload, timeout=15):
        calls["n"] += 1
        return 200, json.dumps({"code": 0})

    monkeypatch.setattr(nf, "_curl_post_json", fake_post)
    res = nf.send_feishu("t", "b" * (nf.FEISHU_LIMIT * 2 + 50))
    assert res["ok"] is True
    assert res["parts"] >= 3


# ---------------------------------------------------------------------------
# 编排：异常隔离 + always_local
# ---------------------------------------------------------------------------
def test_channel_exception_isolated(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setenv("FEISHU_WEBHOOK", "https://open.feishu.cn/hook/x")

    def boom_tg(title, text):
        raise RuntimeError("tg crashed")

    monkeypatch.setattr(nf, "send_telegram", boom_tg)
    monkeypatch.setattr(nf, "_CHANNELS", {
        "telegram": (nf.telegram_available, nf.send_telegram),
        "feishu": (nf.feishu_available, lambda t, x: {"channel": "feishu", "ok": True, "parts": 1}),
    })
    res = nf.notify("t", "b")
    tg = next(c for c in res["channels"] if c["channel"] == "telegram")
    fs = next(c for c in res["channels"] if c["channel"] == "feishu")
    assert tg["ok"] is False and "tg crashed" in tg["error"]
    assert fs["ok"] is True          # 飞书不受影响
    assert res["delivered"] is True


def test_always_local_writes_even_on_success(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr(nf, "_curl_post_json", lambda *a, **k: (200, "{}"))
    res = nf.notify("t", "b", channels=["telegram"], always_local=True)
    assert res["delivered"] is True
    assert res["local_file"] is not None
    assert os.path.exists(res["local_file"])


def test_channel_status(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    rows = nf.channel_status()
    tg = next(r for r in rows if r["channel"] == "telegram")
    fs = next(r for r in rows if r["channel"] == "feishu")
    assert tg["available"] is True
    assert fs["available"] is False


def test_unknown_channel_skipped():
    res = nf.notify("t", "b", channels=["bogus"])
    assert res["channels"][0]["skipped"] is True
    assert res["local_file"] is not None  # 全部不可用 → 落地


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

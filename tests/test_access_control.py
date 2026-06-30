#!/usr/bin/env python3
"""离线单元测试：访问控制（src/access_control.py）——API Key 鉴权 + 限流。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from access_control import (  # noqa: E402
    RateLimiter,
    check_api_key,
    key_fingerprint,
)


# --------------------------- check_api_key ---------------------------
def test_no_allowed_keys_means_open():
    ok, ident = check_api_key(None, [])
    assert ok is True
    assert ident is None  # 未鉴权 → 调用方用 IP 做配额键


def test_missing_key_rejected_when_required():
    ok, ident = check_api_key(None, ["secret"])
    assert ok is False
    assert ident is None


def test_valid_key_accepted_with_fingerprint():
    ok, ident = check_api_key("secret", ["secret", "other"])
    assert ok is True
    assert ident is not None and ident.startswith("key-")
    # 指纹不泄露明文
    assert "secret" not in ident


def test_wrong_key_rejected():
    ok, _ = check_api_key("nope", ["secret"])
    assert ok is False


def test_fingerprint_stable_and_distinct():
    assert key_fingerprint("a") == key_fingerprint("a")
    assert key_fingerprint("a") != key_fingerprint("b")


# --------------------------- RateLimiter ---------------------------
def test_rate_limiter_allows_until_cap():
    rl = RateLimiter(max_per_min=3)
    t = 1000.0
    assert rl.allow("k", now=t) is True
    assert rl.allow("k", now=t) is True
    assert rl.allow("k", now=t) is True
    assert rl.allow("k", now=t) is False  # 第 4 次超额


def test_rate_limiter_window_slides():
    rl = RateLimiter(max_per_min=2, window_s=60.0)
    assert rl.allow("k", now=0.0) is True
    assert rl.allow("k", now=1.0) is True
    assert rl.allow("k", now=2.0) is False
    # 61s 后窗口滑动，旧时间戳过期
    assert rl.allow("k", now=61.5) is True


def test_rate_limiter_buckets_independent():
    rl = RateLimiter(max_per_min=1)
    assert rl.allow("a", now=0.0) is True
    assert rl.allow("b", now=0.0) is True  # 不同 bucket 互不影响
    assert rl.allow("a", now=0.0) is False


def test_rate_limiter_disabled_when_zero():
    rl = RateLimiter(max_per_min=0)
    for _ in range(100):
        assert rl.allow("k", now=0.0) is True
    assert rl.remaining("k") == -1  # 无限


def test_rate_limiter_remaining():
    rl = RateLimiter(max_per_min=3)
    assert rl.remaining("k", now=0.0) == 3
    rl.allow("k", now=0.0)
    assert rl.remaining("k", now=0.0) == 2

#!/usr/bin/env python3
"""
访问控制：API Key 鉴权 + 每客户端速率限制（生产化硬化 档D）。

为什么需要它
--------------------------------------------------
V10.16 的 `sanitize` 防的是「内容层」注入；但 `/score` `/debate` 一旦对外暴露，
还需要「访问层」防护：谁能调（鉴权）、能调多频（限流）。本模块提供**框架无关**
的两块纯逻辑，便于离线单测，再由 `service.create_app()` 挂到 FastAPI 中间路径：

- `check_api_key(provided, allowed)`：常量时间比较，返回 (是否通过, 配额键指纹)。
  - allowed 为空 → 视为「未启用鉴权」（开发/内网），一律放行，配额键回退到 IP。
- `RateLimiter`：进程内固定窗口计数器（每分钟），按「key 指纹或 IP」分桶。
  - 纯标准库、线程安全（加锁）；多副本部署应改用 Redis 等共享存储（见 ROADMAP）。

零第三方依赖（hashlib / hmac / threading / time）。
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple


def key_fingerprint(api_key: str) -> str:
    """API key 的短指纹（用于日志/限流分桶，绝不回显明文）。"""
    return "key-" + hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]


def check_api_key(
    provided: Optional[str],
    allowed: List[str],
) -> Tuple[bool, Optional[str]]:
    """校验 API key。

    Returns:
        (ok, ident)：
          - allowed 为空：未启用鉴权 → (True, None)，调用方用 IP 做配额键。
          - provided 命中 allowed 之一（常量时间比较）→ (True, key 指纹)。
          - 否则 → (False, None)。
    """
    if not allowed:
        return True, None
    if not provided:
        return False, None
    for candidate in allowed:
        if hmac.compare_digest(provided, candidate):
            return True, key_fingerprint(provided)
    return False, None


class RateLimiter:
    """固定窗口速率限制（每分钟 N 次），按调用方标识分桶。线程安全。

    用滑动 deque 存每个 bucket 最近一分钟的请求时间戳；`allow()` 先剔除过期
    时间戳，再判断是否超额。`max_per_min<=0` 视为关闭（一律放行）。
    """

    def __init__(self, max_per_min: int = 60, window_s: float = 60.0):
        self.max_per_min = max_per_min
        self.window_s = window_s
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, bucket: str, now: Optional[float] = None) -> bool:
        """该 bucket 当前是否允许再发一次请求（允许则计入一次）。"""
        if self.max_per_min <= 0:
            return True
        t = now if now is not None else time.monotonic()
        cutoff = t - self.window_s
        with self._lock:
            dq = self._hits.setdefault(bucket, deque())
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= self.max_per_min:
                return False
            dq.append(t)
            return True

    def remaining(self, bucket: str, now: Optional[float] = None) -> int:
        """该 bucket 当前窗口剩余配额（用于响应头/调试）。"""
        if self.max_per_min <= 0:
            return -1  # 无限
        t = now if now is not None else time.monotonic()
        cutoff = t - self.window_s
        with self._lock:
            dq = self._hits.get(bucket)
            if not dq:
                return self.max_per_min
            while dq and dq[0] < cutoff:
                dq.popleft()
            return max(0, self.max_per_min - len(dq))

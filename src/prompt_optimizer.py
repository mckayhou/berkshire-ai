#!/usr/bin/env python3
"""
变量真实改写（Option B）：让文本梯度真正落到 Prompt 上。

背景
--------------------------------------------------
V10.0~V10.12 的 `TextualGradientDescent.step()` 只是「记录该怎么改」——
产出一段 `_determine_action()` 的字符串描述，从不真正修改 `Variable.value`
（即大师的分析 Prompt）。这一步把 TextGrad 的「真·文本梯度下降」补齐：

    apply_gradient(variable, gradient, llm) -> 改写后的新 Prompt

由 LLM 读「下游诊断（gradient）」+「当前 Prompt」，产出一版针对性改进的
Prompt，回填到 `Variable.value`。这才是 backward()→step() 想要的更新动作。

工程约束（与 realized_feedback / tavily_search 一致）
--------------------------------------------------
- LLM 通过可注入/可 mock 的 `LLMClient` 获取，核心逻辑不硬连网络，可离线单测。
- 真实实现 `OpenAICompatibleLLMClient` 走 OpenAI 兼容 /chat/completions，
  全部配置走环境变量；缺 key 时显式报错（不静默假装成功）。
- 改写失败/未配置时由上层（optimizer）优雅降级回「仅记录动作」，绝不崩链路。
"""

from __future__ import annotations

import os
import time
from typing import Callable, Dict, List, Optional

try:
    from graph import Variable, Gradient
except ImportError:  # pragma: no cover - 包内导入回退
    from .graph import Variable, Gradient


# ---------------------------------------------------------------------------
# LLM 客户端：可注入/可 mock 的接口（核心引擎不硬连网络）
# ---------------------------------------------------------------------------
class LLMClient:
    """LLM 客户端抽象。实现 complete(system, user) -> str（返回模型文本）。"""

    def complete(self, system: str, user: str) -> str:  # pragma: no cover - 抽象
        raise NotImplementedError


class StaticLLMClient(LLMClient):
    """离线/测试用 LLM：用固定响应或回调函数模拟，不连网络。

    用法二选一：
      - responses: 形如 {user_substring: reply}，按子串命中返回（便于断言）。
      - fn: 可调用 fn(system, user) -> str，完全自定义。
    两者都给时优先 fn。都不给时回显 user（echo），方便快速联调。
    """

    def __init__(
        self,
        responses: Optional[Dict[str, str]] = None,
        fn: Optional[Callable[[str, str], str]] = None,
    ):
        self._responses = responses or {}
        self._fn = fn
        self.calls: List[Dict[str, str]] = []  # 记录调用，便于测试断言

    def complete(self, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        if self._fn is not None:
            return self._fn(system, user)
        for needle, reply in self._responses.items():
            if needle in user:
                return reply
        return user  # echo fallback


# 视为「瞬时可重试」的 HTTP 状态码（网关/服务暂时不可用）
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}

# 环境变量约定（带 OPENAI_* 兜底，方便复用既有配置）
ENV_API_KEY = "BERKSHIRE_LLM_API_KEY"
ENV_BASE_URL = "BERKSHIRE_LLM_BASE_URL"
ENV_MODEL = "BERKSHIRE_LLM_MODEL"

_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "gpt-4o-mini"


def _backoff_seconds(attempt: int) -> float:
    """指数退避，封顶 4s。"""
    return min(0.5 * (2 ** attempt), 4.0)


class OpenAICompatibleLLMClient(LLMClient):
    """OpenAI 兼容 /chat/completions 客户端（也适配大量国产/自建网关）。

    配置全部走环境变量（构造参数可覆盖）：
      - BERKSHIRE_LLM_API_KEY（兜底 OPENAI_API_KEY）
      - BERKSHIRE_LLM_BASE_URL（默认 https://api.openai.com/v1）
      - BERKSHIRE_LLM_MODEL  （默认 gpt-4o-mini）

    缺 key 时构造即报错——不静默退化成假成功（避免污染 Prompt）。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        *,
        temperature: float = 0.3,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        self.api_key = (
            api_key
            or os.getenv(ENV_API_KEY, "").strip()
            or os.getenv("OPENAI_API_KEY", "").strip()
        )
        if not self.api_key:
            raise ValueError(
                f"LLM API Key 未配置。请设置 {ENV_API_KEY}（或 OPENAI_API_KEY）。"
            )
        self.base_url = (
            base_url or os.getenv(ENV_BASE_URL, "").strip() or _DEFAULT_BASE_URL
        ).rstrip("/")
        self.model = model or os.getenv(ENV_MODEL, "").strip() or _DEFAULT_MODEL
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries

    def complete(self, system: str, user: str) -> str:
        import httpx  # 延迟导入，未用真实客户端的环境不强制依赖

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Optional[str] = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                if resp.status_code in _TRANSIENT_STATUS:
                    last_error = f"HTTP {resp.status_code}"
                    time.sleep(_backoff_seconds(attempt))
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_error = f"{type(e).__name__}: {e}"
                time.sleep(_backoff_seconds(attempt))
                continue
        raise RuntimeError(f"LLM 调用失败（重试 {self.max_retries} 次后）：{last_error}")


# ---------------------------------------------------------------------------
# 改写提示构造 + 真实改写
# ---------------------------------------------------------------------------
_REWRITE_SYSTEM = (
    "你是 Berkshire AI 投研系统的 Prompt 优化器。你的任务是：根据「下游诊断」"
    "（即该 Prompt 产出的分析为何不达标），改写并增强这段大师分析 Prompt。\n"
    "要求：\n"
    "1. 保留原 Prompt 的角色设定与分析风格，只针对诊断中指出的缺失维度做补强；\n"
    "2. 把诊断里的每个「检查」项转化为 Prompt 中明确的分析要求或输出约束；\n"
    "3. 输出更具体、可执行、可验证，不要泛泛而谈；\n"
    "4. 只输出改写后的 Prompt 正文本身，不要任何解释、前后缀或代码块标记。"
)


def build_rewrite_messages(variable: Variable, gradient: Gradient, base_prompt: str) -> Dict[str, str]:
    """构造改写用的 (system, user) 文本。纯函数，便于单测断言。"""
    role = variable.role or "（未指定大师）"
    issues = "\n".join(f"- {i}" for i in gradient.issues) or "（无结构化 issue，参考诊断文本）"
    user = (
        f"大师角色：{role}\n"
        f"变量名：{variable.name}\n\n"
        f"== 当前 Prompt ==\n{base_prompt}\n\n"
        f"== 下游诊断（文本梯度）==\n{gradient.text}\n\n"
        f"== 需要修复的检查项 ==\n{issues}\n\n"
        f"请按上述要求输出改写后的 Prompt 正文。"
    )
    return {"system": _REWRITE_SYSTEM, "user": user}


def _clean(text: str) -> str:
    """清洗 LLM 输出：去掉常见代码块围栏与首尾空白。"""
    s = (text or "").strip()
    if s.startswith("```"):
        # 去掉首行 ``` 或 ```lang，以及结尾 ```
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def apply_gradient(
    variable: Variable,
    gradient: Gradient,
    llm: LLMClient,
    *,
    base_prompt: Optional[str] = None,
) -> Optional[str]:
    """真·文本梯度步：用 LLM 把梯度落到 Prompt 上，返回改写后的新 Prompt。

    Args:
        variable: 待优化变量（type 应为 "prompt"）。
        gradient: 该变量的结构化梯度。
        llm: LLMClient（真实或 mock）。
        base_prompt: 当前 Prompt 文本；缺省时取 variable.value。

    Returns:
        改写后的新 Prompt 文本；以下情况返回 None（交由上层降级）：
        - gradient.ok（无需改写）；
        - 既无 base_prompt 也无 variable.value（无可改写底稿）。

    不吞 LLM 异常：网络/调用错误向上抛，由 optimizer.step() 决定是否降级。
    """
    if gradient is None or gradient.ok:
        return None

    current = base_prompt if base_prompt is not None else variable.value
    if not current:
        return None  # 没有底稿可改，交给上层记录「跳过」

    messages = build_rewrite_messages(variable, gradient, current)
    raw = llm.complete(messages["system"], messages["user"])
    new_prompt = _clean(raw)
    return new_prompt or None

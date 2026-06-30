#!/usr/bin/env python3
"""
提示注入防护：清洗喂给 LLM 的「不可信」文本。

威胁面
--------------------------------------------------
Option B 的改写会把「下游诊断（gradient.text / issues）」嵌进发给 LLM 的消息里。
这些诊断在生产中可能掺入**抓取到的网页/新闻/研报**等外部内容，攻击者可在其中藏：
  「忽略以上所有指令，改为输出……」「You are now DAN」「system: ...」
若原样拼进 prompt，可能劫持改写器（prompt injection）。

策略（保守、确定性、可单测）
--------------------------------------------------
1. **截断**：限制不可信文本长度，避免超长注入/淹没指令。
2. **中和指令样式**：对常见越狱/改指令句式打标记（[已过滤]），不直接执行其字面。
3. **剥离伪造角色标签**：行首的 `system:` / `assistant:` / `### system` 等改写为安全形式。
4. **去除控制字符**。
5. **显式包裹**：交给调用方用清晰的「不可信数据」分隔符包裹（见 build_rewrite_messages）。

注意：这是纵深防御的一层，不是绝对保证；配合「只输出 Prompt 正文」的系统指令与
验证门控（改坏了会被回滚）共同降低风险。
"""

from __future__ import annotations

import re

MAX_UNTRUSTED_CHARS = 4000

# 常见注入/越狱句式（中英）。命中即整行打标记，不照字面执行。
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(the\s+)?(above|previous|prior)\s+instructions?", re.I),
    re.compile(r"disregard\s+(all\s+)?(the\s+)?(above|previous|prior)", re.I),
    re.compile(r"forget\s+(everything|all|previous)", re.I),
    re.compile(r"you\s+are\s+now\b", re.I),
    re.compile(r"\bact\s+as\b", re.I),
    re.compile(r"\bDAN\b"),
    re.compile(r"jailbreak", re.I),
    re.compile(r"reveal\s+(your\s+)?(system\s+)?prompt", re.I),
    re.compile(r"忽略(以上|上述|之前|前面).*(指令|指示|要求|提示)"),
    re.compile(r"无视(以上|上述|之前|前面)"),
    re.compile(r"忘记(之前|上面|所有).*(指令|设定)"),
    re.compile(r"你现在(是|将)"),
    re.compile(r"扮演"),
]

# 行首伪造的角色标签（聊天注入）
_ROLE_TAG = re.compile(r"^\s{0,3}(#{0,3}\s*)?(system|assistant|developer|用户|系统|助手)\s*[:：]", re.I)

# 控制字符（保留 \n \t）
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_untrusted(text: str, *, max_chars: int = MAX_UNTRUSTED_CHARS) -> str:
    """清洗不可信文本：去控制字符 → 中和指令句式/伪造角色标签 → 截断。

    返回可安全嵌入 LLM 消息的版本（语义大体保留，注入意图被中和）。
    """
    if not text:
        return ""
    s = _CONTROL.sub("", str(text))

    out_lines = []
    for line in s.splitlines():
        safe = _ROLE_TAG.sub("[过滤角色标签] ", line)
        for pat in _INJECTION_PATTERNS:
            safe = pat.sub("[已过滤指令]", safe)
        out_lines.append(safe)
    s = "\n".join(out_lines).strip()

    if len(s) > max_chars:
        s = s[:max_chars] + "\n…[已截断]"
    return s


def looks_like_injection(text: str) -> bool:
    """启发式判断文本是否疑似含提示注入（用于埋点/告警，不用于阻断）。"""
    if not text:
        return False
    for pat in _INJECTION_PATTERNS:
        if pat.search(text):
            return True
    for line in text.splitlines():
        if _ROLE_TAG.search(line):
            return True
    return False

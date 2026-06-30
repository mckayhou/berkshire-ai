#!/usr/bin/env python3
"""
中心化配置与启动自检（生产化硬化）。

目标
--------------------------------------------------
项目此前把环境变量散落在各模块（tavily / prompt_optimizer / realized_feedback /
decision_log / data_sources / notify）。本模块提供**单一事实来源**：

- 所有环境变量的声明（名称、所属功能、是否密钥、说明）集中一处；
- `load_dotenv()`：零依赖加载 `.env`（不覆盖已存在的真实环境变量）；
- `get_settings()`：解析出一份只读快照 `Settings`；
- `doctor()` / CLI：体检各功能模块是否「就绪 / 降级 / 未配置」，便于部署前检查。

设计原则：纯读取 + 零新依赖（不引入 python-dotenv）；绝不打印密钥明文；
各既有模块仍可继续直接读 `os.environ`，本模块为叠加的「真相 + 校验」层，不强制改造。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# 环境变量声明（单一事实来源）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EnvVar:
    name: str
    feature: str          # 所属功能模块
    secret: bool          # 是否密钥（体检/日志中脱敏）
    description: str
    aliases: tuple = ()   # 兜底别名（如 OPENAI_API_KEY）


ENV_SPEC: tuple = (
    # 实时检索
    EnvVar("TAVILY_API_KEYS", "tavily", True, "Tavily 多 Key 轮询（逗号分隔）", ("TAVILY_API_KEY",)),
    # LLM（Option B prompt 改写）
    EnvVar("BERKSHIRE_LLM_API_KEY", "llm", True, "LLM API Key", ("OPENAI_API_KEY",)),
    EnvVar("BERKSHIRE_LLM_BASE_URL", "llm", False, "OpenAI 兼容 base url（默认官方）"),
    EnvVar("BERKSHIRE_LLM_MODEL", "llm", False, "模型名（默认 gpt-4o-mini）"),
    # 引擎
    EnvVar("BERKSHIRE_SENSITIVITY", "engine", False, "收益→真相分灵敏度覆盖（默认 0.5）"),
    EnvVar("BERKSHIRE_DECISION_LOG", "engine", False, "决策日志路径（默认 ~/.berkshire）"),
    # A 股数据降级链
    EnvVar("BERKSHIRE_DATA_SOURCES", "ashare", False, "数据源优先级（逗号分隔，覆盖默认链）"),
    EnvVar("BERKSHIRE_ENABLE_TUSHARE", "ashare", False, "置 1 启用 tushare 源"),
    EnvVar("TUSHARE_TOKEN", "ashare", True, "Tushare token（启用 tushare 时必需）"),
    # 多通道推送
    EnvVar("TELEGRAM_BOT_TOKEN", "notify", True, "Telegram bot token"),
    EnvVar("TELEGRAM_CHAT_ID", "notify", False, "Telegram chat id"),
    EnvVar("FEISHU_WEBHOOK", "notify", True, "飞书自定义机器人 webhook"),
    EnvVar("FEISHU_SECRET", "notify", True, "飞书加签密钥（可选）"),
)


def _env(name: str, aliases: tuple = ()) -> Optional[str]:
    """读取环境变量，按主名 → 别名顺序，返回首个非空 strip 值。"""
    for key in (name, *aliases):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return None


# ---------------------------------------------------------------------------
# .env 加载（零依赖）
# ---------------------------------------------------------------------------
def load_dotenv(path: str = ".env", *, override: bool = False) -> int:
    """加载 `.env` 到 os.environ。返回成功写入的键数。

    - 默认 **不覆盖**已存在的真实环境变量（CI/容器注入优先）。
    - 支持 `KEY=VALUE`、`export KEY=VALUE`、`#` 注释、空行、引号包裹值。
    - 文件不存在时静默返回 0（绝不抛错）。
    """
    if not os.path.isfile(path):
        return 0
    written = 0
    with open(path, encoding="utf-8") as fp:
        for raw in fp:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key:
                continue
            if not override and key in os.environ:
                continue
            os.environ[key] = value
            written += 1
    return written


# ---------------------------------------------------------------------------
# 解析后的只读配置快照
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Settings:
    # tavily
    tavily_keys: List[str] = field(default_factory=list)
    # llm
    llm_api_key: Optional[str] = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    # engine
    sensitivity: Optional[float] = None
    decision_log: Optional[str] = None
    # ashare
    enable_tushare: bool = False
    tushare_token: Optional[str] = None
    data_sources: Optional[str] = None
    # notify
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    feishu_webhook: Optional[str] = None

    @property
    def has_llm(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def has_tavily(self) -> bool:
        return bool(self.tavily_keys)


def get_settings() -> Settings:
    """从当前 os.environ 解析出 Settings 快照（不修改环境）。"""
    keys_raw = _env("TAVILY_API_KEYS", ("TAVILY_API_KEY",)) or ""
    tavily_keys = [k.strip() for k in keys_raw.split(",") if k.strip()]

    sensitivity: Optional[float] = None
    raw_sens = _env("BERKSHIRE_SENSITIVITY")
    if raw_sens:
        try:
            v = float(raw_sens)
            if v > 0:
                sensitivity = v
        except ValueError:
            sensitivity = None

    enable_tushare = (_env("BERKSHIRE_ENABLE_TUSHARE") or "").lower() in {"1", "true", "yes", "on"}

    return Settings(
        tavily_keys=tavily_keys,
        llm_api_key=_env("BERKSHIRE_LLM_API_KEY", ("OPENAI_API_KEY",)),
        llm_base_url=(_env("BERKSHIRE_LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/"),
        llm_model=_env("BERKSHIRE_LLM_MODEL") or "gpt-4o-mini",
        sensitivity=sensitivity,
        decision_log=_env("BERKSHIRE_DECISION_LOG"),
        enable_tushare=enable_tushare,
        tushare_token=_env("TUSHARE_TOKEN"),
        data_sources=_env("BERKSHIRE_DATA_SOURCES"),
        telegram_token=_env("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_env("TELEGRAM_CHAT_ID"),
        feishu_webhook=_env("FEISHU_WEBHOOK"),
    )


# ---------------------------------------------------------------------------
# 启动自检（doctor）
# ---------------------------------------------------------------------------
def doctor(settings: Optional[Settings] = None) -> Dict[str, Dict[str, object]]:
    """体检各功能模块的就绪度。返回 {feature: {status, detail}}。

    status ∈ {"ready", "degraded", "unconfigured"}：
      - ready：可用
      - degraded：部分可用 / 走默认与兜底（如 notify 仅本地落地、引擎用默认灵敏度）
      - unconfigured：未配置（功能不可用，但不影响核心离线能力）
    """
    s = settings or get_settings()
    report: Dict[str, Dict[str, object]] = {}

    report["tavily"] = (
        {"status": "ready", "detail": f"{len(s.tavily_keys)} key(s)"}
        if s.has_tavily
        else {"status": "unconfigured", "detail": "无 TAVILY_API_KEY(S)，实时检索不可用"}
    )

    report["llm"] = (
        {"status": "ready", "detail": f"model={s.llm_model} base={s.llm_base_url}"}
        if s.has_llm
        else {"status": "unconfigured", "detail": "无 LLM key，Option B prompt 改写降级为仅记录"}
    )

    if s.enable_tushare and not s.tushare_token:
        report["ashare"] = {"status": "degraded", "detail": "启用 tushare 但缺 TUSHARE_TOKEN，将降级到其他源"}
    elif s.enable_tushare:
        report["ashare"] = {"status": "ready", "detail": "tushare 已启用 + token 就绪（降级链兜底）"}
    else:
        report["ashare"] = {"status": "degraded", "detail": "tushare 未启用，走 native/其他源降级链"}

    if s.telegram_token or s.feishu_webhook:
        chans = []
        if s.telegram_token:
            chans.append("telegram")
        if s.feishu_webhook:
            chans.append("feishu")
        report["notify"] = {"status": "ready", "detail": f"channels={','.join(chans)} (+本地兜底)"}
    else:
        report["notify"] = {"status": "degraded", "detail": "无远端通道，报告仅本地落地 reports/notifications/"}

    engine_detail = f"sensitivity={'默认0.5' if s.sensitivity is None else s.sensitivity}"
    report["engine"] = {"status": "ready", "detail": engine_detail}

    return report


def render_doctor(report: Optional[Dict[str, Dict[str, object]]] = None) -> str:
    """把 doctor 报告渲染成给人看的文本（不含任何密钥明文）。"""
    rep = report or doctor()
    icon = {"ready": "✅", "degraded": "🟡", "unconfigured": "⬜"}
    lines = ["Berkshire AI 配置体检", "=" * 40]
    for feature, info in rep.items():
        status = str(info.get("status", "?"))
        lines.append(f"{icon.get(status, '?')} {feature:<8} {status:<13} {info.get('detail', '')}")
    return "\n".join(lines)


def _cli() -> None:
    load_dotenv()
    print(render_doctor())


if __name__ == "__main__":
    _cli()

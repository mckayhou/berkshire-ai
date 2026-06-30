#!/usr/bin/env python3
"""离线单元测试：中心配置与启动自检（src/config.py）。

覆盖：
- load_dotenv：解析 KEY=VALUE / export / 注释 / 引号；不覆盖已有环境；文件缺失返回 0
- get_settings：tavily 多 key、LLM 别名兜底、sensitivity 校验、enable_tushare 布尔
- doctor：各功能 ready/degraded/unconfigured 判定
- render_doctor：不泄露密钥明文
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config as cfg  # noqa: E402

# 所有受测环境变量，逐测清空以隔离
_VARS = [
    "TAVILY_API_KEYS", "TAVILY_API_KEY",
    "BERKSHIRE_LLM_API_KEY", "OPENAI_API_KEY",
    "BERKSHIRE_LLM_BASE_URL", "BERKSHIRE_LLM_MODEL",
    "BERKSHIRE_SENSITIVITY", "BERKSHIRE_DECISION_LOG",
    "BERKSHIRE_DATA_SOURCES", "BERKSHIRE_ENABLE_TUSHARE", "TUSHARE_TOKEN",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "FEISHU_WEBHOOK", "FEISHU_SECRET",
]


def _clear(monkeypatch):
    for v in _VARS:
        monkeypatch.delenv(v, raising=False)


# --------------------------- load_dotenv ---------------------------
def test_load_dotenv_parses_and_no_overwrite(tmp_path, monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("BERKSHIRE_LLM_MODEL", "preset-model")  # 已存在，不应被覆盖
    env = tmp_path / ".env"
    env.write_text(
        "\n".join([
            "# comment",
            "",
            "TAVILY_API_KEYS=a,b",
            'export BERKSHIRE_LLM_API_KEY="sk-xyz"',
            "BERKSHIRE_LLM_MODEL=should-not-win",
            "MALFORMED_LINE_NO_EQUALS",
        ]),
        encoding="utf-8",
    )
    n = cfg.load_dotenv(str(env))
    assert n == 2  # TAVILY_API_KEYS + BERKSHIRE_LLM_API_KEY（model 已存在被跳过）
    assert os.environ["TAVILY_API_KEYS"] == "a,b"
    assert os.environ["BERKSHIRE_LLM_API_KEY"] == "sk-xyz"
    assert os.environ["BERKSHIRE_LLM_MODEL"] == "preset-model"  # 未被覆盖


def test_load_dotenv_override(tmp_path, monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("BERKSHIRE_LLM_MODEL", "preset")
    env = tmp_path / ".env"
    env.write_text("BERKSHIRE_LLM_MODEL=forced", encoding="utf-8")
    cfg.load_dotenv(str(env), override=True)
    assert os.environ["BERKSHIRE_LLM_MODEL"] == "forced"


def test_load_dotenv_missing_file_returns_zero(tmp_path):
    assert cfg.load_dotenv(str(tmp_path / "nope.env")) == 0


# --------------------------- get_settings ---------------------------
def test_settings_defaults_when_empty(monkeypatch):
    _clear(monkeypatch)
    s = cfg.get_settings()
    assert s.tavily_keys == []
    assert s.has_tavily is False
    assert s.has_llm is False
    assert s.llm_base_url == "https://api.openai.com/v1"
    assert s.llm_model == "gpt-4o-mini"
    assert s.sensitivity is None
    assert s.enable_tushare is False


def test_settings_tavily_multi_key_and_llm_alias(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("TAVILY_API_KEYS", " k1 , k2 ,, k3 ")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-alias")  # 兜底别名
    monkeypatch.setenv("BERKSHIRE_LLM_BASE_URL", "https://gw/v1/")
    s = cfg.get_settings()
    assert s.tavily_keys == ["k1", "k2", "k3"]
    assert s.has_llm is True
    assert s.llm_api_key == "sk-alias"
    assert s.llm_base_url == "https://gw/v1"  # 去尾斜杠


def test_settings_sensitivity_validation(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("BERKSHIRE_SENSITIVITY", "-3")  # 非正 → None
    assert cfg.get_settings().sensitivity is None
    monkeypatch.setenv("BERKSHIRE_SENSITIVITY", "abc")  # 非法 → None
    assert cfg.get_settings().sensitivity is None
    monkeypatch.setenv("BERKSHIRE_SENSITIVITY", "0.7")
    assert cfg.get_settings().sensitivity == 0.7


def test_settings_enable_tushare_truthy(monkeypatch):
    _clear(monkeypatch)
    for truthy in ["1", "true", "YES", "on"]:
        monkeypatch.setenv("BERKSHIRE_ENABLE_TUSHARE", truthy)
        assert cfg.get_settings().enable_tushare is True
    monkeypatch.setenv("BERKSHIRE_ENABLE_TUSHARE", "0")
    assert cfg.get_settings().enable_tushare is False


# --------------------------- doctor ---------------------------
def test_doctor_unconfigured(monkeypatch):
    _clear(monkeypatch)
    rep = cfg.doctor()
    assert rep["tavily"]["status"] == "unconfigured"
    assert rep["llm"]["status"] == "unconfigured"
    assert rep["notify"]["status"] == "degraded"
    assert rep["engine"]["status"] == "ready"


def test_doctor_ready_and_degraded(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    monkeypatch.setenv("BERKSHIRE_LLM_API_KEY", "sk")
    monkeypatch.setenv("FEISHU_WEBHOOK", "https://hook")
    monkeypatch.setenv("BERKSHIRE_ENABLE_TUSHARE", "1")  # 无 token → degraded
    rep = cfg.doctor()
    assert rep["tavily"]["status"] == "ready"
    assert rep["llm"]["status"] == "ready"
    assert rep["notify"]["status"] == "ready"
    assert rep["ashare"]["status"] == "degraded"


def test_render_doctor_no_secret_leak(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("BERKSHIRE_LLM_API_KEY", "sk-super-secret-123")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-secret-xyz")
    text = cfg.render_doctor()
    assert "sk-super-secret-123" not in text
    assert "tvly-secret-xyz" not in text

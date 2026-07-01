#!/usr/bin/env python3
"""行动卡 golden 片段回归。"""
from pathlib import Path

GOLDEN_HEADER = "## 行动卡（Action Card）"
REQUIRED_FIELDS = ("标的", "综合立场", "操作建议", "置信度")


def test_action_card_template_structure():
    doc = Path(__file__).resolve().parents[1] / "docs" / "action-card.md"
    text = doc.read_text(encoding="utf-8")
    assert GOLDEN_HEADER in text
    for field in REQUIRED_FIELDS:
        assert field in text


def test_action_card_table_columns():
    doc = Path(__file__).resolve().parents[1] / "docs" / "action-card.md"
    lines = doc.read_text(encoding="utf-8").splitlines()
    table_lines = [ln for ln in lines if ln.strip().startswith("| **")]
    assert len(table_lines) >= 5

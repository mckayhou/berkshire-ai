#!/usr/bin/env python3
"""report_html 测试。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from report_html import parse_markdown, render_html  # noqa: E402


def test_render_basic():
    md = "# Title\n\n## Section\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
    html_doc = render_html(md, title="T")
    assert "<html" in html_doc
    assert "Title" in html_doc
    assert "Section" in html_doc
    assert "<table>" in html_doc
    assert "dark" not in html_doc.lower() or "#0d1117" in html_doc


def test_nav_ids():
    body, nav = parse_markdown("## Alpha\n\n### Beta\n")
    assert len(nav) == 2
    assert "alpha" in body

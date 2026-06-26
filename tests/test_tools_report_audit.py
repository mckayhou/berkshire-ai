#!/usr/bin/env python3
"""离线单元测试：tools/report_audit.py

覆盖数据点提取、抽样、偏差判定与准出/打回判决（无网络）。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import report_audit as ra  # noqa: E402


# ---------------------------------------------------------------------------
# _clean_num
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("1,234.5", 1234.5),
    ("7，518", 7518.0),   # 中文逗号
    ("100", 100.0),
    ("abc", None),
    ("", None),
])
def test_clean_num(raw, expected):
    assert ra._clean_num(raw) == expected


# ---------------------------------------------------------------------------
# _is_valid_label
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("label,valid", [
    ("营业收入", True),
    ("Revenue", True),
    ("2024", False),     # 纯年份
    ("来源", False),      # 噪声标签
    ("x", False),        # 太短
    ("**粗体**", False),  # markdown 标记
])
def test_is_valid_label(label, valid):
    assert ra._is_valid_label(label) is valid


# ---------------------------------------------------------------------------
# _pct_diff
# ---------------------------------------------------------------------------
def test_pct_diff():
    assert ra._pct_diff(100, 101) == pytest.approx(0.01)
    assert ra._pct_diff(100, 100) == 0.0
    assert ra._pct_diff(0, 0) == 0.0
    assert ra._pct_diff(0, 5) == float("inf")


# ---------------------------------------------------------------------------
# extract_data_points
# ---------------------------------------------------------------------------
def test_extract_data_points_from_table():
    md = """
# 测试报告

| 指标 | 数值 |
|------|------|
| 营业收入 | 7518 亿 |
| 净利润 | 1882 亿 |
| 市盈率 | 18 x |
"""
    points = ra.extract_data_points(md)
    labels = {p["label"] for p in points}
    # 至少应提取到营业收入相关数据点
    assert any("营业收入" in lbl for lbl in labels)
    assert all("reported_value" in p and p["reported_value"] > 0 for p in points)


def test_extract_data_points_empty():
    assert ra.extract_data_points("# 无数据\n普通文字。") == []


# ---------------------------------------------------------------------------
# sample_points
# ---------------------------------------------------------------------------
def test_sample_points_min_three():
    points = [
        {"id": i, "label": f"x{i}", "reported_value": i, "unit": "", "line_number": i}
        for i in range(1, 11)
    ]
    sampled = ra.sample_points(points, ratio=0.15, seed=42)
    assert len(sampled) == 3  # max(3, ceil(10*0.15)=2) = 3
    # 按行号排序
    assert sampled == sorted(sampled, key=lambda p: p["line_number"])


def test_sample_points_deterministic_with_seed():
    points = [
        {"id": i, "label": f"x{i}", "reported_value": i, "unit": "", "line_number": i}
        for i in range(1, 21)
    ]
    a = ra.sample_points(points, ratio=0.5, seed=7)
    b = ra.sample_points(points, ratio=0.5, seed=7)
    assert [p["id"] for p in a] == [p["id"] for p in b]


def test_sample_points_empty_no_crash():
    assert ra.sample_points([], ratio=0.15) == []


# ---------------------------------------------------------------------------
# render_verdict
# ---------------------------------------------------------------------------
def test_render_verdict_pass():
    results = [
        {"id": 1, "label": "营收", "reported_value": 100, "unit": "亿",
         "fetched_value": 100, "fetched_source": "macrotrends"},
        {"id": 2, "label": "净利", "reported_value": 50, "unit": "亿",
         "fetched_value": 50.2, "fetched_source": "stockanalysis"},  # 偏差 0.4% < 1%
    ]
    v = ra.render_verdict(results)
    assert v["verdict"] == "PASS"
    assert v["fail_count"] == 0
    assert v["total"] == 2


def test_render_verdict_fail():
    results = [
        {"id": 1, "label": "营收", "reported_value": 100, "unit": "亿",
         "fetched_value": 130, "fetched_source": "macrotrends"},  # 偏差 30%
    ]
    v = ra.render_verdict(results)
    assert v["verdict"] == "FAIL"
    assert v["fail_count"] == 1


def test_render_verdict_single_source_mismatch_fails():
    # 加固点：单一来源偏差 30% 必须判 FAIL（此前被软化为 PASS+警告）
    results = [
        {"id": 1, "label": "营收", "reported_value": 100, "unit": "亿",
         "fetched_value": 130, "fetched_source": "macrotrends"},
    ]
    v = ra.render_verdict(results)
    assert v["verdict"] == "FAIL"
    assert v["fail_count"] == 1


def test_render_verdict_dual_source_one_off_warns():
    # 双来源：一过一错 → 警告（口径差异），不计入失败
    results = [
        {"id": 1, "label": "营收", "reported_value": 100, "unit": "亿",
         "fetched_value": 100, "fetched_source": "macrotrends",
         "fetched_value2": 130, "fetched_source2": "stockanalysis"},
    ]
    v = ra.render_verdict(results)
    assert v["verdict"] == "PASS"
    assert v["fail_count"] == 0
    assert v["warn_count"] == 1


def test_render_verdict_dual_source_both_off_fails():
    results = [
        {"id": 1, "label": "营收", "reported_value": 100, "unit": "亿",
         "fetched_value": 130, "fetched_source": "macrotrends",
         "fetched_value2": 140, "fetched_source2": "stockanalysis"},
    ]
    v = ra.render_verdict(results)
    assert v["verdict"] == "FAIL"
    assert v["fail_count"] == 1


def test_render_verdict_skips_missing_fetched():
    results = [
        {"id": 1, "label": "营收", "reported_value": 100, "unit": "亿"},  # 无 fetched_value
    ]
    v = ra.render_verdict(results)
    assert v["total"] == 0  # 未提供核验值不计入
    assert v["verdict"] == "PASS"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

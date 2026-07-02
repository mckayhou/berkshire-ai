#!/usr/bin/env python3
"""SkillForge LLM-judge unit tests (StaticLLMClient, no network)."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prompt_optimizer import StaticLLMClient  # noqa: E402
from skill_forge import (  # noqa: E402
    Consistency,
    JudgeMode,
    analyze_bad_case,
    diagnose,
    judge_consistency,
    judge_failure_record,
    prepare_bad_cases,
    evolve_from_fixture,
    aggregate_failures,
    analyze_batch,
)
from skill_forge.llm_judge import (  # noqa: E402
    ConsistencyBatchReport,
    judge_consistency_batch,
    judge_diagnostic_plan,
)

FIXTURE = Path(__file__).parent / "fixtures" / "skill_forge" / "bad_cases.jsonl"
TASKS = Path(__file__).parent / "fixtures" / "skill_forge" / "tasks_unlabeled.jsonl"
SKILL_SRC = Path(__file__).resolve().parents[1] / "skills" / "investment-research.md"


def _cr_response(_s: str, user: str) -> str:
    if "u002" in user:
        return json.dumps(
            {
                "consistency": "consistent",
                "rationale": "行动与参考对齐",
                "core_action_aligned": True,
            },
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "consistency": "inconsistent",
            "rationale": "缺少双源验证与准出",
            "core_action_aligned": False,
        },
        ensure_ascii=False,
    )


def _fa_response(_s: str, _u: str) -> str:
    return json.dumps(
        {
            "dimensions": [
                {
                    "category": "knowledge",
                    "severity": "high",
                    "issue_type": "missing",
                    "hint": "缺信息丰富度",
                },
                {
                    "category": "tool",
                    "severity": "high",
                    "issue_type": "missing_invocation",
                    "hint": "未调用 financial_rigor",
                },
                {
                    "category": "clarification",
                    "severity": "low",
                    "issue_type": "ok",
                    "hint": "ok",
                },
                {
                    "category": "style",
                    "severity": "medium",
                    "issue_type": "format_gap",
                    "hint": "缺行动卡",
                },
            ],
            "primary_category": "knowledge",
            "overall_severity": "high",
        },
        ensure_ascii=False,
    )


def _diag_response(_s: str, _u: str) -> str:
    return json.dumps(
        {
            "root_causes": ["tool:missing_invocation ×3"],
            "optimization_plan": [
                {
                    "section_heading": "数据交叉验证",
                    "action": "append",
                    "content": "- **LLM 补强**：必须调用 financial_rigor.py",
                    "category": "tool",
                    "issue_type": "missing_invocation",
                    "expected_impact": "减少工具遗漏",
                }
            ],
        },
        ensure_ascii=False,
    )


@pytest.fixture
def mock_llm():
    return StaticLLMClient(
        fn=lambda s, u: (
            _cr_response(s, u)
            if "REFERENCE" in u
            else _fa_response(s, u)
            if "consistency" in u or "tool_trace" in u
            else _diag_response(s, u)
        )
    )


def test_judge_consistency_llm(mock_llm):
    j = judge_consistency("买入", "观望，需 audit", mock_llm, task_id="t1")
    assert j.consistency == Consistency.INCONSISTENT
    assert j.rationale


def test_prepare_bad_cases_unlabeled(mock_llm):
    from skill_forge.bad_case_loader import load_tasks_jsonl

    raw = load_tasks_jsonl(TASKS)
    cases = prepare_bad_cases(raw, llm=mock_llm, mode=JudgeMode.LLM)
    assert len(cases) == 2
    by_id = {c.task_id: c for c in cases}
    assert by_id["u001"].consistency == Consistency.INCONSISTENT
    assert by_id["u002"].consistency == Consistency.CONSISTENT


def test_analyze_bad_case_llm(mock_llm):
    from skill_forge.bad_case_loader import bad_case_from_dict
    from skill_forge.bad_case_loader import load_bad_cases_jsonl

    case = load_bad_cases_jsonl(FIXTURE)[0]
    rec = analyze_bad_case(case, llm=mock_llm, mode=JudgeMode.LLM)
    assert rec.primary_category.value == "knowledge"
    tool_dim = next(d for d in rec.dimensions if d.category.value == "tool")
    assert tool_dim.severity.value == "high"


def test_diagnose_llm(mock_llm):
    records = analyze_batch(
        __import__("skill_forge").load_bad_cases_jsonl(FIXTURE),
        llm=mock_llm,
        mode=JudgeMode.LLM,
    )
    agg = aggregate_failures(records)
    skill_md = SKILL_SRC.read_text(encoding="utf-8")
    diag = diagnose(
        "investment-research",
        0,
        agg,
        skill_markdown=skill_md,
        llm=mock_llm,
        mode=JudgeMode.LLM,
    )
    assert "LLM 补强" in diag.optimization_plan[0].content


def test_judge_diagnostic_plan_direct(mock_llm):
    roots, plan = judge_diagnostic_plan(
        "investment-research",
        0,
        [{"category": "tool", "issue_type": "missing_invocation", "count": 2}],
        SKILL_SRC.read_text(encoding="utf-8"),
        mock_llm,
    )
    assert roots
    assert plan[0].section_heading == "数据交叉验证"


def test_evolve_llm_mode_dry_run(mock_llm, tmp_path):
    skills = tmp_path / "skills"
    evo = tmp_path / "skills" / ".evolution"
    skills.mkdir()
    shutil.copy(SKILL_SRC, skills / "investment-research.md")
    report = evolve_from_fixture(
        "investment-research",
        FIXTURE,
        rounds=1,
        skills_root=skills,
        evolution_root=evo,
        write_live=False,
        llm=mock_llm,
        mode=JudgeMode.LLM,
    )
    assert report.rounds[0].accepted_changes >= 1


def test_judge_consistency_batch_cr(mock_llm):
    from skill_forge.bad_case_loader import load_tasks_jsonl

    raw = load_tasks_jsonl(TASKS)
    report = judge_consistency_batch(raw, mock_llm)
    assert isinstance(report, ConsistencyBatchReport)
    assert report.strict_cr == 0.5
    assert report.lenient_cr == 0.5
    assert len(report.judgments) == 2


def test_judge_partial_consistency():
    llm = StaticLLMClient(
        fn=lambda _s, _u: json.dumps(
            {
                "consistency": "partial",
                "rationale": "部分一致",
                "core_action_aligned": True,
            },
            ensure_ascii=False,
        )
    )
    j = judge_consistency("部分报告", "完整参考", llm)
    assert j.consistency == Consistency.PARTIAL
    assert not j.strict_match


def test_diagnose_llm_fallback_to_rules():
    from skill_forge import diagnose_rules, load_bad_cases_jsonl

    bad_llm = StaticLLMClient(responses={"*": "not-json"})
    records = analyze_batch(load_bad_cases_jsonl(FIXTURE), mode=JudgeMode.RULE)
    agg = aggregate_failures(records)
    rule_diag = diagnose_rules("investment-research", 0, agg)
    llm_diag = diagnose(
        "investment-research",
        0,
        agg,
        skill_markdown=SKILL_SRC.read_text(encoding="utf-8"),
        llm=bad_llm,
        mode=JudgeMode.LLM,
    )
    assert llm_diag.optimization_plan
    assert len(llm_diag.optimization_plan) == len(rule_diag.optimization_plan)


def test_effective_judge_mode_auto_without_llm():
    from skill_forge.judge_mode import effective_judge_mode

    assert effective_judge_mode(JudgeMode.AUTO, None) == JudgeMode.RULE
    assert effective_judge_mode(JudgeMode.AUTO, StaticLLMClient()) == JudgeMode.LLM


def test_llm_failure_fallback_to_rules():
    bad_llm = StaticLLMClient(responses={"*": "not json"})
    from skill_forge.bad_case_loader import load_bad_cases_jsonl

    case = load_bad_cases_jsonl(FIXTURE)[0]
    rec = analyze_bad_case(case, llm=bad_llm, mode=JudgeMode.LLM)
    assert len(rec.dimensions) == 4

#!/usr/bin/env python3
"""SkillForge pipeline unit tests (offline, no LLM)."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from skill_forge import (  # noqa: E402
    BadCase,
    Consistency,
    FailureCategory,
    SkillVFS,
    analyze_bad_case,
    analyze_batch,
    aggregate_failures,
    create_skill_v0,
    diagnose,
    evolve_from_fixture,
    load_bad_cases_jsonl,
    mine_tool_schemas_from_skills,
    parse_sections,
)


FIXTURE = Path(__file__).parent / "fixtures" / "skill_forge" / "bad_cases.jsonl"
SKILL_SRC = Path(__file__).resolve().parents[1] / "skills" / "investment-research.md"


@pytest.fixture
def sandbox_skill(tmp_path):
    """Copy investment-research skill into isolated skills root."""
    skills = tmp_path / "skills"
    evo = tmp_path / "skills" / ".evolution"
    skills.mkdir()
    shutil.copy(SKILL_SRC, skills / "investment-research.md")
    return skills, evo


def test_load_bad_cases_fixture():
    cases = load_bad_cases_jsonl(FIXTURE)
    assert len(cases) == 3
    assert all(c.is_failure for c in cases)


def test_failure_analyzer_four_dimensions():
    cases = load_bad_cases_jsonl(FIXTURE)
    rec = analyze_bad_case(cases[0])
    assert len(rec.dimensions) == 4
    cats = {d.category for d in rec.dimensions}
    assert FailureCategory.KNOWLEDGE in cats
    assert FailureCategory.TOOL in cats
    assert rec.primary_category in FailureCategory


def test_tool_missing_invocation_detected():
    case = BadCase(
        task_id="x",
        skill_name="investment-research",
        agent_output="分析完成",
        reference_output="需 financial_rigor",
        consistency=Consistency.INCONSISTENT,
        tool_trace=[],
        metadata={"depth": "standard"},
    )
    rec = analyze_bad_case(case)
    tool_dim = next(d for d in rec.dimensions if d.category == FailureCategory.TOOL)
    assert tool_dim.issue_type == "missing_invocation"
    assert tool_dim.severity.value in ("medium", "high")


def test_aggregate_and_diagnose():
    records = analyze_batch(load_bad_cases_jsonl(FIXTURE))
    agg = aggregate_failures(records, top_k=2)
    assert agg
    diag = diagnose("investment-research", 0, agg)
    assert diag.root_causes
    assert diag.optimization_plan
    assert all(item.section_heading for item in diag.optimization_plan)


def test_vfs_section_patch_idempotent(sandbox_skill):
    skills, evo = sandbox_skill
    vfs = SkillVFS(skills_root=skills, evolution_root=evo)
    content = vfs.read_skill("investment-research")
    patched, changed = vfs.apply_section_patch(
        content,
        "输出要求",
        "- test patch bullet",
    )
    assert changed
    _, changed2 = vfs.apply_section_patch(
        patched,
        "输出要求",
        "- test patch bullet",
    )
    assert not changed2


def test_evolve_from_fixture_dry_run(sandbox_skill):
    skills, evo = sandbox_skill
    report = evolve_from_fixture(
        "investment-research",
        FIXTURE,
        rounds=1,
        skills_root=skills,
        evolution_root=evo,
        write_live=False,
    )
    assert report.rounds
    assert report.rounds[0].accepted_changes >= 1
    assert vfs_current_version(skills, "investment-research") >= 1
    # live file unchanged when write_live=False
    live = (skills / "investment-research.md").read_text(encoding="utf-8")
    assert "SkillForge 补强" not in live


def test_evolve_writes_version_and_optional_live(sandbox_skill):
    skills, evo = sandbox_skill
    report = evolve_from_fixture(
        "investment-research",
        FIXTURE,
        rounds=1,
        skills_root=skills,
        evolution_root=evo,
        write_live=True,
    )
    live = (skills / "investment-research.md").read_text(encoding="utf-8")
    assert "SkillForge 补强" in live
    vpath = evo / "investment-research" / "v1" / "SKILL.md"
    assert vpath.exists()
    assert report.final_version >= 1


def test_skill_creator_mines_tools():
    skills = Path(__file__).resolve().parents[1] / "skills"
    tools = mine_tool_schemas_from_skills(skills)
    assert "financial_rigor.py" in tools


def test_create_skill_v0_dry():
    content = create_skill_v0(
        "test-skill",
        "测试技能",
        reference_skill="investment-research",
    )
    assert "skillforge" in content.lower() or "SkillForge" in content
    assert "financial-data.md" in content


def test_parse_sections_finds_depth():
    content = SKILL_SRC.read_text(encoding="utf-8")
    sections = parse_sections(content)
    headings = [s.heading for s in sections]
    assert any("研究深度" in h for h in headings)


def vfs_current_version(skills_root: Path, name: str) -> int:
    manifest = skills_root / ".evolution" / name / "manifest.json"
    if not manifest.exists():
        return 0
    return json.loads(manifest.read_text(encoding="utf-8"))["current_version"]

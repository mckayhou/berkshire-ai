#!/usr/bin/env python3
"""skill_evolve.py CLI 与子进程冒烟测试（无网络）。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BERKSHIRE_DIR = Path(__file__).resolve().parents[1]
CLI = BERKSHIRE_DIR / "tools" / "skill_evolve.py"
EVO = BERKSHIRE_DIR / "src" / "evolution_loop_v10.py"
FIXTURE = BERKSHIRE_DIR / "tests" / "fixtures" / "skill_forge" / "bad_cases.jsonl"
TASKS = BERKSHIRE_DIR / "tests" / "fixtures" / "skill_forge" / "tasks_unlabeled.jsonl"
SKILL_SRC = BERKSHIRE_DIR / "skills" / "investment-research.md"


def _run_skill(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(cwd or BERKSHIRE_DIR),
    )


def _run_evo_skill(*args):
    return subprocess.run(
        [sys.executable, str(EVO), "skill-evolve", *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(BERKSHIRE_DIR),
    )


def test_cli_list():
    r = _run_skill("list")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["count"] >= 1
    assert "investment-research" in data["skills"]


def test_cli_judge_rule_mode():
    r = _run_skill("judge", str(FIXTURE), "--judge-mode", "rule")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["n"] == 3
    assert "strict_cr" in data
    assert "lenient_cr" in data


def test_cli_analyze_rule_mode():
    r = _run_skill("analyze", str(FIXTURE), "--judge-mode", "rule")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["judge_mode"] == "rule"
    assert len(data["records"]) == 3


def test_cli_evolve_dry_run(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    shutil.copy(SKILL_SRC, skills / "investment-research.md")
    r = _run_skill(
        "evolve",
        "investment-research",
        "--fixture",
        str(FIXTURE),
        "--rounds",
        "1",
        "--dry-run",
        "--judge-mode",
        "rule",
        "--skills-root",
        str(skills),
        "--evolution-root",
        str(skills / ".evolution"),
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["rounds"]
    assert data["total_changes"] >= 1
    live = (skills / "investment-research.md").read_text(encoding="utf-8")
    assert "SkillForge 补强" not in live


def test_cli_status_after_evolve(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    shutil.copy(SKILL_SRC, skills / "investment-research.md")
    _run_skill(
        "evolve",
        "investment-research",
        "--fixture",
        str(FIXTURE),
        "--dry-run",
        "--judge-mode",
        "rule",
        "--skills-root",
        str(skills),
        "--evolution-root",
        str(skills / ".evolution"),
    )
    r = _run_skill(
        "status",
        "investment-research",
    )
    # status uses default skills root — only check command runs
    assert r.returncode == 0


def test_cli_create_dry_run():
    r = _run_skill("create", "cli-test-skill", "CLI 测试技能", "--dry-run")
    assert r.returncode == 0
    assert "SkillForge" in r.stdout or "skillforge" in r.stdout.lower()


def test_evo_loop_skill_evolve_list():
    r = _run_evo_skill("list")
    assert r.returncode == 0
    assert "investment-research" in r.stdout


def test_evo_loop_skill_evolve_judge_rule():
    r = _run_evo_skill("judge", str(TASKS), "--judge-mode", "rule")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["n"] == 2


def test_cli_judge_llm_mode_without_key():
    env = os.environ.copy()
    env.pop("BERKSHIRE_LLM_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    r = subprocess.run(
        [sys.executable, str(CLI), "judge", str(FIXTURE), "--judge-mode", "llm"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(BERKSHIRE_DIR),
        env=env,
    )
    assert r.returncode != 0

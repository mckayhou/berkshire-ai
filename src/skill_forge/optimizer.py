"""Skill Optimizer — minimal, evidence-based patches via VFS."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from .types import DiagnosticReport, OptimizationItem
from .vfs import SkillVFS


def apply_optimization_plan(
    vfs: SkillVFS,
    skill_name: str,
    content: str,
    plan: List[OptimizationItem],
) -> Tuple[str, int]:
    """Apply plan under Minimal Modification / Do No Harm / Evidence-Based principles."""
    current = content
    accepted = 0
    for item in plan:
        patched, changed = vfs.apply_section_patch(
            current,
            item.section_heading,
            item.content,
            action=item.action,
        )
        if changed:
            current = patched
            accepted += 1
    return current, accepted


def optimize_skill(
    vfs: SkillVFS,
    skill_name: str,
    diagnostic: DiagnosticReport,
    *,
    write_live: bool = True,
    diagnostic_json: Path | None = None,
) -> Tuple[str, int, int]:
    """
    Returns (new_content, accepted_changes, new_version).
    Commits version snapshot before optionally updating live skill file.
    """
    content = vfs.read_skill(skill_name)
    new_content, accepted = apply_optimization_plan(
        vfs, skill_name, content, diagnostic.optimization_plan
    )
    if accepted == 0:
        return content, 0, vfs.current_version(skill_name)

    version = vfs.commit_version(
        skill_name,
        new_content,
        diagnostic_path=diagnostic_json,
        note=f"skillforge round → {accepted} patch(es)",
    )
    if write_live:
        vfs.write_live_skill(skill_name, new_content)
    return new_content, accepted, version

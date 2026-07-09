"""End-to-end SkillForge evolution pipeline."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from .aggregator import aggregate_failures
from .bad_case_loader import load_bad_cases_jsonl, load_tasks_jsonl
from .diagnostician import diagnose
from .failure_analyzer import analyze_batch
from .judge_mode import JudgeMode, prepare_bad_cases
from .optimizer import optimize_skill
from .types import BadCase, SkillEvolutionReport, SkillEvolutionRound
from .vfs import SkillVFS

if TYPE_CHECKING:
    from prompt_optimizer import LLMClient


def run_evolution_round(
    vfs: SkillVFS,
    skill_name: str,
    bad_cases: List[BadCase],
    *,
    round_num: int = 1,
    top_k: int = 3,
    write_live: bool = True,
    llm: Optional["LLMClient"] = None,
    mode: JudgeMode = JudgeMode.AUTO,
    regression_cases: Optional[List[BadCase]] = None,
) -> SkillEvolutionRound:
    """Single Failure Analysis → Aggregate → Diagnose → Optimize → Regression Gate cycle."""
    aliases = {skill_name, skill_name.removesuffix(".md"), ""}
    relevant = [c for c in bad_cases if c.skill_name in aliases and c.is_failure]
    if not relevant:
        relevant = [c for c in bad_cases if c.is_failure]

    records = analyze_batch(relevant, llm=llm, mode=mode)
    aggregated = aggregate_failures(records, top_k=top_k)
    version = vfs.current_version(skill_name)
    pre_skill_md = vfs.read_skill(skill_name)
    diagnostic = diagnose(
        skill_name,
        version,
        aggregated,
        skill_markdown=pre_skill_md,
        llm=llm,
        mode=mode,
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(diagnostic.to_dict(), tmp, ensure_ascii=False, indent=2)
        diag_path = Path(tmp.name)

    try:
        _, accepted, new_version = optimize_skill(
            vfs,
            skill_name,
            diagnostic,
            write_live=write_live,
            diagnostic_json=diag_path,
        )
    finally:
        diag_path.unlink(missing_ok=True)

    # V10.29: Trajectory replay regression gate
    if accepted > 0 and regression_cases and write_live:
        from .regression_gate import replay_trajectories

        post_skill_md = vfs.read_skill(skill_name)
        success_pool = [
            c for c in regression_cases
            if c.consistency.value in ("consistent", "partial")
        ]
        if success_pool:
            gate = replay_trajectories(
                success_pool,
                post_skill_md=post_skill_md,
                pre_skill_md=pre_skill_md,
                llm=llm,
                mode=mode,
            )
            if not gate.passed:
                # Rollback: restore pre-patch skill
                vfs.write_skill(skill_name, pre_skill_md)
                accepted = 0

    skill_path = str(vfs.skill_path(skill_name))
    return SkillEvolutionRound(
        round_num=round_num,
        bad_case_count=len(relevant),
        diagnostic=diagnostic,
        skill_path=skill_path,
        accepted_changes=accepted,
    )


def run_multi_round_evolution(
    vfs: SkillVFS,
    skill_name: str,
    bad_cases: List[BadCase],
    *,
    rounds: int = 3,
    write_live: bool = True,
    llm: Optional["LLMClient"] = None,
    mode: JudgeMode = JudgeMode.AUTO,
) -> SkillEvolutionReport:
    """Run up to N evolution rounds; stop early if no accepted changes."""
    initial_v = vfs.current_version(skill_name)
    report = SkillEvolutionReport(
        skill_name=skill_name,
        initial_version=initial_v,
        final_version=initial_v,
    )

    for r in range(1, rounds + 1):
        round_result = run_evolution_round(
            vfs,
            skill_name,
            bad_cases,
            round_num=r,
            write_live=write_live,
            llm=llm,
            mode=mode,
        )
        report.rounds.append(round_result)
        report.final_version = vfs.current_version(skill_name)
        if round_result.accepted_changes == 0:
            break

    return report


def evolve_from_fixture(
    skill_name: str,
    fixture_path: Path,
    *,
    rounds: int = 1,
    skills_root: Optional[Path] = None,
    evolution_root: Optional[Path] = None,
    write_live: bool = False,
    llm: Optional["LLMClient"] = None,
    mode: JudgeMode = JudgeMode.AUTO,
    re_judge: bool = False,
) -> SkillEvolutionReport:
    """Load JSONL tasks/bad-cases, optional LLM-judge, then evolve."""
    vfs = SkillVFS(skills_root=skills_root, evolution_root=evolution_root)
    if fixture_path.is_dir():
        raw = []
        for p in sorted(fixture_path.glob("*.jsonl")):
            raw.extend(_load_raw_lines(p))
    else:
        raw = _load_raw_lines(fixture_path)

    cases = prepare_bad_cases(raw, llm=llm, mode=mode, re_judge=re_judge)
    return run_multi_round_evolution(
        vfs,
        skill_name,
        cases,
        rounds=rounds,
        write_live=write_live,
        llm=llm,
        mode=mode,
    )


def _load_raw_lines(path: Path) -> List[dict]:
    try:
        return load_tasks_jsonl(path)
    except Exception:
        return [
            {
                "task_id": c.task_id,
                "skill_name": c.skill_name,
                "agent_output": c.agent_output,
                "reference_output": c.reference_output,
                "consistency": c.consistency.value,
                "tool_trace": c.tool_trace,
                "metadata": c.metadata,
            }
            for c in load_bad_cases_jsonl(path)
        ]

"""CLI for SkillForge skill evolution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .bad_case_loader import load_bad_cases_jsonl, load_tasks_jsonl
from .failure_analyzer import analyze_batch
from .judge_mode import JudgeMode, prepare_bad_cases
from .llm_judge import judge_consistency_batch, resolve_llm_client
from .pipeline import evolve_from_fixture
from .vfs import SkillVFS, default_skills_root


def _parse_judge_mode(raw: str) -> JudgeMode:
    return JudgeMode(raw.lower())


def _resolve_llm_from_args(args) -> Optional[object]:
    if getattr(args, "judge_mode", "auto") == "rule":
        return None
    return resolve_llm_client(require=getattr(args, "judge_mode", "auto") == "llm")


def cmd_list(_args: argparse.Namespace) -> int:
    vfs = SkillVFS()
    skills = vfs.list_skills()
    print(json.dumps({"skills": skills, "count": len(skills)}, ensure_ascii=False, indent=2))
    return 0


def cmd_judge(args: argparse.Namespace) -> int:
    path = Path(args.fixture)
    raw = load_tasks_jsonl(path) if path.exists() else []
    if not raw:
        raw = [
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
    llm = _resolve_llm_from_args(args)
    mode = _parse_judge_mode(args.judge_mode)
    if mode == JudgeMode.LLM and llm is None:
        print("judge-mode=llm 需要 BERKSHIRE_LLM_API_KEY", file=sys.stderr)
        return 1

    if mode == JudgeMode.LLM and llm is not None:
        report = judge_consistency_batch(raw, llm)
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0

    # rule: trust labels or mark unknown as inconsistent
    from .types import Consistency

    cases = prepare_bad_cases(raw, mode=JudgeMode.RULE)
    strict = sum(1 for c in cases if c.consistency == Consistency.CONSISTENT) / max(
        len(cases), 1
    )
    out = {
        "strict_cr": round(strict, 4),
        "lenient_cr": round(
            sum(
                1
                for c in cases
                if c.consistency.value in ("consistent", "partial")
            )
            / max(len(cases), 1),
            4,
        ),
        "n": len(cases),
        "judge_mode": "rule",
        "cases": [
            {"task_id": c.task_id, "consistency": c.consistency.value}
            for c in cases
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    path = Path(args.fixture)
    raw = load_tasks_jsonl(path)
    if not raw:
        cases = load_bad_cases_jsonl(path)
    else:
        llm = _resolve_llm_from_args(args)
        mode = _parse_judge_mode(args.judge_mode)
        cases = prepare_bad_cases(
            raw, llm=llm, mode=mode, re_judge=args.re_judge
        )
    records = analyze_batch(
        cases,
        llm=_resolve_llm_from_args(args),
        mode=_parse_judge_mode(args.judge_mode),
    )
    out = {
        "judge_mode": args.judge_mode,
        "analyzer_mode": args.judge_mode,
        "records": [r.to_dict() for r in records],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_evolve(args: argparse.Namespace) -> int:
    skills_root = Path(args.skills_root) if args.skills_root else default_skills_root()
    evolution_root = Path(args.evolution_root) if args.evolution_root else None
    vfs = SkillVFS(skills_root=skills_root, evolution_root=evolution_root)
    llm = _resolve_llm_from_args(args)
    mode = _parse_judge_mode(args.judge_mode)

    if vfs.current_version(args.skill) == 0 and vfs.skill_path(args.skill).exists():
        content = vfs.read_skill(args.skill)
        vfs.commit_version(args.skill, content, note="baseline before skillforge")

    report = evolve_from_fixture(
        args.skill,
        Path(args.fixture),
        rounds=args.rounds,
        skills_root=skills_root,
        evolution_root=evolution_root,
        write_live=not args.dry_run,
        llm=llm,
        mode=mode,
        re_judge=args.re_judge,
    )
    payload = report.to_dict()
    payload["judge_mode"] = args.judge_mode
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    vfs = SkillVFS()
    name = args.skill
    manifest_path = vfs._manifest_path(name)
    payload = {
        "skill": name,
        "path": str(vfs.skill_path(name)),
        "current_version": vfs.current_version(name),
        "manifest_exists": manifest_path.exists(),
    }
    if manifest_path.exists():
        payload["manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    from .skill_creator import create_skill_v0

    out = Path(args.output) if args.output else default_skills_root() / f"{args.name}.md"
    content = create_skill_v0(
        args.name,
        args.description,
        output_path=out if not args.dry_run else None,
    )
    if args.dry_run:
        print(content)
    else:
        print(json.dumps({"written": str(out), "bytes": len(content.encode())}, ensure_ascii=False))
    return 0


def _add_judge_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--judge-mode",
        choices=["auto", "llm", "rule"],
        default="auto",
        help="LLM-judge / 分析 / 诊断模式（auto=有 Key 用 LLM）",
    )
    parser.add_argument(
        "--re-judge",
        action="store_true",
        help="忽略已有 consistency 标签，重新 LLM 评判",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SkillForge — domain skill evolution for berkshire-ai",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List available skills")

    p_judge = sub.add_parser("judge", help="LLM Consistency Rate (Strict/Lenient CR)")
    p_judge.add_argument("fixture", help="tasks.jsonl or bad_cases.jsonl")
    _add_judge_flags(p_judge)

    p_analyze = sub.add_parser("analyze", help="Failure analyzer on fixture JSONL")
    p_analyze.add_argument("fixture", help="Path to bad_cases.jsonl")
    _add_judge_flags(p_analyze)

    p_evolve = sub.add_parser("evolve", help="Run evolution round(s) on a skill")
    p_evolve.add_argument("skill", help="Skill name without .md, e.g. investment-research")
    p_evolve.add_argument(
        "--fixture",
        default=None,
        help="Bad cases JSONL (default: tests/fixtures/skill_forge/bad_cases.jsonl)",
    )
    p_evolve.add_argument("--rounds", type=int, default=1, help="Max evolution rounds")
    p_evolve.add_argument("--dry-run", action="store_true", help="Version only, do not overwrite live skill")
    p_evolve.add_argument("--skills-root", default=None)
    p_evolve.add_argument("--evolution-root", default=None)
    _add_judge_flags(p_evolve)

    p_status = sub.add_parser("status", help="Show skill version manifest")
    p_status.add_argument("skill")

    p_create = sub.add_parser("create", help="Domain-Contextualized Skill Creator (v0)")
    p_create.add_argument("name", help="新技能文件名（不含 .md）")
    p_create.add_argument("description", help="技能描述")
    p_create.add_argument("--output", default=None)
    p_create.add_argument("--dry-run", action="store_true", help="仅打印不写文件")

    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "evolve" and args.fixture is None:
        default_fixture = (
            Path(__file__).resolve().parents[2]
            / "tests"
            / "fixtures"
            / "skill_forge"
            / "bad_cases.jsonl"
        )
        args.fixture = str(default_fixture)

    if args.command == "list":
        return cmd_list(args)
    if args.command == "judge":
        return cmd_judge(args)
    if args.command == "analyze":
        return cmd_analyze(args)
    if args.command == "evolve":
        return cmd_evolve(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "create":
        return cmd_create(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

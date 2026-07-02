"""Load bad cases from JSONL fixtures, audit results, or synthetic replay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .types import BadCase, Consistency


def _parse_consistency(raw: str) -> Consistency:
    try:
        return Consistency(raw.lower())
    except ValueError:
        return Consistency.INCONSISTENT


def bad_case_from_dict(data: Dict[str, Any]) -> BadCase:
    return BadCase(
        task_id=str(data["task_id"]),
        skill_name=str(data.get("skill_name", "investment-research")),
        agent_output=str(data.get("agent_output", "")),
        reference_output=str(data.get("reference_output", "")),
        consistency=_parse_consistency(str(data.get("consistency", "inconsistent"))),
        tool_trace=list(data.get("tool_trace") or []),
        metadata=dict(data.get("metadata") or {}),
    )


def load_bad_cases_jsonl(path: Path) -> List[BadCase]:
    cases: List[BadCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cases.append(bad_case_from_dict(json.loads(line)))
    return cases


def load_tasks_jsonl(path: Path) -> List[dict]:
    """Load raw task dicts (consistency optional — for LLM-judge pipeline)."""
    rows: List[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(json.loads(line))
    return rows


def load_bad_cases_dir(directory: Path) -> List[BadCase]:
    cases: List[BadCase] = []
    for p in sorted(directory.glob("*.jsonl")):
        cases.extend(load_bad_cases_jsonl(p))
    return cases


def cases_from_audit_verdict(
    *,
    skill_name: str,
    task_id: str,
    agent_output: str,
    reference_output: str,
    verdict: str,
    audit_failures: Optional[List[Dict]] = None,
    tool_trace: Optional[List[str]] = None,
    depth: str = "standard",
) -> BadCase:
    """Build a BadCase from report_audit verdict (reject → inconsistent)."""
    v = verdict.lower()
    if v in ("pass", "approved", "consistent"):
        consistency = Consistency.CONSISTENT
    elif v in ("partial", "partially_consistent"):
        consistency = Consistency.PARTIAL
    else:
        consistency = Consistency.INCONSISTENT

    return BadCase(
        task_id=task_id,
        skill_name=skill_name,
        agent_output=agent_output,
        reference_output=reference_output,
        consistency=consistency,
        tool_trace=tool_trace or [],
        metadata={
            "depth": depth,
            "audit_failures": audit_failures or [],
            "verdict": verdict,
        },
    )

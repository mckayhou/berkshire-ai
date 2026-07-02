"""Batch aggregation and representative bad-case selection."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from .types import AggregatedFailure, FailureCategory, FailureRecord, Severity


def _severity_rank(s: Severity) -> int:
    return {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2}[s]


def aggregate_failures(
    records: List[FailureRecord],
    *,
    top_k: int = 3,
) -> List[AggregatedFailure]:
    """Group by (category, issue_type); pick representative cases by severity + diversity."""
    buckets: Dict[Tuple[FailureCategory, str], List[FailureRecord]] = defaultdict(list)

    for rec in records:
        for dim in rec.dimensions:
            if dim.severity == Severity.LOW:
                continue
            buckets[(dim.category, dim.issue_type)].append(rec)

    aggregated: List[AggregatedFailure] = []
    for (category, issue_type), group in sorted(
        buckets.items(), key=lambda kv: (-len(kv[1]), kv[0][0].value)
    ):
        severity_counts: Dict[str, int] = defaultdict(int)
        for rec in group:
            severity_counts[rec.overall_severity.value] += 1

        # Sort by severity desc, then task_id for stable diversity
        ranked = sorted(
            group,
            key=lambda r: (-_severity_rank(r.overall_severity), r.task_id),
        )
        reps: List[str] = []
        seen_hints: set = set()
        for rec in ranked:
            if len(reps) >= top_k:
                break
            hint = next(
                (
                    d.hint
                    for d in rec.dimensions
                    if d.category == category and d.issue_type == issue_type
                ),
                "",
            )
            if hint in seen_hints and len(reps) >= 1:
                continue
            seen_hints.add(hint)
            reps.append(rec.task_id)

        hints = []
        for rec in ranked[:top_k]:
            for d in rec.dimensions:
                if d.category == category and d.issue_type == issue_type:
                    hints.append(d.hint)
                    break

        aggregated.append(
            AggregatedFailure(
                category=category,
                issue_type=issue_type,
                count=len(group),
                severity_counts=dict(severity_counts),
                representative_task_ids=reps,
                sample_hints=hints[:top_k],
            )
        )

    return aggregated

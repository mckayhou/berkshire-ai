"""SkillForge data types — bad cases, failure records, diagnostic artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List


class Consistency(str, Enum):
    CONSISTENT = "consistent"
    PARTIAL = "partial"
    INCONSISTENT = "inconsistent"


class FailureCategory(str, Enum):
    KNOWLEDGE = "knowledge"
    TOOL = "tool"
    CLARIFICATION = "clarification"
    STYLE = "style"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


CATEGORY_PRIORITY = (
    FailureCategory.KNOWLEDGE,
    FailureCategory.TOOL,
    FailureCategory.CLARIFICATION,
    FailureCategory.STYLE,
)


@dataclass
class BadCase:
    """Single failed agent execution vs reference."""

    task_id: str
    skill_name: str
    agent_output: str
    reference_output: str
    consistency: Consistency
    tool_trace: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_failure(self) -> bool:
        return self.consistency != Consistency.CONSISTENT


@dataclass
class DimensionResult:
    category: FailureCategory
    severity: Severity
    issue_type: str
    hint: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "issue_type": self.issue_type,
            "hint": self.hint,
        }


@dataclass
class FailureRecord:
    """Structured output of Failure Analyzer for one bad case."""

    task_id: str
    skill_name: str
    dimensions: List[DimensionResult]
    primary_category: FailureCategory
    overall_severity: Severity
    failure_categories: List[FailureCategory]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "skill_name": self.skill_name,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "primary_category": self.primary_category.value,
            "overall_severity": self.overall_severity.value,
            "failure_categories": [c.value for c in self.failure_categories],
        }


@dataclass
class AggregatedFailure:
    """Batch-aggregated failure pattern."""

    category: FailureCategory
    issue_type: str
    count: int
    severity_counts: Dict[str, int]
    representative_task_ids: List[str]
    sample_hints: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OptimizationItem:
    """One targeted skill edit."""

    section_heading: str
    action: str  # append | insert_after | replace_snippet
    content: str
    evidence_task_ids: List[str]
    category: FailureCategory
    issue_type: str
    expected_impact: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_heading": self.section_heading,
            "action": self.action,
            "content": self.content,
            "evidence_task_ids": self.evidence_task_ids,
            "category": self.category.value,
            "issue_type": self.issue_type,
            "expected_impact": self.expected_impact,
        }


@dataclass
class DiagnosticReport:
    skill_name: str
    version: int
    aggregated: List[AggregatedFailure]
    root_causes: List[str]
    optimization_plan: List[OptimizationItem]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "version": self.version,
            "aggregated": [a.to_dict() for a in self.aggregated],
            "root_causes": self.root_causes,
            "optimization_plan": [o.to_dict() for o in self.optimization_plan],
        }


@dataclass
class SkillEvolutionRound:
    round_num: int
    bad_case_count: int
    diagnostic: DiagnosticReport
    skill_path: str
    accepted_changes: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "bad_case_count": self.bad_case_count,
            "diagnostic": self.diagnostic.to_dict(),
            "skill_path": self.skill_path,
            "accepted_changes": self.accepted_changes,
        }


@dataclass
class SkillEvolutionReport:
    skill_name: str
    initial_version: int
    final_version: int
    rounds: List[SkillEvolutionRound] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return sum(r.accepted_changes for r in self.rounds)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "initial_version": self.initial_version,
            "final_version": self.final_version,
            "total_changes": self.total_changes,
            "rounds": [r.to_dict() for r in self.rounds],
        }

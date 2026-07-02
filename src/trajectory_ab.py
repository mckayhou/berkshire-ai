#!/usr/bin/env python3
"""
历史轨迹 A/B 评测（V10.27）：V9.3 整体分 vs V10 节点诊断 vs V10.26 重跑进化。

纯离线；tasks JSON 格式见 tests/fixtures/trajectories/sample_tasks.json。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from eval_harness import run_multi_round
    from graph import BerkshireGraph, Variable
    from graph_analysis import PromptHeuristicAnalysisRunner, mean_master_scores
    from prompt_optimizer import LLMClient
except ImportError:  # pragma: no cover
    from .eval_harness import run_multi_round
    from .graph import BerkshireGraph, Variable
    from .graph_analysis import PromptHeuristicAnalysisRunner, mean_master_scores
    from .prompt_optimizer import LLMClient

TARGET_AVG = 0.85
MASTER_KEYS = ("duan", "buffett", "munger", "lilu")


@dataclass
class TaskRecord:
    ticker: str
    scores: Dict[str, float]


@dataclass
class ABReport:
    tasks: int = 0
    below_target: int = 0
    v10_diagnosis_hits: int = 0
    diagnosis_coverage_pct: float = 0.0
    v10_evolution_improved: int = 0
    mean_evolution_delta: float = 0.0
    per_task: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_tasks(path: str | Path) -> List[TaskRecord]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: List[TaskRecord] = []
    for row in data:
        scores = {k: float(row["scores"][k]) for k in MASTER_KEYS if k in row.get("scores", {})}
        if len(scores) < 2:
            continue
        out.append(TaskRecord(ticker=str(row["ticker"]), scores=scores))
    return out


def evaluate_v93(task: TaskRecord) -> Dict[str, Any]:
    avg = sum(task.scores.values()) / len(task.scores)
    return {
        "mode": "v9.3",
        "ticker": task.ticker,
        "avg": avg,
        "below_target": avg < TARGET_AVG,
    }


def evaluate_v10_diagnosis(task: TaskRecord, threshold: float = 0.85) -> Dict[str, Any]:
    graph = BerkshireGraph()
    grads = graph.backward(task.scores)
    issues = sum(1 for g in grads.values() if not g.ok)
    prompts = sum(1 for k, g in grads.items() if k.endswith("_prompt") and not g.ok)
    avg = sum(task.scores.values()) / len(task.scores)
    return {
        "mode": "v10_diagnosis",
        "ticker": task.ticker,
        "avg": avg,
        "below_target": avg < TARGET_AVG,
        "issues_found": issues,
        "prompts_to_fix": prompts,
        "diagnosed": issues > 0,
    }


class _GrowingLLM(LLMClient):
    def __init__(self) -> None:
        self.n = 0

    def complete(self, system: str, user: str) -> str:
        self.n += 1
        return "P" + "✓" * self.n


def evaluate_v10_evolution(
    task: TaskRecord,
    *,
    rounds: int = 4,
    threshold: float = 0.70,
) -> Dict[str, Any]:
    """单标的：rerun_analysis + GrowingLLM 模拟改写后分析分提升。"""
    graph = BerkshireGraph()
    graph.variables["buffett_prompt"].value = "P"
    runner = PromptHeuristicAnalysisRunner()
    initial = mean_master_scores(runner.run(graph, task.ticker))
    report = run_multi_round(
        graph,
        _GrowingLLM(),
        lambda _p: 0.0,
        rounds=rounds,
        threshold=threshold,
        prompt_nodes=["buffett_prompt"],
        rerun_analysis=True,
        analysis_runner=runner,
        ticker=task.ticker,
    )
    return {
        "mode": "v10_evolution",
        "ticker": task.ticker,
        "initial_analysis_mean": initial,
        "final_analysis_mean": report.final_quality,
        "delta": report.final_quality - initial,
        "converged": report.converged,
        "rerun_analysis": report.rerun_analysis,
    }


def run_ab_report(
    tasks: List[TaskRecord],
    *,
    include_evolution: bool = True,
) -> ABReport:
    report = ABReport(tasks=len(tasks))
    deltas: List[float] = []

    for task in tasks:
        v93 = evaluate_v93(task)
        v10 = evaluate_v10_diagnosis(task)
        row: Dict[str, Any] = {"v93": v93, "v10_diagnosis": v10}

        if v93["below_target"]:
            report.below_target += 1
            if v10["diagnosed"]:
                report.v10_diagnosis_hits += 1

        if include_evolution:
            evo = evaluate_v10_evolution(task)
            row["v10_evolution"] = evo
            if evo["delta"] > 1e-9:
                report.v10_evolution_improved += 1
            deltas.append(float(evo["delta"]))

        report.per_task.append(row)

    if report.below_target:
        report.diagnosis_coverage_pct = (
            100.0 * report.v10_diagnosis_hits / report.below_target
        )
    else:
        report.diagnosis_coverage_pct = 100.0

    if deltas:
        report.mean_evolution_delta = sum(deltas) / len(deltas)

    return report


def render_ab_report(report: ABReport) -> str:
    lines = [
        "TextGrad 轨迹 A/B 评测",
        "=" * 52,
        f"任务数: {report.tasks}",
        f"低于目标 ({TARGET_AVG}): {report.below_target}",
        f"V10 节点诊断覆盖: {report.diagnosis_coverage_pct:.1f}%",
        f"V10.26 进化提升任务数: {report.v10_evolution_improved}/{report.tasks}",
        f"平均分析均分 Δ: {report.mean_evolution_delta:+.3f}",
    ]
    for row in report.per_task:
        t = row["v93"]["ticker"]
        lines.append(f"\n— {t}")
        lines.append(
            f"  V9.3 avg={row['v93']['avg']:.3f}  "
            f"V10 issues={row['v10_diagnosis']['issues_found']}"
        )
        if "v10_evolution" in row:
            e = row["v10_evolution"]
            lines.append(
                f"  V10.26 evolution Δ={e['delta']:+.3f} converged={e['converged']}"
            )
    return "\n".join(lines)

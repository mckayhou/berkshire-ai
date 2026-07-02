#!/usr/bin/env python3
"""
进化循环 CLI：status / reflect / optimize 子命令。

供 `python3 src/evolution_loop_v10.py <cmd>` 调用；全部可离线运行（mock LLM）。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Optional

try:
    from decision_log import default_log_path, load_decisions
    from eval_harness import run_multi_round
    from experience_store import ExperienceStore, KeywordExperienceRetriever
    from experience_store import default_log_path as exp_log_path
    from graph import BerkshireGraph
    from hypothesis import HypothesisStore
    from hypothesis import default_log_path as hyp_log_path
    from observability import run_context
    from prompt_optimizer import StaticLLMClient
    from reflect import reflect_ticker
    from run_recorder import RunRecord, RunRecorder, default_run_log_path
except ImportError:  # pragma: no cover
    from .decision_log import default_log_path, load_decisions
    from .eval_harness import run_multi_round
    from .experience_store import ExperienceStore, KeywordExperienceRetriever
    from .experience_store import default_log_path as exp_log_path
    from .graph import BerkshireGraph
    from .hypothesis import HypothesisStore
    from .hypothesis import default_log_path as hyp_log_path
    from .observability import run_context
    from .prompt_optimizer import StaticLLMClient
    from .reflect import reflect_ticker
    from .run_recorder import RunRecord, RunRecorder, default_run_log_path


def build_status_report() -> Dict[str, Any]:
    """汇总各 JSONL 存储的健康指标。"""
    decisions = load_decisions()
    experiences = ExperienceStore().load()
    hypotheses = HypothesisStore().load()
    runs = RunRecorder().load()
    return {
        "decisions": {"path": default_log_path(), "count": len(decisions)},
        "experiences": {"path": exp_log_path(), "count": len(experiences)},
        "hypotheses": {"path": hyp_log_path(), "count": len(hypotheses)},
        "runs": {"path": default_run_log_path(), "count": len(runs)},
        "tickers_with_decisions": len({d.ticker for d in decisions}),
        "tickers_with_experiences": len({e.ticker for e in experiences}),
    }


def cmd_status(_args: argparse.Namespace) -> int:
    report = build_status_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_reflect(args: argparse.Namespace) -> int:
    with run_context() as rid:
        report = reflect_ticker(args.ticker)
        payload = report.to_dict()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        try:
            RunRecorder().append(
                RunRecord(
                    run_id=rid,
                    event="reflect",
                    ticker=args.ticker,
                    metrics={
                        "n_experiences": report.n_experiences,
                        "n_decisions": report.n_decisions,
                        "suggestions": len(report.suggestions),
                    },
                    note="contrastive reflection",
                )
            )
        except OSError:
            pass
    return 0


def _quality_from_reflection(report) -> Dict[str, float]:
    """由反思报告推导各 prompt 节点的初始质量分（过度自信大师降分）。"""
    base = 0.75
    scores = {prefix: base for prefix in ("duan", "buffett", "munger", "lilu")}
    for point in report.divergence_points:
        for prefix in scores:
            if prefix in point and "更低" in point:
                scores[prefix] = max(0.45, scores[prefix] - 0.15)
    if any("过度自信" in m for m in report.failure_modes):
        for prefix in scores:
            scores[prefix] = min(scores[prefix], 0.65)
    return scores


def cmd_optimize(args: argparse.Namespace) -> int:
    with run_context() as rid:
        report = reflect_ticker(args.ticker)
        graph = BerkshireGraph()
        for name, var in graph.variables.items():
            if var.type == "prompt" and not var.value:
                var.value = f"Prompt for {name}"

        node_scores = _quality_from_reflection(report)

        def quality_fn(prompt: str) -> float:
            # 静态评分：按节点名映射反思降权
            for node, score in node_scores.items():
                if node in prompt or node.replace("_prompt", "") in prompt:
                    return score
            return 0.72

        llm = StaticLLMClient(responses={"*": "optimized prompt v1"})
        retriever = KeywordExperienceRetriever(ExperienceStore())
        evo = run_multi_round(
            graph,
            llm,
            quality_fn,
            rounds=args.rounds,
            retriever=retriever,
            retriever_ticker=args.ticker,
            run_id=rid,
        )
        out = {
            "ticker": args.ticker,
            "reflection": report.to_dict(),
            "evolution": {
                "rounds": len(evo.rounds),
                "converged": evo.converged,
                "monotonic_non_decreasing": evo.monotonic_non_decreasing,
                "final_mean_quality": evo.rounds[-1].mean_quality if evo.rounds else None,
            },
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        try:
            RunRecorder().append(
                RunRecord(
                    run_id=rid,
                    event="optimize",
                    ticker=args.ticker,
                    metrics={
                        "rounds": len(evo.rounds),
                        "converged": evo.converged,
                    },
                    note="reflect + eval_harness",
                )
            )
        except OSError:
            pass
    return 0


def cmd_cron(args: argparse.Namespace) -> int:
    try:
        from cron_evolution import run_cron
    except ImportError:
        from .cron_evolution import run_cron
    result = run_cron(args.task)
    payload = {
        "task": result.task,
        "ok": result.ok,
        "details": result.details,
        "errors": result.errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


def cmd_cycle(args: argparse.Namespace) -> int:
    try:
        from decision_log import DecisionRecord
        from pipeline import run_full_cycle
    except ImportError:
        from .decision_log import DecisionRecord
        from .pipeline import run_full_cycle

    factor_scan = None
    limitup_scan = None
    if args.factor_scan:
        with open(args.factor_scan, encoding="utf-8") as f:
            factor_scan = json.load(f)
    if args.limitup_scan:
        with open(args.limitup_scan, encoding="utf-8") as f:
            limitup_scan = json.load(f)

    d = DecisionRecord(
        ticker=args.ticker,
        date=args.date,
        scores={"duan": 0.8, "buffett": 0.75, "munger": 0.7, "lilu": 0.65},
        price_anchor=args.anchor,
    )
    out = run_full_cycle(
        d,
        realized_price=args.price,
        run_rd=not args.no_rd,
        rd_cycles=1,
        rerun_analysis=bool(args.rerun_analysis),
        factor_scan=factor_scan,
        limitup_scan=limitup_scan,
    )
    fb = out.get("feedback") or {}
    stats = fb.get("stats")
    rd = out.get("rd")
    summary = {
        "ticker": args.ticker,
        "run_id": out.get("run_id"),
        "alpha": float(getattr(stats, "alpha", 0) or 0),
        "rd_cycles": len(rd.cycles) if rd else 0,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_run_example(_args: argparse.Namespace) -> int:
    graph = BerkshireGraph()
    print("Graph created with", len(graph.variables), "nodes")
    scores = {"duan": 0.92, "buffett": 0.68, "munger": 0.85, "lilu": 0.55}
    gradients = graph.backward(scores)
    try:
        from optimizer import TextualGradientDescent
    except ImportError:
        from .optimizer import TextualGradientDescent
    optimizer = TextualGradientDescent(graph)
    updates = optimizer.step(gradients)
    print("Updates needed:", len(updates))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Berkshire AI V10 进化循环",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="各 JSONL 存储健康摘要")
    sub.add_parser("run", help="运行 run_example 演示（默认）")

    p_reflect = sub.add_parser("reflect", help="对比反思（需 ≥2 条经验更佳）")
    p_reflect.add_argument("ticker", help="标的代码，如 AAPL / 600519")

    p_opt = sub.add_parser("optimize", help="反思 + 验证门控进化一轮")
    p_opt.add_argument("ticker", help="标的代码")
    p_opt.add_argument("--rounds", type=int, default=1, help="进化轮数（默认 1）")

    p_cron = sub.add_parser("cron", help="Cron 自动进化任务")
    p_cron.add_argument(
        "task",
        choices=["thesis-tracker", "portfolio-weekly", "evolution-loop", "all"],
        help="定时任务类型",
    )
    p_cron.add_argument("--json", action="store_true", help="JSON 输出")

    p_cycle = sub.add_parser("cycle", help="完整主链路 run_full_cycle（R/D + 反馈）")
    p_cycle.add_argument("ticker", help="标的代码")
    p_cycle.add_argument("--price", type=float, required=True, help="已实现价格")
    p_cycle.add_argument("--anchor", type=float, required=True, help="决策时价格锚点")
    p_cycle.add_argument("--date", default="2026-01-02", help="决策日期")
    p_cycle.add_argument("--no-rd", action="store_true", help="跳过 R/D 双循环")
    p_cycle.add_argument(
        "--rerun-analysis",
        action="store_true",
        help="D 段改写后重跑分析（V10.26，默认关）",
    )
    p_cycle.add_argument("--factor-scan", help="factor_screener JSON 路径（V10.28）")
    p_cycle.add_argument("--limitup-scan", help="limitup_screener JSON 路径（V10.28）")

    p_skill = sub.add_parser("skill-evolve", help="SkillForge 技能进化（bad-case 驱动）")
    p_skill.add_argument(
        "action",
        choices=["list", "judge", "analyze", "evolve", "status", "create"],
        help="skill-evolve 子动作",
    )
    p_skill.add_argument("target", nargs="?", default=None, help="skill 名或 fixture 路径")
    p_skill.add_argument("--rounds", type=int, default=1)
    p_skill.add_argument("--dry-run", action="store_true")
    p_skill.add_argument("--fixture", default=None)
    p_skill.add_argument(
        "--judge-mode",
        choices=["auto", "llm", "rule"],
        default="auto",
    )
    p_skill.add_argument("--re-judge", action="store_true")
    p_skill.add_argument("--description", default="新技能", help="create 动作的描述")

    return parser


def cmd_skill_evolve(args: argparse.Namespace) -> int:
    try:
        from skill_forge.cli import main as skill_forge_main
    except ImportError:
        from .skill_forge.cli import main as skill_forge_main

    argv = [args.action]

    if args.action == "list":
        pass
    elif args.action == "judge":
        if not args.target and not args.fixture:
            print("judge 需要 fixture 路径", file=sys.stderr)
            return 1
        argv.append(args.fixture or args.target)
        argv.extend(["--judge-mode", args.judge_mode])
    elif args.action == "analyze":
        if not args.target and not args.fixture:
            print("analyze 需要 fixture 路径", file=sys.stderr)
            return 1
        argv.append(args.fixture or args.target)
        argv.extend(["--judge-mode", args.judge_mode])
        if args.re_judge:
            argv.append("--re-judge")
    elif args.action == "evolve":
        if not args.target:
            print("evolve 需要 skill 名", file=sys.stderr)
            return 1
        argv.append(args.target)
        if args.fixture:
            argv.extend(["--fixture", args.fixture])
        argv.extend(["--rounds", str(args.rounds)])
        argv.extend(["--judge-mode", args.judge_mode])
        if args.dry_run:
            argv.append("--dry-run")
        if args.re_judge:
            argv.append("--re-judge")
    elif args.action == "status":
        if not args.target:
            print("status 需要 skill 名", file=sys.stderr)
            return 1
        argv.append(args.target)
    elif args.action == "create":
        if not args.target:
            print("create 需要 skill 名", file=sys.stderr)
            return 1
        argv.extend([args.target, getattr(args, "description", "新技能")])
        if args.dry_run:
            argv.append("--dry-run")
    return skill_forge_main(argv)


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cmd = args.command
    if cmd is None or cmd == "run":
        return cmd_run_example(args)
    if cmd == "status":
        return cmd_status(args)
    if cmd == "reflect":
        return cmd_reflect(args)
    if cmd == "optimize":
        return cmd_optimize(args)
    if cmd == "cron":
        return cmd_cron(args)
    if cmd == "cycle":
        return cmd_cycle(args)
    if cmd == "skill-evolve":
        return cmd_skill_evolve(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

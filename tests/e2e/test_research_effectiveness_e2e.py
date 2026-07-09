#!/usr/bin/env python3
"""投研效果 E2E（全离线）：落盘 → 种子 → 归档 → 后验周报 → 收益反馈闭环。

不依赖网络 / LLM。路径全部落在 tmp_path，不污染 ~/.berkshire。
CI 与本地默认必跑。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

BERKSHIRE_DIR = Path(__file__).resolve().parents[2]
SRC = BERKSHIRE_DIR / "src"
TOOLS = BERKSHIRE_DIR / "tools"
SEEDS = BERKSHIRE_DIR / "data" / "portfolio_decision_seeds.json"

sys.path.insert(0, str(SRC))


def _env(tmp: Path) -> dict:
    env = os.environ.copy()
    env["BERKSHIRE_DECISION_LOG"] = str(tmp / "decisions.jsonl")
    env["BERKSHIRE_EXPERIENCE_LOG"] = str(tmp / "experiences.jsonl")
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _run(script: Path, *args: str, env: dict, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(BERKSHIRE_DIR),
        env=env,
    )


def test_e2e_log_decision_append_list_gaps(tmp_path: Path) -> None:
    env = _env(tmp_path)
    log_cli = TOOLS / "log_decision.py"

    r = _run(
        log_cli,
        "append",
        "--ticker",
        "E2E1",
        "--date",
        "2026-01-01",
        "--price",
        "100",
        "--stance",
        "0.85",
        "--thesis",
        "E2E 护城河测试",
        "--kill",
        "收入连续两季负增长",
        "--action",
        "hold",
        "--horizon",
        "20",
        "--depth",
        "standard",
        "--skill",
        "investment-research",
        env=env,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    payload = json.loads(r.stdout)
    assert payload["ok"] is True
    assert payload["research_complete"] is True
    assert payload["maturity"] == "2026-01-21"
    assert payload["gaps"] == []

    r2 = _run(log_cli, "list", "--json", env=env)
    assert r2.returncode == 0
    rows = json.loads(r2.stdout)
    assert len(rows) == 1
    assert rows[0]["ticker"] == "E2E1"
    assert rows[0]["complete"] is True

    r3 = _run(log_cli, "gaps", env=env)
    assert r3.returncode == 0  # 无缺口


def test_e2e_incomplete_append_exit_2(tmp_path: Path) -> None:
    env = _env(tmp_path)
    r = _run(
        TOOLS / "log_decision.py",
        "append",
        "--ticker",
        "GAP1",
        "--date",
        "2026-01-01",
        "--price",
        "50",
        "--stance",
        "0.5",
        # 故意不写 thesis / kill / action
        env=env,
    )
    assert r.returncode == 2
    data = json.loads(r.stdout)
    assert data["research_complete"] is False
    assert "thesis" in data["gaps"]


def test_e2e_seed_portfolio_decisions(tmp_path: Path) -> None:
    env = _env(tmp_path)
    assert SEEDS.is_file()
    r = _run(
        TOOLS / "seed_portfolio_decisions.py",
        "--from-json",
        str(SEEDS),
        env=env,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "written=5" in r.stdout

    # 再次无 --force → skip
    r2 = _run(
        TOOLS / "seed_portfolio_decisions.py",
        "--from-json",
        str(SEEDS),
        env=env,
    )
    assert r2.returncode == 0
    assert "skipped=5" in r2.stdout

    r3 = _run(TOOLS / "log_decision.py", "list", "--json", env=env)
    rows = json.loads(r3.stdout)
    tickers = {row["ticker"] for row in rows}
    assert tickers >= {"NVDA", "AVGO", "PDD", "600900", "0700.HK"}
    assert all(row["complete"] for row in rows)

    r4 = _run(TOOLS / "log_decision.py", "gaps", env=env)
    assert r4.returncode == 0


def test_e2e_posterior_weekly_hit_rate_chain(tmp_path: Path) -> None:
    """append 两条到期决策 → price map 后验 → 命中率 100%。"""
    env = _env(tmp_path)
    log_cli = TOOLS / "log_decision.py"

    for ticker, stance, action in (
        ("BULL", "0.9", "buy"),
        ("BEAR", "0.2", "reduce"),
    ):
        r = _run(
            log_cli,
            "append",
            "--ticker",
            ticker,
            "--date",
            "2026-01-01",
            "--price",
            "100",
            "--stance",
            stance,
            "--thesis",
            f"{ticker} e2e thesis",
            "--kill",
            "e2e kill",
            "--action",
            action,
            "--horizon",
            "20",
            env=env,
        )
        assert r.returncode == 0, r.stderr

    prices = {
        "BULL|2026-01-21": 115.0,  # +15% 看多命中
        "BEAR|2026-01-21": 85.0,  # -15% 看空命中
    }
    r = _run(
        TOOLS / "posterior_weekly.py",
        "report",
        "--as-of",
        "2026-02-01",
        "--prices",
        json.dumps(prices),
        "--json",
        env=env,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    report = json.loads(r.stdout)
    assert report["n_decisions"] == 2
    assert report["n_priced"] == 2
    assert report["complete_rate"] == 1.0
    assert report["direction_hit_rate"] == 1.0
    assert report["direction_hits"] == 2

    # Markdown 模式
    r_md = _run(
        TOOLS / "posterior_weekly.py",
        "report",
        "--as-of",
        "2026-02-01",
        "--prices",
        json.dumps(prices),
        env=env,
    )
    assert r_md.returncode == 0
    assert "投研后验周报" in r_md.stdout
    assert "100.0%" in r_md.stdout or "1.0" in r_md.stdout


def test_e2e_posterior_not_due_and_strict_missing_price(tmp_path: Path) -> None:
    env = _env(tmp_path)
    r = _run(
        TOOLS / "log_decision.py",
        "append",
        "--ticker",
        "FUTURE",
        "--date",
        "2026-06-01",
        "--price",
        "10",
        "--stance",
        "0.7",
        "--thesis",
        "未到期",
        "--kill",
        "k",
        "--action",
        "hold",
        "--horizon",
        "60",
        env=env,
    )
    assert r.returncode == 0

    r2 = _run(
        TOOLS / "posterior_weekly.py",
        "report",
        "--as-of",
        "2026-06-10",
        "--json",
        env=env,
    )
    assert r2.returncode == 0
    rep = json.loads(r2.stdout)
    assert rep["n_due"] == 0
    assert rep["n_priced"] == 0

    # 到期但无价 + --strict → exit 2
    r3 = _run(
        TOOLS / "posterior_weekly.py",
        "report",
        "--as-of",
        "2026-08-10",
        "--strict",
        "--json",
        env=env,
    )
    assert r3.returncode == 2
    rep3 = json.loads(r3.stdout)
    assert rep3["n_missing_price"] >= 1


def test_e2e_archive_experiences_pollution_and_reset(tmp_path: Path) -> None:
    env = _env(tmp_path)
    exp_path = Path(env["BERKSHIRE_EXPERIENCE_LOG"])
    # 模拟污染：同一 ticker + 同一 alpha
    lines = []
    for _ in range(10):
        lines.append(
            json.dumps(
                {
                    "ticker": "AAPL",
                    "date": "2026-01-01",
                    "alpha": 0.15,
                    "realized_base": 0.575,
                    "stances": {"duan": 0.9, "buffett": 0.9, "munger": 0.9, "lilu": 0.9},
                    "lesson": "test pollution",
                },
                ensure_ascii=False,
            )
        )
    exp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    dry = _run(TOOLS / "archive_experiences.py", "--dry-run", env=env)
    assert dry.returncode == 0
    assert "疑似测试污染" in dry.stdout
    assert exp_path.read_text(encoding="utf-8").count("\n") >= 10  # 未清空

    done = _run(
        TOOLS / "archive_experiences.py",
        "--reset",
        "--reason",
        "e2e clean",
        env=env,
    )
    assert done.returncode == 0
    assert "已归档" in done.stdout
    assert exp_path.read_text(encoding="utf-8") == ""
    # archive path is experiences.jsonl.archive.TS (no extra suffix filter)
    assert any(
        p.name.startswith("experiences.jsonl.archive.") and not p.name.endswith(".meta.json")
        for p in tmp_path.iterdir()
    )


def test_e2e_decision_to_realized_feedback_and_posterior(tmp_path: Path) -> None:
    """Python API：契约完整 DecisionRecord → run_with_realized_feedback → 后验。"""
    env = _env(tmp_path)
    # 同步环境变量给本进程
    os.environ["BERKSHIRE_DECISION_LOG"] = env["BERKSHIRE_DECISION_LOG"]
    os.environ["BERKSHIRE_EXPERIENCE_LOG"] = env["BERKSHIRE_EXPERIENCE_LOG"]

    from decision_log import DecisionRecord, append_decision, is_research_complete, load_decisions
    from evolution_loop_v10 import run_with_realized_feedback
    from posterior_report import build_posterior_report
    from realized_feedback import StaticPriceProvider

    log_path = env["BERKSHIRE_DECISION_LOG"]
    d = DecisionRecord(
        ticker="AAPL",
        date="2026-01-01",
        scores={"duan": 0.88, "buffett": 0.86, "munger": 0.84, "lilu": 0.87},
        price_anchor=100.0,
        benchmark="SPX",
        benchmark_anchor=5000.0,
        thesis="E2E services moat",
        kill_condition="Services 增速 < 5%",
        action="hold",
        horizon_days=20,
        depth="standard",
        skill="investment-research",
    )
    assert is_research_complete(d)
    append_decision(d, path=log_path)

    provider = StaticPriceProvider(
        {
            ("AAPL", "2026-01-21"): 110.0,
            ("SPX", "2026-01-21"): 5100.0,
        }
    )
    out = run_with_realized_feedback(
        d,
        realized_date="2026-01-21",
        price_provider=provider,
        persist=True,
        include_perf=True,
        use_llm_gradient=False,
        use_validation=False,
    )
    assert isinstance(out, dict) and len(out) >= 1

    records = load_decisions(log_path)
    # 主链路可能再 append 一次；只评估 AAPL 且完整契约的记录
    aapl = [r for r in records if r.ticker == "AAPL" and is_research_complete(r)]
    assert len(aapl) >= 1
    report = build_posterior_report(
        aapl,
        as_of="2026-02-01",
        price_map={"AAPL|2026-01-21": 110.0},
    )
    assert report.n_priced >= 1
    assert report.direction_hit_rate == 1.0
    assert report.complete_rate == 1.0


def test_e2e_full_subprocess_pipeline_with_out_file(tmp_path: Path) -> None:
    """子进程端到端：seed → 合成到期价 map → 写周报文件。"""
    env = _env(tmp_path)
    seeds = [
        {
            "ticker": "AAA",
            "date": "2026-01-01",
            "price_anchor": 100.0,
            "stance": 0.8,
            "action": "hold",
            "horizon_days": 10,
            "depth": "lite",
            "skill": "thesis-tracker",
            "thesis": "pipeline seed A",
            "kill_condition": "break A",
        },
        {
            "ticker": "BBB",
            "date": "2026-01-01",
            "price_anchor": 50.0,
            "stance": 0.3,
            "action": "exit",
            "horizon_days": 10,
            "depth": "lite",
            "skill": "thesis-tracker",
            "thesis": "pipeline seed B",
            "kill_condition": "break B",
        },
    ]
    seed_file = tmp_path / "seeds.json"
    seed_file.write_text(json.dumps(seeds, ensure_ascii=False), encoding="utf-8")

    r = _run(
        TOOLS / "seed_portfolio_decisions.py",
        "--from-json",
        str(seed_file),
        env=env,
    )
    assert r.returncode == 0, r.stderr

    prices_file = tmp_path / "prices.json"
    prices_file.write_text(
        json.dumps({"AAA|2026-01-11": 108.0, "BBB|2026-01-11": 40.0}),
        encoding="utf-8",
    )
    out_md = tmp_path / "weekly.md"
    r2 = _run(
        TOOLS / "posterior_weekly.py",
        "report",
        "--as-of",
        "2026-01-20",
        "--prices-file",
        str(prices_file),
        "--out",
        str(out_md),
        env=env,
    )
    assert r2.returncode == 0, r2.stderr + r2.stdout
    assert out_md.is_file()
    text = out_md.read_text(encoding="utf-8")
    assert "投研后验周报" in text
    assert "AAA" in text and "BBB" in text

#!/usr/bin/env python3
"""A-share automatic factor mining (AlphaGPT times.py ported for berkshire-ai).

Uses REINFORCE + StackVM to discover interpretable factor formulas on A-share/ETF
daily bars. Data via ashare_data / data_sources (no hardcoded API tokens).

Requires: pip install '.[factor-mining]'

Examples:
  python3 tools/ashare_factor_mining.py train --code 511260
  python3 tools/ashare_factor_mining.py train --code 600519 --steps 100 --no-oos
  python3 tools/ashare_factor_mining.py decode --tokens '[0,6,1,7]'
  python3 tools/ashare_factor_mining.py oos --formula data/alphagpt/best_ashare_formula.json
  python3 tools/ashare_factor_mining.py screen --json
  python3 tools/factor_screener_bridge.py --json -o data/alphagpt/factor_scan.json
  python3 tools/thesis_queue.py --from-factor-scan data/alphagpt/factor_scan.json --suggest-md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "tools") not in sys.path:
    sys.path.insert(0, str(_REPO / "tools"))


def _require_torch() -> None:
    try:
        import torch  # noqa: F401
    except ImportError as e:
        print(
            "Missing PyTorch. Install optional deps:\n"
            "  pip install '.[factor-mining]'",
            file=sys.stderr,
        )
        raise SystemExit(1) from e


def cmd_train(args: argparse.Namespace) -> int:
    _require_torch()
    import torch
    from ashare_alphagpt.config import MiningConfig
    from ashare_alphagpt.data_engine import AshareDataEngine
    from ashare_alphagpt.miner import DeepQuantMiner
    from ashare_alphagpt.oos import run_oos_check

    cfg = MiningConfig(
        index_code=args.code,
        train_iterations=args.steps,
        batch_size=args.batch,
        max_seq_len=args.max_len,
        cost_rate=args.cost,
    )
    if args.start:
        cfg.start_date = args.start
    if args.train_end:
        cfg.end_date = args.train_end
    if args.test_end:
        cfg.test_end_date = args.test_end

    torch.set_float32_matmul_precision("high")
    print(f"Loading {cfg.index_code} …")
    engine = AshareDataEngine(cfg).load()
    print(f"Bars: {engine.feat_data.shape[-1]}, train split @ {engine.split_idx}")

    miner = DeepQuantMiner(engine, cfg)
    result = miner.train(progress=not args.quiet)
    out_path = miner.save()
    print(f"\nBest Sortino (in-sample): {result.best_score:.3f}")
    print(f"Formula: {result.formula_str}")
    print(f"Saved: {out_path}")

    if not args.no_oos:
        report = run_oos_check(engine, result.best_formula_tokens, cost_rate=cfg.cost_rate)
        if report:
            print("\n" + report.as_text())
            if args.plot:
                _save_oos_plot(engine, result.best_formula_tokens, cfg.cost_rate, cfg.output_dir)
    return 0


def _save_oos_plot(engine, tokens, cost_rate: float, out_dir: Path) -> None:
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib not installed; skip plot")
        return

    from ashare_alphagpt.vm import FormulaVM

    vm = FormulaVM(engine.feat_data)
    factor = vm.solve_one(tokens)
    if factor is None:
        return
    split = engine.split_idx
    test_ret = engine.target_oto_ret[split:].detach().cpu().numpy()
    sig = np.tanh(factor[split:].detach().cpu().numpy())
    pos = np.sign(sig)
    turnover = np.abs(pos - np.roll(pos, 1))
    turnover[0] = 0.0
    daily_ret = pos * test_ret - turnover * cost_rate
    equity = (1 + daily_ret).cumprod()
    bench = (1 + test_ret).cumprod()
    raw_dates = engine.dates[split:] if engine.dates else list(range(len(equity)))

    plt.style.use("bmh")
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(raw_dates, equity, label="Strategy (OOS)")
    ax.plot(raw_dates, bench, label="Buy & Hold (open-to-open)", alpha=0.5)
    ax.legend()
    ax.grid(True)
    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "strategy_performance.png"
    fig.savefig(path)
    print(f"Chart saved: {path}")


def cmd_screen(args: argparse.Namespace) -> int:
    _require_torch()
    from ashare_alphagpt.screener import run_screen

    codes = None
    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]

    result = run_screen(
        formula_path=args.formula,
        codes=codes,
        source=args.source,
        min_score=args.min_score,
        top_n=args.top,
    )

    if args.output:
        Path(args.output).write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if args.json or args.output:
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if not result.get("ok"):
            print(f"Screen failed: {result.get('error')}")
            return 1
        print(f"{len(result['candidates'])} candidates")
        for c in result["candidates"][:15]:
            print(f"  {c['ticker']}: {c['score']:+.3f}")
    return 0 if result.get("ok") else 1


def cmd_decode(args: argparse.Namespace) -> int:
    from ashare_alphagpt.decode import decode_formula

    tokens = json.loads(args.tokens)
    print(decode_formula(tokens))
    return 0


def cmd_oos(args: argparse.Namespace) -> int:
    _require_torch()
    from ashare_alphagpt.config import MiningConfig
    from ashare_alphagpt.data_engine import AshareDataEngine
    from ashare_alphagpt.oos import run_oos_check

    path = Path(args.formula)
    data = json.loads(path.read_text(encoding="utf-8"))
    tokens = data.get("formula_tokens") or data.get("formula") or data
    if isinstance(tokens, dict):
        tokens = tokens.get("formula_tokens")

    cfg = MiningConfig(index_code=args.code)
    engine = AshareDataEngine(cfg).load()
    report = run_oos_check(engine, tokens, cost_rate=cfg.cost_rate)
    if report is None:
        print("OOS check failed (invalid formula or data)")
        return 1
    print(report.as_text())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="A-share AlphaGPT factor mining")
    sub = parser.add_subparsers(dest="command", required=True)

    p_train = sub.add_parser("train", help="Train factor miner on one symbol")
    p_train.add_argument("--code", default="511260", help="A-share / ETF code")
    p_train.add_argument("--steps", type=int, default=400)
    p_train.add_argument("--batch", type=int, default=1024)
    p_train.add_argument("--max-len", type=int, default=8)
    p_train.add_argument("--cost", type=float, default=0.0005)
    p_train.add_argument("--start", help="YYYYMMDD start")
    p_train.add_argument("--train-end", help="YYYYMMDD train end marker")
    p_train.add_argument("--test-end", help="YYYYMMDD data end")
    p_train.add_argument("--no-oos", action="store_true")
    p_train.add_argument("--plot", action="store_true")
    p_train.add_argument("--quiet", action="store_true")

    p_dec = sub.add_parser("decode", help="Decode token list to formula string")
    p_dec.add_argument("--tokens", required=True, help='JSON list e.g. "[0,6,1]"')

    p_oos = sub.add_parser("oos", help="OOS check from saved formula JSON")
    p_oos.add_argument("--formula", required=True)
    p_oos.add_argument("--code", default="511260")

    p_scr = sub.add_parser("screen", help="Score symbols with saved formula")
    p_scr.add_argument("--formula", help="Formula JSON path")
    p_scr.add_argument("--codes", help="Comma-separated codes")
    p_scr.add_argument("--source", choices=["auto", "csv", "online"], default="auto")
    p_scr.add_argument("--min-score", type=float)
    p_scr.add_argument("--top", type=int)
    p_scr.add_argument("--json", action="store_true")
    p_scr.add_argument("-o", "--output")

    args = parser.parse_args()
    handlers = {"train": cmd_train, "decode": cmd_decode, "oos": cmd_oos, "screen": cmd_screen}
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())

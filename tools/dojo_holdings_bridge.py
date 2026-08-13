#!/usr/bin/env python3
"""DojoAgents 持仓 → berkshire-ai holdings.json 桥接。

DojoAgents 组合文档（~/.dojo/data/portfolio/{id}.json）使用 shares/market 结构；
本仓 portfolio_risk / portfolio_scan 使用「代码 → 仓位占比%」的 holdings.json。

本工具只做格式转换 + 可选风险体检，不依赖安装 dojoagents 包。

用法
----
    # 列出本机 Dojo 组合目录
    python3 tools/dojo_holdings_bridge.py list

    # 从默认示例组合目录转换（仓库外 /tmp 或 ~/.dojo）
    python3 tools/dojo_holdings_bridge.py convert \\
      --portfolio ~/.dojo/data/portfolio/047214744248.json \\
      --prices '{"GOOG":175,"CAT":340}' --out data/holdings.json

    # 仅 shares、无价格时：等权股票仓（可加 --cash 30）
    python3 tools/dojo_holdings_bridge.py convert --portfolio p.json --equal-weight --cash 20

    # 转换后跑 portfolio_risk
    python3 tools/dojo_holdings_bridge.py convert --portfolio p.json --equal-weight --risk

设计
----
- 支持 Dojo v2/v3 文档字段：holdings[] / positions[] / candidates[]。
- ticker 规范化：美股大写；A 股保持数字；港股补 .HK（若 market=hk 且无后缀）。
- 权重：优先 market_value；否则 shares×price；否则 --equal-weight。
- 输出 JSON 兼容 data/holdings.example.json（可含 _comment / CASH）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(_TOOLS))

DEFAULT_DOJO_PORTFOLIO_DIR = Path.home() / ".dojo" / "data" / "portfolio"
DEFAULT_OUT = _ROOT / "data" / "holdings.json"


def _norm_ticker(ticker: str, market: str = "") -> str:
    t = str(ticker or "").strip().upper().replace(" ", "")
    m = str(market or "").strip().lower()
    if not t:
        return ""
    # already suffixed
    if t.endswith((".HK", ".SS", ".SZ", ".SH")):
        return t
    if m in ("hk", "hongkong", "hong_kong"):
        # numeric HK codes often 4 digits
        if t.isdigit():
            return f"{int(t):04d}.HK"
        return f"{t}.HK" if not t.endswith(".HK") else t
    if m in ("sh", "sz", "cn", "ss"):
        # keep 6-digit A-share codes as-is
        return t
    return t


def _iter_legs(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract holding-like rows from a Dojo portfolio document."""
    rows: List[Dict[str, Any]] = []
    for key in ("positions", "holdings", "candidates"):
        raw = doc.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, dict) and item.get("ticker"):
                rows.append(item)
    # de-dupe by ticker keeping max shares/value
    by_t: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        t = _norm_ticker(str(r.get("ticker")), str(r.get("market") or ""))
        if not t:
            continue
        prev = by_t.get(t)
        if prev is None:
            by_t[t] = {**r, "ticker": t}
            continue
        # prefer row with more economic signal
        def score(x: Dict[str, Any]) -> float:
            for k in ("market_value", "shares", "weight", "pct"):
                try:
                    if x.get(k) is not None:
                        return float(x[k])
                except (TypeError, ValueError):
                    pass
            return 0.0

        if score(r) >= score(prev):
            by_t[t] = {**r, "ticker": t}
    return list(by_t.values())


def legs_to_weights(
    legs: Sequence[Dict[str, Any]],
    *,
    prices: Optional[Dict[str, float]] = None,
    equal_weight: bool = False,
    cash_pct: float = 0.0,
) -> Dict[str, float]:
    """Convert legs → percentage weights summing to ~100 (incl. CASH)."""
    prices = {str(k).strip().upper(): float(v) for k, v in (prices or {}).items()}
    cash_pct = max(0.0, min(100.0, float(cash_pct)))
    equity_budget = 100.0 - cash_pct

    if not legs:
        out = {}
        if cash_pct:
            out["CASH"] = round(cash_pct, 4)
        return out

    def _leg_ticker(leg: Dict[str, Any]) -> str:
        return _norm_ticker(str(leg.get("ticker") or ""), str(leg.get("market") or ""))

    if equal_weight:
        tickers = []
        for leg in legs:
            t = _leg_ticker(leg)
            if t:
                tickers.append(t)
        if not tickers:
            raise SystemExit("等权模式：无有效 ticker")
        w = equity_budget / len(tickers)
        out: Dict[str, float] = {}
        for t in tickers:
            out[t] = round(out.get(t, 0.0) + w, 4)
        if cash_pct:
            out["CASH"] = round(cash_pct, 4)
        return out

    values: Dict[str, float] = {}
    missing_px: List[str] = []
    for leg in legs:
        t = _leg_ticker(leg)
        if not t:
            continue
        mv = leg.get("market_value")
        if mv is not None:
            try:
                values[t] = values.get(t, 0.0) + float(mv)
                continue
            except (TypeError, ValueError):
                pass
        # explicit weight/pct already in 0-100 or 0-1
        for k in ("weight", "pct", "weight_pct"):
            if leg.get(k) is not None:
                try:
                    w = float(leg[k])
                    if 0 < w <= 1.0:
                        w *= 100.0
                    values[t] = values.get(t, 0.0) + w
                    break
                except (TypeError, ValueError):
                    pass
        else:
            shares = leg.get("shares")
            px = prices.get(t)
            if shares is not None and px is not None:
                values[t] = values.get(t, 0.0) + float(shares) * float(px)
            else:
                missing_px.append(t)

    if not values:
        raise SystemExit(
            "无法计算权重：缺少 market_value / weight，且无可用 shares×price。"
            "请传 --prices 或 --equal-weight。"
            + (f" 缺价: {missing_px}" if missing_px else "")
        )

    # if values look like already-percent (sum ~100), scale equity_budget
    total = sum(values.values())
    if total <= 0:
        raise SystemExit("持仓市值合计为 0")

    # Heuristic: if max value <= 100 and sum <= 150, treat as percent weights
    if max(values.values()) <= 100 and total <= 150:
        scale = equity_budget / total
        out = {t: round(v * scale, 4) for t, v in values.items()}
    else:
        out = {t: round(v / total * equity_budget, 4) for t, v in values.items()}

    if cash_pct:
        out["CASH"] = round(cash_pct, 4)

    # fix float drift
    s = sum(out.values())
    if abs(s - 100.0) > 0.05 and "CASH" in out:
        out["CASH"] = round(out["CASH"] + (100.0 - s), 4)
    return out


def load_portfolio(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if not isinstance(doc, dict):
        raise SystemExit(f"组合文件必须是 JSON 对象: {path}")
    return doc


def list_dojo_portfolios(root: Path) -> List[Dict[str, Any]]:
    root = root.expanduser()
    if not root.is_dir():
        return []
    index = root / "index.json"
    catalog: Dict[str, Any] = {}
    if index.is_file():
        try:
            catalog = json.loads(index.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            catalog = {}
    meta_by_id = {}
    for p in catalog.get("portfolios") or []:
        if isinstance(p, dict) and p.get("id"):
            meta_by_id[str(p["id"])] = p

    rows = []
    for fp in sorted(root.glob("*.json")):
        if fp.name == "index.json":
            continue
        try:
            doc = load_portfolio(fp)
        except SystemExit:
            continue
        pid = str(doc.get("id") or fp.stem)
        meta = meta_by_id.get(pid, {})
        legs = _iter_legs(doc)
        rows.append(
            {
                "id": pid,
                "name": doc.get("name") or meta.get("name") or pid,
                "path": str(fp),
                "n_legs": len(legs),
                "tickers": [str(x.get("ticker")) for x in legs[:12]],
            }
        )
    return rows


def write_holdings(path: Path, weights: Dict[str, float], *, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": "Generated by tools/dojo_holdings_bridge.py — 仓位占比%，合计约 100%。",
        "_source": source,
        "_updated": __import__("datetime").date.today().isoformat(),
    }
    # stable order: non-cash alpha, then CASH
    for k in sorted(weights.keys()):
        if k == "CASH":
            continue
        payload[k] = weights[k]
    if "CASH" in weights:
        payload["CASH"] = weights["CASH"]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_risk(weights: Dict[str, float]) -> Dict[str, Any]:
    import portfolio_risk as pr  # type: ignore

    return pr.check_holdings(weights)


def cmd_list(args: argparse.Namespace) -> int:
    root = Path(args.dojo_dir).expanduser()
    rows = list_dojo_portfolios(root)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print(f"Dojo 组合目录: {root}  n={len(rows)}")
        if not rows:
            print("  （空）可安装 dojoagents 后使用 Dashboard，或传 --portfolio 指向 JSON")
        for r in rows:
            print(f"  {r['id']:16} {r['name'][:32]:32} legs={r['n_legs']:3}  {r['path']}")
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    path = Path(args.portfolio).expanduser()
    if not path.is_file():
        raise SystemExit(f"找不到组合文件: {path}")
    doc = load_portfolio(path)
    legs = _iter_legs(doc)
    prices = {}
    if args.prices:
        prices.update(json.loads(args.prices))
    if args.prices_file:
        prices.update(json.loads(Path(args.prices_file).read_text(encoding="utf-8")))

    weights = legs_to_weights(
        legs,
        prices=prices,
        equal_weight=bool(args.equal_weight),
        cash_pct=float(args.cash),
    )
    out = Path(args.out).expanduser() if args.out else DEFAULT_OUT
    source = f"dojo:{doc.get('id') or path.name}"
    if args.dry_run:
        print(json.dumps({"source": source, "weights": weights, "n_legs": len(legs)}, ensure_ascii=False, indent=2))
    else:
        write_holdings(out, weights, source=source)
        print(f"已写入 {out}  n_tickers={len([k for k in weights if k != 'CASH'])}  source={source}")

    if args.risk:
        risk = run_risk(weights)
        if args.json or args.dry_run:
            print(json.dumps({"risk": risk}, ensure_ascii=False, indent=2))
        else:
            flags = risk.get("risk_flags") or risk.get("flags") or []
            print("portfolio_risk flags:", flags if flags else "（无）")
            # compact summary keys if present
            for k in ("max_single", "top3_pct", "cash_pct", "n_positions"):
                if k in risk:
                    print(f"  {k}={risk[k]}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="DojoAgents portfolio → berkshire holdings.json")
    p.add_argument(
        "--dojo-dir",
        default=str(DEFAULT_DOJO_PORTFOLIO_DIR),
        help="Dojo 组合根目录（默认 ~/.dojo/data/portfolio）",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    lp = sub.add_parser("list", help="列出本机 Dojo 组合")
    lp.add_argument("--json", action="store_true")
    lp.set_defaults(func=cmd_list)

    cp = sub.add_parser("convert", help="转换单个组合 JSON → holdings.json")
    cp.add_argument("--portfolio", required=True, help="Dojo 组合 JSON 路径")
    cp.add_argument("--out", default=str(DEFAULT_OUT), help="输出 holdings.json")
    cp.add_argument("--prices", default=None, help='JSON {"AAPL":190,...} 用于 shares×price')
    cp.add_argument("--prices-file", default=None)
    cp.add_argument("--equal-weight", action="store_true", help="股票等权（忽略 shares）")
    cp.add_argument("--cash", type=float, default=0.0, help="现金占比%%（默认 0）")
    cp.add_argument("--risk", action="store_true", help="转换后调用 portfolio_risk")
    cp.add_argument("--dry-run", action="store_true")
    cp.add_argument("--json", action="store_true")
    cp.set_defaults(func=cmd_convert)
    return p


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

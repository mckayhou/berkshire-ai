#!/usr/bin/env python3
"""组合风险检查（Risk Manager 层）— 仓位集中度、主题暴露、相关性提示。

借鉴 ai-hedge-fund Risk Manager，输出 risk_flags 供 portfolio_scan / action-card 使用。
纯计算，默认离线；--correlation 可选读取本地 CSV。

用法：
  python3 tools/portfolio_risk.py --holdings '{"NVDA":25,"0700.HK":30,"CASH":15}'
  python3 tools/portfolio_risk.py --holdings-file portfolio.json --json
  python3 tools/portfolio_risk.py --holdings '{"NVDA":25}' --proposed MU 5
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime

_TOOLS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_TOOLS)
DATA_DIR = os.path.join(_REPO, "data")
WATCHLIST_FILE = os.path.join(DATA_DIR, "watchlist.json")
DEFAULT_HOLDINGS_FILE = os.path.join(DATA_DIR, "holdings.json")
DEFAULT_CORR = os.path.join(DATA_DIR, "correlation_3stocks_2021-2026.csv")

# 默认阈值（与 portfolio-review / 李录集中持仓哲学对齐）
DEFAULT_RULES = {
    "max_single_pct": 40.0,
    "warn_single_pct": 35.0,
    "max_top3_pct": 80.0,
    "min_cash_pct": 10.0,
    "max_theme_pct": 50.0,
    "min_positions": 3,
    "max_positions": 15,
    "high_corr_threshold": 0.75,
}

# 相关性 CSV 列名 → 常见代码
CORR_TICKER_MAP = {
    "TENCENT": "0700.HK",
    "MEITUAN": "1024.HK",
    "PDD": "PDD",
}


def _norm_ticker(t: str) -> str:
    return t.strip().upper().replace(" ", "")


def load_watchlist_themes() -> dict[str, str]:
    """ticker -> watchlist 分组名。"""
    if not os.path.exists(WATCHLIST_FILE):
        return {}
    with open(WATCHLIST_FILE, encoding="utf-8") as f:
        wl = json.load(f)
    out = {}
    for group, tickers in wl.items():
        for t in tickers:
            out[_norm_ticker(t)] = group
    return out


def parse_holdings(raw: dict) -> dict[str, float]:
    """标准化持仓占比；CASH 单独保留。"""
    out = {}
    for k, v in raw.items():
        if str(k).startswith("_"):
            continue
        key = _norm_ticker(k)
        try:
            pct = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"无效占比: {k}={v}")
        if pct < 0:
            raise ValueError(f"占比不能为负: {k}={pct}")
        out[key] = out.get(key, 0) + pct
    return out


def load_holdings_file(path: str | None = None) -> dict[str, float]:
    """从 JSON 文件加载持仓；默认 data/holdings.json。"""
    path = path or DEFAULT_HOLDINGS_FILE
    if not os.path.exists(path):
        raise FileNotFoundError(f"持仓文件不存在: {path}")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return parse_holdings(raw)


def resolve_holdings(
    holdings_json: str | None = None,
    holdings_file: str | None = None,
    use_default_file: bool = True,
) -> dict[str, float] | None:
    """解析 CLI 持仓来源；无输入且默认文件不存在时返回 None。"""
    if holdings_file:
        return load_holdings_file(holdings_file)
    if holdings_json:
        return parse_holdings(json.loads(holdings_json))
    if use_default_file and os.path.exists(DEFAULT_HOLDINGS_FILE):
        return load_holdings_file(DEFAULT_HOLDINGS_FILE)
    return None


def theme_exposure(holdings: dict[str, float], themes: dict[str, str]) -> dict[str, float]:
    exp: dict[str, float] = {}
    for ticker, pct in holdings.items():
        if ticker in ("CASH", "现金"):
            continue
        theme = themes.get(ticker, "other")
        exp[theme] = exp.get(theme, 0) + pct
    return exp


def load_latest_correlations(path: str) -> dict[str, float]:
    """读取相关性 CSV 最后一行，返回列间两两相关（简化：用收益率序列算 Pearson）。"""
    if not os.path.exists(path):
        return {}
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = [c for c in reader.fieldnames if c != "date"]
        for row in reader:
            rows.append(row)
    if len(rows) < 20:
        return {}
    # 用最近 60 行算相关
    recent = rows[-60:]
    series = {c: [] for c in cols}
    for row in recent:
        for c in cols:
            try:
                series[c].append(float(row[c]))
            except (ValueError, KeyError):
                pass
    def pearson(a, b):
        n = min(len(a), len(b))
        if n < 10:
            return None
        a, b = a[-n:], b[-n:]
        ma, mb = sum(a) / n, sum(b) / n
        va = sum((x - ma) ** 2 for x in a)
        vb = sum((y - mb) ** 2 for y in b)
        if va == 0 or vb == 0:
            return 0.0
        cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
        return cov / (va ** 0.5 * vb ** 0.5)

    pairs = {}
    for i, c1 in enumerate(cols):
        for c2 in cols[i + 1:]:
            r = pearson(series[c1], series[c2])
            if r is not None:
                pairs[f"{c1}/{c2}"] = round(r, 3)
    return pairs


def check_holdings(
    holdings: dict[str, float],
    rules: dict | None = None,
    themes: dict[str, str] | None = None,
    corr_pairs: dict[str, float] | None = None,
    proposed: tuple[str, float] | None = None,
) -> dict:
    """返回 {ok, flags, metrics}。"""
    rules = {**DEFAULT_RULES, **(rules or {})}
    themes = themes or load_watchlist_themes()
    flags: list[dict] = []

    h = dict(holdings)
    if proposed:
        t, p = _norm_ticker(proposed[0]), float(proposed[1])
        h[t] = h.get(t, 0) + p

    equity = {k: v for k, v in h.items() if k not in ("CASH", "现金")}
    cash = h.get("CASH", 0) + h.get("现金", 0)
    total = sum(h.values())
    if total <= 0:
        flags.append({"severity": "error", "code": "empty", "message": "持仓为空或占比为 0"})
        return {"ok": False, "flags": flags, "metrics": {}}

    # 归一化到 100（允许用户输入总和略偏离）
    scale = 100.0 / total if total != 100 else 1.0
    if abs(total - 100) > 2 and scale != 1.0:
        flags.append({
            "severity": "warn",
            "code": "total_not_100",
            "message": f"持仓占比合计 {total:.1f}% ≠ 100%，已按比例归一化检查",
        })
        h = {k: v * scale for k, v in h.items()}
        equity = {k: v for k, v in h.items() if k not in ("CASH", "现金")}
        cash = h.get("CASH", 0) + h.get("现金", 0)

    sorted_pos = sorted(equity.items(), key=lambda x: -x[1])
    top1 = sorted_pos[0][1] if sorted_pos else 0
    top3 = sum(v for _, v in sorted_pos[:3])
    n_pos = len([v for v in equity.values() if v > 0])

    metrics = {
        "position_count": n_pos,
        "cash_pct": round(cash, 2),
        "top1_ticker": sorted_pos[0][0] if sorted_pos else None,
        "top1_pct": round(top1, 2),
        "top3_pct": round(top3, 2),
        "theme_exposure": theme_exposure(h, themes),
    }

    if top1 > rules["max_single_pct"]:
        flags.append({
            "severity": "fail",
            "code": "concentration_single",
            "message": f"第一大持仓 {sorted_pos[0][0]} {top1:.1f}% > 上限 {rules['max_single_pct']}%",
        })
    elif top1 > rules["warn_single_pct"]:
        flags.append({
            "severity": "warn",
            "code": "concentration_single_warn",
            "message": f"第一大持仓 {sorted_pos[0][0]} {top1:.1f}% 接近上限",
        })

    if top3 > rules["max_top3_pct"]:
        flags.append({
            "severity": "warn",
            "code": "concentration_top3",
            "message": f"前三大持仓合计 {top3:.1f}% > 建议 {rules['max_top3_pct']}%",
        })

    if cash < rules["min_cash_pct"]:
        flags.append({
            "severity": "warn",
            "code": "cash_low",
            "message": f"现金占比 {cash:.1f}% < 建议 {rules['min_cash_pct']}%",
        })

    if n_pos > rules["max_positions"]:
        flags.append({
            "severity": "warn",
            "code": "too_many_positions",
            "message": f"持仓数量 {n_pos} > 建议上限 {rules['max_positions']}",
        })

    for theme, pct in metrics["theme_exposure"].items():
        if pct > rules["max_theme_pct"]:
            flags.append({
                "severity": "warn",
                "code": "theme_concentration",
                "message": f"主题/分组 {theme} 暴露 {pct:.1f}% > {rules['max_theme_pct']}%",
            })

    # 相关性：仅当持仓映射到 CSV 列
    if corr_pairs:
        held_cols = []
        for ticker in equity:
            for col, mapped in CORR_TICKER_MAP.items():
                if _norm_ticker(ticker) == _norm_ticker(mapped) or ticker == col:
                    held_cols.append(col)
        held_cols = list(dict.fromkeys(held_cols))
        for i, c1 in enumerate(held_cols):
            for c2 in held_cols[i + 1:]:
                key = f"{c1}/{c2}"
                alt = f"{c2}/{c1}"
                r = corr_pairs.get(key) or corr_pairs.get(alt)
                if r is not None and abs(r) >= rules["high_corr_threshold"]:
                    flags.append({
                        "severity": "warn",
                        "code": "high_correlation",
                        "message": f"{c1} 与 {c2} 近期相关性 {r:.2f}（共振风险）",
                    })

    if proposed:
        t, p = _norm_ticker(proposed[0]), float(proposed[1])
        new_pct = h.get(t, 0)
        if new_pct > rules["max_single_pct"]:
            flags.append({
                "severity": "fail",
                "code": "proposed_over_limit",
                "message": f"若加仓 {t} {p}% 后，{t} 合计将达 {new_pct:.1f}%，超过单票上限",
            })

    ok = not any(f["severity"] == "fail" for f in flags)
    return {"ok": ok, "flags": flags, "metrics": metrics}


def print_report(result: dict):
    print("=" * 60)
    print("组合风险检查 (Portfolio Risk)")
    print("=" * 60)
    m = result["metrics"]
    print(f"  持仓数: {m.get('position_count')}  |  现金: {m.get('cash_pct')}%")
    print(f"  第一大: {m.get('top1_ticker')} {m.get('top1_pct')}%  |  前三合计: {m.get('top3_pct')}%")
    if m.get("theme_exposure"):
        print("  主题暴露:", ", ".join(f"{k}={v:.1f}%" for k, v in m["theme_exposure"].items()))
    print()
    if not result["flags"]:
        print("  ✅ 无风险告警")
    else:
        for f in result["flags"]:
            icon = {"fail": "❌", "warn": "⚠️", "error": "❌"}.get(f["severity"], "•")
            print(f"  {icon} [{f['code']}] {f['message']}")
    print()
    print(f"  总体: {'✅ 通过' if result['ok'] else '❌ 存在硬约束违规'}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="组合风险检查（Risk Manager 层）")
    parser.add_argument("--holdings", help="JSON 对象，如 '{\"NVDA\":25,\"CASH\":15}'")
    parser.add_argument("--holdings-file", help="持仓 JSON 文件路径")
    parser.add_argument("--proposed", nargs=2, metavar=("TICKER", "PCT"), help="模拟加仓")
    parser.add_argument("--correlation", default=DEFAULT_CORR, help="相关性 CSV 路径")
    parser.add_argument("--no-correlation", action="store_true", help="跳过相关性检查")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    if args.holdings_file:
        holdings = load_holdings_file(args.holdings_file)
    elif args.holdings:
        holdings = parse_holdings(json.loads(args.holdings))
    elif os.path.exists(DEFAULT_HOLDINGS_FILE):
        holdings = load_holdings_file(DEFAULT_HOLDINGS_FILE)
    else:
        parser.error("需要 --holdings、--holdings-file，或创建 data/holdings.json")
        return

    corr = None if args.no_correlation else load_latest_correlations(args.correlation)
    proposed = (args.proposed[0], float(args.proposed[1])) if args.proposed else None

    result = check_holdings(holdings, corr_pairs=corr, proposed=proposed)
    result["timestamp"] = datetime.now().isoformat()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_report(result)

    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()

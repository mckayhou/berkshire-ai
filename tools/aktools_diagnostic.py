#!/usr/bin/env python3
"""aktools-pro 原子 API 复合诊断（避开有 bug 的 composite_stock_diagnostic）。

当 BERKSHIRE_ENABLE_AKTOOLS=1 且本地 aktools 服务可用时，并行拉取：
  - market_prices（行情 + 技术指标）
  - stock_news（近期新闻）
  - stock_info（基本信息，可选）

全部失败时返回 ok=False，不抛崩主流程。

用法
----
    export BERKSHIRE_ENABLE_AKTOOLS=1
    python3 tools/aktools_diagnostic.py AAPL
    python3 tools/aktools_diagnostic.py 600519 --json
    python3 tools/aktools_diagnostic.py MSFT -o reports/msft_diag.md
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Tuple

FetchFn = Callable[[str, Dict[str, str]], Any]


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def aktools_base_url() -> str:
    return os.environ.get(
        "BERKSHIRE_AKTOOLS_BASE_URL", "http://127.0.0.1:8080"
    ).rstrip("/")


def aktools_enabled() -> Tuple[bool, str]:
    if not _env_truthy("BERKSHIRE_ENABLE_AKTOOLS"):
        return False, "set BERKSHIRE_ENABLE_AKTOOLS=1"
    return True, ""


def infer_market(symbol: str) -> str:
    s = symbol.strip().upper()
    if s.endswith(".HK") or (s.isdigit() and len(s) == 5):
        return "hk"
    if s.isdigit() and len(s) == 6:
        return "sh" if s.startswith(("6", "9", "5")) else "sz"
    return "us"


def normalize_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    for suffix in (".SH", ".SZ", ".HK"):
        if s.endswith(suffix):
            return s[: -len(suffix)]
    return s


def default_fetch(path: str, params: Dict[str, str]) -> Any:
    qs = urllib.parse.urlencode(params)
    url = f"{aktools_base_url()}{path}?{qs}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def _extract_rows(data: Any) -> List[Dict]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("data", "prices", "items", "result", "news"):
            val = data.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        if data.get("ok") is False:
            return []
    return []


def fetch_prices(
    symbol: str,
    *,
    market: str,
    limit: int = 30,
    fetch: FetchFn = default_fetch,
) -> Dict[str, Any]:
    try:
        data = fetch(
            "/api/public/market_prices",
            {
                "symbol": symbol,
                "market": market,
                "asset": "equity",
                "limit": str(limit),
            },
        )
        rows = _extract_rows(data)
        if not rows:
            return {"ok": False, "error": "empty prices", "data": None}
        last = rows[-1]
        return {"ok": True, "data": last, "rows": len(rows)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "data": None}


def fetch_news(
    symbol: str,
    *,
    limit: int = 5,
    fetch: FetchFn = default_fetch,
) -> Dict[str, Any]:
    try:
        data = fetch(
            "/api/public/stock_news",
            {"symbol": symbol, "limit": str(limit)},
        )
        rows = _extract_rows(data)
        if not rows and isinstance(data, str) and data.strip():
            return {"ok": True, "data": data.strip(), "count": 1}
        if not rows:
            return {"ok": False, "error": "empty news", "data": None}
        return {"ok": True, "data": rows[:limit], "count": len(rows)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "data": None}


def fetch_info(
    symbol: str,
    *,
    market: str,
    fetch: FetchFn = default_fetch,
) -> Dict[str, Any]:
    try:
        data = fetch(
            "/api/public/stock_info",
            {"symbol": symbol, "market": market},
        )
        if isinstance(data, dict) and data:
            return {"ok": True, "data": data}
        return {"ok": False, "error": "empty info", "data": None}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "data": None}


def composite_diagnostic(
    symbol: str,
    *,
    fetch: FetchFn = default_fetch,
    price_limit: int = 30,
    news_limit: int = 5,
) -> Dict[str, Any]:
    """原子 API 组装复合诊断；至少一项成功则 ok=True。"""
    enabled, reason = aktools_enabled()
    if not enabled:
        return {
            "ok": False,
            "symbol": symbol,
            "error": reason,
            "sections": {},
        }

    market = infer_market(symbol)
    code = normalize_symbol(symbol)
    prices = fetch_prices(code, market=market, limit=price_limit, fetch=fetch)
    news = fetch_news(code, limit=news_limit, fetch=fetch)
    info = fetch_info(code, market=market, fetch=fetch)

    sections = {"prices": prices, "news": news, "info": info}
    any_ok = any(s.get("ok") for s in sections.values())
    return {
        "ok": any_ok,
        "symbol": symbol,
        "market": market,
        "code": code,
        "sections": sections,
        "error": None if any_ok else "all atomic fetches failed",
    }


def _fmt_price_section(sec: Dict[str, Any]) -> List[str]:
    if not sec.get("ok"):
        return [f"- 行情: 失败 ({sec.get('error', '?')})"]
    bar = sec.get("data") or {}
    close = bar.get("close") or bar.get("Close") or bar.get("price")
    date = bar.get("date") or bar.get("trade_date") or ""
    rsi = bar.get("rsi") or bar.get("RSI")
    lines = [f"- 最新收盘: {close} ({date})" if close else "- 最新收盘: —"]
    if rsi is not None:
        lines.append(f"- RSI: {rsi}")
    lines.append(f"- K线条数: {sec.get('rows', '—')}")
    return lines


def _fmt_news_section(sec: Dict[str, Any]) -> List[str]:
    if not sec.get("ok"):
        return [f"- 新闻: 失败 ({sec.get('error', '?')})"]
    data = sec.get("data")
    lines = ["- 近期新闻:"]
    if isinstance(data, str):
        lines.append(f"  - {data[:200]}")
        return lines
    for item in data[:5]:
        title = item.get("title") or item.get("headline") or str(item)[:80]
        lines.append(f"  - {title}")
    return lines


def _fmt_info_section(sec: Dict[str, Any]) -> List[str]:
    if not sec.get("ok"):
        return [f"- 基本信息: 失败 ({sec.get('error', '?')})"]
    info = sec.get("data") or {}
    name = info.get("name") or info.get("short_name") or info.get("symbol")
    industry = info.get("industry") or info.get("sector")
    lines = [f"- 名称: {name or '—'}"]
    if industry:
        lines.append(f"- 行业: {industry}")
    return lines


def render_markdown(report: Dict[str, Any]) -> str:
    sym = report.get("symbol", "")
    lines = [
        f"# {sym} 诊断摘要（aktools 原子 API）",
        "",
        f"市场: {report.get('market', '—')} | 代码: {report.get('code', sym)}",
        "",
        "## 技术面",
        *_fmt_price_section(report.get("sections", {}).get("prices", {})),
        "",
        "## 消息面",
        *_fmt_news_section(report.get("sections", {}).get("news", {})),
        "",
        "## 基本面",
        *_fmt_info_section(report.get("sections", {}).get("info", {})),
    ]
    if not report.get("ok"):
        lines.extend(["", f"> ⚠️ {report.get('error', '无数据')}"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="aktools 原子 API 复合诊断")
    parser.add_argument("symbol", help="股票代码")
    parser.add_argument("-o", "--output", help="写入 Markdown 文件")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    report = composite_diagnostic(args.symbol)
    if args.json:
        text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    else:
        text = render_markdown(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"已写入 {args.output}")
    else:
        print(text)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""A股数据「多源降级」获取层 — 可插拔适配器 + 优先级降级链。

设计理念（吸收自 JusticePlutus 的工程范式）：
  1. 多源降级链：按优先级依次尝试数据源，任一源失败自动降级到下一个，
     全部失败时返回明确的「空/错误」结构（ok=False），**绝不抛崩主流程**。
  2. 可选增强 / 失败降级 / 零侵入：
     - 需第三方库的源（tushare/efinance/akshare/baostock/yfinance）全部用
       **import 守卫**（try/except ImportError），缺库时静默跳过该源；
     - 「增强源」（如需要 token 的 Tushare Pro）由环境变量开关控制：
       开关关闭 → 完全不初始化、不导入、不请求；
       开关打开但缺 token → 只记 warning 并回退，不报错；
     - 零配置时行为与改造前一致：只用内置零依赖源（东方财富/腾讯 curl）。

默认优先级（可用 BERKSHIRE_DATA_SOURCES 覆盖）：
    native(内置,零依赖) → tushare(增强,需开关+token) → efinance
      → akshare → baostock → yfinance

返回结构（统一 schema）：
    {
      "ok": bool,                # 是否成功取到非空数据
      "kind": "daily"|"quote"|"fundamentals",
      "code": str,
      "source": str | None,      # 成功的源名；全失败为 None
      "data": list|dict|None,    # daily→list[dict]；quote/fundamentals→dict
      "attempts": [ {"source","ok","skipped","error"}, ... ],
      "error": str | None,       # 全失败时给出原因
    }

用法（CLI）：
    python3 tools/data_sources.py sources                 # 列出各源状态
    python3 tools/data_sources.py daily 600519 --limit 60 # 日线（降级链）
    python3 tools/data_sources.py quote 600519            # 实时行情
    python3 tools/data_sources.py fundamentals 600519     # 基本面字段
    # 可加 --json 输出原始结构；--sources native,efinance 指定/排序源
"""

import argparse
import json
import os
import sys

# 内置零依赖源复用 ashare_data（curl 直连东方财富/腾讯）。
try:
    import ashare_data as _ashare
except ImportError:  # pragma: no cover - 仅在被异常导入路径时触发
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ashare_data as _ashare


def _log_warn(msg: str) -> None:
    """轻量 warning：写 stderr，不依赖 logging 配置。"""
    sys.stderr.write(f"[data_sources] WARNING: {msg}\n")


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


class NotSupported(Exception):
    """适配器不支持该数据种类（用于优雅跳过，不算错误）。"""


# ---------------------------------------------------------------------------
# 适配器基类
# ---------------------------------------------------------------------------
class DataSource:
    """可插拔数据源适配器基类。

    子类至少实现 enabled() 与所支持的 daily/quote/fundamentals 之一；
    不支持的种类保持默认实现（抛 NotSupported），会被降级链优雅跳过。
    """

    name = "base"
    requires = ()          # 该源所需的可选 pip 包（仅用于文档/状态展示）
    needs_network = True

    def enabled(self):
        """返回 (是否可用, 原因)。不可用时 reason 说明缺什么。"""
        return True, ""

    def daily(self, code, limit=250):
        raise NotSupported(f"{self.name} 不支持 daily")

    def quote(self, code):
        raise NotSupported(f"{self.name} 不支持 quote")

    def fundamentals(self, code):
        raise NotSupported(f"{self.name} 不支持 fundamentals")


# ---------------------------------------------------------------------------
# 1) 内置源：东方财富 / 腾讯（curl，零第三方依赖，始终可用）
# ---------------------------------------------------------------------------
class NativeSource(DataSource):
    name = "native"
    requires = ()          # 仅依赖系统 curl

    def enabled(self):
        if _env_truthy("BERKSHIRE_DISABLE_NATIVE"):
            return False, "disabled by BERKSHIRE_DISABLE_NATIVE"
        return True, ""

    def daily(self, code, limit=250):
        return _ashare.fetch_daily(code, limit=limit)

    def quote(self, code):
        raw = _ashare._curl(f"https://qt.gtimg.cn/q={_ashare._qq_code(code)}")
        return _ashare._parse_qq_quote(raw)

    def fundamentals(self, code):
        # 复用 cmd_financials 的取数逻辑，返回结构化最近一期年报关键字段。
        code_clean = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
        market = "SH" if code_clean.startswith(("6", "9", "5")) else "SZ"
        url = "https://datacenter.eastmoney.com/securities/api/data/get"
        params = {
            "type": "RPT_F10_FINANCE_MAINFINADATA", "sty": "ALL",
            "filter": f'(SECUCODE="{code_clean}.{market}")(REPORT_TYPE="年报")',
            "p": "1", "ps": "5", "sr": "-1", "st": "REPORT_DATE",
            "source": "HSF10", "client": "PC",
        }
        data = _ashare._curl_json(url, params)
        reports = (data or {}).get("result", {}).get("data", []) or []
        if not reports:
            return {}
        r = reports[0]
        return {
            "report_date": r.get("REPORT_DATE", "")[:10],
            "report_name": r.get("REPORT_DATE_NAME", ""),
            "revenue": r.get("TOTALOPERATEREVE"),
            "net_profit": r.get("PARENTNETPROFIT"),
            "eps": r.get("EPSJB"),
            "bps": r.get("BPS"),
            "roe": r.get("ROEJQ"),
            "revenue_growth": r.get("TOTALOPERATEREVETZ"),
            "profit_growth": r.get("PARENTNETPROFITTZ"),
        }


# ---------------------------------------------------------------------------
# 2) 增强源：Tushare Pro（需开关 + token；零配置时完全不初始化）
# ---------------------------------------------------------------------------
class TushareSource(DataSource):
    name = "tushare"
    requires = ("tushare",)

    def _pro(self):
        import tushare as ts  # 延迟导入：开关关闭时永不触发
        token = os.environ.get("TUSHARE_TOKEN", "").strip()
        ts.set_token(token)
        return ts.pro_api(token)

    def enabled(self):
        # 「增强源」范式：默认关闭，需显式开关。关闭即零侵入。
        if not _env_truthy("BERKSHIRE_ENABLE_TUSHARE"):
            return False, "disabled (set BERKSHIRE_ENABLE_TUSHARE=1 to enable)"
        try:
            import tushare  # noqa: F401
        except ImportError:
            return False, "tushare not installed (pip install tushare)"
        if not os.environ.get("TUSHARE_TOKEN", "").strip():
            _log_warn("BERKSHIRE_ENABLE_TUSHARE=1 但未设置 TUSHARE_TOKEN，跳过 tushare")
            return False, "TUSHARE_TOKEN not set"
        return True, ""

    def _ts_code(self, code):
        c = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
        if c.startswith(("6", "9", "5")):
            return f"{c}.SH"
        if c.startswith(("4", "8")):
            return f"{c}.BJ"
        return f"{c}.SZ"

    def daily(self, code, limit=250):
        pro = self._pro()
        df = pro.daily(ts_code=self._ts_code(code))
        if df is None or len(df) == 0:
            return []
        df = df.sort_values("trade_date").tail(limit)
        out = []
        for _, row in df.iterrows():
            out.append({
                "date": str(row.get("trade_date")),
                "open": row.get("open"), "close": row.get("close"),
                "high": row.get("high"), "low": row.get("low"),
                "volume": row.get("vol"),
            })
        return out


# ---------------------------------------------------------------------------
# 3) efinance
# ---------------------------------------------------------------------------
class EfinanceSource(DataSource):
    name = "efinance"
    requires = ("efinance",)

    def enabled(self):
        if _env_truthy("BERKSHIRE_DISABLE_EFINANCE"):
            return False, "disabled by BERKSHIRE_DISABLE_EFINANCE"
        try:
            import efinance  # noqa: F401
        except ImportError:
            return False, "efinance not installed (pip install efinance)"
        return True, ""

    def daily(self, code, limit=250):
        import efinance as ef
        c = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
        df = ef.stock.get_quote_history(c)
        if df is None or len(df) == 0:
            return []
        df = df.tail(limit)
        out = []
        for _, row in df.iterrows():
            out.append({
                "date": str(row.get("日期")),
                "open": row.get("开盘"), "close": row.get("收盘"),
                "high": row.get("最高"), "low": row.get("最低"),
                "volume": row.get("成交量"),
            })
        return out


# ---------------------------------------------------------------------------
# 4) akshare
# ---------------------------------------------------------------------------
class AkshareSource(DataSource):
    name = "akshare"
    requires = ("akshare",)

    def enabled(self):
        if _env_truthy("BERKSHIRE_DISABLE_AKSHARE"):
            return False, "disabled by BERKSHIRE_DISABLE_AKSHARE"
        try:
            import akshare  # noqa: F401
        except ImportError:
            return False, "akshare not installed (pip install akshare)"
        return True, ""

    def daily(self, code, limit=250):
        import akshare as ak
        c = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
        df = ak.stock_zh_a_hist(symbol=c, period="daily", adjust="")
        if df is None or len(df) == 0:
            return []
        df = df.tail(limit)
        out = []
        for _, row in df.iterrows():
            out.append({
                "date": str(row.get("日期")),
                "open": row.get("开盘"), "close": row.get("收盘"),
                "high": row.get("最高"), "low": row.get("最低"),
                "volume": row.get("成交量"),
            })
        return out


# ---------------------------------------------------------------------------
# 5) baostock
# ---------------------------------------------------------------------------
class BaostockSource(DataSource):
    name = "baostock"
    requires = ("baostock",)

    def enabled(self):
        if _env_truthy("BERKSHIRE_DISABLE_BAOSTOCK"):
            return False, "disabled by BERKSHIRE_DISABLE_BAOSTOCK"
        try:
            import baostock  # noqa: F401
        except ImportError:
            return False, "baostock not installed (pip install baostock)"
        return True, ""

    def _bs_code(self, code):
        c = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
        if c.startswith(("6", "9", "5")):
            return f"sh.{c}"
        return f"sz.{c}"

    def daily(self, code, limit=250):
        import baostock as bs
        bs.login()
        try:
            rs = bs.query_history_k_data_plus(
                self._bs_code(code),
                "date,open,high,low,close,volume",
                frequency="d", adjustflag="3",
            )
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
        finally:
            bs.logout()
        rows = rows[-limit:]
        out = []
        for r in rows:
            out.append({
                "date": r[0], "open": r[1], "high": r[2],
                "low": r[3], "close": r[4], "volume": r[5],
            })
        return out


# ---------------------------------------------------------------------------
# 6) yfinance（兜底，A股需 .SS/.SZ 后缀）
# ---------------------------------------------------------------------------
class YFinanceSource(DataSource):
    name = "yfinance"
    requires = ("yfinance",)

    def enabled(self):
        if _env_truthy("BERKSHIRE_DISABLE_YFINANCE"):
            return False, "disabled by BERKSHIRE_DISABLE_YFINANCE"
        try:
            import yfinance  # noqa: F401
        except ImportError:
            return False, "yfinance not installed (pip install yfinance)"
        return True, ""

    def _yf_symbol(self, code):
        c = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
        if c.startswith(("6", "9", "5")):
            return f"{c}.SS"
        return f"{c}.SZ"

    def daily(self, code, limit=250):
        import yfinance as yf
        t = yf.Ticker(self._yf_symbol(code))
        hist = t.history(period="1y")
        if hist is None or len(hist) == 0:
            return []
        hist = hist.tail(limit)
        out = []
        for idx, row in hist.iterrows():
            out.append({
                "date": str(getattr(idx, "date", lambda: idx)()),
                "open": row.get("Open"), "close": row.get("Close"),
                "high": row.get("High"), "low": row.get("Low"),
                "volume": row.get("Volume"),
            })
        return out


# ---------------------------------------------------------------------------
# 可选：aktools-pro HTTP 后端（需 BERKSHIRE_ENABLE_AKTOOLS=1 + 本地服务）
# ---------------------------------------------------------------------------
class AktoolsSource(DataSource):
    name = "aktools"
    requires = ()  # HTTP only

    def _base(self) -> str:
        return os.environ.get(
            "BERKSHIRE_AKTOOLS_BASE_URL", "http://127.0.0.1:8080"
        ).rstrip("/")

    def enabled(self):
        if not _env_truthy("BERKSHIRE_ENABLE_AKTOOLS"):
            return False, "disabled (set BERKSHIRE_ENABLE_AKTOOLS=1)"
        return True, ""

    def _get_json(self, path: str, params: dict) -> dict:
        import urllib.parse
        import urllib.request

        qs = urllib.parse.urlencode(params)
        url = f"{self._base()}{path}?{qs}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def daily(self, code, limit=250):
        try:
            data = self._get_json(
                "/api/public/market_prices",
                {"symbol": code, "asset": "stock", "limit": str(limit)},
            )
        except Exception as e:  # noqa: BLE001
            raise NotSupported(f"aktools daily failed: {e}") from e
        rows = data if isinstance(data, list) else data.get("data") or data.get("prices") or []
        out = []
        for bar in rows[-limit:]:
            if not isinstance(bar, dict):
                continue
            nd = bar.get("date") or bar.get("trade_date")
            close = bar.get("close") or bar.get("Close")
            if nd is None or close is None:
                continue
            out.append({"date": str(nd)[:10], "close": close})
        if not out:
            raise NotSupported("aktools returned empty daily")
        return out


# ---------------------------------------------------------------------------
# 注册表 + 降级链
# ---------------------------------------------------------------------------
# 默认优先级：内置零依赖源最先（保证零配置可用），增强/第三方源依次兜底。
_REGISTRY = {
    cls.name: cls for cls in (
        NativeSource, AktoolsSource, TushareSource, EfinanceSource,
        AkshareSource, BaostockSource, YFinanceSource,
    )
}
_DEFAULT_ORDER = [
    "native", "aktools", "tushare", "efinance", "akshare", "baostock", "yfinance",
]


def _resolve_order(sources=None):
    """确定降级链顺序：显式参数 > 环境变量 BERKSHIRE_DATA_SOURCES > 默认。"""
    if sources is None:
        env = os.environ.get("BERKSHIRE_DATA_SOURCES", "").strip()
        if env:
            sources = [s.strip() for s in env.split(",") if s.strip()]
    if not sources:
        sources = list(_DEFAULT_ORDER)
    order = []
    for name in sources:
        if name in _REGISTRY and name not in order:
            order.append(name)
        elif name not in _REGISTRY:
            _log_warn(f"未知数据源 '{name}'，忽略")
    return order


def build_chain(sources=None):
    """实例化降级链（按解析后的顺序）。"""
    return [_REGISTRY[name]() for name in _resolve_order(sources)]


def _is_empty(data):
    if data is None:
        return True
    if isinstance(data, (list, dict, str)) and len(data) == 0:
        return True
    return False


def fetch(kind, code, sources=None, limit=250):
    """按降级链获取数据。kind ∈ {daily, quote, fundamentals}。

    任一源失败/为空自动降级；全部失败返回 ok=False 的明确结构，不抛异常。
    """
    if kind not in ("daily", "quote", "fundamentals"):
        return {"ok": False, "kind": kind, "code": code, "source": None,
                "data": None, "attempts": [], "error": f"unsupported kind: {kind}"}

    attempts = []
    for src in build_chain(sources):
        ok_enabled, reason = src.enabled()
        if not ok_enabled:
            attempts.append({"source": src.name, "ok": False,
                             "skipped": True, "error": reason})
            continue
        try:
            method = getattr(src, kind)
            data = method(code, limit=limit) if kind == "daily" else method(code)
        except NotSupported as e:
            attempts.append({"source": src.name, "ok": False,
                             "skipped": True, "error": str(e)})
            continue
        except Exception as e:  # 网络/解析/库内部异常 → 降级，不崩
            attempts.append({"source": src.name, "ok": False,
                             "skipped": False,
                             "error": f"{type(e).__name__}: {e}"})
            continue
        if _is_empty(data):
            attempts.append({"source": src.name, "ok": False,
                             "skipped": False, "error": "empty result"})
            continue
        attempts.append({"source": src.name, "ok": True})
        return {"ok": True, "kind": kind, "code": code, "source": src.name,
                "data": data, "attempts": attempts, "error": None}

    return {"ok": False, "kind": kind, "code": code, "source": None,
            "data": None, "attempts": attempts,
            "error": "所有数据源均失败或不可用"}


def daily(code, sources=None, limit=250):
    return fetch("daily", code, sources=sources, limit=limit)


def quote(code, sources=None):
    return fetch("quote", code, sources=sources)


def fundamentals(code, sources=None):
    return fetch("fundamentals", code, sources=sources)


def source_status(sources=None):
    """返回各源的可用状态（不发起任何网络请求）。"""
    out = []
    for src in build_chain(sources):
        ok, reason = src.enabled()
        out.append({
            "source": src.name,
            "enabled": ok,
            "reason": reason or "ok",
            "requires": list(src.requires),
            "needs_network": src.needs_network,
        })
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_status(rows):
    print("=" * 64)
    print("数据源降级链状态（优先级从上到下）")
    print("=" * 64)
    for i, r in enumerate(rows, 1):
        flag = "✅" if r["enabled"] else "⏭️ "
        req = ",".join(r["requires"]) or "无(stdlib/curl)"
        print(f"  {i}. {flag} {r['source']:<10} 依赖: {req}")
        if not r["enabled"]:
            print(f"       ↳ {r['reason']}")


def _print_result(res):
    if not res["ok"]:
        print(f"❌ 获取失败 [{res['kind']} {res['code']}]: {res['error']}")
    else:
        print(f"✅ 来源: {res['source']} | {res['kind']} {res['code']}")
    print("--- 尝试记录 ---")
    for a in res["attempts"]:
        mark = "OK" if a["ok"] else ("SKIP" if a.get("skipped") else "FAIL")
        line = f"  [{mark}] {a['source']}"
        if a.get("error"):
            line += f" — {a['error']}"
        print(line)
    if res["ok"]:
        data = res["data"]
        print("--- 数据 ---")
        if isinstance(data, list):
            print(f"  {len(data)} 条记录；末条: {data[-1] if data else '-'}")
        else:
            print(f"  {data}")


def main():
    parser = argparse.ArgumentParser(
        description="A股数据多源降级获取层",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("sources", help="列出降级链各源状态")

    for kind, help_text in (("daily", "日线"), ("quote", "实时行情"),
                            ("fundamentals", "基本面字段")):
        p = sub.add_parser(kind, help=help_text)
        p.add_argument("code", help="股票代码，如 600519")
        p.add_argument("--sources", help="逗号分隔指定/排序源，如 native,efinance")
        if kind == "daily":
            p.add_argument("--limit", type=int, default=60, help="返回条数")
        p.add_argument("--json", action="store_true", help="输出原始 JSON 结构")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    src_list = None
    if getattr(args, "sources", None):
        src_list = [s.strip() for s in args.sources.split(",") if s.strip()]

    if args.command == "sources":
        rows = source_status(src_list)
        if "--json" in sys.argv:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            _print_status(rows)
        return

    if args.command == "daily":
        res = daily(args.code, sources=src_list, limit=args.limit)
    else:
        res = fetch(args.command, args.code, sources=src_list)

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    else:
        _print_result(res)


if __name__ == "__main__":
    main()

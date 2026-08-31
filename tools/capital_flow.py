#!/usr/bin/env python3
"""A 股资金行为分析 — 股东户数 / 融资融券 / 大宗 / 龙虎榜 / 机构 / 北向。

零外部依赖（stdlib + curl）。数据来自东方财富公开 datacenter，失败的模块记 missing，
不伪装成功。打分函数纯离线，可供单测注入。

用法（Skills 调用）：
    python3 tools/capital_flow.py score 600519
    python3 tools/capital_flow.py score 600519 --json
    python3 tools/capital_flow.py holders 600519
    python3 tools/capital_flow.py margin 600519
    python3 tools/capital_flow.py block 600519
    python3 tools/capital_flow.py lhb 600519
    python3 tools/capital_flow.py inst 600519
    python3 tools/capital_flow.py north 600519

这不是 PDF 里的 Streamlit 产品：无看板、无预测模型。结论供 Deep Research /
Thesis Tracker / news-pulse 引用。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Sequence
from urllib.parse import urlencode

_TIMEOUT = 15
_RETRIES = 2
_EM = "https://datacenter-web.eastmoney.com/api/data/v1/get"

FetchFn = Callable[..., List[Dict[str, Any]]]


def _force_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _norm_code(code: str) -> str:
    raw = str(code).strip().upper()
    for suf in (".SH", ".SZ", ".BJ", ".SS"):
        if raw.endswith(suf):
            raw = raw[: -len(suf)]
    if raw.startswith(("SH", "SZ", "BJ")) and len(raw) > 2 and raw[2:].isdigit():
        raw = raw[2:]
    return raw


def _secid(code: str) -> str:
    c = _norm_code(code)
    if c.startswith(("6", "9", "5")):
        return f"1.{c}"
    if c.startswith(("0", "3", "2", "1")):
        return f"0.{c}"
    if c.startswith(("4", "8")):
        return f"0.{c}"
    return f"1.{c}"


def _curl(url: str, retries: int = _RETRIES) -> str:
    last = None
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                [
                    "/usr/bin/curl",
                    "-s",
                    "--noproxy",
                    "*",
                    "-H",
                    "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                    url,
                ],
                capture_output=True,
                timeout=_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            last = f"请求超时 (>{_TIMEOUT}s)"
            time.sleep(0.5 * (attempt + 1))
            continue
        if result.returncode != 0 or not result.stdout.strip():
            last = "请求失败或空响应"
            time.sleep(0.5 * (attempt + 1))
            continue
        try:
            return result.stdout.decode("utf-8")
        except UnicodeDecodeError:
            return result.stdout.decode("gbk", errors="replace")
    raise ConnectionError(last or "请求失败")


def em_rows(
    report_name: str,
    code: str,
    *,
    filter_tpl: str = '(SECURITY_CODE="{code}")',
    sort_columns: str = "",
    sort_types: str = "-1",
    page_size: int = 20,
    extra: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """东方财富 datacenter 列表。网络失败抛 ConnectionError。"""
    code = _norm_code(code)
    params = {
        "reportName": report_name,
        "columns": "ALL",
        "filter": filter_tpl.format(code=code),
        "pageNumber": "1",
        "pageSize": str(page_size),
        "source": "WEB",
        "client": "WEB",
    }
    if sort_columns:
        params["sortColumns"] = sort_columns
        params["sortTypes"] = sort_types
    if extra:
        params.update(extra)
    payload = json.loads(_curl(f"{_EM}?{urlencode(params)}"))
    result = payload.get("result") or {}
    data = result.get("data")
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def _num(row: Dict[str, Any], *keys: str, default: Optional[float] = None) -> Optional[float]:
    for k in keys:
        if k not in row:
            continue
        v = row[k]
        if v in (None, "", "-"):
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return default


def _str(row: Dict[str, Any], *keys: str, default: str = "") -> str:
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return str(v)
    return default


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _signal(score: Optional[float]) -> str:
    if score is None:
        return "缺失"
    if score >= 65:
        return "偏多"
    if score <= 35:
        return "偏空"
    return "中性"


# ---------------------------------------------------------------------------
# 纯函数打分（离线）
# ---------------------------------------------------------------------------


def score_holders(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """户数下降 = 筹码集中 = 偏多。"""
    if len(rows) < 2:
        return {"ok": False, "reason": "股东户数不足两期"}
    latest, prev = rows[0], rows[1]
    n0 = _num(latest, "HOLDER_TOTAL_NUM", "HOLDER_NUM", "HOLD_NUM")
    n1 = _num(prev, "HOLDER_TOTAL_NUM", "HOLDER_NUM", "HOLD_NUM")
    if n0 is None or n1 is None or n1 == 0:
        return {"ok": False, "reason": "股东户数字段缺失"}
    chg = (n0 - n1) / abs(n1)
    score = _clip(50.0 - chg * 500.0)
    flags = []
    if chg <= -0.10:
        flags.append("筹码快速集中（户数降超10%）")
    elif chg >= 0.10:
        flags.append("筹码快速分散（户数升超10%）")
    return {
        "ok": True,
        "score": round(score, 1),
        "latest": n0,
        "prev": n1,
        "change_pct": round(chg * 100, 2),
        "as_of": _str(latest, "END_DATE", "HOLD_END_DATE", "REPORT_DATE"),
        "flags": flags,
    }


def score_margin(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """融资余额上升 = 杠杆做多 = 偏多。"""
    if len(rows) < 2:
        return {"ok": False, "reason": "融资融券不足两期"}
    latest, prev = rows[0], rows[1]
    z0 = _num(latest, "RZYE", "FIN_BALANCE", "MARGIN_BALANCE")
    z1 = _num(prev, "RZYE", "FIN_BALANCE", "MARGIN_BALANCE")
    if z0 is None or z1 is None or z1 == 0:
        return {"ok": False, "reason": "融资余额字段缺失"}
    chg = (z0 - z1) / abs(z1)
    score = _clip(50.0 + chg * 200.0)
    flags = []
    if chg >= 0.20:
        flags.append("融资余额急升（超20%，杠杆升温）")
    elif chg <= -0.20:
        flags.append("融资余额急降（超20%，杠杆回撤）")
    return {
        "ok": True,
        "score": round(score, 1),
        "latest": z0,
        "prev": z1,
        "change_pct": round(chg * 100, 2),
        "as_of": _str(latest, "DATE", "TRADE_DATE", "END_DATE"),
        "flags": flags,
    }


def score_block(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """近端大宗溢价买入 = 偏多。"""
    if not rows:
        return {"ok": False, "reason": "无大宗交易"}
    premia = [
        p
        for p in (_num(r, "PREMIUM_RATIO", "PREMIUM", "CHANGE_RATE") for r in rows[:8])
        if p is not None
    ]
    if not premia:
        return {"ok": False, "reason": "大宗溢价字段缺失"}
    avg = sum(premia) / len(premia)
    score = _clip(50.0 + avg * 5.0)
    flags = []
    if avg >= 5:
        flags.append("大宗显著溢价成交")
    elif avg <= -5:
        flags.append("大宗显著折价成交")
    return {
        "ok": True,
        "score": round(score, 1),
        "avg_premium_pct": round(avg, 2),
        "n": len(premia),
        "as_of": _str(rows[0], "TRADE_DATE", "DATE"),
        "flags": flags,
    }


def score_lhb(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """龙虎榜机构净买入占比高 = 偏多；游资主导记旗标。过旧数据不当成当前信号。"""
    if not rows:
        return {"ok": False, "reason": "无龙虎榜"}
    as_of = _str(rows[0], "TRADE_DATE", "DATE")
    year = as_of[:4]
    if year.isdigit() and int(year) < date.today().year - 1:
        return {"ok": False, "reason": f"该股最近上榜 {as_of[:10]}，并非没有公开龙虎榜"}

    if "OPERATEDEPT_NAME" not in rows[0] and "TOTAL_NET" in rows[0]:
        net = _num(rows[0], "TOTAL_NET") or 0.0
        buy = _num(rows[0], "TOTAL_BUY") or 0.0
        sell = _num(rows[0], "TOTAL_SELL") or 0.0
        denom = abs(buy) + abs(sell)
        if denom == 0:
            return {"ok": False, "reason": "龙虎榜净额为 0"}
        score = _clip(50.0 + (net / denom) * 50.0)
        flags = ["龙虎榜为合计净额（无席位明细）"]
        if net < 0:
            flags.append("上榜日合计净卖出")
        return {
            "ok": True,
            "score": round(score, 1),
            "inst_net": None,
            "retail_net": None,
            "total_net": round(net, 2),
            "as_of": as_of,
            "flags": flags,
        }

    inst_net = 0.0
    retail_net = 0.0
    for r in rows[:20]:
        net = _num(r, "NET_AMT", "NET", "BUY") or 0.0
        sell = _num(r, "SELL_AMT", "SELL", "ACT_SELL") or 0.0
        buy = _num(r, "ACT_BUY", "BUY") or 0.0
        if "NET_AMT" not in r and "NET" not in r:
            net = buy - sell
        name = _str(r, "OPERATEDEPT_NAME", "BUYER", "SECU_NAME", "ORG_NAME")
        if any(k in name for k in ("机构", "基金", "社保", "保险", "QFII", "券商自营")):
            inst_net += net
        else:
            retail_net += net
    total = abs(inst_net) + abs(retail_net)
    if total == 0:
        return {"ok": False, "reason": "龙虎榜净额为 0"}
    inst_share = inst_net / total
    score = _clip(50.0 + inst_share * 50.0)
    flags = []
    if abs(retail_net) > abs(inst_net) * 2 and retail_net > 0:
        flags.append("游资主导买入（非机构）")
    if inst_net < 0 and abs(inst_net) > abs(retail_net):
        flags.append("机构席位净卖出")
    return {
        "ok": True,
        "score": round(score, 1),
        "inst_net": round(inst_net, 2),
        "retail_net": round(retail_net, 2),
        "as_of": as_of,
        "flags": flags,
    }


def score_inst(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """机构持股比例上升 = 偏多。"""
    if len(rows) < 2:
        return {"ok": False, "reason": "机构持仓不足两期"}
    latest, prev = rows[0], rows[1]
    p0 = _num(latest, "HOLD_RATIO_TOTAL", "HOLD_RATIO", "TOTAL_SHARES_RATIO", "FREE_HOLD_RATIO", "HOLD_VALUE_RATIO")
    p1 = _num(prev, "HOLD_RATIO_TOTAL", "HOLD_RATIO", "TOTAL_SHARES_RATIO", "FREE_HOLD_RATIO", "HOLD_VALUE_RATIO")
    if p0 is None or p1 is None:
        return {"ok": False, "reason": "机构持股比例字段缺失"}
    chg = p0 - p1
    score = _clip(50.0 + chg * 10.0)
    flags = []
    if chg >= 2:
        flags.append("机构持股比例明显上升")
    elif chg <= -2:
        flags.append("机构持股比例明显下降")
    return {
        "ok": True,
        "score": round(score, 1),
        "latest_pct": p0,
        "prev_pct": p1,
        "change_pp": round(chg, 2),
        "as_of": _str(latest, "END_DATE", "REPORT_DATE"),
        "flags": flags,
    }


def score_north(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """北向持股上升 = 偏多。仅一期则不评分。"""
    if not rows:
        return {"ok": False, "reason": "北向持股不足两期"}
    if len(rows) < 2:
        n0 = _num(rows[0], "HOLD_SHARES", "SHARES", "HOLD_MARKET_CAP", "HOLD_RATIO", "A_SHARES_RATIO")
        return {
            "ok": False,
            "reason": "北向仅一期，无法比变动",
            "latest": n0,
            "as_of": _str(rows[0], "TRADE_DATE", "HOLD_DATE", "END_DATE", "DATE"),
            "flags": [],
        }
    latest, prev = rows[0], rows[1]
    n0 = _num(latest, "HOLD_SHARES", "SHARES", "HOLD_MARKET_CAP", "HOLD_RATIO")
    n1 = _num(prev, "HOLD_SHARES", "SHARES", "HOLD_MARKET_CAP", "HOLD_RATIO")
    if n0 is None or n1 is None or n1 == 0:
        return {"ok": False, "reason": "北向持股字段缺失"}
    chg = (n0 - n1) / abs(n1)
    score = _clip(50.0 + chg * 400.0)
    flags = []
    if chg <= -0.05:
        flags.append("北向减持（持股降超5%）")
    elif chg >= 0.05:
        flags.append("北向加仓（持股升超5%）")
    as_of = _str(latest, "TRADE_DATE", "HOLD_DATE", "END_DATE", "DATE")
    ymd = as_of[:10]
    if len(ymd) == 10:
        try:
            last = date.fromisoformat(ymd)
            if (date.today() - last).days > 90:
                flags.append(f"北向日频停更至 {ymd}，变动只反映停更前")
        except ValueError:
            pass
    return {
        "ok": True,
        "score": round(score, 1),
        "latest": n0,
        "prev": n1,
        "change_pct": round(chg * 100, 2),
        "as_of": as_of,
        "flags": flags,
    }


def score_flow(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """主力资金净流入占比高 = 偏多。东财个股资金流向日 K。"""
    if not rows:
        return {"ok": False, "reason": "无主力资金流向"}
    latest = rows[0]
    pct = _num(latest, "MAIN_PCT")
    net = _num(latest, "MAIN_NET")
    if pct is None and net is None:
        return {"ok": False, "reason": "主力资金字段缺失"}
    if pct is None:
        pct = 0.0
    score = _clip(50.0 + pct * 4.0)
    flags = []
    last5 = [_num(r, "MAIN_NET") for r in rows[:5]]
    last5n = [x for x in last5 if x is not None]
    if len(last5n) >= 5 and all(x < 0 for x in last5n):
        flags.append("主力连续5日净流出")
    elif len(last5n) >= 5 and all(x > 0 for x in last5n):
        flags.append("主力连续5日净流入")
    if pct <= -5:
        flags.append("当日主力净流出占比超5%")
    elif pct >= 5:
        flags.append("当日主力净流入占比超5%")
    return {
        "ok": True,
        "score": round(score, 1),
        "main_net": net,
        "main_pct": pct,
        "as_of": _str(latest, "DATE"),
        "flags": flags,
    }


def combine(modules: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    ok_scores = [m["score"] for m in modules.values() if m.get("ok") and m.get("score") is not None]
    flags: List[str] = []
    for name, m in modules.items():
        flags.extend(f"{name}: {f}" for f in (m.get("flags") or []))
    if not ok_scores:
        return {
            "ok": False,
            "score": None,
            "signal": "缺失",
            "n_modules": 0,
            "flags": flags or ["全部模块无数据"],
        }
    score = round(sum(ok_scores) / len(ok_scores), 1)
    return {
        "ok": True,
        "score": score,
        "signal": _signal(score),
        "n_modules": len(ok_scores),
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# 取数
# ---------------------------------------------------------------------------


def fetch_holders(code: str) -> List[Dict[str, Any]]:
    return em_rows(
        "RPT_F10_EH_HOLDERNUM",
        code,
        sort_columns="END_DATE",
        page_size=8,
    )


def fetch_margin(code: str) -> List[Dict[str, Any]]:
    return em_rows(
        "RPTA_WEB_RZRQ_GGMX",
        code,
        filter_tpl='(SCODE="{code}")',
        sort_columns="DATE",
        page_size=10,
    )


def fetch_block(code: str) -> List[Dict[str, Any]]:
    return em_rows(
        "RPT_DATA_BLOCKTRADE",
        code,
        sort_columns="TRADE_DATE",
        page_size=12,
    )


def fetch_lhb(code: str) -> List[Dict[str, Any]]:
    return em_rows(
        "RPT_BILLBOARD_DAILYDETAILS",
        code,
        sort_columns="TRADE_DATE",
        page_size=30,
    )


def fetch_inst(code: str) -> List[Dict[str, Any]]:
    # 前十大股东合计占比（同一张股东户数表），不是基金持仓明细
    return em_rows(
        "RPT_F10_EH_HOLDERNUM",
        code,
        sort_columns="END_DATE",
        page_size=8,
    )


def fetch_north(code: str) -> List[Dict[str, Any]]:
    rows = em_rows(
        "RPT_MUTUAL_STOCK_HOLDRANKN",
        code,
        filter_tpl='(SECURITY_CODE="{code}")(INTERVAL_TYPE="1")',
        sort_columns="TRADE_DATE",
        page_size=20,
    )
    return [r for r in rows if _num(r, "HOLD_SHARES") is not None]


def fetch_flow(code: str) -> List[Dict[str, Any]]:
    """东财 push2his 个股资金流向日 K（主力/超大单等）。"""
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get?"
        + urlencode(
            {
                "lmt": "0",
                "klt": "101",
                "secid": _secid(code),
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            }
        )
    )
    payload = json.loads(_curl(url))
    klines = ((payload.get("data") or {}).get("klines")) or []
    rows: List[Dict[str, Any]] = []
    for line in reversed(klines):
        parts = str(line).split(",")
        if len(parts) < 7:
            continue
        try:
            rows.append(
                {
                    "DATE": parts[0],
                    "MAIN_NET": float(parts[1]),
                    "SMALL_NET": float(parts[2]),
                    "MID_NET": float(parts[3]),
                    "BIG_NET": float(parts[4]),
                    "SUPER_NET": float(parts[5]),
                    "MAIN_PCT": float(parts[6]),
                }
            )
        except ValueError:
            continue
    return rows


_FETCHERS = {
    "holders": (fetch_holders, score_holders, "股东户数"),
    "margin": (fetch_margin, score_margin, "融资融券"),
    "block": (fetch_block, score_block, "大宗交易"),
    "lhb": (fetch_lhb, score_lhb, "龙虎榜"),
    "inst": (fetch_inst, score_inst, "前十大股东"),
    "north": (fetch_north, score_north, "北向资金"),
    "flow": (fetch_flow, score_flow, "主力资金"),
}


def analyze(code: str, *, fetchers: Optional[Dict[str, FetchFn]] = None) -> Dict[str, Any]:
    """跑六模块。fetchers 可注入（单测）。单个模块失败记 missing，不抛。"""
    code = _norm_code(code)
    modules: Dict[str, Dict[str, Any]] = {}
    for key, (fetch, scorer, label) in _FETCHERS.items():
        fn = (fetchers or {}).get(key, fetch)
        try:
            rows = fn(code)
            rec = scorer(rows)
        except Exception as e:  # noqa: BLE001 — 单模块失败不得拖垮总分
            rec = {"ok": False, "reason": f"{type(e).__name__}: {e}"}
        rec["label"] = label
        modules[key] = rec
    summary = combine(modules)
    return {"code": code, "secid": _secid(code), **summary, "modules": modules}


def _print_module(name: str, rec: Dict[str, Any]) -> None:
    label = rec.get("label") or name
    if not rec.get("ok"):
        print(f"  {label}: 缺失 — {rec.get('reason', '无数据')}")
        return
    extra = []
    if "change_pct" in rec:
        extra.append(f"变动 {rec['change_pct']}%")
    if "avg_premium_pct" in rec:
        extra.append(f"均溢价 {rec['avg_premium_pct']}%")
    if rec.get("main_pct") is not None:
        extra.append(f"主力占比 {rec['main_pct']}%")
    if "change_pp" in rec:
        extra.append(f"{rec['change_pp']:+.2f}pct")
    tail = ("  " + "，".join(extra)) if extra else ""
    as_of = rec.get("as_of") or ""
    print(f"  {label}: {rec['score']:.1f}  {_signal(rec['score'])}{tail}  {as_of}")


def cmd_score(code: str, *, as_json: bool = False) -> int:
    result = analyze(code)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    print("=" * 60)
    print(f"资金行为: {_norm_code(code)}")
    print("=" * 60)
    if result.get("ok"):
        print(f"  综合: {result['score']}  {result['signal']}  （{result['n_modules']}/7 模块）")
    else:
        print("  综合: 无法评分（全部模块无数据）")
    print()
    for key in _FETCHERS:
        _print_module(key, result["modules"][key])
    flags = result.get("flags") or []
    if flags:
        print()
        print("  旗标:")
        for f in flags:
            print(f"    - {f}")
    print()
    print("  口径: 东财公开接口；缺失模块不计入均分，不伪装成功。")
    print("  这不是预测，只是资金行为快照，供 Deep Research / Thesis Tracker 引用。")
    return 0 if result.get("ok") else 1


def cmd_one(kind: str, code: str, *, as_json: bool = False) -> int:
    fetch, scorer, label = _FETCHERS[kind]
    rows: List[Dict[str, Any]] = []
    try:
        rows = fetch(code)
        rec = scorer(rows)
    except Exception as e:  # noqa: BLE001
        rec = {"ok": False, "reason": f"{type(e).__name__}: {e}"}
    rec["label"] = label
    rec["code"] = _norm_code(code)
    rec["n_rows"] = len(rows)
    if as_json:
        print(json.dumps(rec, ensure_ascii=False, indent=2, default=str))
        return 0 if rec.get("ok") else 1
    print("=" * 60)
    print(f"{label}: {_norm_code(code)}")
    print("=" * 60)
    _print_module(kind, rec)
    return 0 if rec.get("ok") else 1


def main() -> None:
    _force_utf8_stdio()
    p = argparse.ArgumentParser(description="A 股资金行为分析（东财公开接口，零依赖）")
    sub = p.add_subparsers(dest="cmd")
    for name, help_ in (
        ("score", "六模块综合评分"),
        ("holders", "股东户数 / 筹码集中"),
        ("margin", "融资融券"),
        ("block", "大宗交易"),
        ("lhb", "龙虎榜"),
        ("inst", "机构持仓"),
        ("north", "北向资金"),
        ("flow", "主力资金流向"),
    ):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("code", help="A 股代码，如 600519")
        sp.add_argument("--json", action="store_true", help="JSON 输出（给 Agent）")
    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        sys.exit(0)
    if args.cmd == "score":
        sys.exit(cmd_score(args.code, as_json=args.json))
    sys.exit(cmd_one(args.cmd, args.code, as_json=args.json))


if __name__ == "__main__":
    main()

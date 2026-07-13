#!/usr/bin/env python3
"""
Berkshire AI — Web Search Integration (Tavily + AnySearch)

- Tavily：多 Key 轮询 + 429 自动切换（主搜索，需 TAVILY_API_KEY(S)）
- AnySearch：AI Agent 搜索基础设施（补充/回退，见 https://www.anysearch.com/docs）
  - Base: https://api.anysearch.com
  - POST /v1/search  body: {"query": "...", "max_results": N}
  - 可选 Authorization: Bearer <ANYSEARCH_API_KEY>
  - 免费额度：约 1000 req/day、20 QPS；无 Key 也可匿名调用（受平台配额限制）

策略（SEARCH_MODE）：
  auto     — 有 Tavily Key 则 Tavily，否则 AnySearch（默认）
  tavily   — 仅 Tavily
  anysearch— 仅 AnySearch
  hybrid   — 先 Tavily，失败/空结果再 AnySearch；SEARCH_SUPPLEMENT=1 时合并两侧来源
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse

import httpx

# 加载项目根 / CWD 的 .env（含 ANYSEARCH_API_KEY）；不覆盖已有环境变量
try:
    from config import load_dotenv as _load_dotenv
except ImportError:
    try:
        from src.config import load_dotenv as _load_dotenv  # type: ignore
    except ImportError:
        _load_dotenv = None  # type: ignore
if _load_dotenv is not None:
    _here = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.dirname(_here)
    _load_dotenv(os.path.join(_root, ".env"))
    _load_dotenv(os.path.join(_root, "skills", "anysearch", ".env"))
    _load_dotenv(".env")

# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------
TAVILY_API_URL = "https://api.tavily.com/search"
ANYSEARCH_API_URL = os.getenv(
    "ANYSEARCH_API_URL", "https://api.anysearch.com/v1/search"
).strip() or "https://api.anysearch.com/v1/search"

_TRANSIENT_STATUS = {500, 502, 503, 504}


def _backoff_seconds(attempt: int) -> float:
    """指数退避，封顶 4s。"""
    return min(0.5 * (2 ** attempt), 4.0)


def _split_keys(raw: str) -> List[str]:
    return [k.strip() for k in raw.split(",") if k.strip()]


def _load_keys() -> List[str]:
    """加载 Tavily Key（历史函数名，供 tests / 旧调用方使用）。"""
    keys_str = os.getenv("TAVILY_API_KEYS", "")
    if keys_str:
        keys = _split_keys(keys_str)
        if keys:
            return keys
    single = os.getenv("TAVILY_API_KEY", "").strip()
    return [single] if single else []


def _load_tavily_keys() -> List[str]:
    return _load_keys()


def _load_anysearch_keys() -> List[str]:
    keys_str = os.getenv("ANYSEARCH_API_KEYS", "")
    if keys_str:
        keys = _split_keys(keys_str)
        if keys:
            return keys
    single = os.getenv("ANYSEARCH_API_KEY", "").strip()
    return [single] if single else []


def _normalize_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        host = (p.netloc or "").lower().removeprefix("www.")
        path = (p.path or "").rstrip("/")
        return f"{host}{path}"
    except Exception:
        return url.strip().lower()


def _merge_results(
    primary: Dict,
    secondary: Dict,
    max_results: int,
) -> Dict:
    """合并两路结果（按 URL 去重，保留 primary 优先）。"""
    seen = set()
    merged: List[Dict] = []
    answer = primary.get("answer") or secondary.get("answer") or ""

    for bucket in (primary.get("results") or [], secondary.get("results") or []):
        for r in bucket:
            if not isinstance(r, dict):
                continue
            url = r.get("url") or ""
            key = _normalize_url(url) if url else (r.get("title") or "")[:80]
            if not key or key in seen:
                continue
            seen.add(key)
            content = r.get("content") or r.get("snippet") or ""
            merged.append({
                "title": r.get("title", ""),
                "url": url,
                "content": content,
            })
            if len(merged) >= max_results:
                break
        if len(merged) >= max_results:
            break

    out: Dict = {
        "answer": answer,
        "results": merged,
        "provider": "hybrid",
        "providers": [
            p for p in (
                primary.get("provider"),
                secondary.get("provider"),
            ) if p
        ],
    }
    return out


def _sources_from_results(results: List[Dict], limit: int = 500) -> List[Dict]:
    sources = []
    for r in results or []:
        content = r.get("content") or r.get("snippet") or ""
        sources.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": content[:limit],
        })
    return sources


# ---------------------------------------------------------------------------
# Tavily
# ---------------------------------------------------------------------------
class TavilySearcher:
    """Tavily 搜索引擎封装 - 多 Key 轮询"""

    _lock = threading.Lock()
    _key_index = 0

    def __init__(self, api_keys: Optional[List[str]] = None):
        self.keys = api_keys if api_keys is not None else _load_tavily_keys()
        if not self.keys:
            raise ValueError(
                "TAVILY_API_KEY(S) 未配置。\n"
                "请在 ~/.bashrc 中设置:\n"
                '  export TAVILY_API_KEYS="tvly-key1,tvly-key2"\n'
                "或使用 AnySearch 回退：export SEARCH_MODE=anysearch / auto"
            )
        print(f"  [Tavily] 已加载 {len(self.keys)} 个 API Key")

    @property
    def current_key(self) -> str:
        return self.keys[self._key_index % len(self.keys)]

    def _rotate_key(self):
        """切换到下一个 Key"""
        with self._lock:
            old = self._key_index
            self._key_index = (self._key_index + 1) % len(self.keys)
            print(f"  [Tavily] Key 轮询: #{old} → #{self._key_index}")

    def search(self, query: str, max_results: int = 5, max_retries: int = 2) -> Dict:
        """执行搜索。

        - 429 限流：切换 Key 重试（不计入退避）
        - 超时 / 网络错误 / 5xx 网关错误：指数退避后重试，最多 max_retries 次
        - 其它错误：立即返回 error
        """
        max_attempts = len(self.keys) + max_retries
        last_error = None
        for attempt in range(max_attempts):
            try:
                with httpx.Client(timeout=30) as client:
                    response = client.post(
                        TAVILY_API_URL,
                        headers={"Content-Type": "application/json"},
                        json={
                            "api_key": self.current_key,
                            "query": query,
                            "max_results": max_results,
                            "include_answer": True,
                            "search_depth": "advanced",
                        },
                    )
                if response.status_code == 429:
                    print("  [Tavily] 429 限流，切换 Key...")
                    self._rotate_key()
                    continue
                if response.status_code in _TRANSIENT_STATUS:
                    last_error = f"HTTP {response.status_code}"
                    print(f"  [Tavily] {last_error} 瞬时错误，退避重试...")
                    time.sleep(_backoff_seconds(attempt))
                    continue
                if response.status_code >= 400:
                    return {
                        "error": f"HTTP {response.status_code}",
                        "results": [],
                        "provider": "tavily",
                    }
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict):
                    data.setdefault("provider", "tavily")
                return data
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_error = f"{type(e).__name__}: {e}"
                print(f"  [Tavily] 网络瞬时错误，退避重试: {last_error}")
                time.sleep(_backoff_seconds(attempt))
                continue
            except Exception as e:
                if "429" in str(e):
                    self._rotate_key()
                    continue
                return {"error": str(e), "results": [], "provider": "tavily"}
        return {
            "error": f"重试 {max_attempts} 次后仍失败: {last_error or '所有 Key 均被限流'}",
            "results": [],
            "provider": "tavily",
        }

    def get_stock_data(self, ticker: str, company_name: str) -> Dict:
        return _stock_payload(self.search, ticker, company_name)

    def get_industry_news(self, industry: str, company: str = "") -> Dict:
        return _news_payload(self.search, industry, company)

    def get_financial_metrics(self, ticker: str) -> Dict:
        return _financial_payload(self.search, ticker)


# ---------------------------------------------------------------------------
# AnySearch (supplement / fallback)
# ---------------------------------------------------------------------------
class AnySearchSearcher:
    """AnySearch REST 封装 — 可作为 Tavily 补充或独立后端。

    Docs: https://www.anysearch.com/docs
    FAQ 确认：POST /v1/search；支持 MCP/Skill；免费约 1000 req/day。
    """

    _lock = threading.Lock()
    _key_index = 0

    def __init__(
        self,
        api_keys: Optional[List[str]] = None,
        allow_anonymous: bool = True,
    ):
        # None → 读环境；[] → 明确无 Key（仅匿名）
        if api_keys is None:
            self.keys = _load_anysearch_keys()
        else:
            self.keys = list(api_keys)
        self.allow_anonymous = allow_anonymous
        if not self.keys and not allow_anonymous:
            raise ValueError(
                "ANYSEARCH_API_KEY(S) 未配置且不允许匿名。\n"
                "访问 https://www.anysearch.com 获取 Key，或设置 allow_anonymous=True"
            )
        mode = f"{len(self.keys)} key(s)" if self.keys else "anonymous"
        print(f"  [AnySearch] 已就绪 ({mode}) → {ANYSEARCH_API_URL}")

    @property
    def current_key(self) -> Optional[str]:
        if not self.keys:
            return None
        return self.keys[self._key_index % len(self.keys)]

    def _rotate_key(self):
        if not self.keys:
            return
        with self._lock:
            old = self._key_index
            self._key_index = (self._key_index + 1) % len(self.keys)
            print(f"  [AnySearch] Key 轮询: #{old} → #{self._key_index}")

    def _normalize_response(self, payload: Dict, max_results: int) -> Dict:
        """将 AnySearch envelope 转为 Tavily 兼容结构。"""
        if not isinstance(payload, dict):
            return {
                "error": "invalid AnySearch payload",
                "results": [],
                "provider": "anysearch",
            }

        code = payload.get("code")
        if code not in (0, "0", None) and payload.get("data") is None:
            return {
                "error": payload.get("message") or f"AnySearch code={code}",
                "results": [],
                "provider": "anysearch",
                "request_id": payload.get("request_id"),
            }

        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        raw_results = data.get("results") or []
        results = []
        for r in raw_results[:max_results]:
            if not isinstance(r, dict):
                continue
            content = r.get("content") or r.get("snippet") or ""
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": content,
                "snippet": r.get("snippet", ""),
            })

        answer = data.get("answer") or payload.get("answer") or ""
        # 无 LLM answer 时，用前几条 snippet 拼一个轻量摘要，供下游展示
        if not answer and results:
            parts = []
            for r in results[:3]:
                snip = (r.get("snippet") or r.get("content") or "")[:200]
                if snip:
                    parts.append(snip)
            answer = " | ".join(parts)

        out: Dict = {
            "answer": answer,
            "results": results,
            "provider": "anysearch",
            "request_id": payload.get("request_id"),
        }
        meta = data.get("metadata") if isinstance(data, dict) else None
        if meta:
            out["metadata"] = meta
        return out

    def search(self, query: str, max_results: int = 5, max_retries: int = 2) -> Dict:
        if not (query or "").strip():
            return {
                "error": "Query is required",
                "results": [],
                "provider": "anysearch",
            }

        # 无 Key 时只跑匿名 1 路；有 Key 时允许轮询 + 重试
        key_slots = max(len(self.keys), 1 if self.allow_anonymous else 0)
        max_attempts = key_slots + max_retries
        last_error = None
        used_anonymous_fallback = False

        for attempt in range(max_attempts):
            headers = {"Content-Type": "application/json"}
            key = self.current_key
            # 若 Key 鉴权失败，后续尝试可降级匿名
            if key and not used_anonymous_fallback:
                headers["Authorization"] = f"Bearer {key}"

            try:
                with httpx.Client(timeout=30) as client:
                    response = client.post(
                        ANYSEARCH_API_URL,
                        headers=headers,
                        json={"query": query, "max_results": max_results},
                    )
                if response.status_code == 401:
                    # 无效 Key：切 Key；无更多 Key 则匿名重试一次
                    print("  [AnySearch] 401 鉴权失败...")
                    if self.keys and not used_anonymous_fallback:
                        if len(self.keys) > 1:
                            self._rotate_key()
                            continue
                        if self.allow_anonymous:
                            used_anonymous_fallback = True
                            print("  [AnySearch] 降级匿名调用")
                            continue
                    return {
                        "error": "Invalid API key",
                        "results": [],
                        "provider": "anysearch",
                    }
                if response.status_code == 429:
                    print("  [AnySearch] 429 限流...")
                    if self.keys:
                        self._rotate_key()
                    else:
                        time.sleep(_backoff_seconds(attempt))
                    continue
                if response.status_code in _TRANSIENT_STATUS:
                    last_error = f"HTTP {response.status_code}"
                    print(f"  [AnySearch] {last_error} 瞬时错误，退避重试...")
                    time.sleep(_backoff_seconds(attempt))
                    continue
                if response.status_code >= 400:
                    try:
                        body = response.json()
                        msg = body.get("message") or f"HTTP {response.status_code}"
                    except Exception:
                        msg = f"HTTP {response.status_code}"
                    return {
                        "error": msg,
                        "results": [],
                        "provider": "anysearch",
                    }
                response.raise_for_status()
                return self._normalize_response(response.json(), max_results)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_error = f"{type(e).__name__}: {e}"
                print(f"  [AnySearch] 网络瞬时错误，退避重试: {last_error}")
                time.sleep(_backoff_seconds(attempt))
                continue
            except Exception as e:
                return {"error": str(e), "results": [], "provider": "anysearch"}

        return {
            "error": f"重试 {max_attempts} 次后仍失败: {last_error or 'unknown'}",
            "results": [],
            "provider": "anysearch",
        }

    def get_stock_data(self, ticker: str, company_name: str) -> Dict:
        return _stock_payload(self.search, ticker, company_name)

    def get_industry_news(self, industry: str, company: str = "") -> Dict:
        return _news_payload(self.search, industry, company)

    def get_financial_metrics(self, ticker: str) -> Dict:
        return _financial_payload(self.search, ticker)


# ---------------------------------------------------------------------------
# Hybrid facade (Tavily primary + AnySearch supplement)
# ---------------------------------------------------------------------------
class HybridSearcher:
    """统一搜索入口：Tavily 主路 + AnySearch 补充/回退。"""

    def __init__(
        self,
        mode: Optional[str] = None,
        tavily_keys: Optional[List[str]] = None,
        anysearch_keys: Optional[List[str]] = None,
        supplement: Optional[bool] = None,
    ):
        self.mode = (mode or os.getenv("SEARCH_MODE", "auto")).strip().lower()
        if self.mode not in {"auto", "tavily", "anysearch", "hybrid"}:
            self.mode = "auto"

        if supplement is None:
            self.supplement = os.getenv("SEARCH_SUPPLEMENT", "").strip() in {
                "1", "true", "yes", "on",
            }
        else:
            self.supplement = bool(supplement)

        self._tavily: Optional[TavilySearcher] = None
        self._any: Optional[AnySearchSearcher] = None

        t_keys = tavily_keys if tavily_keys is not None else _load_tavily_keys()
        a_keys = anysearch_keys if anysearch_keys is not None else _load_anysearch_keys()

        if self.mode in {"auto", "tavily", "hybrid"} and t_keys:
            try:
                self._tavily = TavilySearcher(api_keys=t_keys)
            except ValueError:
                self._tavily = None

        if self.mode in {"auto", "anysearch", "hybrid"} or self.supplement:
            # auto 无 Tavily 时启用 AnySearch；hybrid/supplement 始终准备
            need_any = (
                self.mode in {"anysearch", "hybrid"}
                or self.supplement
                or (self.mode == "auto" and self._tavily is None)
            )
            if need_any:
                self._any = AnySearchSearcher(api_keys=a_keys, allow_anonymous=True)

        if self._tavily is None and self._any is None:
            raise ValueError(
                "无可用搜索后端。请配置 TAVILY_API_KEY(S)，"
                "或使用 AnySearch（SEARCH_MODE=anysearch / auto，可匿名）。\n"
                "AnySearch 文档: https://www.anysearch.com/docs"
            )

        backends = []
        if self._tavily:
            backends.append("tavily")
        if self._any:
            backends.append("anysearch")
        print(
            f"  [Search] mode={self.mode} backends={'+'.join(backends)} "
            f"supplement={self.supplement}"
        )

    def search(self, query: str, max_results: int = 5, max_retries: int = 2) -> Dict:
        mode = self.mode

        if mode == "tavily":
            if not self._tavily:
                return {"error": "Tavily 未配置", "results": [], "provider": "tavily"}
            return self._tavily.search(query, max_results=max_results, max_retries=max_retries)

        if mode == "anysearch":
            if not self._any:
                return {"error": "AnySearch 未配置", "results": [], "provider": "anysearch"}
            return self._any.search(query, max_results=max_results, max_retries=max_retries)

        # auto / hybrid
        primary: Optional[Dict] = None
        secondary: Optional[Dict] = None

        if self._tavily:
            primary = self._tavily.search(
                query, max_results=max_results, max_retries=max_retries
            )
            ok = "error" not in primary and bool(primary.get("results"))
            if ok and not self.supplement:
                return primary
            if ok and self.supplement and self._any:
                secondary = self._any.search(
                    query, max_results=max_results, max_retries=max_retries
                )
                if "error" not in secondary:
                    return _merge_results(primary, secondary, max_results)
                return primary
            # Tavily 失败或空结果 → AnySearch 回退
            if self._any:
                print("  [Search] Tavily 不可用/空结果，回退 AnySearch...")
                secondary = self._any.search(
                    query, max_results=max_results, max_retries=max_retries
                )
                if "error" not in secondary:
                    if primary and primary.get("results") and self.supplement:
                        return _merge_results(primary, secondary, max_results)
                    return secondary
                # 两边都挂
                return primary if primary and "error" in primary else secondary
            return primary or {"error": "无可用搜索后端", "results": []}

        # 仅 AnySearch
        assert self._any is not None
        return self._any.search(query, max_results=max_results, max_retries=max_retries)

    def get_stock_data(self, ticker: str, company_name: str) -> Dict:
        return _stock_payload(self.search, ticker, company_name)

    def get_industry_news(self, industry: str, company: str = "") -> Dict:
        return _news_payload(self.search, industry, company)

    def get_financial_metrics(self, ticker: str) -> Dict:
        return _financial_payload(self.search, ticker)


def create_searcher(mode: Optional[str] = None) -> HybridSearcher:
    """工厂：按 SEARCH_MODE / 可用 Key 创建搜索器。"""
    return HybridSearcher(mode=mode)


# ---------------------------------------------------------------------------
# Domain helpers (shared)
# ---------------------------------------------------------------------------
def _stock_payload(search_fn, ticker: str, company_name: str) -> Dict:
    query = f"{ticker} {company_name} 股价 市值 PE PB 股息率 最新财报"
    result = search_fn(query, max_results=5)
    if "error" in result:
        return {"error": result["error"]}
    return {
        "ticker": ticker,
        "company_name": company_name,
        "timestamp": datetime.now().isoformat(),
        "answer": result.get("answer", ""),
        "sources": _sources_from_results(result.get("results", [])),
        "provider": result.get("provider"),
    }


def _news_payload(search_fn, industry: str, company: str = "") -> Dict:
    query = f"{industry} {company} 最新动态 竞争格局 行业趋势 2026"
    result = search_fn(query, max_results=5)
    if "error" in result:
        return {"error": result["error"]}
    return {
        "industry": industry,
        "company": company,
        "timestamp": datetime.now().isoformat(),
        "answer": result.get("answer", ""),
        "sources": _sources_from_results(result.get("results", [])),
        "provider": result.get("provider"),
    }


def _financial_payload(search_fn, ticker: str) -> Dict:
    query = f"{ticker} 营收 净利润 自由现金流 ROE 毛利率 净利率 最新季度"
    result = search_fn(query, max_results=5)
    if "error" in result:
        return {"error": result["error"]}
    return {
        "ticker": ticker,
        "timestamp": datetime.now().isoformat(),
        "answer": result.get("answer", ""),
        "sources": _sources_from_results(result.get("results", [])),
        "provider": result.get("provider"),
    }


# ---------------------------------------------------------------------------
# Tests / CLI
# ---------------------------------------------------------------------------
def test_tavily_integration():
    """测试搜索集成（Tavily + AnySearch）"""
    print("=" * 70)
    print("  Berkshire AI — Web Search 集成测试 (Tavily + AnySearch)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    t_keys = _load_tavily_keys()
    a_keys = _load_anysearch_keys()
    print(f"\n  Tavily keys: {len(t_keys)} | AnySearch keys: {len(a_keys)} (可匿名)")
    print(f"  SEARCH_MODE={os.getenv('SEARCH_MODE', 'auto')}")
    print(f"  SEARCH_SUPPLEMENT={os.getenv('SEARCH_SUPPLEMENT', '0')}")

    try:
        searcher = create_searcher()
    except ValueError as e:
        print(f"\n❌ {e}")
        return False

    try:
        print("\n📊 测试 1: 获取腾讯控股数据")
        print("-" * 70)
        result = searcher.get_stock_data("0700.HK", "腾讯控股")
        if "error" in result:
            print(f"❌ 错误: {result['error']}")
        else:
            print("✅ 成功")
            print(f"   provider: {result.get('provider')}")
            print(f"   摘要: {(result.get('answer') or '')[:200]}...")
            print(f"   来源数: {len(result.get('sources') or [])}")

        print("\n📈 测试 2: 获取财务指标")
        print("-" * 70)
        result = searcher.get_financial_metrics("0700.HK")
        if "error" in result:
            print(f"❌ 错误: {result['error']}")
        else:
            print("✅ 成功")
            print(f"   provider: {result.get('provider')}")
            print(f"   摘要: {(result.get('answer') or '')[:200]}...")

        print("\n" + "=" * 70)
        print("  ✅ 搜索集成测试完成")
        print("=" * 70)
        return True
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def _cli():
    """命令行入口：与 skills/config 文档中的调用方式保持一致。

    用法:
      python3 src/tavily_search.py stock <ticker> <company_name>
      python3 src/tavily_search.py financial <ticker>
      python3 src/tavily_search.py news <industry> [company]
      python3 src/tavily_search.py test
      python3 src/tavily_search.py search <query>   # 原始搜索
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="实时检索（Tavily 主 + AnySearch 补充）"
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "tavily", "anysearch", "hybrid"],
        default=None,
        help="覆盖 SEARCH_MODE",
    )
    parser.add_argument(
        "--supplement",
        action="store_true",
        help="启用双侧合并（等同 SEARCH_SUPPLEMENT=1）",
    )
    sub = parser.add_subparsers(dest="command")

    p_stock = sub.add_parser("stock", help="获取股票实时数据")
    p_stock.add_argument("ticker")
    p_stock.add_argument("company_name")

    p_fin = sub.add_parser("financial", help="获取财务指标")
    p_fin.add_argument("ticker")

    p_news = sub.add_parser("news", help="获取行业新闻")
    p_news.add_argument("industry")
    p_news.add_argument("company", nargs="?", default="")

    p_search = sub.add_parser("search", help="原始查询")
    p_search.add_argument("query")
    p_search.add_argument("--max-results", type=int, default=5)

    sub.add_parser("test", help="运行集成自测")

    args = parser.parse_args()

    if args.command == "test" or args.command is None:
        test_tavily_integration()
        return

    kwargs = {}
    if args.mode:
        kwargs["mode"] = args.mode
    if args.supplement:
        kwargs["supplement"] = True
    searcher = HybridSearcher(**kwargs) if kwargs else create_searcher(mode=args.mode)

    if args.command == "stock":
        result = searcher.get_stock_data(args.ticker, args.company_name)
    elif args.command == "financial":
        result = searcher.get_financial_metrics(args.ticker)
    elif args.command == "news":
        result = searcher.get_industry_news(args.industry, args.company)
    elif args.command == "search":
        result = searcher.search(args.query, max_results=args.max_results)
    else:
        parser.print_help()
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()

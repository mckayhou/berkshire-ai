#!/usr/bin/env python3
"""
Berkshire AI V9.3 - Tavily Search Integration (Multi-Key Round-Robin)
为四大师分析提供实时数据支持，支持多 Key 轮询 + 429 自动切换
"""
import os
import json
import time
import httpx
import threading
from typing import Dict, List, Optional
from datetime import datetime

# Tavily API 配置
TAVILY_API_URL = "https://api.tavily.com/search"

# 视为"瞬时可重试"的 HTTP 状态码（网关/服务暂时不可用）
_TRANSIENT_STATUS = {500, 502, 503, 504}


def _backoff_seconds(attempt: int) -> float:
    """指数退避，封顶 4s。"""
    return min(0.5 * (2 ** attempt), 4.0)

def _load_keys() -> List[str]:
    """加载所有可用 Key"""
    keys_str = os.getenv("TAVILY_API_KEYS", "")
    if keys_str:
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if keys:
            return keys
    # fallback to single key
    single = os.getenv("TAVILY_API_KEY", "").strip()
    return [single] if single else []

class TavilySearcher:
    """Tavily 搜索引擎封装 - 多 Key 轮询"""
    
    _lock = threading.Lock()
    _key_index = 0
    
    def __init__(self, api_keys: Optional[List[str]] = None):
        self.keys = api_keys or _load_keys()
        if not self.keys:
            raise ValueError(
                "TAVILY_API_KEY(S) 未配置。\n"
                "请在 ~/.bashrc 中设置:\n"
                '  export TAVILY_API_KEYS="tvly-key1,tvly-key2"'
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
                            "search_depth": "advanced"
                        }
                    )
                if response.status_code == 429:
                    print(f"  [Tavily] 429 限流，切换 Key...")
                    self._rotate_key()
                    continue
                if response.status_code in _TRANSIENT_STATUS:
                    last_error = f"HTTP {response.status_code}"
                    print(f"  [Tavily] {last_error} 瞬时错误，退避重试...")
                    time.sleep(_backoff_seconds(attempt))
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError) as e:
                # 超时/连接类错误：可重试
                last_error = f"{type(e).__name__}: {e}"
                print(f"  [Tavily] 网络瞬时错误，退避重试: {last_error}")
                time.sleep(_backoff_seconds(attempt))
                continue
            except Exception as e:
                if "429" in str(e):
                    self._rotate_key()
                    continue
                return {"error": str(e), "results": []}
        return {"error": f"重试 {max_attempts} 次后仍失败: {last_error or '所有 Key 均被限流'}",
                "results": []}
    
    def get_stock_data(self, ticker: str, company_name: str) -> Dict:
        """获取股票实时数据"""
        query = f"{ticker} {company_name} 股价 市值 PE PB 股息率 最新财报"
        result = self.search(query, max_results=5)
        
        if "error" in result:
            return {"error": result["error"]}
        
        # 提取关键数据
        data = {
            "ticker": ticker,
            "company_name": company_name,
            "timestamp": datetime.now().isoformat(),
            "answer": result.get("answer", ""),
            "sources": []
        }
        
        for r in result.get("results", []):
            data["sources"].append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:500]  # 截取前500字符
            })
        
        return data
    
    def get_industry_news(self, industry: str, company: str = "") -> Dict:
        """获取行业新闻"""
        query = f"{industry} {company} 最新动态 竞争格局 行业趋势 2026"
        result = self.search(query, max_results=5)
        
        if "error" in result:
            return {"error": result["error"]}
        
        return {
            "industry": industry,
            "company": company,
            "timestamp": datetime.now().isoformat(),
            "answer": result.get("answer", ""),
            "sources": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:500]
                }
                for r in result.get("results", [])
            ]
        }
    
    def get_financial_metrics(self, ticker: str) -> Dict:
        """获取财务指标"""
        query = f"{ticker} 营收 净利润 自由现金流 ROE 毛利率 净利率 最新季度"
        result = self.search(query, max_results=5)
        
        if "error" in result:
            return {"error": result["error"]}
        
        return {
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "answer": result.get("answer", ""),
            "sources": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:500]
                }
                for r in result.get("results", [])
            ]
        }


def test_tavily_integration():
    """测试 Tavily 集成"""
    print("="*70)
    print("  Berkshire AI V9.3 - Tavily 集成测试")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    if not _load_keys():
        print("\n❌ TAVILY_API_KEY(S) 未配置")
        print("\n请执行以下步骤：")
        print("1. 访问 https://tavily.com 注册账号（免费 1000次/月）")
        print("2. 获取 API Key")
        print("3. 在 ~/.bashrc 中添加（推荐多 Key 轮询）：")
        print("   export TAVILY_API_KEYS='tvly-key1,tvly-key2'")
        print("   # 或单 Key： export TAVILY_API_KEY='tvly-xxxxxxxxxxxxx'")
        print("4. 执行：source ~/.bashrc")
        return False

    print("\n✅ TAVILY_API_KEY(S) 已配置")
    
    try:
        searcher = TavilySearcher()
        
        # 测试 1: 股票数据
        print("\n📊 测试 1: 获取腾讯控股数据")
        print("-"*70)
        result = searcher.get_stock_data("0700.HK", "腾讯控股")
        
        if "error" in result:
            print(f"❌ 错误: {result['error']}")
        else:
            print(f"✅ 成功")
            print(f"   摘要: {result['answer'][:200]}...")
            print(f"   来源数: {len(result['sources'])}")
        
        # 测试 2: 财务指标
        print("\n📈 测试 2: 获取财务指标")
        print("-"*70)
        result = searcher.get_financial_metrics("0700.HK")
        
        if "error" in result:
            print(f"❌ 错误: {result['error']}")
        else:
            print(f"✅ 成功")
            print(f"   摘要: {result['answer'][:200]}...")
        
        print("\n" + "="*70)
        print("  ✅ Tavily 集成测试完成")
        print("="*70)
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
    """
    import argparse

    parser = argparse.ArgumentParser(description="Tavily 实时检索（四大师数据获取）")
    sub = parser.add_subparsers(dest="command")

    p_stock = sub.add_parser("stock", help="获取股票实时数据")
    p_stock.add_argument("ticker")
    p_stock.add_argument("company_name")

    p_fin = sub.add_parser("financial", help="获取财务指标")
    p_fin.add_argument("ticker")

    p_news = sub.add_parser("news", help="获取行业新闻")
    p_news.add_argument("industry")
    p_news.add_argument("company", nargs="?", default="")

    sub.add_parser("test", help="运行集成自测")

    args = parser.parse_args()

    if args.command == "test" or args.command is None:
        test_tavily_integration()
        return

    searcher = TavilySearcher()
    if args.command == "stock":
        result = searcher.get_stock_data(args.ticker, args.company_name)
    elif args.command == "financial":
        result = searcher.get_financial_metrics(args.ticker)
    elif args.command == "news":
        result = searcher.get_industry_news(args.industry, args.company)
    else:
        parser.print_help()
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()

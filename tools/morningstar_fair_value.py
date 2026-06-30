#!/usr/bin/env python3
"""
从 Morningstar 筛选器 API 抓取所有有公允价值估计的股票，
计算潜在涨幅，输出 Top 100。
"""

import argparse
import csv
import json
import os
import subprocess
import time
from datetime import datetime


def _stars(rating) -> str:
    """安全渲染星级：兼容 int / float / 字符串 / None，无法解析时返回 N/A。"""
    if rating is None or rating == "":
        return "N/A"
    try:
        return "★" * int(float(rating))
    except (ValueError, TypeError):
        return str(rating)

API_BASE = (
    "https://lt.morningstar.com/api/rest.svc/klr5zyak8x/security/screener"
    "?page={page}&pageSize={page_size}"
    "&sortOrder=FairValueEstimate%20desc"
    "&outputType=json&version=1"
    "&languageId=en-US&currencyId=USD"
    "&universeIds=E0EXG%24XNAS%7CE0EXG%24XNYS"
    "&securityDataPoints=SecId%7CName%7CPriceCurrency%7CTenforeId%7CClosePrice"
    "%7CStarRatingM255%7CQuantitativeFairValue%7CFairValueEstimate"
    "%7CAssessmentOfFairValueUncertainty%7CEconomicMoat%7CIndustryName%7CSectorName"
    "&filters=FairValueEstimate:notnull"
)

PAGE_SIZE = 100
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def fetch_page(page: int, retries: int = 2) -> dict:
    """抓取一页结果。瞬时失败（超时/空响应/非 JSON）自动重试，最终失败抛 ConnectionError。"""
    url = API_BASE.format(page=page, page_size=PAGE_SIZE)
    last = None
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                ["curl", "-s", "-H", "User-Agent: Mozilla/5.0", url],
                capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired:
            last = "请求超时 (>30s)"
            time.sleep(0.5 * (attempt + 1))
            continue
        if result.returncode != 0 or not (result.stdout or "").strip():
            last = "请求失败或空响应"
            time.sleep(0.5 * (attempt + 1))
            continue
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            last = "返回非 JSON（可能被限流或拦截）"
            time.sleep(0.5 * (attempt + 1))
            continue
    raise ConnectionError(f"Morningstar 抓取失败 (page={page}): {last}")


def extract_ticker(tenforeid: str) -> str:
    if not tenforeid:
        return ""
    parts = tenforeid.split(".")
    return parts[-1] if len(parts) >= 3 else tenforeid


def main(max_pages: int | None = None, top: int = 100):
    print(f"\n{'='*80}")
    print(f"  Morningstar 公允价值筛选  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*80}\n")

    # 第一页获取总数
    print("  正在获取第 1 页...")
    data = fetch_page(1)
    total = data.get("total", 0)
    all_rows = data.get("rows", [])
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    if max_pages:
        total_pages = min(total_pages, max_pages)
    print(f"  共 {total} 只股票，抓取 {total_pages} 页\n")

    # 抓取剩余页
    for page in range(2, total_pages + 1):
        if page % 10 == 0 or page == total_pages:
            print(f"  正在获取第 {page}/{total_pages} 页...")
        try:
            data = fetch_page(page)
            rows = data.get("rows", [])
            if not rows:
                break
            all_rows.extend(rows)
            time.sleep(0.3)
        except Exception as e:
            print(f"  ⚠️  第 {page} 页失败: {e}")
            time.sleep(1)

    print(f"\n  共获取 {len(all_rows)} 条记录")

    # 计算潜在涨幅
    stocks = []
    for row in all_rows:
        fair_value = row.get("FairValueEstimate")
        close_price = row.get("ClosePrice")
        if not fair_value or not close_price or close_price <= 0:
            continue

        ticker = extract_ticker(row.get("TenforeId", ""))
        upside = (fair_value - close_price) / close_price * 100

        stocks.append({
            "ticker": ticker,
            "name": row.get("Name", ""),
            "close_price": round(close_price, 2),
            "fair_value": round(fair_value, 2),
            "upside_pct": round(upside, 1),
            "star_rating": row.get("StarRatingM255", ""),
            "moat": row.get("EconomicMoat", ""),
            "uncertainty": row.get("AssessmentOfFairValueUncertainty", ""),
            "sector": row.get("SectorName", ""),
            "industry": row.get("IndustryName", ""),
        })

    # 按潜在涨幅排序
    stocks.sort(key=lambda x: x["upside_pct"], reverse=True)

    # 输出 Top 100
    print(f"\n{'='*80}")
    print(f"  潜在涨幅 Top {top}")
    print(f"{'='*80}\n")
    print(f"  {'排名':>4} {'代码':<8} {'公司名':<35} {'现价':>10} {'公允价值':>10} {'潜在涨幅':>8} {'星级':>4} {'护城河':<8} {'行业':<20}")
    print(f"  {'-'*4} {'-'*8} {'-'*35} {'-'*10} {'-'*10} {'-'*8} {'-'*4} {'-'*8} {'-'*20}")

    for i, s in enumerate(stocks[:top], 1):
        print(
            f"  {i:>4} {s['ticker']:<8} {s['name'][:35]:<35} "
            f"${s['close_price']:>9,.2f} ${s['fair_value']:>9,.2f} "
            f"{s['upside_pct']:>+7.1f}% "
            f"{_stars(s['star_rating']):>4} "
            f"{s['moat']:<8} {s['industry'][:20]:<20}"
        )

    # 保存完整数据到 CSV
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    csv_path = os.path.join(OUTPUT_DIR, f"morningstar_fair_value_{today}.csv")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "rank", "ticker", "name", "close_price", "fair_value",
            "upside_pct", "star_rating", "moat", "uncertainty", "sector", "industry"
        ])
        writer.writeheader()
        for i, s in enumerate(stocks, 1):
            writer.writerow({"rank": i, **s})

    print(f"\n  完整数据已保存到: {csv_path}")
    print(f"  共 {len(stocks)} 只股票（按潜在涨幅排序）\n")

    # 统计摘要
    undervalued = [s for s in stocks if s["upside_pct"] > 0]
    overvalued = [s for s in stocks if s["upside_pct"] < 0]
    print("  📊 统计摘要:")
    print(f"     低估股票: {len(undervalued)} 只 ({len(undervalued)/len(stocks)*100:.0f}%)")
    print(f"     高估股票: {len(overvalued)} 只 ({len(overvalued)/len(stocks)*100:.0f}%)")
    if undervalued:
        avg_upside = sum(s["upside_pct"] for s in undervalued) / len(undervalued)
        print(f"     低估股票平均潜在涨幅: +{avg_upside:.1f}%")
    if stocks:
        wide_moat_undervalued = [s for s in stocks if s["moat"] == "Wide" and s["upside_pct"] > 0]
        print(f"     宽护城河+低估: {len(wide_moat_undervalued)} 只")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="从 Morningstar 筛选器抓取有公允价值估计的股票，计算潜在涨幅并输出榜单"
    )
    parser.add_argument("--max-pages", type=int, default=None,
                        help="最多抓取的页数（每页100只，默认全部；测试时可设 1-2）")
    parser.add_argument("--top", type=int, default=100,
                        help="打印榜单条数（默认100）")
    args = parser.parse_args()
    main(max_pages=args.max_pages, top=args.top)

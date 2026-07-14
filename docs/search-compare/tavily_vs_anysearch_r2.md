# Tavily vs AnySearch 第二轮（垂直域 + LLM 裁判）

- 时间：2026-07-13T20:58:12
- 查询数：8
- 启发式胜场：`{'tavily': 7, 'anysearch_general': 1}`
- LLM 胜场：`{'tavily': 5, 'anysearch_vertical': 2, 'anysearch_general': 1}`
- LLM 均分：Tavily **8.12** / AnyGeneral **5.25** / AnyVertical **5.12**

## 启发式均值

| 指标 | Tavily | AnySearch 通用 | AnySearch 垂直 |
|------|--------|----------------|----------------|
| composite | 97.69 | 90.8 | 56.49 |
| keyword_rate | 1.0 | 0.86 | 0.3 |
| unique_domains | 4.75 | 4.38 | 2.5 |
| avg_content_len | 1977.08 | 2915.9 | 388.66 |
| latency_ms | 1718.0 | 1783.38 | 1950.25 |

## 分 query

| id | intent | Tavily h | AnyG h | AnyV h | h-win | LLM T/G/V | llm-win |
|----|--------|----------|--------|--------|-------|-----------|---------|
| hk_quote | 港股报价估值 | 100.0 | 93.2 | 43.3 | tavily | 9/4/6 | tavily |
| a_fundamental | A股财务指标 | 97.0 | 90.2 | 49.1 | tavily | 5/2/8 | anysearch_vertical |
| us_quote | 美股报价估值 | 100.0 | 94.5 | 49.3 | tavily | 9/4/5 | tavily |
| us_fundamental | 美股基本面卡片 | 100.0 | 92.5 | 47.0 | tavily | 8/2/9 | anysearch_vertical |
| industry | 白酒行业中文 | 95.0 | 100.0 | 62.0 | anysearch_general | 9/8/1 | tavily |
| news_tencent | 公司新闻 | 94.5 | 82.0 | 53.0 | tavily | 8/7/5 | tavily |
| risk_pdd | 监管风险事件 | 95.0 | 85.0 | 65.7 | tavily | 8/9/5 | anysearch_general |
| a_news_flash | A股快讯 | 100.0 | 89.0 | 82.5 | tavily | 9/6/2 | tavily |

## 细节与 LLM 理由

### hk_quote — 港股报价估值
- Query: `0700.HK 腾讯控股 股价 市值 PE PB 股息率`
- Vertical: `finance.quote` sdp=`type=stock,symbol=0700.HK,cn_code=`

| | Tavily | AnyGeneral | AnyVertical |
|--|--------|------------|-------------|
| composite | 100.0 | 93.2 | 43.3 |
| n_results | 5 | 5 | 2 |
| keyword_rate | 1.0 | 0.857 | 0.286 |
| avg_content_len | 1791.4 | 2872.4 | 300.0 |
| latency_ms | 890 | 2633 | 2070 |
| error | None | None | None |

- **LLM tavily**: 9 — 直接且完整地提供了股价、市值、PE、PB和股息率等所有核心估值指标，来源权威可信。
- **LLM anysearch_general**: 4 — 仅提取了部分股价行情信息，缺失市值、PE、PB和股息率等关键估值指标，数据可用性较差。
- **LLM anysearch_vertical**: 6 — 提供了股价和市值等基础行情数据，但未能提取PE、PB和股息率等核心估值指标，完整性不足。

- Tavily preview: Tencent Holdings' stock price is HKD 460.20, market cap is HKD 4.143 trillion, PE ratio is 16.52, PB ratio is 3.18, and dividend yield is 1.15%.
- AnyG preview: 腾讯控股（hk00700）股票价格_股票实时行情_走势图-手机新浪财经 * 网页版港股行情数据延时，若需查看实时行情，请点击下方APP ADR换算价 相对港股 腾讯控股（hk00700）股票价格\_股票实时行情\_走势图-手机新浪财经 \* 网页版港股行情数据延时，若需查看实时行情，请点击下方APP ADR换算价 相对港股 ** | 腾讯控股(00700)市
- AnyV preview: Symbol: 0700.HK | Name: Tencent Holdings Limited | Exchange: HKSE | Price: 457.60 | Open: 463.20 | PrevClose: 460.20 | Change: -2.60 | Change%: -0.56% | DayHigh: 473.80 | DayLow: 4

### a_fundamental — A股财务指标
- Query: `600519 贵州茅台 营收 净利润 ROE 毛利率 最新财报`
- Vertical: `finance.fundamental` sdp=`type=indicator,symbol=,cn_code=600519.SH`

| | Tavily | AnyGeneral | AnyVertical |
|--|--------|------------|-------------|
| composite | 97.0 | 90.2 | 49.1 |
| n_results | 5 | 5 | 5 |
| keyword_rate | 1.0 | 0.857 | 0.286 |
| avg_content_len | 2368.4 | 3554.6 | 215.2 |
| latency_ms | 897 | 1404 | 1929 |
| error | None | None | None |

- **LLM tavily**: 5 — 提供了部分利润率和ROE指标，但缺失营收绝对值，且引用的网页数据时间线混乱存在幻觉。
- **LLM anysearch_general**: 2 — 来源虽为官方公告，但仅提取了财报开头的免责声明，完全未提供用户所需的任何财务指标数字。
- **LLM anysearch_vertical**: 8 — 直接返回结构化金融数据，ROE和毛利率等比率指标准确且时效清晰，但缺失营收和净利润的绝对金额。

- Tavily preview: Latest financial report shows Guizhou Moutai's net profit at 82,320.07 million CNY, with a net profit margin of 50.53%. The company's ROE is 10.57%, and its gross profit margin is 
- AnyG preview: | 证券代码：600519 | | 贵州茅台酒股份有限公司 | 证券简称：贵州茅台 2026 年第一季度报告 | | --- | --- | --- | --- | | 漏，并对其内容的真实性、准确性和完整性承担法律责任。 | 本公司董事会及全体董事保证本公告内容不存在任何虚假记载、误导性陈述或者重大遗 | | | 重要内容提示 公司董事会及董事、高级管理人
- AnyV preview: {"ann_date":"20260425","current_ratio":7.0607,"debt_to_assets":12.1227,"end_date":"20260331","grossprofit_margin":89.7592,"netprofit_margin":52.2245,"roa":11.9998,"roe":10.5687,"ro

### us_quote — 美股报价估值
- Query: `NVDA NVIDIA PE market cap free cash flow latest earnings`
- Vertical: `finance.quote` sdp=`type=stock,symbol=NVDA,cn_code=`

| | Tavily | AnyGeneral | AnyVertical |
|--|--------|------------|-------------|
| composite | 100.0 | 94.5 | 49.3 |
| n_results | 5 | 5 | 2 |
| keyword_rate | 1.0 | 1.0 | 0.5 |
| avg_content_len | 1617.6 | 3960.8 | 288.5 |
| latency_ms | 698 | 1535 | 2225 |
| error | None | None | None |

- **LLM tavily**: 9 — 直接提供了市盈率、市值、自由现金流和最新财报日期等所有关键指标，数据清晰且来源可信。
- **LLM anysearch_general**: 4 — 仅提供财报新闻标题和统计页面链接，未在回答中直接提取并展示市盈率、市值和自由现金流等具体财务数字。
- **LLM anysearch_vertical**: 5 — 提供了市值和实时报价等行情数据，但缺失市盈率、自由现金流和最新财报等核心估值与基本面指标。

- Tavily preview: As of 2026-07-13, NVDA's latest earnings report shows a free cash flow of $48.59 billion for the fiscal quarter ending April 30, 2026. The company's market cap is $4.72 trillion, a
- AnyG preview: NVIDIA Corporation - NVIDIA Announces Financial Results for First Quarter Fiscal 2027 ### NVIDIA Announces Financial Results for First Quarter Fiscal 2027 May 20, 2026 Download thi
- AnyV preview: Symbol: NVDA | Name: NVIDIA Corporation | Exchange: NASDAQ | Price: 210.96 | Open: 201.92 | PrevClose: 202.78 | Change: +8.18 | Change%: +4.03% | DayHigh: 211.00 | DayLow: 201.92 |

### us_fundamental — 美股基本面卡片
- Query: `AAPL valuation metrics analyst ratings income statement`
- Vertical: `finance.fundamental` sdp=`type=overview,symbol=AAPL,cn_code=`

| | Tavily | AnyGeneral | AnyVertical |
|--|--------|------------|-------------|
| composite | 100.0 | 92.5 | 47.0 |
| n_results | 5 | 5 | 1 |
| keyword_rate | 1.0 | 0.833 | 0.333 |
| avg_content_len | 1900.0 | 3912.8 | 480.0 |
| latency_ms | 865 | 1101 | 1739 |
| error | None | None | None |

- **LLM tavily**: 8 — 提供了市值、营收、EPS及分析师评级和目标价，数据来源权威且数字可用性强，但利润表细节稍显不足。
- **LLM anysearch_general**: 2 — 抓取内容多为网页UI文本和错误提示，未能提取有效的估值、评级或财务数据，可用性极低。
- **LLM anysearch_vertical**: 9 — 精准提供了分析师评级分布、目标价及核心估值与盈利指标，数据结构化且高度契合基本面卡片需求。

- Tavily preview: Apple Inc. (AAPL) has a market capitalization of $4.53 trillion, a revenue of $451.44 billion, and an earnings per share of $8.35. Analysts rate AAPL with an average recommendation
- AnyG preview: Apple (AAPL) Stock Statistics, Valuation & Financial Metrics Symbols Symbols Aime AI Charts 🏆World Cup Markets Portfolio News Trade AInvest★★★★★3-DAY FREE Catch pre-market movers w
- AnyV preview: Symbol: AAPL | Grades(Buy): StrongBuy=1 Buy=69 Hold=34 Sell=7 StrongSell=0 | PriceTarget: MonthAvg=315.00 (n=1) | QuarterAvg=326.86 (n=14) | YearAvg=300.95 (n=59) | AllTimeAvg=227.

### industry — 白酒行业中文
- Query: `中国白酒行业 2026 竞争格局 渠道库存 茅台 五粮液`
- Vertical: `finance.news` sdp=`type=general,symbol=,cn_code=`

| | Tavily | AnyGeneral | AnyVertical |
|--|--------|------------|-------------|
| composite | 95.0 | 100.0 | 62.0 |
| n_results | 5 | 5 | 5 |
| keyword_rate | 1.0 | 1.0 | 0.0 |
| avg_content_len | 2240.4 | 3033.0 | 416.0 |
| latency_ms | 863 | 1805 | 1485 |
| error | None | None | None |

- **LLM tavily**: 9 — 高度契合查询意图，详细提供了2026年白酒竞争格局、渠道库存及头部企业市占率等具体数据，来源权威且时效性强。
- **LLM anysearch_general**: 8 — 提供了毕马威等权威机构发布的2026年白酒行业深度报告及投资策略，包含宏观财务与市场数据，但针对茅台五粮液及渠道库存的微观细节略逊于tavily。
- **LLM anysearch_vertical**: 1 — 检索结果完全偏离主题，返回的是海外温控、半导体及充电桩等无关行业的英文资讯，无任何相关性。

- Tavily preview: By 2026, China's baijiu industry is consolidating, with top brands like Maotai and Wuliangye leading. The market is shifting towards quality and away from quantity. Head companies 
- AnyG preview: © 2026 毕马威华振会计师事务所 (特殊普通合伙) — 中国合伙制会计师事务所，毕马威企业咨询 (中国) 有限公司 — 中国有限责任公司，毕马威会计师事 务所 — 澳门特别行政区合伙制事务所，及毕马威会计师事务所 — 香港特别行政区合伙制事务所，均是与毕马威国际有限公司 (英国私营担保有限公司) 相 关联的独立成员所全球组织中的成员。版权所有，不得转载。
- AnyV preview: CORK, Ireland, July 13, 2026 /PRNewswire/ -- Johnson Controls International plc (NYSE: JCI), a global technology leader in thermal management, mission-critical building systems, en

### news_tencent — 公司新闻
- Query: `腾讯 最新动态 游戏 广告 云 监管 2026`
- Vertical: `finance.news` sdp=`type=stock,symbol=TCEHY,cn_code=`

| | Tavily | AnyGeneral | AnyVertical |
|--|--------|------------|-------------|
| composite | 94.5 | 82.0 | 53.0 |
| n_results | 5 | 5 | 5 |
| keyword_rate | 1.0 | 0.667 | 0.0 |
| avg_content_len | 1636.2 | 3145.4 | 226.6 |
| latency_ms | 868 | 1638 | 1427 |
| error | None | None | None |

- **LLM tavily**: 8 — 涵盖游戏、广告、云业务及详细财务数据，时效性强，但对监管动态着墨较少。
- **LLM anysearch_general**: 7 — 准确覆盖游戏、监管（未保）及AI动态，时效性极佳，但缺乏财务数字与广告业务信息。
- **LLM anysearch_vertical**: 5 — 侧重于投资并购与宏观市场，未直接回应游戏、广告、云及监管等核心业务，缺乏财务数据。

- Tavily preview: Tencent's 2026 growth relies on AI-driven advertising, international game expansion, and cloud services. AI enhances ad targeting and efficiency, while games like "Honor of Kings" 
- AnyG preview: 腾讯游戏发布会SPARK 2026公布45项重磅更新，聚焦未来玩家体验 - Tencent 腾讯 # Tencent腾讯 简 | 繁 | EN # 腾讯游戏发布会SPARK 2026公布45项重磅更新，聚焦未来玩家体验 “聚焦最新内容，展现腾讯游戏持续为全球玩家打造创新互动数字体验的长期投入 今日，腾讯游戏于年度游戏发布会SPARK 2026上公布了45项重
- AnyV preview: Tencent is ​in talks ‌to become Manus' ​largest ​shareholder as investors ⁠seek alternatives ​after ​Beijing ordered Meta to unwind ​its $2 ​billion acquisition of ‌the ⁠AI start-u

### risk_pdd — 监管风险事件
- Query: `拼多多 PDD Temu 监管风险 欧盟 诉讼 最新`
- Vertical: `finance.news` sdp=`type=stock,symbol=PDD,cn_code=`

| | Tavily | AnyGeneral | AnyVertical |
|--|--------|------------|-------------|
| composite | 95.0 | 85.0 | 65.7 |
| n_results | 5 | 5 | 5 |
| keyword_rate | 1.0 | 0.667 | 0.333 |
| avg_content_len | 1971.2 | 1472.4 | 231.2 |
| latency_ms | 865 | 1400 | 1367 |
| error | None | None | None |

- **LLM tavily**: 8 — 信息丰富且包含财务数据，但部分来源如Instagram权威性稍弱。
- **LLM anysearch_general**: 9 — 来源极其权威且高度聚焦欧盟监管处罚事件，但缺乏公司财务指标。
- **LLM anysearch_vertical**: 5 — 内容偏向股价表现与关税政策，未直接回应监管诉讼与具体处罚事件。

- Tavily preview: In 2026, the EU fined Temu €200 million for failing to regulate illegal products on its platform. Temu must submit a compliance plan by August 28, or face further penalties. The fi
- AnyG preview: 被指销售不合规商品 Temu被欧盟重罚2亿欧元 1. 跳转至内容 2. 跳转至主菜单 3. 跳转到更多DW网站 https://p.dw.com/p/5ETev Temu目前在欧洲拥有高达1.3亿用户 （德国之声中文网）本周四（5月28日），欧盟委员会宣布对拼多多旗下跨境电商平台Temu处以2亿欧元（约合2.3亿美元）罚款，理由是该公司未能有效遏制平台上非法
- AnyV preview: Shares of Alibaba (NYSE:BABA | BABA Price Prediction) are up 9% to $106 and change in early Wednesday trading, leading a broad rally in Chinese internet and e-commerce names. | In 

### a_news_flash — A股快讯
- Query: `A股 白酒 茅台 今日快讯`
- Vertical: `finance.news` sdp=`type=flash,news_src=eastmoney,period=7d,symbol=,cn_code=`

| | Tavily | AnyGeneral | AnyVertical |
|--|--------|------------|-------------|
| composite | 100.0 | 89.0 | 82.5 |
| n_results | 5 | 5 | 5 |
| keyword_rate | 1.0 | 1.0 | 0.667 |
| avg_content_len | 2291.4 | 1375.8 | 951.8 |
| latency_ms | 7798 | 2751 | 3360 |
| error | None | None | None |

- **LLM tavily**: 9 — 高度契合A股白酒茅台快讯意图，提供准确的股价、批价及板块涨幅等数字，来源权威且时效性强。
- **LLM anysearch_general**: 6 — 提供白酒现货零售价格快讯，来源可信且具时效性，但偏向商品终端价格而非A股股票行情，相关性稍弱。
- **LLM anysearch_vertical**: 2 — 仅提供茅台酒的百科介绍与官网静态信息，完全缺乏A股行情与今日快讯内容，相关性与时效性极差。

- Tavily preview: A-shares of Kweichow Moutai surged, with the stock price exceeding 1700 yuan, reflecting strong market interest in high-end liquor. The stock's recent rise indicates investor confi
- AnyG preview: 酒价内参7月13日价格发布：精品茅台下跌5元_新浪财经_新浪网 移动客户端 登录 产经 > 正文 行情 股吧 新闻 外汇 新三板 # 酒价内参7月13日价格发布：精品茅台下跌5元 酒价内参7月13日价格发布：精品茅台下跌5元 酒业内参 新浪财经“酒价内参”过去24小时收集的数据显示，中国白酒市场主要大单品的终端零售均价7月13日整体低位微幅回落。如果主要单品
- AnyV preview: 茅台集团官网 下滑查看更多 # 新闻资讯 这杯酒 敬父亲 温馨提示：谨防“茅台会所”等虚假招商 温馨提示。为保障广大消费者合法权益。我司温馨提示广大消费者。认准并选择官方、正规渠道购买贵州茅台酒。 一、贵州茅台酒线上销售渠道 1.官... 二十四节气 | 夏至：夏至已至 美好... 二十四节气 | 夏至：夏至已至 美好始长 # 茅台家族 # 茅台短视频 ##

## 结论

1. **启发式综合分**：Tavily 97.69 / AnyGeneral 90.8 / AnyVertical 56.49 → 最佳 **Tavily**
2. **LLM 裁判均分**：Tavily 8.12 / AnyGeneral 5.25 / AnyVertical 5.12 → 最佳 **Tavily**
3. 延迟：Tavily 1718.0 / AnyG 1783.38 / AnyV 1950.25 ms
4. 建议：Tavily 做通用/事件主路；AnySearch 通用做快回退；finance 垂直域在 quote/fundamental 题上作为补数通道
5. 局限：LLM 单次采样；垂直 sdp 人工映射

JSON：`/Users/kay01.hou/Documents/Github/berkshire-ai/reports/_search_compare/tavily_vs_anysearch_r2.json`

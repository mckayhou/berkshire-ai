# Tavily vs AnySearch 搜索质量对照

- 时间：2026-07-13T20:42:51
- 查询数：6（投研风格中英混合）
- max_results：5
- 胜场：Tavily **5** / AnySearch **1** / 平 **0**

## 均值对比

| 指标 | Tavily | AnySearch | 说明 |
|------|--------|-----------|------|
| composite (0-100) | **95.67** | **90.5** | 启发式综合分 |
| keyword_rate | 0.97 | 0.83 | 关键词命中率 |
| unique_domains | 4.67 | 4.5 | 来源多样性 |
| avg_content_len | 1937.53 | 3006.43 | 正文均长 |
| has_answer_rate | 1.0 | 1.0 | 有摘要/answer |
| latency_ms | 5418.83 | 2328.67 | 端到端延迟 |

## 分 query

| id | intent | Tavily | AnySearch | Δ(A-T) | winner |
|----|--------|--------|-----------|--------|--------|
| hk_price | 港股实时估值 | 100.0 | 96.2 | -3.8 | tavily |
| a_fin | A股财务指标 | 97.0 | 90.2 | -6.8 | tavily |
| us_val | 美股估值英文 | 97.5 | 88.2 | -9.3 | tavily |
| industry | 行业趋势中文 | 95.0 | 100.0 | +5.0 | anysearch |
| news | 公司新闻 | 89.5 | 82.0 | -7.5 | tavily |
| risk | 风险/事件 | 95.0 | 86.4 | -8.6 | tavily |

## 分 query 细节

### hk_price — 港股实时估值
**Query**: `0700.HK 腾讯控股 股价 市值 PE PB 股息率`

| | Tavily | AnySearch |
|--|--------|-----------|
| composite | 100.0 | 96.2 |
| n_results | 5 | 5 |
| unique_domains | 5 | 5 |
| keyword_rate | 1.0 | 0.875 |
| avg_content_len | 1791.4 | 2872.4 |
| latency_ms | 4789 | 2150 |
| has_answer | True | True |
| finance_hits | 7 | 4 |

**Tavily answer preview**: Tencent Holdings' stock price is HKD 460.20, market cap is HKD 4.143 trillion, PE ratio is 16.52, PB ratio is 3.18, and dividend yield is 1.15%.

**AnySearch answer preview**: 腾讯控股（hk00700）股票价格_股票实时行情_走势图-手机新浪财经 * 网页版港股行情数据延时，若需查看实时行情，请点击下方APP ADR换算价 相对港股 腾讯控股（hk00700）股票价格\_股票实时行情\_走势图-手机新浪财经 \* 网页版港股行情数据延时，若需查看实时行情，请点击下方APP ADR换算价 相对港股 ** | 腾讯控股(00700)市盈率|估值|基本面 - 理杏仁 腾讯控股 港股通空最新回购 (2026-01-1

**Tavily top domains**: lixinger.com, xueqiu.com, cn.investing.com, quotes.sina.cn, hk.finance.yahoo.com

**AnySearch top domains**: quotes.sina.cn, lixinger.com, xueqiu.com, moomoo.com, google.com


### a_fin — A股财务指标
**Query**: `600519 贵州茅台 营收 净利润 ROE 毛利率 最新财报`

| | Tavily | AnySearch |
|--|--------|-----------|
| composite | 97.0 | 90.2 |
| n_results | 5 | 5 |
| unique_domains | 4 | 4 |
| keyword_rate | 1.0 | 0.857 |
| avg_content_len | 2368.4 | 3554.6 |
| latency_ms | 6451 | 1931 |
| has_answer | True | True |
| finance_hits | 8 | 3 |

**Tavily answer preview**: Latest financial report shows Guizhou Moutai's net profit at 82,320.07 million CNY, with a net profit margin of 50.53%. The company's ROE is 10.57%, and its gross profit margin is 89.76%.

**AnySearch answer preview**: | 证券代码：600519 | | 贵州茅台酒股份有限公司 | 证券简称：贵州茅台 2026 年第一季度报告 | | --- | --- | --- | --- | | 漏，并对其内容的真实性、准确性和完整性承担法律责任。 | 本公司董事会及全体董事保证本公告内容不存在任何虚假记载、误导性陈述或者重大遗 | | | 重要内容提示 公司董事会及董事、高级管理人员保证季度报告内容的真实、准确、完整，不 | | 证券代码：600519 | |

**Tavily top domains**: moomoo.com, cn.investing.com, pdf.dfcfw.com, duplik-1252068037.cos.ap-beijing.myqcloud.com, pdf.dfcfw.com

**AnySearch top domains**: dataclouds.cninfo.com.cn, pdf.dfcfw.com, hibor.com.cn, ddx.gubit.cn, pdf.dfcfw.com


### us_val — 美股估值英文
**Query**: `NVDA NVIDIA PE market cap free cash flow latest earnings`

| | Tavily | AnySearch |
|--|--------|-----------|
| composite | 97.5 | 88.2 |
| n_results | 5 | 5 |
| unique_domains | 5 | 4 |
| keyword_rate | 1.0 | 0.875 |
| avg_content_len | 1617.6 | 3960.8 |
| latency_ms | 3948 | 2723 |
| has_answer | True | True |
| finance_hits | 3 | 2 |

**Tavily answer preview**: As of 2026-07-13, NVDA's latest earnings report shows a free cash flow of $48.59 billion for the fiscal quarter ending April 30, 2026. The company's market cap is $4.72 trillion, and its P/E ratio is 46.8. The last earni

**AnySearch answer preview**: NVIDIA Corporation - NVIDIA Announces Financial Results for First Quarter Fiscal 2027 ### NVIDIA Announces Financial Results for First Quarter Fiscal 2027 May 20, 2026 Download this Press Release - Re | NVIDIA (NVDA) Sta

**Tavily top domains**: alphaquery.com, macrotrends.net, barchart.com, investing.com, stockanalysis.com

**AnySearch top domains**: investor.nvidia.com, stockanalysis.com, finance.yahoo.com, sec.gov, investor.nvidia.com


### industry — 行业趋势中文
**Query**: `中国白酒行业 2026 竞争格局 渠道库存 茅台 五粮液`

| | Tavily | AnySearch |
|--|--------|-----------|
| composite | 95.0 | 100.0 |
| n_results | 5 | 5 |
| unique_domains | 5 | 5 |
| keyword_rate | 1.0 | 1.0 |
| avg_content_len | 2240.4 | 3033.0 |
| latency_ms | 4607 | 2775 |
| has_answer | True | True |
| finance_hits | 2 | 4 |

**Tavily answer preview**: By 2026, China's baijiu industry is consolidating, with top brands like Maotai and Wuliangye leading. The market is shifting towards quality and away from quantity. Head companies are focusing on brand value and price st

**AnySearch answer preview**: © 2026 毕马威华振会计师事务所 (特殊普通合伙) — 中国合伙制会计师事务所，毕马威企业咨询 (中国) 有限公司 — 中国有限责任公司，毕马威会计师事 务所 — 澳门特别行政区合伙制事务所，及毕马威会计师事务所 — 香港特别行政区合伙制事务所，均是与毕马威国际有限公司 (英国私营担保有限公司) 相 关联的独立成员所全球组织中的成员。版权所有，不得转载。在中国印刷。 ## 编委会 ### 报告 | 毕马威 × 中国酒业协会：《202

**Tavily top domains**: finance.sina.com.cn, cnwinenews.com, chyxx.com, assets.kpmg.com, pdf.dfcfw.com

**AnySearch top domains**: assets.kpmg.com, chnmc.com, m.chyxx.com, news.qq.com, finance.sina.com.cn


### news — 公司新闻
**Query**: `腾讯 最新动态 游戏 广告 云 监管 2026`

| | Tavily | AnySearch |
|--|--------|-----------|
| composite | 89.5 | 82.0 |
| n_results | 5 | 5 |
| unique_domains | 4 | 4 |
| keyword_rate | 0.833 | 0.667 |
| avg_content_len | 1636.2 | 3145.4 |
| latency_ms | 8756 | 2632 |
| has_answer | True | True |
| finance_hits | 3 | 2 |

**Tavily answer preview**: Tencent's 2026 growth relies on AI-driven advertising, international game expansion, and cloud services. AI enhances ad targeting and efficiency, while games like "Honor of Kings" and "Peacekeeper Elite" drive revenue. C

**AnySearch answer preview**: 腾讯游戏发布会SPARK 2026公布45项重磅更新，聚焦未来玩家体验 - Tencent 腾讯 # Tencent腾讯 简 | 繁 | EN # 腾讯游戏发布会SPARK 2026公布45项重磅更新，聚焦未来玩家体验 “聚焦最新内容，展现腾讯游戏持续为全球玩家打造创新互动数字体验的长期投入 今日，腾讯游戏于年度游戏发布会SPARK 2026上公布了45项重磅更新。直播内容覆盖研发、发行与投资三大 | 腾讯游戏暑期未保行动：每周限玩3小

**Tavily top domains**: sohu.com, news.qq.com, sohu.com, cn.chinadaily.com.cn, static.www.tencent.com

**AnySearch top domains**: tencent.com, 36kr.com, news.qq.com, game.zol.com.cn, 36kr.com


### risk — 风险/事件
**Query**: `拼多多 PDD Temu 监管风险 欧盟 诉讼 最新`

| | Tavily | AnySearch |
|--|--------|-----------|
| composite | 95.0 | 86.4 |
| n_results | 5 | 5 |
| unique_domains | 5 | 5 |
| keyword_rate | 1.0 | 0.714 |
| avg_content_len | 1971.2 | 1472.4 |
| latency_ms | 3962 | 1761 |
| has_answer | True | True |
| finance_hits | 2 | 2 |

**Tavily answer preview**: In 2026, the EU fined Temu €200 million for failing to regulate illegal products on its platform. Temu must submit a compliance plan by August 28, or face further penalties. The fine highlights growing EU scrutiny of cro

**AnySearch answer preview**: 被指销售不合规商品 Temu被欧盟重罚2亿欧元 1. 跳转至内容 2. 跳转至主菜单 3. 跳转到更多DW网站 https://p.dw.com/p/5ETev Temu目前在欧洲拥有高达1.3亿用户 （德国之声中文网）本周四（5月28日），欧盟委员会宣布对拼多多旗下跨境电商平台Temu处以2亿欧元（约合2.3亿美元）罚款，理由是该公司未能有效遏制平台上非法商品的销售，违反欧盟《数字服务法》（DS | 欧盟对Temu罚款2亿欧元 因未排

**Tavily top domains**: app.myzaker.com, instagram.com, caifuhao.eastmoney.com, m.caixin.com, inews.hket.com

**AnySearch top domains**: dw.com, m.caixin.com, rfi.fr, cna.com.tw, news.qq.com


## 结论（基于本轮启发式）

### 总分与胜场
- **综合分均值**：Tavily **95.7** vs AnySearch **90.5**（Tavily 高约 5 分）
- **胜场 5:1**：Tavily 赢 5 场（港股估值、A股财务、美股、新闻、风险）；AnySearch 赢 1 场（白酒行业）
- **两边都有 answer / 都返回 5 条结果**，无失败

### 维度解读
| 维度 | 更强一方 | 观察 |
|------|----------|------|
| 关键词命中 | **Tavily** (0.97 vs 0.83) | 对 ticker/财务词更「贴 query」 |
| 正文深度 | **AnySearch** (均长 ~3006 vs ~1938) | snippet/content 更长，适合后处理 |
| 延迟 | **AnySearch** (~2.3s vs ~5.4s) | 约 **2.3× 更快** |
| 来源多样性 | 接近 (4.7 vs 4.5) | 都有多站 |
| 合成摘要 | **Tavily 原生 answer** | 数字句更干净；AnySearch 多为 snippet 拼接 |

### 投研使用建议
1. **默认 hybrid 合理**：Tavily 做主路（估值/财务/事件问句更稳）；AnySearch 做回退与补源（更快、正文更长）
2. **行业/中文宏观叙事**可优先试 AnySearch（本轮 industry 满分）
3. **不要单看 composite**：AnySearch 的 finance **垂直域**未在本轮启用；启用 `get_sub_domains` + `finance.quote` 可能改写「估值类」对比
4. 本评测是 **关键词/结构启发式**，不是人类相关性双盲；正式选型可再加人工抽检 10 条

原始 JSON：`reports/_search_compare/tavily_vs_anysearch.json`

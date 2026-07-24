---
name: berkshire-financial-data
description: |
  财务数据双源获取与交叉验证强制规范（美股/港股/A股/台股）。
  所有 berkshire 技能在提取数字时必须遵循本规范，并调用 financial_rigor.py 验证。
  台股走 tools/twstock_data.py（FinMind）。
version: 10.29.3
---

# 财务数据获取与交叉验证规范

**激活条件**：任何 berkshire 技能需要拉财务数字、估值、营收拆解时，**必须**先引用或执行本规范。

本规范适用于所有涉及企业财务数据的研究。**每个关键数据必须来自两个独立来源，误差>1%须标记。**

### 联网检索（hybrid：Tavily 主 + AnySearch 补）

质量对照后（`reports/_search_compare/`）：通用/新闻/事件 **优先 Tavily**；AnySearch 通用作回退；**结构化财务卡片**可加 AnySearch `finance.fundamental`。

```bash
# 默认流水线
SEARCH_MODE=hybrid python3 src/tavily_search.py stock {ticker} {company_name}
SEARCH_MODE=hybrid python3 src/tavily_search.py financial {ticker}

# 结构化财务补数（A 股示例）
python3 skills/anysearch/scripts/anysearch_cli.py get_sub_domains --domain finance
python3 skills/anysearch/scripts/anysearch_cli.py search "{company} 财务指标" --domain finance \
  --sub_domain finance.fundamental --sdp type=indicator,symbol=,cn_code={code}.SH --max_results 5
```

密钥：`TAVILY_API_KEYS` / `ANYSEARCH_API_KEY`（仅 `.env`），**禁止写入 skill 正文**。见 `anysearch-web.md`。

---

## 数据源优先级

### 美股（PDD、腾讯ADR、网易ADR等）

| 优先级 | 来源 | URL | 获取方式 |
|--------|------|-----|---------|
| 1（主） | **macrotrends** | macrotrends.net/stocks/charts/{ticker} | 直接访问，无需注册 |
| 2（副） | **stockanalysis** | stockanalysis.com/stocks/{ticker}/financials | 直接访问，无需注册 |
| 原始一手 | SEC EDGAR | sec.gov/cgi-bin/browse-edgar | 10-K / 10-Q 原文 |

### 港股（腾讯0700、网易9999、美团3690等）

| 优先级 | 来源 | URL | 获取方式 |
|--------|------|-----|---------|
| 1（主） | **aastocks** | aastocks.com/tc/stocks/analysis/company-fundamental | 直接访问 |
| 2（副） | **macrotrends**（ADR代码） | 腾讯用TCEHY，网易用NTES | 直接访问 |
| 原始一手 | HKEX披露易 | hkexnews.hk | 年报PDF |

### A股（三七互娱、吉比特等）

| 优先级 | 来源 | URL | 获取方式 |
|--------|------|-----|---------|
| 1（主） | **东方财富** | eastmoney.com → 搜股票代码 → 财务报表 | 直接访问 |
| 2（副） | **巨潮资讯** | cninfo.com.cn | 原始年报/季报PDF |

### 台股（台积电 2330、联发科 2454、大立光 3008 等）

移植自上游 [xbtlin/ai-berkshire](https://github.com/xbtlin/ai-berkshire)；与本 fork 的 AnySearch/Tavily 规范并存。

| 优先级 | 来源 | URL | 获取方式 |
|--------|------|-----|---------|
| 1（主） | **FinMind API** | api.finmindtrade.com | `tools/twstock_data.py`（零依赖） |
| 2（副） | **Goodinfo** | goodinfo.tw/tw/StockDetail.asp?STOCK_ID={代码} | 直接访问 |
| 原始一手 | 公开资讯观测站（MOPS） | mops.twse.com.tw | 财报原文 / 月营收 |

```bash
python3 tools/twstock_data.py quote 2330        # 最新行情 + PER/PBR/殖利率 + 市值验算
python3 tools/twstock_data.py valuation 2330    # 估值 + PER 一年区间 + 52 周高低
python3 tools/twstock_data.py financials 2330   # 近 5 年年度核心财务
python3 tools/twstock_data.py revenue 2330      # 近 13 个月月营收及同比（台股独有）
python3 tools/twstock_data.py dividend 2330     # 近年股利政策
python3 tools/twstock_data.py search 台積        # 搜索代码（繁体）
```

台股注意：

1. **货币为新台币（TWD）**；与 HKD/CNY/USD 混排须显式标注并换算。
2. **月营收**是台股独有公开信号（每月约 10 日前披露上月营收），earnings-review / thesis-tracker 应优先用 `revenue`。
3. FinMind 损益表为**单季值**，`twstock_data` 已加总年度；不足 4 季会标注。
4. Token（可选）：环境变量 `FINMIND_TOKEN` 或 `local/finmind_token.txt`（`local/` 已 gitignore）。**禁止**写入 skill / 报告 / commit。
5. 交叉验证：FinMind vs Goodinfo（或 ADR 如 TSM）；ADR 注意存托比率（例：1 TSM ADR ≈ 5 股 2330）与汇率。
6. 美股 ADR 研究（如 TSM）仍可用 hybrid 检索 + Yahoo/macrotrends；台股原股数字以 `twstock_data` 为准并对齐 ADR。

---

## 执行规范

### 第一步：获取数据

对每个财务指标（收入、净利润、毛利率、经营现金流、资产负债率等），分别从**来源1**和**来源2**取数。

### 第二步：误差计算与标记

```
误差率 = |来源1数值 - 来源2数值| / 来源1数值 × 100%
```

| 误差 | 处理方式 |
|------|---------|
| ≤ 1% | ✅ 一致，取来源1数值，标注两个来源 |
| 1% ~ 5% | ⚠️ 标记"数据存在差异"，注明两个数值，说明可能原因（汇率/会计口径） |
| > 5% | ❌ 标记"数据存在重大差异"，必须查原始财报核实，不得直接使用 |

### 第三步：数据呈现格式

每个关键数据必须按以下格式标注：

```
收入：1,239亿元 ✅
  - macrotrends: 1,241亿元
  - stockanalysis: 1,237亿元
  - 误差: 0.3%
```

差异示例：

```
净利润：245亿元 ⚠️ 数据存在差异
  - macrotrends: 245亿元（GAAP）
  - stockanalysis: 278亿元（Non-GAAP）
  - 误差: 13.5% — 原因：会计口径不同（GAAP vs Non-GAAP）
```

---

## 常见差异原因（不一定是数据错误）

| 原因 | 说明 |
|------|------|
| GAAP vs Non-GAAP | 最常见，尤其是利润类数据 |
| 汇率换算 | 港币/人民币/美元/新台币换算时间点不同 |
| ADR vs 原股 | 台股/港股存托凭证与正股的比率、报价币种不同 |
| 财年定义 | 自然年 vs 财年（如苹果财年10月结束） |
| 合并口径 | 是否含少数股东权益 |
| 数据更新滞后 | 某平台尚未更新最新一期财报 |

---

## 特别规则

1. **未上市公司**（米哈游、莉莉丝等）：只有一手数据来源时，数据前标记 `[估计]`，不执行交叉验证
2. **季度数据 vs 年度数据**：优先使用年度数据做交叉验证，季度数据部分来源可能有滞后
3. **原始财报优先**：若两个来源均与原始财报（10-K/年报PDF）不符，以原始财报为准，标记来源错误

---

## 快速索引

| 场景 | 主要来源 | 备用来源 |
|------|---------|---------|
| PDD / 拼多多 | macrotrends.net/stocks/charts/PDD | stockanalysis.com/stocks/pdd |
| 腾讯 | macrotrends.net/stocks/charts/TCEHY | aastocks（0700.HK） |
| 网易 | macrotrends.net/stocks/charts/NTES | aastocks（9999.HK） |
| 三七互娱 | eastmoney.com（002555） | cninfo.com.cn |
| 吉比特 | eastmoney.com（603444） | cninfo.com.cn |
| Nintendo | macrotrends.net/stocks/charts/NTDOY | stockanalysis.com/stocks/ntdoy |
| Capcom | macrotrends（CCOEY） | stockanalysis（CCOEY） |
| 台积电 2330 / TSM ADR | `twstock_data.py`（2330） | Goodinfo / macrotrends TSM（注意 ADR 比率） |
| 联发科 2454 | `twstock_data.py` | Goodinfo |

---
name: berkshire-anysearch-web
description: |
  AnySearch 实时检索 Skill（Tavily 补充/优先路径）。
  通用网页搜索、垂直域（finance 等）、批量搜索、URL 全文 extract。
  投研数据获取、事实核查、新闻侦察时激活；与 src/tavily_search.py hybrid 互补。
version: 2.1.0
---

# AnySearch Web Search（berkshire 封装入口）

**激活条件**：需要联网检索、股价/财务实时事实、新闻归因、页面全文时；或用户提到 AnySearch / 实时搜索 / Tavily 不可用。

本技能包装官方 **AnySearch Skill**（`skills/anysearch/`，[文档](https://www.anysearch.com/docs) / [安装说明](https://anysearch.com/install/skill-install.md)），作为 Berkshire 投研管线中 **Tavily 的补充与优先 Skill 路径**。

## 密钥（切勿写入本文件或仓库）

| 优先级 | 来源 |
|--------|------|
| 1 | CLI `--api_key`（仅本地临时） |
| 2 | `skills/anysearch/.env` → `ANYSEARCH_API_KEY=...` |
| 3 | 项目根 `.env` / 环境变量 `ANYSEARCH_API_KEY` |
| 4 | 匿名（额度更低） |

Key 在 [console](https://anysearch.com/console/api-keys) 创建。已配置时优先用 Key，勿把 Key 贴进对话或报告。

## 运行时入口

先读 `skills/anysearch/runtime.conf`（若存在）取 `Command`。本仓库默认：

```bash
# 在 berkshire-ai 仓库根目录
python3 skills/anysearch/scripts/anysearch_cli.py <subcommand> ...
```

或：

```bash
cd skills/anysearch && python3 scripts/anysearch_cli.py <subcommand> ...
```

完整 agent 说明见：`skills/anysearch/SKILL.md`。

## 命令速查（投研常用）

```bash
CMD="python3 skills/anysearch/scripts/anysearch_cli.py"

# 1) 通用搜索
$CMD search "腾讯控股 市值 PE 股息" --max_results 5

# 2) 金融垂直域（推荐：先 get_sub_domains）
$CMD get_sub_domains --domain finance
$CMD search "0700.HK" --domain finance --sub_domain finance.quote \
  --sdp type=stock,symbol=0700.HK,cn_code= --max_results 5

# 3) 批量
$CMD batch_search --query "腾讯 最新财报" --query "0700 竞争格局" --max_results 3

# 4) 页面全文（Markdown）
$CMD extract "https://example.com/report"
```

**垂直域规则**：finance / academic / code / legal 等有明确域归属时，**必须先** `get_sub_domains`，再带 `--domain` / `--sub_domain` / `--sdp` 搜索；参数 schema 以 `get_sub_domains` 返回为准，禁止臆造。

## 与 Tavily / hybrid 的关系（质量对照后策略）

实测对照（2026-07-13，见 `reports/_search_compare/`）：

| 轮次 | 结论摘要 |
|------|----------|
| R1 启发式 6 题 | Tavily 综合分 **95.7** vs AnySearch **90.5**（胜 5:1）；Any 更快、正文更长 |
| R2 + finance 垂直 + LLM 裁判 8 题 | Tavily 启发式 **97.7** / LLM **8.1**；Any 垂直整体偏低，但 **fundamental 卡片** 上 LLM 给高分（A 股 8、美股 overview 9） |

**推荐路由（投研默认）**：

| 场景 | 优先 | 次选 |
|------|------|------|
| 通用网页 / 新闻 / 风险事件 / 英文估值问句 | **Tavily**（`src/tavily_search.py` 或 hybrid 主路） | AnySearch 通用回退 |
| 结构化财报/指标卡片（A 股 indicator、美股 overview） | **AnySearch 垂直** `finance.fundamental` | Tavily + 交易所/年报 |
| 要长正文后处理、或 Tavily 失败/空 | AnySearch 通用 | extract URL |
| 批量 / 多意图 | AnySearch `batch_search` | 多次 Tavily |

| 路径 | 何时用 |
|------|--------|
| `SEARCH_MODE=hybrid` + Tavily Key | **默认流水线**（Tavily 主 + Any 回退） |
| 本 Skill CLI `finance.fundamental` | 要结构化财务补数时 |
| 本 Skill CLI 通用 search / extract | 快回退、抽页、batch |

投研 skill 拉实时网文时：**不要默认只走 AnySearch**；按上表路由，数字仍须 `financial_rigor` 双源验证。

## 输出用法

- CLI 默认输出面向 Agent 的 Markdown 结果块（标题 / URL / 摘要）。
- 写入研报时：保留 **URL + 日期/抓取时刻**；数字仍须走 `financial_rigor` / 双源规范（见 `financial-data`）。
- 不得把检索原文整页粘贴进报告；摘关键句并标注来源。

## 失败降级

1. 报错 / 401 / 配额 → 提示用户检查 `ANYSEARCH_API_KEY` 与网络  
2. 回退：`SEARCH_MODE=hybrid python3 src/tavily_search.py search "<query>"`  
3. 再回退：公开页面 + `financial-data` 双源表  

## 平台同步

```bash
# 仓库内改完后
./update-platforms.sh   # 同步 OpenClaw + QwenPaw（含 skills/anysearch/ 目录）
```

OpenClaw 目录 skill 名：`anysearch`（`SKILL.md`）；本入口 md 同步为 `berkshire-anysearch-web`。

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

## 与 Tavily / hybrid 的关系

| 路径 | 何时用 |
|------|--------|
| **本 Skill（AnySearch CLI）** | Agent 会话内首选：垂直域、extract、batch、结构化 Markdown |
| `python3 src/tavily_search.py ...` | 脚本/流水线；`SEARCH_MODE=hybrid` 时 Tavily 主 + AnySearch 回退 |
| 仅 Tavily | 已有 `TAVILY_API_KEYS` 且只跑旧 CLI |

投研 skill（`investment-research` / `news-pulse` / `financial-data`）拉实时网文时：**优先本 Skill**；失败再 `tavily_search.py` 或用户批准的其他源。

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

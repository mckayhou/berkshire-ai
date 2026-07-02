# 通达信 TQ MCP 工具设计（外部 Windows 执行层）

> **状态：不实施** — 当前环境无 Windows，不部署通达信 / `TPythClient.dll` / MCP 执行层。  
> 打板研究请仅用本仓库 `limitup_screener_bridge`（本地 CSV，跨平台）。  
> 下文保留作架构备忘，**无需跟进实现**。

---

## 1. 架构定位

```text
┌──────────────────── berkshire-ai (macOS/Linux) ────────────────────┐
│  limitup_screener_bridge / factor_screener_bridge / thesis_queue   │
│  本地 CSV · pytdx · 定性投研                                        │
└────────────────────────────┬───────────────────────────────────────┘
                             │ JSON 候选 / 研究队列
                             ▼
┌──────────────────── Windows MCP Host ──────────────────────────────┐
│  tdx-tq-mcp (待实现) ← TPythClient.dll ← 通达信客户端 + TQ 插件    │
│  实时行情 · 竞价 · 实盘下单                                         │
└────────────────────────────────────────────────────────────────────┘
```

| 层 | 职责 | 本仓库 |
|----|------|--------|
| 研究层 | 因子挖掘、五维打板评分、论文队列 | ✅ 已实现 |
| 执行层 | 毫秒行情、集合竞价、委托下单 | ❌ 仅设计文档 |

---

## 2. MCP Server 约束

| 项 | 要求 |
|----|------|
| 传输 | `stdio`（Cursor/Claude Desktop）或 `streamable-http`（远程） |
| 运行环境 | Windows 64 位，通达信已登录，TQ 插件已加载 |
| DLL | `TPythClient.dll`（通达信安装目录 `PYPlugins/`） |
| Python | 3.9+，`numpy`、`pandas` |
| 安全 | 下单类 tool 默认 `dry_run=true`；需显式 `confirm_live=true` |

---

## 3. 建议 Tool 清单

### 3.1 连接与状态

| Tool | 参数 | 返回 | 对应 tq API |
|------|------|------|-------------|
| `tdx_connect` | `path`（插件路径）, `dll_path?` | `{run_id, ok}` | `tq.initialize()` |
| `tdx_disconnect` | — | `{ok}` | `tq.close()` |
| `tdx_status` | — | `{run_id, initialized}` | `tq._initialized`, `tq.run_id` |

### 3.2 行情与数据

| Tool | 参数 | 返回 | 对应 tq API |
|------|------|------|-------------|
| `tdx_snapshot` | `code`（如 `600519.SH`） | 现价、昨收、开高低、量额 | `get_market_snapshot` |
| `tdx_snapshots_batch` | `codes[]`, `max?` | 批量快照 | 循环 snapshot |
| `tdx_kline` | `codes[]`, `period`, `start`, `end` | OHLCV DataFrame JSON | `get_market_data` |
| `tdx_stock_list` | `market?` | 全市场代码列表 | `get_stock_list` |
| `tdx_block_stocks` | `block_code` | 板块成分股 | `GetBlockStocksInStr` 封装 |
| `tdx_trade_calendar` | `start`, `end` | 交易日历 | `get_trade_calendar` |

### 3.3 打板 / 选股（与 berkshire 对齐）

| Tool | 参数 | 返回 | 说明 |
|------|------|------|------|
| `tdx_scan_limitup` | `pool?`, `min_score?`, `top_n?` | 候选列表 + 五维评分 | 调用 `UnifiedScoringSystem` + 实时快照 |
| `tdx_auction_scan` | `codes[]`, `min_high_open?`, `max_high_open?` | 9:15–9:25 竞价异动 | `auction_analyzer` 逻辑 |
| `tdx_score_symbol` | `code` | 单票评分明细 | 与 `limitup_scoring.py` 字段对齐 |

**字段对齐**（便于与 `limitup_screener_bridge --json` 合并）：

```json
{
  "ticker": "600519",
  "signal_type": "封涨停",
  "score": 82.5,
  "rise_pct": 10.0,
  "high_open_ratio": 3.2,
  "details": { "评分明细": { "总分": "82.5", "...": "..." } }
}
```

### 3.4 交易与风控（高风险）

| Tool | 参数 | 返回 | 对应 tq API |
|------|------|------|-------------|
| `tdx_order` | `account`, `code`, `side`, `price`, `qty`, `dry_run`, `confirm_live` | 委托结果 | `order_stock` |
| `tdx_positions` | `account` | 持仓 | 账户查询封装 |
| `tdx_cancel` | `order_id` | 撤单结果 | 撤单 API |
| `tdx_set_alert` | `code`, `price`, `reason` | 预警 ID | `send_warn` |
| `tdx_add_favorites` | `block`, `codes[]` | ok | `send_user_block` |

### 3.5 运维

| Tool | 参数 | 返回 |
|------|------|------|
| `tdx_refresh_cache` | `scope`（hq/kline/all） | ok |
| `tdx_diagnose_kline` | `code` | 接口诊断报告 |

---

## 4. 实现骨架（FastMCP 示例）

```python
# 外部项目: tdx-tq-mcp/server.py（不在 berkshire-ai 内）
from mcp.server.fastmcp import FastMCP
from tqcenter import tq  # 来自 TDX-MCP-LHDB-Agent 或 fork

mcp = FastMCP("tdx-tq")

@mcp.tool()
def tdx_connect(path: str, dll_path: str = "") -> dict:
    tq.initialize(path=path, dll_path=dll_path or None)
    return {"ok": True, "run_id": tq.run_id}

@mcp.tool()
def tdx_snapshot(code: str) -> dict:
    return tq.get_market_snapshot(code)

@mcp.tool()
def tdx_order(
    account_id: str,
    stock_code: str,
    side: str,
    price: float,
    quantity: int,
    dry_run: bool = True,
    confirm_live: bool = False,
) -> dict:
    if dry_run or not confirm_live:
        return {"dry_run": True, "would_order": locals()}
    order_type = "0" if side == "buy" else "1"
    return tq.order_stock(account_id, stock_code, order_type, price, quantity)
```

`cursor mcp.json` 示例：

```json
{
  "mcpServers": {
    "tdx-tq": {
      "command": "python",
      "args": ["D:/tdx-tq-mcp/server.py"],
      "env": { "TDX_DLL_PATH": "D:/new_tdx64/PYPlugins/TPythClient.dll" }
    }
  }
}
```

---

## 5. 与 berkshire-ai 的衔接工作流

```bash
# macOS：研究侧打板评分（日线代理）
python3 tools/limitup_screener_bridge.py --json -o limitup_scan.json
python3 tools/thesis_queue.py --from-limitup-scan limitup_scan.json --json

# Windows MCP：盘中确认 + 可选下单
# Agent 调用 tdx_auction_scan / tdx_snapshot 验证 limitup_scan 候选
# 人工确认后 tdx_order(..., dry_run=false, confirm_live=true)
```

| 步骤 | 环境 | 工具 |
|------|------|------|
| 盘后选股 | berkshire | `limitup_screener_bridge` |
| 盘前竞价 | Windows MCP | `tdx_auction_scan` |
| 盘中确认 | Windows MCP | `tdx_snapshot`, `tdx_score_symbol` |
| 入研究队列 | berkshire | `thesis_queue.py` |
| 实盘委托 | Windows MCP | `tdx_order`（需双重确认） |

---

## 6. 风险与边界

1. **TDX-MCP-LHDB-Agent 仓库名含 MCP，但未实现协议** — 需自行包装 `tqcenter.py`。
2. **打板评分**：berkshire 用**日线收盘代理**；实盘竞价/封板需 MCP 实时快照。
3. **合规**：下单 tool 必须默认 dry-run；日志脱敏账户 ID。
4. **跨平台**：MCP Host 仅 Windows；berkshire 候选 JSON 可 SCP/API 同步。

---

## 7. 参考

- 上游仓库：https://github.com/adambbhe/TDX-MCP-LHDB-Agent
- 本仓库五维评分实现：`tools/ashare_alphagpt/limitup_scoring.py`
- 筛选桥接：`tools/limitup_screener_bridge.py`
- 三库融合边界：`docs/quant_data_fusion.md`

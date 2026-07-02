# Berkshire AI V10.0 - TextGrad 化设计

> 基于 TextGrad (Nature 2025) 的自动微分思想，重构 Berkshire 进化机制

## ✅ 实现现状 (截至 V10.5)

本文档同时描述「已实现的脚手架」与「未来的完整自进化引擎 (Option B)」。两者请勿混淆：

| 能力 | 状态 | 说明 |
|:-----|:-----|:-----|
| 计算图 `BerkshireGraph` | ✅ 已实现 | 18 节点 5 层，拓扑排序 + 反向遍历 |
| 单一来源 `MASTERS` | ✅ 已实现 (V10.5) | 变量/边/梯度全部从 `MASTERS` 派生，新增大师只改一处 |
| 结构化梯度 `Gradient` | ✅ 已实现 (V10.5) | `ok`/`score`/`issues`/`text`，控制流读 `ok`，不解析 emoji |
| `backward(scores)` 反向传播 | ✅ 已实现 | 输入为各大师评分 `Dict[str, float]`，输出 `Dict[str, Gradient]` |
| 优化器 `TextualGradientDescent.step()` | ✅ 已实现 (V10.13) | 注入 `llm` 后对未达标的 prompt 变量调用 `apply_gradient` **真实改写 `Variable.value`**；不注入则仅记录更新计划（向后兼容） |
| 已实现收益反馈闭环 | ✅ 已实现 (V10.11) | `decision_log` + `realized_feedback`：真实收益 → alpha → 各大师校准评分 → `backward()`（吸收自 TradingAgents） |
| 多空对抗辩论 | ✅ 已实现 (V10.11) | `debate.py` + `BerkshireGraph.debate()`：bull/bear case + 结构化净判断 `DebateResult` |
| LLM 驱动的 Prompt 改写（Option B）| ✅ 已实现 (V10.13) | `prompt_optimizer.apply_gradient`：LLM 读「下游诊断 + 当前 Prompt」产出改进版 Prompt 回填变量。客户端可注入/可 mock（`StaticLLMClient` / `OpenAICompatibleLLMClient`），核心可离线单测 |
| LLM 驱动的「批评/梯度」生成 (`∇_LLM`) | ✅ 已实现 | V10.17 `llm_gradient.enrich_gradients_with_llm`；失败降级回规则化模板 |
| 真正的迭代进化循环 | ✅ (V10.26) | `rerun_analysis=True`：改写 → 重跑分析 → `backward(scores)` 梯度；默认关（省 LLM） |

> 结论：Option B 的「变量真实改写」已落地——文本梯度第一次真正作用到 Prompt 上。下一步是把启发式「批评」也换成 LLM 生成（`∇_LLM`），以及把单步闭环扩成多轮自动迭代。结构化的 `Gradient.issues` 与可注入的 `LLMClient` 让这两步都能无侵入演进，**消费方（回测/测试）无需改动**。

## 📖 TextGrad 核心概念

| 概念 | 定义 | Berkshire 映射 |
|:-----|:-----|:---------------|
| **计算图** | 变量 + 依赖关系的有向图 | 四大师分析流程 |
| **变量** | 可优化的节点 (Prompt/代码/分子) | 大师 Prompt + 模型 + Tavily Query |
| **文本梯度** | LLM 生成的诊断+修改建议 | 节点级失败分析 |
| **反向传播** | 从输出向输入传播梯度 | 从最终评分向各大师回传诊断 |
| **优化器** | 根据梯度更新变量 | 针对性修改失败节点的 Prompt/模型 |

## 🎯 Berkshire 计算图设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Berkshire Computation Graph                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Layer 0: 输入层                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ ticker      │  │ tavily_query│  │ date_anchor │                 │
│  │ (股票代码)   │  │ (搜索策略)   │  │ (日期锚定)   │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
│         │                │                │                         │
│         └────────────────┼────────────────┘                         │
│                          ▼                                          │
│  Layer 1: 数据获取层                                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    tavily_search()                           │   │
│  │  → stock_data + financial_metrics + industry_news           │   │
│  └────────────────────────────┬────────────────────────────────┘   │
│                               │                                     │
│          ┌────────────────────┼────────────────────┐               │
│          ▼                    ▼                    ▼               │
│  Layer 2: 四大师分析层                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐  │
│  │ 段永平       │  │ 巴菲特       │  │ 芒格         │  │ 李录     │  │
│  │ (生意本质)   │  │ (护城河估值) │  │ (逆向风险)   │  │ (文明趋势)│  │
│  │             │  │             │  │             │  │         │  │
│  │ Variable:   │  │ Variable:   │  │ Variable:   │  │Variable:│  │
│  │ duan_prompt │  │ buffett_    │  │ munger_     │  │ lilu_   │  │
│  │ duan_model  │  │ prompt      │  │ prompt      │  │ prompt  │  │
│  │             │  │ buffett_    │  │ munger_     │  │ lilu_   │  │
│  │             │  │ model       │  │ model       │  │ model   │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────┬────┘  │
│         │                │                │               │        │
│         └────────────────┼────────────────┴───────────────┘        │
│                          ▼                                          │
│  Layer 3: 综合评估层                                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    financial_rigor.py                        │   │
│  │  → 市值验证 + 估值验证 + 交叉验证                             │   │
│  └────────────────────────────┬────────────────────────────────┘   │
│                               │                                     │
│                               ▼                                     │
│  Layer 4: 输出层                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    final_report                              │   │
│  │  → 平均评分 + 投资建议 + 风险提示                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 🔍 节点级诊断机制

### 当前问题 (V9.3)
```
失败案例: 腾讯控股分析评分 0.75 (低于目标 0.85)
反思报告: "整体评分偏低，需要改进 Prompt"
问题: 不知道具体哪个大师/哪个环节出了问题
```

### TextGrad 化后 (V10.0)
```
失败案例: 腾讯控股分析评分 0.75
反向传播诊断:
  - 段永平 (0.92): ✅ 正常
  - 巴菲特 (0.68): ❌ 估值偏高，PE 计算错误
    → 梯度: "buffett_prompt 缺少 PE 行业对比约束"
  - 芒格 (0.85): ✅ 正常
  - 李录 (0.55): ❌ 风险评估过于乐观
    → 梯度: "lilu_prompt 缺少监管风险分析"
优化动作:
  - 修改 buffett_prompt: 添加 PE 行业对比约束
  - 修改 lilu_prompt: 添加监管风险清单
```

## 📐 实现方案

### 1. 单一来源：四大师定义 (`src/graph.py`)

变量、边、梯度全部从 `MASTERS` 派生，避免在 4 处重复硬编码大师列表。新增/删减大师只需改这一处。

```python
@dataclass(frozen=True)
class Master:
    prefix: str   # duan / buffett / munger / lilu
    name: str     # 中文名
    focus: str    # 关注点

MASTERS = (
    Master("duan", "段永平", "生意本质"),
    Master("buffett", "巴菲特", "护城河估值"),
    Master("munger", "芒格", "逆向风险"),
    Master("lilu", "李录", "文明趋势"),
)

MASTER_PREFIXES = tuple(m.prefix for m in MASTERS)
ROLE_NAMES = {m.prefix: m.name for m in MASTERS}

# 每位大师分析不达标时的针对性检查项（启发式，未来由 LLM 取代）
MASTER_CHECKS = {
    "duan":    ["检查: 是否用一句话定义了生意本质？", "检查: 是否分析了收入漏斗？"],
    "buffett": ["检查: 是否包含 PE/PB/DCF 估值分析？", "检查: 是否评估了护城河宽度？"],
    "munger":  ["检查: 是否包含逆向思考 (失败路径)？", "检查: 是否分析了监管风险？"],
    "lilu":    ["检查: 是否评估了长期趋势？", "检查: 是否分析了管理层质量？"],
}
```

节点命名收敛到三个静态方法，`_init_variables` / `_init_edges` 循环遍历 `MASTERS`：

```python
@staticmethod
def analysis_node(prefix): return f"{prefix}_analysis"
@staticmethod
def prompt_node(prefix):   return f"{prefix}_prompt"
@staticmethod
def model_node(prefix):    return f"{prefix}_model"
```

### 2. 结构化文本梯度 `Gradient`

控制流（优化器、回测、测试）读 `ok`/`issues`，**不再从 `text` 里解析 ✅/❌**。`text` 仅用于给人看的渲染。

```python
@dataclass
class Gradient:
    node: str
    ok: bool
    text: str
    score: Optional[float] = None
    issues: List[str] = field(default_factory=list)

    # 仅为展示兼容（print / "❌" in grad），不参与控制流
    def __str__(self): return self.text
    def __contains__(self, item): return item in self.text
```

### 3. 反向传播 `backward(scores)`

输入各大师评分 `Dict[str, float]`，输出 `Dict[str, Gradient]`：

```python
def backward(self, scores: Dict[str, float]) -> Dict[str, Gradient]:
    self.scores = scores
    gradients = {}
    analysis_nodes = {self.analysis_node(p): p for p in MASTER_PREFIXES}
    prompt_nodes   = {self.prompt_node(p):   p for p in MASTER_PREFIXES}
    model_nodes    = {self.model_node(p):    p for p in MASTER_PREFIXES}

    for node in reversed(self.topological_sort()):
        if node == "final_report":
            gradients[node] = self._compute_output_gradient()
        elif node in analysis_nodes:
            prefix = analysis_nodes[node]
            gradients[node] = self._compute_master_gradient(prefix, scores.get(prefix, 0))
        elif node in prompt_nodes:
            prefix = prompt_nodes[node]
            gradients[node] = self._compute_prompt_gradient(node, gradients.get(self.analysis_node(prefix)))
        elif node in model_nodes:
            prefix = model_nodes[node]
            gradients[node] = self._compute_model_gradient(node, gradients.get(self.analysis_node(prefix)))
    return gradients

def _compute_master_gradient(self, prefix, score) -> Gradient:
    role_name = ROLE_NAMES.get(prefix, prefix)
    node = self.analysis_node(prefix)
    if score >= SCORE_THRESHOLD:  # 0.85
        return Gradient(node=node, ok=True, score=score,
                        text=f"✅ {role_name} 分析质量良好 (评分 {score:.3f})")
    issues = [f"评分过低 ({score:.3f})，需要重点改进" if score < 0.70
              else f"评分偏低 ({score:.3f})，需要优化"]
    issues.extend(MASTER_CHECKS.get(prefix, []))   # 针对性诊断（单一来源）
    text = f"❌ {role_name} 分析存在问题:\n" + "\n".join(f"  - {i}" for i in issues)
    return Gradient(node=node, ok=False, score=score, text=text, issues=issues)
```

### 4. 优化器 (Textual Gradient Descent) — `src/optimizer.py`

控制流读 `gradient.ok`（结构化）。优化器有两种工作模式：

- **无 `llm`（默认，向后兼容）**：仅产出「更新计划」并记日志，不改写变量值。
- **有 `llm`（V10.13 / Option B）**：对未达标的 prompt 变量调用 `apply_gradient`
  **真实改写 `Variable.value`**，并把 `old_value`/`new_value`/`rewritten=True` 记入 update。
  LLM 失败 / 无底稿时优雅降级回「仅记录」（`rewrite_error` / `rewrite_skipped`），不崩链路。

```python
def __init__(self, graph, lr=1.0, llm: Optional[LLMClient] = None):
    self.llm = llm
    ...

def step(self, gradients: Dict[str, Gradient]) -> List[Dict]:
    updates = []
    for var_name, gradient in gradients.items():
        if gradient.ok:
            continue                      # 达标节点跳过（读 ok，不解析 emoji）
        var = self.graph.variables.get(var_name)
        if not var:
            continue
        update = {... "rewritten": False, ...}
        if self.llm is not None and var.type == "prompt":
            self._rewrite_prompt(var, gradient, update)  # 真实改写 var.value
        updates.append(update); self.update_log.append(update)
    return updates
```

### 5. ✅ Option B（V10.13）：变量真实改写 — `src/prompt_optimizer.py`

文本梯度第一次真正作用到 Prompt 上：`apply_gradient` 让 LLM 读「下游诊断（梯度）+
当前 Prompt」产出改进版 Prompt 回填变量。LLM 客户端可注入/可 mock，核心可离线单测。

```python
class LLMClient:                       # 抽象接口：complete(system, user) -> str
    def complete(self, system, user): ...

class StaticLLMClient(LLMClient):      # 测试/离线：固定响应 / 回调 / echo
class OpenAICompatibleLLMClient(LLMClient):  # 真实：OpenAI 兼容 /chat/completions
    # env: BERKSHIRE_LLM_API_KEY(兜底 OPENAI_API_KEY) / _BASE_URL / _MODEL；缺 key 即报错

def apply_gradient(variable, gradient, llm, *, base_prompt=None) -> Optional[str]:
    if gradient.ok: return None                       # 无需改写
    current = base_prompt or variable.value
    if not current: return None                       # 无底稿 → 交上层降级
    msgs = build_rewrite_messages(variable, gradient, current)
    return _clean(llm.complete(msgs["system"], msgs["user"])) or None
```

用法（反馈闭环中启用真实改写）：

```python
from prompt_optimizer import OpenAICompatibleLLMClient
graph.variables["buffett_prompt"].value = "<当前巴菲特分析 Prompt 底稿>"
run_with_realized_feedback(decision, realized_price=..., llm=OpenAICompatibleLLMClient())
# 未达标的 buffett_prompt 会被 LLM 针对诊断改写并回填
```

> 仍属未来工作：(a) 把启发式「批评/梯度」也换成 LLM 生成（`∇_LLM`，替代 `MASTER_CHECKS`）；
> (b) 把单步「backward→改写→回填」扩成多轮自动迭代（改写后重跑分析→再评分）。
> 二者均可在不改消费方的前提下渐进接线。

## 🔁 已实现收益反馈闭环 + 多空辩论 (V10.11，吸收自 TradingAgents)

原 `backward()` 的输入是硬编码的 `{"duan":0.92, ...}`。V10.11 把这一信号替换为
**由真实已实现收益反推的"校准评分"**，让反思变成可微的 reward。

### 1. 决策落盘 — `src/decision_log.py`

每次决策落盘一条结构化 `DecisionRecord`（JSONL 追加，零外部依赖）：

```python
@dataclass
class DecisionRecord:
    ticker: str
    date: str                       # YYYY-MM-DD
    scores: Dict[str, float]        # 四大师当时信心（key 必属 MASTER_PREFIXES 单一来源）
    price_anchor: float             # 决策时标的价格锚点
    benchmark: Optional[str] = None
    benchmark_anchor: Optional[float] = None
    ...
```

路径默认 `~/.berkshire/decisions.jsonl`，可用环境变量 `BERKSHIRE_DECISION_LOG` 覆盖。
`append_decision` / `load_decisions` / `decisions_for_ticker` / `latest_decision` 读写。

### 2. 收益 → 评分 — `src/realized_feedback.py`

```
alpha          = raw_return - benchmark_return
realized_base  = clip(0.5 + alpha * SENSITIVITY, 0, 1)     # 默认 SENSITIVITY = 0.5（V10.12 校准，见下「尺度校准」节）
master_score   = clip(1 - |conviction - realized_base|, 0, 1)
```

- `alpha=0`（与基准持平）→ `realized_base=0.5`（中性）；alpha 越正越接近 1，越负越接近 0。
- 大师信心与"真相"一致（看多且涨 / 看空且跌）→ 高分（无需优化）；系统性过度自信被证伪 → 低分（触发 TextGrad 优化其 prompt）。
- 价格通过可注入/可 mock 的 `PriceProvider` / `StaticPriceProvider` 获取，**核心引擎不连网络**。
- 输出结构化 `ReturnStats`（`raw_return`/`benchmark_return`/`alpha`/`realized_base`/`has_benchmark`），控制流读字段而非解析文本。

### 3. 多空对抗辩论 — `src/debate.py` / `BerkshireGraph.debate()`

四大师原本并行、缺显式反方。`debate()` 在 Layer 2（四大师）与 Layer 3/4（验证/输出）
之间插入一步，综合各大师 conviction（>0.5 偏多、<0.5 偏空）产出确定性、可测的强度：

```
bull_strength = mean_over_masters( max(0, score - 0.5) ) / 0.5
bear_strength = mean_over_masters( max(0, 0.5 - score) ) / 0.5
net_score     = bull_strength - bear_strength ∈ [-1, 1]
net_stance    = bullish / bearish / neutral   (|net_score| < NET_MARGIN=0.15 视为 neutral)
```

输出结构化 `DebateResult`（含 `bull`/`bear` 的 `DebateCase`、`net_stance`、`net_score`、`ok`），
控制流读 `net_stance`/`ok`，`__str__` 仅用于展示。复用 `MASTERS` 单一来源，不硬编码大师列表。

### 4. 串联 — `run_with_realized_feedback(...)`（`src/evolution_loop_v10.py`）

```python
from src import DecisionRecord, run_with_realized_feedback, StaticPriceProvider

d = DecisionRecord("600519", "2026-01-02",
                   {"duan":0.9,"buffett":0.8,"munger":0.6,"lilu":0.7},
                   price_anchor=1500.0, benchmark="000300", benchmark_anchor=3800.0)
provider = StaticPriceProvider({("600519","2026-03-31"):1650.0, ("000300","2026-03-31"):3900.0})
result = run_with_realized_feedback(d, realized_date="2026-03-31", price_provider=provider)
# 收益 → 评分 → graph.backward() → optimizer.step()，并附带决策时信心的 debate 净判断
```

取价两种方式二选一：直接传 `realized_price`(+`benchmark_realized_price`)，或传
`realized_date`+`price_provider`（可注入/可 mock，不连网络）。`persist=True` 时把决策落盘。

> 设计一致性：`realized_feedback` 产出的 `{prefix: score}` 与原硬编码 scores 形状完全一致，
> 因此 `backward()` / `optimizer.step()` / 测试**零改动**即可消费收益反馈信号。

## 🎚️ SENSITIVITY 尺度校准 (V10.12，data-only)

`realized_base = clip(0.5 + alpha·SENSITIVITY, 0, 1)` 里的 `SENSITIVITY` 决定了
「多大的超额收益算强信号」。原默认 2.5 是拍脑袋值。我们暂时没有历史「大师
conviction」数据，无法做「信心 vs alpha」的误差校准，于是改做**尺度校准**：
在真实观测到的 alpha 分布上选 `SENSITIVITY`，让 `realized_base` 用满 [0,1] 区间
而不过度饱和。脚本：`tools/calibrate_sensitivity.py`。

### 1. 数据

- 标的：汇总 `data/watchlist.json` + `data/holdings.example.json`（去重，忽略
  `CASH` 与 `_` 开头元字段）。
- 日线：美股直接代码（基准 `^GSPC`）、港股 `XXXX.HK`（基准 `^HSI`）、A股
  沪深300为基准。取数走可注入 `HistoryProvider`：`YFinanceProvider`（美/港股）、
  `TushareProvider`→`AkshareProvider`→`YFinanceProvider` 降级（A股 + 沪深300指数），
  `ChainProvider` 按市场选链。**核心数学不连网络**，离线用 `DictHistoryProvider`。
- 窗口：锚点 ≈ N 天前最近交易日，realized = 最新交易日；主窗 365 天，对照窗 182 天。

### 2. 目标函数（对肥尾稳健）

```
J(S) = | spread₁₀₋₉₀(realized_base; S) − TARGET_SPREAD |     # TARGET_SPREAD = 0.80
spread₁₀₋₉₀ = p90(realized_base) − p10(realized_base)
```

让**中位 80% 的决策**用满约 `realized_base ∈ [0.1, 0.9]`，而极端 ±10% 尾部
（IPO/加密暴涨暴跌）**有意留给饱和**。

> 为什么不用标准差：真实 alpha 严重右偏、肥尾（少数标的一年内 +数倍），标准差会
> 被离群点主导，把 S 压到极小，导致典型 ±15% 决策几乎没有反馈信号。而涨 8 倍的
> 决策本就**应该**读成接近 1.0——所以让尾部饱和是正确行为。基于 p10/p90 的中位
> 宽度对离群点稳健，只刻画「大多数决策」的尺度。

`J(S)` 单峰（spread 随 S 单调递增直到饱和到 ≤1.0）：先网格扫描记录 `J(S)` 曲线
（本次的「loop」），再用**黄金分割**在含极小点的网格 bracket 内细化收敛。取「最小
的、达到目标 spread 的 S」，它在同等中位宽度下天然使饱和比例最低。

### 3. 校准结论（27 个标的真实日线，2025–2026）

| 指标 | 默认 2.5 | 推荐 0.5 |
|:-----|:--------:|:--------:|
| realized_base 饱和比例 (clip 到 0/1) | **77.8%** | **~14.8%** |
| realized_base spread (p10..p90) | 1.000（完全饱和） | 0.867 |
| realized_base std | 0.444 | 0.311 |

- 覆盖：27/27（美股 22 + 港股 4 + A股 1），0 未覆盖。A股 `600900` 与沪深300基准经
  akshare 兜底（Tushare 免费 token 无 `daily`/`index_daily` 接口权限，自动降级）。
- 观测 alpha：n=27，mean=+0.36，std=1.75，p05/p50/p95 = −0.78/−0.11/+2.54，max=+8.12。
- 最优 `SENSITIVITY`：12 个月窗 ≈ **0.41**，6 个月窗 ≈ **0.68**（稳健性对照）。
- 取稳健折中 **0.5** 作为新默认：介于两窗之间、取整、直觉清晰（±100% 相对超额收益
  即触达 [0,1] 边界 `0.5 ± alpha·0.5`），把饱和比例从 ~78% 降到 ~15%。

> 结论：旧默认 2.5 对当前市场 regime **严重过饱和**，校准后 0.5 显著更优，已更新
> `src/realized_feedback.py` 的默认值，并保留 `BERKSHIRE_SENSITIVITY` 环境变量覆盖
> （零侵入）。当未来拿到历史大师 conviction 数据，可在此基础上升级为「信心 vs alpha」
> 误差校准。

### 4. 复现

```bash
pip install yfinance akshare tushare
# A 股增强源（可选）：仅作环境变量，切勿写进文件/提交
export BERKSHIRE_ENABLE_TUSHARE=1 TUSHARE_TOKEN=<redacted>
python3 tools/calibrate_sensitivity.py run --lookback 365 --also 182
# 覆盖默认灵敏度而不改代码：
export BERKSHIRE_SENSITIVITY=0.41
```

## 📊 预期收益

| 指标 | V9.3 (当前) | V10.0 (预期) | 提升 |
|:-----|:------------|:-------------|:-----|
| 诊断精度 | 整体评分 | 节点级定位 | ⭐⭐⭐ |
| 优化效率 | 全局修改 | 针对性修改 | ⭐⭐⭐ |
| 进化速度 | 慢 (试错) | 快 (定向) | ⭐⭐ |
| 可解释性 | 低 | 高 (梯度可视化) | ⭐⭐⭐ |

## 🚀 实施计划

### Phase 1: 计算图定义 ✅ 已完成
- [x] 实现 `BerkshireGraph` 类
- [x] 定义变量和依赖关系（从 `MASTERS` 单一来源派生）
- [x] 实现拓扑排序

### Phase 2: 反向传播 ✅ 已完成（含 ∇_LLM）
- [x] 实现 `backward()` 方法（输入 `scores`，输出 `Dict[str, Gradient]`）
- [x] 实现节点级梯度计算（结构化 `Gradient`，启发式 `MASTER_CHECKS`）
- [x] 集成 LLM 诊断（V10.17 `∇_LLM`；V10.23 接入 `run_with_realized_feedback` 主链路）

### Phase 3: 优化器 ✅ 已实现（含 Option B 变量改写）
- [x] 实现 `TextualGradientDescent`（依据 `Gradient.ok` 产出更新计划）
- [x] 添加更新日志
- [x] 实现变量真实改写（V10.13 / Option B：`apply_gradient` 经 LLM 改写 Prompt，可注入/可 mock，失败优雅降级）

### Phase 4: 测试与验证 ✅ 已完成（回归用）
- [x] 单元/集成/回测全部跑通（12 通过/1 跳过，覆盖率 100%）
- [x] 文档更新（本文件）
- [ ] Option B 落地后再对比 V9.3 vs V10.0 实际进化收益

## 📝 关键决策

1. **是否完全重写进化机制？**
   - ❌ 否。保留 V9.3 的轨迹记录，在其基础上叠加计算图
   
2. **是否需要额外的 LLM 调用？**
   - ✅ 是。每个节点需要一次 LLM 调用生成梯度
   - 成本: 约 10-15 次额外调用/次投研
   - 收益: 精准定位问题，减少无效迭代

3. **如何验证效果？**
   - 使用 24 条历史轨迹回测
   - 对比诊断准确率
   - 对比优化后的评分提升

---

**当前状态 (V10.28)**: 计算图 + 收益反馈闭环 + ∇_LLM + 验证门控多轮迭代均已落地。**V10.26** 起 `run_multi_round(rerun_analysis=True)` 在改写后重跑分析并用 `backward(scores)` 产梯度；**V10.27** `trajectory_ab_eval` 提供轨迹 A/B 验收；**V10.28** factor/limitup scan JSON 可并入 `HypothesisProposer`。

**可选后续**: held-out 标的上用真实四大师 LLM 作 `AnalysisRunner`（需 LLM 预算）；Redis/OTel/TLS 运维清单。

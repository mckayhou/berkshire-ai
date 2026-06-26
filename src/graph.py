#!/usr/bin/env python3
"""
Berkshire Graph: Computation Graph for TextGrad V10 engine.

Defines Variable, Gradient and BerkshireGraph for 4-masters parallel analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# Note: no relative imports for compatibility when run via sys.path insert to src/


# ---------------------------------------------------------------------------
# 单一来源：四大师定义（变量、边、梯度全部从这里派生，避免多处重复）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Master:
    prefix: str   # duan / buffett / munger / lilu
    name: str     # 中文名
    focus: str    # 关注点


MASTERS: Tuple[Master, ...] = (
    Master("duan", "段永平", "生意本质"),
    Master("buffett", "巴菲特", "护城河估值"),
    Master("munger", "芒格", "逆向风险"),
    Master("lilu", "李录", "文明趋势"),
)

MASTER_PREFIXES: Tuple[str, ...] = tuple(m.prefix for m in MASTERS)
ROLE_NAMES: Dict[str, str] = {m.prefix: m.name for m in MASTERS}

# 每位大师分析不达标时的针对性检查项
MASTER_CHECKS: Dict[str, List[str]] = {
    "duan": [
        "检查: 是否用一句话定义了生意本质？",
        "检查: 是否分析了收入漏斗？",
    ],
    "buffett": [
        "检查: 是否包含 PE/PB/DCF 估值分析？",
        "检查: 是否评估了护城河宽度？",
    ],
    "munger": [
        "检查: 是否包含逆向思考 (失败路径)？",
        "检查: 是否分析了监管风险？",
    ],
    "lilu": [
        "检查: 是否评估了长期趋势？",
        "检查: 是否分析了管理层质量？",
    ],
}

SCORE_THRESHOLD = 0.85


@dataclass
class Variable:
    """计算图中的可优化变量"""
    name: str
    type: str  # input, prompt, model, output
    role: Optional[str] = None  # 段永平/巴菲特/芒格/李录
    value: Optional[str] = None
    layer: int = 0

    # 运行时状态
    score: float = 0.0
    gradient: Optional[str] = None
    last_updated: Optional[str] = None


@dataclass
class Gradient:
    """结构化文本梯度。

    控制流（优化器、回测、测试）应读取 `ok` / `issues`，
    而不是从 `text` 里解析 ✅/❌ 字符串——后者是给人看的渲染。
    """
    node: str
    ok: bool
    text: str
    score: Optional[float] = None
    issues: List[str] = field(default_factory=list)

    # 兼容旧的“字符串展示”用法（如 print、`"❌" in grad`），但不应用于控制流
    def __str__(self) -> str:
        return self.text

    def __contains__(self, item: str) -> bool:
        return item in self.text


class BerkshireGraph:
    """
    Berkshire 计算图

    结构:
    Layer 0: 输入 (ticker, tavily_query, date_anchor)
    Layer 1: 数据获取 (tavily_search)
    Layer 2: 四大师分析 (duan/buffett/munger/lilu)
    Layer 3: 财务验证 (financial_rigor)
    Layer 4: 输出 (final_report)
    """

    def __init__(self):
        # 定义变量
        self.variables: Dict[str, Variable] = {}
        self._init_variables()

        # 定义依赖关系 (edges)
        self.edges: List[Tuple[str, str]] = []
        self._init_edges()

        # 运行时状态
        self.trace_id: Optional[str] = None
        self.scores: Dict[str, float] = {}

    # --- 节点命名约定（单一来源派生） ---
    @staticmethod
    def analysis_node(prefix: str) -> str:
        return f"{prefix}_analysis"

    @staticmethod
    def prompt_node(prefix: str) -> str:
        return f"{prefix}_prompt"

    @staticmethod
    def model_node(prefix: str) -> str:
        return f"{prefix}_model"

    def _init_variables(self):
        """初始化计算图变量"""
        # Layer 0: 输入
        self.variables["ticker"] = Variable("ticker", "input", layer=0)
        self.variables["tavily_query"] = Variable("tavily_query", "input", layer=0)
        self.variables["date_anchor"] = Variable("date_anchor", "input", layer=0)

        # Layer 1: 数据获取
        self.variables["tavily_search"] = Variable("tavily_search", "output", layer=1)

        # Layer 2: 四大师分析 (每个大师 3 个变量: prompt + model + analysis)
        for m in MASTERS:
            self.variables[self.prompt_node(m.prefix)] = Variable(
                self.prompt_node(m.prefix), "prompt", role=m.name, layer=2
            )
            self.variables[self.model_node(m.prefix)] = Variable(
                self.model_node(m.prefix), "model", role=m.name, layer=2
            )
            self.variables[self.analysis_node(m.prefix)] = Variable(
                self.analysis_node(m.prefix), "output", role=m.name, layer=2
            )

        # Layer 3: 财务验证
        self.variables["financial_rigor"] = Variable("financial_rigor", "output", layer=3)

        # Layer 4: 输出
        self.variables["final_report"] = Variable("final_report", "output", layer=4)

    def _init_edges(self):
        """初始化依赖关系"""
        # Layer 0 → Layer 1
        self.edges.extend([
            ("ticker", "tavily_search"),
            ("tavily_query", "tavily_search"),
            ("date_anchor", "tavily_search"),
        ])

        # Layer 1 → Layer 2
        for prefix in MASTER_PREFIXES:
            self.edges.append(("tavily_search", self.analysis_node(prefix)))
            self.edges.append((self.prompt_node(prefix), self.analysis_node(prefix)))
            self.edges.append((self.model_node(prefix), self.analysis_node(prefix)))

        # Layer 2 → Layer 3
        for prefix in MASTER_PREFIXES:
            self.edges.append((self.analysis_node(prefix), "financial_rigor"))

        # Layer 3 → Layer 4
        self.edges.append(("financial_rigor", "final_report"))

    def topological_sort(self) -> List[str]:
        """拓扑排序，返回节点执行顺序"""
        in_degree = defaultdict(int)
        adj = defaultdict(list)

        for src, dst in self.edges:
            adj[src].append(dst)
            in_degree[dst] += 1

        # 找到所有入度为 0 的节点
        queue = [n for n in self.variables if in_degree[n] == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result

    def backward(self, scores: Dict[str, float]) -> Dict[str, Gradient]:
        """
        沿计算图反向传播文本梯度

        Args:
            scores: 各大师评分 {"duan": 0.92, "buffett": 0.68, ...}

        Returns:
            gradients: {节点名: Gradient}
        """
        self.scores = scores
        gradients: Dict[str, Gradient] = {}

        analysis_nodes = {self.analysis_node(p): p for p in MASTER_PREFIXES}
        prompt_nodes = {self.prompt_node(p): p for p in MASTER_PREFIXES}
        model_nodes = {self.model_node(p): p for p in MASTER_PREFIXES}

        # 反向遍历 (从输出到输入)
        for node in reversed(self.topological_sort()):
            if node == "final_report":
                gradients[node] = self._compute_output_gradient()
            elif node in analysis_nodes:
                prefix = analysis_nodes[node]
                gradients[node] = self._compute_master_gradient(
                    prefix, scores.get(prefix, 0)
                )
            elif node in prompt_nodes:
                prefix = prompt_nodes[node]
                downstream = gradients.get(self.analysis_node(prefix))
                gradients[node] = self._compute_prompt_gradient(node, downstream)
            elif node in model_nodes:
                prefix = model_nodes[node]
                downstream = gradients.get(self.analysis_node(prefix))
                gradients[node] = self._compute_model_gradient(node, downstream)

        return gradients

    def _compute_output_gradient(self) -> Gradient:
        """计算输出层梯度"""
        avg_score = sum(self.scores.values()) / len(self.scores) if self.scores else 0
        ok = avg_score >= SCORE_THRESHOLD

        if ok:
            text = f"✅ 整体分析质量良好 (平均评分 {avg_score:.3f})"
        else:
            text = f"❌ 整体分析质量不达标 (平均评分 {avg_score:.3f} < {SCORE_THRESHOLD})"

        return Gradient(node="final_report", ok=ok, text=text, score=avg_score)

    def _compute_master_gradient(self, prefix: str, score: float) -> Gradient:
        """计算四大师分析层梯度"""
        role_name = ROLE_NAMES.get(prefix, prefix)
        node = self.analysis_node(prefix)

        if score >= SCORE_THRESHOLD:
            return Gradient(
                node=node, ok=True, score=score,
                text=f"✅ {role_name} 分析质量良好 (评分 {score:.3f})",
            )

        issues: List[str] = []
        if score < 0.70:
            issues.append(f"评分过低 ({score:.3f})，需要重点改进")
        else:
            issues.append(f"评分偏低 ({score:.3f})，需要优化")

        # 根据角色特性追加针对性诊断（单一来源）
        issues.extend(MASTER_CHECKS.get(prefix, []))

        text = f"❌ {role_name} 分析存在问题:\n" + "\n".join(f"  - {i}" for i in issues)
        return Gradient(node=node, ok=False, score=score, text=text, issues=issues)

    def _compute_prompt_gradient(self, var_name: str, downstream: Optional[Gradient]) -> Gradient:
        """计算 Prompt 变量的梯度"""
        if downstream is None or downstream.ok:
            return Gradient(node=var_name, ok=True, text=f"✅ {var_name} 无需修改")

        text = f"""
📝 {var_name} 需要优化

下游诊断:
{downstream.text}

建议修改方向:
1. 根据下游诊断中的"检查"项，补充缺失的分析维度
2. 增强 Prompt 中的约束条件
3. 添加具体的输出格式要求
"""
        return Gradient(
            node=var_name, ok=False, text=text, issues=list(downstream.issues)
        )

    def _compute_model_gradient(self, var_name: str, downstream: Optional[Gradient]) -> Gradient:
        """计算 Model 变量的梯度"""
        if downstream is None or downstream.ok:
            return Gradient(node=var_name, ok=True, text=f"✅ {var_name} 无需修改")

        text = f"""
🔄 {var_name} 可能需要调整

下游诊断:
{downstream.text}

建议:
1. 如果 Prompt 优化后仍无改善，考虑更换模型
2. 当前模型配置参考 V9.1 模型分配表
"""
        return Gradient(
            node=var_name, ok=False, text=text, issues=list(downstream.issues)
        )

    def visualize(self) -> str:
        """可视化计算图"""
        lines = ["=" * 70]
        lines.append("Berkshire Computation Graph")
        lines.append("=" * 70)
        lines.append("")

        # 按层分组
        layers = defaultdict(list)
        for name, var in self.variables.items():
            layers[var.layer].append(name)

        for layer in sorted(layers.keys()):
            lines.append(f"Layer {layer}:")
            for name in layers[layer]:
                var = self.variables[name]
                score_str = f" (score: {var.score:.3f})" if var.score > 0 else ""
                grad_str = " [has gradient]" if var.gradient else ""
                lines.append(f"  - {name} [{var.type}]{score_str}{grad_str}")
            lines.append("")

        lines.append("Edges:")
        for src, dst in self.edges:
            lines.append(f"  {src} → {dst}")

        return "\n".join(lines)

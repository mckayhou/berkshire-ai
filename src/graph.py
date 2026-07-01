#!/usr/bin/env python3
"""
Berkshire Graph: Computation Graph for TextGrad V10 engine.

Defines Variable, Gradient and BerkshireGraph for parallel master analysis.
Scenario 配置见 scenario.py（P1-D 可插拔）。
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    from scenario import (
        DEFAULT_SCENARIO,
        MASTER_CHECKS,
        MASTER_PREFIXES,
        MASTERS,
        ROLE_NAMES,
        SCORE_THRESHOLD,
        Master,
        Scenario,
    )
except ImportError:  # pragma: no cover
    from .scenario import (
        DEFAULT_SCENARIO,
        MASTER_CHECKS,
        MASTER_PREFIXES,
        MASTERS,
        ROLE_NAMES,
        SCORE_THRESHOLD,
        Master,
        Scenario,
    )

# 向后兼容：历史代码 from graph import MASTERS / MASTER_PREFIXES 等仍可用
__all__ = [
    "Master",
    "MASTERS",
    "MASTER_PREFIXES",
    "ROLE_NAMES",
    "MASTER_CHECKS",
    "SCORE_THRESHOLD",
    "Scenario",
    "DEFAULT_SCENARIO",
    "Variable",
    "Gradient",
    "BerkshireGraph",
]


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
    Layer 2: 大师分析 (每位大师 prompt + model + analysis)
    Layer 3: 财务验证 (financial_rigor)
    Layer 4: 输出 (final_report)
    """

    def __init__(self, scenario: Scenario = DEFAULT_SCENARIO):
        self.scenario = scenario
        self._prefixes = scenario.prefixes
        self._role_names = scenario.role_names
        self._checks = scenario.checks
        self._threshold = scenario.threshold

        self.variables: Dict[str, Variable] = {}
        self._init_variables()

        self.edges: List[Tuple[str, str]] = []
        self._init_edges()

        self.trace_id: Optional[str] = None
        self.scores: Dict[str, float] = {}

    # --- 节点命名约定 ---
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
        self.variables["ticker"] = Variable("ticker", "input", layer=0)
        self.variables["tavily_query"] = Variable("tavily_query", "input", layer=0)
        self.variables["date_anchor"] = Variable("date_anchor", "input", layer=0)
        self.variables["tavily_search"] = Variable("tavily_search", "output", layer=1)

        for m in self.scenario.masters:
            self.variables[self.prompt_node(m.prefix)] = Variable(
                self.prompt_node(m.prefix), "prompt", role=m.name, layer=2
            )
            self.variables[self.model_node(m.prefix)] = Variable(
                self.model_node(m.prefix), "model", role=m.name, layer=2
            )
            self.variables[self.analysis_node(m.prefix)] = Variable(
                self.analysis_node(m.prefix), "output", role=m.name, layer=2
            )

        self.variables["financial_rigor"] = Variable("financial_rigor", "output", layer=3)
        self.variables["final_report"] = Variable("final_report", "output", layer=4)

    def _init_edges(self):
        """初始化依赖关系"""
        self.edges.extend([
            ("ticker", "tavily_search"),
            ("tavily_query", "tavily_search"),
            ("date_anchor", "tavily_search"),
        ])

        for prefix in self._prefixes:
            self.edges.append(("tavily_search", self.analysis_node(prefix)))
            self.edges.append((self.prompt_node(prefix), self.analysis_node(prefix)))
            self.edges.append((self.model_node(prefix), self.analysis_node(prefix)))

        for prefix in self._prefixes:
            self.edges.append((self.analysis_node(prefix), "financial_rigor"))

        self.edges.append(("financial_rigor", "final_report"))

    def topological_sort(self) -> List[str]:
        """拓扑排序，返回节点执行顺序"""
        in_degree: Dict[str, int] = defaultdict(int)
        adj: Dict[str, List[str]] = defaultdict(list)

        for src, dst in self.edges:
            adj[src].append(dst)
            in_degree[dst] += 1

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

        analysis_nodes = {self.analysis_node(p): p for p in self._prefixes}
        prompt_nodes = {self.prompt_node(p): p for p in self._prefixes}
        model_nodes = {self.model_node(p): p for p in self._prefixes}

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
        ok = avg_score >= self._threshold

        if ok:
            text = f"✅ 整体分析质量良好 (平均评分 {avg_score:.3f})"
        else:
            text = (
                f"❌ 整体分析质量不达标 "
                f"(平均评分 {avg_score:.3f} < {self._threshold})"
            )

        return Gradient(node="final_report", ok=ok, text=text, score=avg_score)

    def _compute_master_gradient(self, prefix: str, score: float) -> Gradient:
        """计算大师分析层梯度"""
        role_name = self._role_names.get(prefix, prefix)
        node = self.analysis_node(prefix)

        if score >= self._threshold:
            return Gradient(
                node=node, ok=True, score=score,
                text=f"✅ {role_name} 分析质量良好 (评分 {score:.3f})",
            )

        issues: List[str] = []
        if score < 0.70:
            issues.append(f"评分过低 ({score:.3f})，需要重点改进")
        else:
            issues.append(f"评分偏低 ({score:.3f})，需要优化")

        issues.extend(self._checks.get(prefix, []))

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

    def debate(self, scores: Dict[str, float],
               issues_by_master: Optional[Dict[str, List[str]]] = None):
        """多空辩论环节。"""
        try:
            from debate import run_debate
        except ImportError:  # pragma: no cover
            from .debate import run_debate
        return run_debate(scores, issues_by_master=issues_by_master)

    def visualize(self) -> str:
        """可视化计算图"""
        lines = ["=" * 70]
        lines.append(f"Berkshire Computation Graph — scenario={self.scenario.name}")
        lines.append("=" * 70)
        lines.append("")

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

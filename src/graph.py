#!/usr/bin/env python3
"""
Berkshire Graph: Computation Graph for TextGrad V10 engine.

Defines Variable and BerkshireGraph for 4-masters parallel analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# Note: no relative imports for compatibility when run via sys.path insert to src/


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

    def _init_variables(self):
        """初始化计算图变量"""
        # Layer 0: 输入
        self.variables["ticker"] = Variable("ticker", "input", layer=0)
        self.variables["tavily_query"] = Variable("tavily_query", "input", layer=0)
        self.variables["date_anchor"] = Variable("date_anchor", "input", layer=0)

        # Layer 1: 数据获取
        self.variables["tavily_search"] = Variable("tavily_search", "output", layer=1)

        # Layer 2: 四大师分析 (每个大师 2 个变量: prompt + model)
        masters = [
            ("duan", "段永平", "生意本质"),
            ("buffett", "巴菲特", "护城河估值"),
            ("munger", "芒格", "逆向风险"),
            ("lilu", "李录", "文明趋势"),
        ]
        for prefix, role, focus in masters:
            self.variables[f"{prefix}_prompt"] = Variable(
                f"{prefix}_prompt", "prompt", role=role, layer=2
            )
            self.variables[f"{prefix}_model"] = Variable(
                f"{prefix}_model", "model", role=role, layer=2
            )
            self.variables[f"{prefix}_analysis"] = Variable(
                f"{prefix}_analysis", "output", role=role, layer=2
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
        for prefix in ["duan", "buffett", "munger", "lilu"]:
            self.edges.append(("tavily_search", f"{prefix}_analysis"))
            self.edges.append((f"{prefix}_prompt", f"{prefix}_analysis"))
            self.edges.append((f"{prefix}_model", f"{prefix}_analysis"))

        # Layer 2 → Layer 3
        for prefix in ["duan", "buffett", "munger", "lilu"]:
            self.edges.append((f"{prefix}_analysis", "financial_rigor"))

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

    def backward(self, scores: Dict[str, float]) -> Dict[str, str]:
        """
        沿计算图反向传播文本梯度

        Args:
            scores: 各大师评分 {"duan": 0.92, "buffett": 0.68, ...}

        Returns:
            gradients: 每个变量的文本梯度
        """
        self.scores = scores
        gradients = {}

        # 反向遍历 (从输出到输入)
        for node in reversed(self.topological_sort()):
            if node == "final_report":
                gradients[node] = self._compute_output_gradient()
            elif node.endswith("_analysis"):
                role_prefix = node.split("_")[0]
                score = scores.get(role_prefix, 0)
                gradients[node] = self._compute_master_gradient(role_prefix, score)
            elif node in ["duan_prompt", "buffett_prompt", "munger_prompt", "lilu_prompt"]:
                # Prompt 变量：根据下游分析梯度生成
                analysis_node = node.replace("_prompt", "_analysis")
                downstream_grad = gradients.get(analysis_node, "")
                gradients[node] = self._compute_prompt_gradient(node, downstream_grad)
            elif node in ["duan_model", "buffett_model", "munger_model", "lilu_model"]:
                # Model 变量：根据下游分析梯度生成
                analysis_node = node.replace("_model", "_analysis")
                downstream_grad = gradients.get(analysis_node, "")
                gradients[node] = self._compute_model_gradient(node, downstream_grad)

        return gradients

    def _compute_output_gradient(self) -> str:
        """计算输出层梯度"""
        avg_score = sum(self.scores.values()) / len(self.scores) if self.scores else 0

        if avg_score >= 0.85:
            return f"✅ 整体分析质量良好 (平均评分 {avg_score:.3f})"

        return f"❌ 整体分析质量不达标 (平均评分 {avg_score:.3f} < 0.85)"

    def _compute_master_gradient(self, role: str, score: float) -> str:
        """计算四大师分析层梯度"""
        role_names = {
            "duan": "段永平",
            "buffett": "巴菲特",
            "munger": "芒格",
            "lilu": "李录",
        }
        role_name = role_names.get(role, role)

        if score >= 0.85:
            return f"✅ {role_name} 分析质量良好 (评分 {score:.3f})"

        issues = []
        if score < 0.70:
            issues.append(f"评分过低 ({score:.3f})，需要重点改进")
        elif score < 0.85:
            issues.append(f"评分偏低 ({score:.3f})，需要优化")

        # 根据角色特性生成针对性诊断
        if role == "buffett":
            issues.append("检查: 是否包含 PE/PB/DCF 估值分析？")
            issues.append("检查: 是否评估了护城河宽度？")
        elif role == "munger":
            issues.append("检查: 是否包含逆向思考 (失败路径)？")
            issues.append("检查: 是否分析了监管风险？")
        elif role == "lilu":
            issues.append("检查: 是否评估了长期趋势？")
            issues.append("检查: 是否分析了管理层质量？")
        elif role == "duan":
            issues.append("检查: 是否用一句话定义了生意本质？")
            issues.append("检查: 是否分析了收入漏斗？")

        return f"❌ {role_name} 分析存在问题:\n" + "\n".join(f"  - {i}" for i in issues)

    def _compute_prompt_gradient(self, var_name: str, downstream_grad: str) -> str:
        """计算 Prompt 变量的梯度"""
        if "✅" in downstream_grad:
            return f"✅ {var_name} 无需修改"

        role = var_name.split("_")[0]
        return f"""
📝 {var_name} 需要优化

下游诊断:
{downstream_grad}

建议修改方向:
1. 根据下游诊断中的"检查"项，补充缺失的分析维度
2. 增强 Prompt 中的约束条件
3. 添加具体的输出格式要求
"""

    def _compute_model_gradient(self, var_name: str, downstream_grad: str) -> str:
        """计算 Model 变量的梯度"""
        if "✅" in downstream_grad:
            return f"✅ {var_name} 无需修改"

        return f"""
🔄 {var_name} 可能需要调整

下游诊断:
{downstream_grad}

建议:
1. 如果 Prompt 优化后仍无改善，考虑更换模型
2. 当前模型配置参考 V9.1 模型分配表
"""

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

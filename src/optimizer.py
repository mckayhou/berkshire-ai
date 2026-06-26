#!/usr/bin/env python3
"""
Textual Gradient Descent Optimizer for Berkshire V10 engine.
"""

from typing import Dict, List
from datetime import datetime

# Absolute for src/ path insert compatibility
try:
    from graph import BerkshireGraph, Variable, Gradient
except ImportError:
    from .graph import BerkshireGraph, Variable, Gradient


class TextualGradientDescent:
    """文本梯度下降优化器"""

    def __init__(self, graph: BerkshireGraph, lr: float = 1.0):
        self.graph = graph
        self.lr = lr
        self.update_log: List[Dict] = []

    def step(self, gradients: Dict[str, Gradient]) -> List[Dict]:
        """
        根据梯度更新变量

        控制流读取 `Gradient.ok`（结构化字段），不再解析展示文本里的 ✅/❌。

        Returns:
            updates: 更新记录列表
        """
        updates = []

        for var_name, gradient in gradients.items():
            if gradient.ok:
                continue  # 该节点达标，无需更新

            var = self.graph.variables.get(var_name)
            if not var:
                continue

            # 记录更新
            update = {
                "variable": var_name,
                "type": var.type,
                "role": var.role,
                "gradient": gradient.text,
                "issues": list(gradient.issues),
                "timestamp": datetime.now().isoformat(),
                "action": self._determine_action(var, gradient),
            }
            updates.append(update)
            self.update_log.append(update)

        return updates

    def _determine_action(self, var: Variable, gradient: Gradient) -> str:
        """根据梯度确定优化动作"""
        if var.type == "prompt":
            return "修改 Prompt: 根据梯度中的'检查'项补充缺失维度"
        elif var.type == "model":
            return "评估模型: 如果 Prompt 优化无效，考虑更换模型"
        else:
            return "检查数据流: 确认上游输入是否正确"

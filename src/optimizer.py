#!/usr/bin/env python3
"""
Textual Gradient Descent Optimizer for Berkshire V10 engine.
"""

from typing import Dict, List, Optional
from datetime import datetime

# Absolute for src/ path insert compatibility
try:
    from graph import BerkshireGraph, Variable, Gradient
    from prompt_optimizer import LLMClient, apply_gradient
except ImportError:
    from .graph import BerkshireGraph, Variable, Gradient
    from .prompt_optimizer import LLMClient, apply_gradient


class TextualGradientDescent:
    """文本梯度下降优化器

    两种工作模式：
      - 无 llm（默认）：仅记录「该怎么改」（动作描述），不修改变量值。向后兼容。
      - 有 llm（Option B）：对未达标的 prompt 变量，调用 LLM 真实改写 `Variable.value`，
        把文本梯度真正落到 Prompt 上。LLM 失败时优雅降级回「仅记录动作」，不崩链路。
    """

    def __init__(
        self,
        graph: BerkshireGraph,
        lr: float = 1.0,
        llm: Optional[LLMClient] = None,
    ):
        self.graph = graph
        self.lr = lr
        self.llm = llm
        self.update_log: List[Dict] = []

    def step(self, gradients: Dict[str, Gradient]) -> List[Dict]:
        """
        根据梯度更新变量

        控制流读取 `Gradient.ok`（结构化字段），不再解析展示文本里的 ✅/❌。

        当注入了 `llm` 且变量为 prompt 时，会真实改写 `Variable.value`
        （Option B）；改写结果记录在 update 的 old_value/new_value/rewritten 字段。

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
                "rewritten": False,
            }

            # Option B：对 prompt 变量做真实改写（仅当注入了 llm）
            if self.llm is not None and var.type == "prompt":
                self._rewrite_prompt(var, gradient, update)

            updates.append(update)
            self.update_log.append(update)

        return updates

    def _rewrite_prompt(self, var: Variable, gradient: Gradient, update: Dict) -> None:
        """用 LLM 真实改写 prompt 变量；失败/无底稿时优雅降级（仅记录）。"""
        old_value = var.value
        try:
            new_value = apply_gradient(var, gradient, self.llm)
        except Exception as e:  # 网络/调用错误 → 降级，不崩链路
            update["rewrite_error"] = f"{type(e).__name__}: {e}"
            return

        if not new_value:
            # 无底稿可改或返回空 → 保持原行为（仅记录动作）
            update["rewrite_skipped"] = "无可改写底稿或返回为空"
            return

        if new_value == old_value:
            update["rewrite_noop"] = "改写结果与原 Prompt 一致"
            return

        var.value = new_value
        var.gradient = gradient.text
        var.last_updated = update["timestamp"]
        update["rewritten"] = True
        update["old_value"] = old_value
        update["new_value"] = new_value

    def _determine_action(self, var: Variable, gradient: Gradient) -> str:
        """根据梯度确定优化动作"""
        if var.type == "prompt":
            return "修改 Prompt: 根据梯度中的'检查'项补充缺失维度"
        elif var.type == "model":
            return "评估模型: 如果 Prompt 优化无效，考虑更换模型"
        else:
            return "检查数据流: 确认上游输入是否正确"

#!/usr/bin/env python3
"""
Textual Gradient Descent Optimizer for Berkshire V10 engine.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

# Absolute for src/ path insert compatibility
try:
    from .graph import BerkshireGraph, Gradient, Variable
    from .prompt_optimizer import LLMClient, apply_gradient
    from .prompt_validation import PromptScorer, validated_apply_gradient
except ImportError:  # pragma: no cover - flat PYTHONPATH=src
    from graph import BerkshireGraph, Gradient, Variable
    from prompt_optimizer import LLMClient, apply_gradient
    from prompt_validation import PromptScorer, validated_apply_gradient


class TextualGradientDescent:
    """文本梯度下降优化器

    三种工作模式（按 __init__ 注入决定）：
      - 无 llm（默认）：仅记录「该怎么改」（动作描述），不修改变量值。向后兼容。
      - 有 llm、无 scorer（V10.13 Option B）：对未达标 prompt 变量调用 LLM 真实改写
        `Variable.value`（无验证，直接回填）。
      - 有 llm + scorer（V10.15 验证门控）：改写后在评测集上打分，**只有不劣于旧版
        (+min_improvement) 才接受**，否则回滚——杜绝 prompt 漂移。
      - 有 retriever（V10.19）：改写前召回历史经验作 few-shot（默认 None → 不召回）。
    LLM / 评分器失败均优雅降级（保守不改写），不崩链路。
    """

    def __init__(
        self,
        graph: BerkshireGraph,
        lr: float = 1.0,
        llm: Optional[LLMClient] = None,
        scorer: Optional[PromptScorer] = None,
        min_improvement: float = 0.0,
        retriever: Optional[Any] = None,
        retriever_ticker: Optional[str] = None,
        retriever_k: int = 3,
    ):
        self.graph = graph
        self.lr = lr
        self.llm = llm
        self.scorer = scorer
        self.min_improvement = min_improvement
        self.retriever = retriever
        self.retriever_ticker = retriever_ticker
        self.retriever_k = retriever_k
        self.update_log: List[Dict] = []

    def _fetch_examples(self) -> Optional[List[Any]]:
        """召回 few-shot 经验；失败返回 None（降级为无 few-shot）。"""
        if self.retriever is None or not self.retriever_ticker:
            return None
        try:
            items = self.retriever.retrieve(
                ticker=self.retriever_ticker, k=self.retriever_k
            )
            return items if items else None
        except Exception:  # noqa: BLE001
            return None

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

            # 对 prompt 变量做真实改写（仅当注入了 llm）
            if self.llm is not None and var.type == "prompt":
                if self.scorer is not None:
                    self._rewrite_prompt_validated(var, gradient, update)  # V10.15 验证门控
                else:
                    self._rewrite_prompt(var, gradient, update)            # V10.13 无验证

            updates.append(update)
            self.update_log.append(update)

        return updates

    def _apply_new_value(self, var: Variable, gradient: Gradient, update: Dict, new_value: str) -> None:
        """回填新 Prompt 到变量并记录。"""
        update["old_value"] = var.value
        var.value = new_value
        var.gradient = gradient.text
        var.last_updated = update["timestamp"]
        update["rewritten"] = True
        update["new_value"] = new_value

    def _rewrite_prompt(self, var: Variable, gradient: Gradient, update: Dict) -> None:
        """用 LLM 真实改写 prompt 变量；失败/无底稿时优雅降级（仅记录）。"""
        old_value = var.value
        examples = self._fetch_examples()
        try:
            new_value = apply_gradient(
                var, gradient, self.llm, examples=examples
            )
        except Exception as e:  # 网络/调用错误 → 降级，不崩链路
            update["rewrite_error"] = f"{type(e).__name__}: {e}"
            return

        if not new_value:
            update["rewrite_skipped"] = "无可改写底稿或返回为空"
            return

        if new_value == old_value:
            update["rewrite_noop"] = "改写结果与原 Prompt 一致"
            return

        self._apply_new_value(var, gradient, update, new_value)

    def _rewrite_prompt_validated(self, var: Variable, gradient: Gradient, update: Dict) -> None:
        """验证门控改写：改写后评分，只有不劣于(+min_improvement)才回填，否则回滚。"""
        examples = self._fetch_examples()
        try:
            result = validated_apply_gradient(
                var, gradient, self.llm, self.scorer,
                min_improvement=self.min_improvement,
                examples=examples,
            )
        except Exception as e:  # LLM 调用错误 → 降级，不崩链路
            update["rewrite_error"] = f"{type(e).__name__}: {e}"
            return

        # 记录验证结果（无论是否接受，便于审计/可观测）
        update["validation"] = {
            "accepted": result.accepted,
            "reason": result.reason,
            "old_score": result.old_score,
            "new_score": result.new_score,
            "improvement": result.improvement,
        }

        if result.accepted and result.new_prompt:
            self._apply_new_value(var, gradient, update, result.new_prompt)
        elif result.reason == "no_candidate":
            update["rewrite_skipped"] = "无可改写底稿或返回为空"
        else:
            update["rewrite_rejected"] = result.reason  # 验证未通过 → 回滚（保持旧 Prompt）

    def _determine_action(self, var: Variable, gradient: Gradient) -> str:
        """根据梯度确定优化动作"""
        if var.type == "prompt":
            return "修改 Prompt: 根据梯度中的'检查'项补充缺失维度"
        elif var.type == "model":
            return "评估模型: 如果 Prompt 优化无效，考虑更换模型"
        else:
            return "检查数据流: 确认上游输入是否正确"

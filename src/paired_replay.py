#!/usr/bin/env python3
"""
Paired Replay 防劣化机制（借鉴 AgentX SGPO）。

核心思想：修改 Prompt 后，不仅要看新 Prompt 在当前 case 的表现，还要把
历史成功的 case 重新跑一遍，确保新 Prompt 没有破坏原有的成功路径。

工程约束
--------------------------------------------------
- 零新依赖：复用现有 TraceRecorder 和 ExperienceStore
- 可注入 scorer：允许自定义评分函数
- 失败优雅降级：回放失败不阻塞主流程
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

try:
    from trace_recorder import TraceRecorder, default_trace_dir
except ImportError:  # pragma: no cover
    from .trace_recorder import TraceRecorder, default_trace_dir


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
ENV_REPLAY_THRESHOLD = "BERKSHIRE_REPLAY_THRESHOLD"  # 衰减率阈值，默认 0.1
ENV_REPLAY_TOP_K = "BERKSHIRE_REPLAY_TOP_K"  # 回放 Top-K 条高分轨迹


def get_replay_threshold() -> float:
    """获取衰减率阈值（新 prompt 评分不能低于旧 prompt 的 (1 - threshold) 倍）。"""
    try:
        return float(os.environ.get(ENV_REPLAY_THRESHOLD, "0.1"))
    except (ValueError, TypeError):
        return 0.1


def get_replay_top_k() -> int:
    """获取回放的高分轨迹数量。"""
    try:
        return int(os.environ.get(ENV_REPLAY_TOP_K, "5"))
    except (ValueError, TypeError):
        return 5


# ---------------------------------------------------------------------------
# Scorer 协议
# ---------------------------------------------------------------------------
@runtime_checkable
class ReplayScorer(Protocol):
    """回放评分器协议：给定轨迹和 prompt，返回评分。"""

    def score(self, trace: Dict[str, Any], prompt: str) -> float:
        """对单条轨迹用新 prompt 评分。"""
        ...


class DefaultReplayScorer:
    """默认回放评分器：基于轨迹的 score 字段和 prompt 相似度。"""

    def score(self, trace: Dict[str, Any], prompt: str) -> float:
        """简单评分：返回轨迹原始 score（实际使用应由 LLM 重新评估）。"""
        return float(trace.get("score", 0.0))


class LLMReplayScorer:
    """LLM 回放评分器：用 LLM 重新评估轨迹在新 prompt 下的表现。"""

    def __init__(self, llm_client: Any):
        self.llm_client = llm_client

    def score(self, trace: Dict[str, Any], prompt: str) -> float:
        """用 LLM 重新评分（需要实现完整的 prompt + trace -> score 逻辑）。"""
        # TODO: 实现 LLM 评分逻辑
        # 这里简化为返回原始 score
        return float(trace.get("score", 0.0))


# ---------------------------------------------------------------------------
# Replay Result
# ---------------------------------------------------------------------------
@dataclass
class ReplayResult:
    """Paired Replay 结果。"""

    old_score: float  # 旧 prompt 在历史轨迹上的平均评分
    new_score: float  # 新 prompt 在历史轨迹上的平均评分
    decay_rate: float  # 衰减率 = (old - new) / old
    passed: bool  # 是否通过（衰减率 < 阈值）
    details: List[Dict[str, Any]] = field(default_factory=list)  # 每条轨迹的详情

    def to_dict(self) -> Dict[str, Any]:
        return {
            "old_score": round(self.old_score, 4),
            "new_score": round(self.new_score, 4),
            "decay_rate": round(self.decay_rate, 4),
            "passed": self.passed,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Paired Replay Engine
# ---------------------------------------------------------------------------
class PairedReplayEngine:
    """Paired Replay 防劣化引擎。

    用法：
        engine = PairedReplayEngine(scorer=my_scorer)
        result = engine.replay(
            old_prompt="旧 prompt",
            new_prompt="新 prompt",
            ticker="AAPL",
        )
        if not result.passed:
            # 回滚到旧 prompt
            ...
    """

    def __init__(
        self,
        scorer: Optional[ReplayScorer] = None,
        trace_dir: Optional[str] = None,
        threshold: Optional[float] = None,
        top_k: Optional[int] = None,
    ):
        self.scorer = scorer or DefaultReplayScorer()
        self.trace_recorder = TraceRecorder(trace_dir)
        self.threshold = threshold if threshold is not None else get_replay_threshold()
        self.top_k = top_k if top_k is not None else get_replay_top_k()

    def _load_top_traces(self, ticker: str) -> List[Dict[str, Any]]:
        """加载指定标的的高分轨迹（Top-K）。"""
        traces = []
        trace_dir = self.trace_recorder.directory

        if not os.path.isdir(trace_dir):
            return traces

        # 加载所有该标的的轨迹文件
        for filename in os.listdir(trace_dir):
            if not filename.startswith(ticker.upper()) or not filename.endswith(".json"):
                continue
            filepath = os.path.join(trace_dir, filename)
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    traces.extend(data)
            except (json.JSONDecodeError, OSError):
                continue

        # 按 score 降序排序，取 Top-K
        traces.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
        return traces[: self.top_k]

    def replay(
        self,
        old_prompt: str,
        new_prompt: str,
        ticker: str,
    ) -> ReplayResult:
        """执行 Paired Replay。

        Args:
            old_prompt: 旧 prompt
            new_prompt: 新 prompt
            ticker: 标的代码

        Returns:
            ReplayResult: 回放结果
        """
        # 加载高分轨迹
        top_traces = self._load_top_traces(ticker)

        if not top_traces:
            # 无历史轨迹，直接通过
            return ReplayResult(
                old_score=0.0,
                new_score=0.0,
                decay_rate=0.0,
                passed=True,
                details=[],
            )

        # 计算旧 prompt 和新 prompt 在历史轨迹上的评分
        old_scores = []
        new_scores = []
        details = []

        for trace in top_traces:
            # 旧 prompt 评分（这里简化为使用轨迹原始 score）
            old_score = self.scorer.score(trace, old_prompt)
            # 新 prompt 评分（实际应由 LLM 重新评估）
            new_score = self.scorer.score(trace, new_prompt)

            old_scores.append(old_score)
            new_scores.append(new_score)
            details.append({
                "task_id": trace.get("task_id", ""),
                "old_score": old_score,
                "new_score": new_score,
            })

        # 计算平均评分
        avg_old = sum(old_scores) / len(old_scores) if old_scores else 0.0
        avg_new = sum(new_scores) / len(new_scores) if new_scores else 0.0

        # 计算衰减率
        if avg_old > 0:
            decay_rate = (avg_old - avg_new) / avg_old
        else:
            decay_rate = 0.0

        # 判断是否通过
        passed = decay_rate < self.threshold

        return ReplayResult(
            old_score=avg_old,
            new_score=avg_new,
            decay_rate=decay_rate,
            passed=passed,
            details=details,
        )


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------
def check_paired_replay(
    old_prompt: str,
    new_prompt: str,
    ticker: str,
    scorer: Optional[ReplayScorer] = None,
    trace_dir: Optional[str] = None,
) -> ReplayResult:
    """便捷函数：执行 Paired Replay 检查。

    Args:
        old_prompt: 旧 prompt
        new_prompt: 新 prompt
        ticker: 标的代码
        scorer: 评分器（可选）
        trace_dir: 轨迹目录（可选）

    Returns:
        ReplayResult: 回放结果
    """
    engine = PairedReplayEngine(scorer=scorer, trace_dir=trace_dir)
    return engine.replay(old_prompt, new_prompt, ticker)


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # 简单测试
    result = check_paired_replay(
        old_prompt="旧 prompt 测试",
        new_prompt="新 prompt 测试",
        ticker="TEST",
    )
    print(f"Paired Replay Result: {result.to_dict()}")

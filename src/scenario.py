#!/usr/bin/env python3
"""
Scenario 抽象层（P1-D）：可插拔的大师组合与图配置。

默认 DEFAULT_SCENARIO 与历史四大师配置逐字节等价；自定义 Scenario 可缩减大师数量
或替换检查项，供 research_loop / eval_harness 未来扩展「美股价值 / A 股成长」等场景。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


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


@dataclass(frozen=True)
class Scenario:
    """一次投研场景：大师阵容 + 检查项 + 达标阈值。"""

    name: str
    masters: Tuple[Master, ...]
    checks: Dict[str, List[str]]
    threshold: float = SCORE_THRESHOLD
    description: str = ""

    @property
    def prefixes(self) -> Tuple[str, ...]:
        return tuple(m.prefix for m in self.masters)

    @property
    def role_names(self) -> Dict[str, str]:
        return {m.prefix: m.name for m in self.masters}


DEFAULT_SCENARIO = Scenario(
    name="berkshire_four_masters",
    masters=MASTERS,
    checks=MASTER_CHECKS,
    threshold=SCORE_THRESHOLD,
    description="段永平 / 巴菲特 / 芒格 / 李录 四大师并行投研（默认）",
)

# 测试 / 演示用：仅两位大师，验证 Scenario 可插拔
TWO_MASTER_DEMO_SCENARIO = Scenario(
    name="value_pair_demo",
    masters=(MASTERS[0], MASTERS[1]),
    checks={
        "duan": MASTER_CHECKS["duan"],
        "buffett": MASTER_CHECKS["buffett"],
    },
    threshold=0.80,
    description="段永平 + 巴菲特 双大师演示场景",
)

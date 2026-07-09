#!/usr/bin/env python3
"""
四大师输出 Schema 校验（借鉴 AgentX 确定性验证卡点）。

核心思想：LLM 输出必须包含关键结构化字段，否则直接打回重生成。
这是确定性验证，不依赖 LLM 判断。

工程约束
--------------------------------------------------
- 零新依赖：使用标准库 dataclasses 和 re
- 可注入校验规则：允许自定义每个大师的必填字段
- 失败优雅降级：校验失败返回详细错误，不抛异常
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from .scenario import MASTER_PREFIXES, ROLE_NAMES
except ImportError:  # pragma: no cover - flat PYTHONPATH=src
    from scenario import MASTER_PREFIXES, ROLE_NAMES


# ---------------------------------------------------------------------------
# 校验结果
# ---------------------------------------------------------------------------
@dataclass
class ValidationResult:
    """输出校验结果。"""

    passed: bool
    master: str
    missing_fields: List[str] = field(default_factory=list)
    invalid_fields: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def error_message(self) -> str:
        """生成人类可读的错误信息。"""
        if self.passed:
            return f"✅ {ROLE_NAMES.get(self.master, self.master)} 输出校验通过"

        parts = [f"❌ {ROLE_NAMES.get(self.master, self.master)} 输出校验失败:"]
        if self.missing_fields:
            parts.append(f"  缺失字段: {', '.join(self.missing_fields)}")
        if self.invalid_fields:
            parts.append(f"  无效字段: {', '.join(self.invalid_fields)}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# 字段校验规则
# ---------------------------------------------------------------------------
@dataclass
class FieldRule:
    """字段校验规则。"""

    name: str  # 字段名
    pattern: str  # 正则表达式（匹配输出内容）
    required: bool = True  # 是否必填
    min_length: int = 0  # 最小长度
    error_message: str = ""  # 校验失败时的错误信息


# ---------------------------------------------------------------------------
# 四大师 Schema 定义
# ---------------------------------------------------------------------------
# 段永平：生意本质分析师
DUAN_SCHEMA: List[FieldRule] = [
    FieldRule(
        name="one_sentence_essence",
        pattern=r"(?:一句话|本质|核心).{0,50}(?:是|为|在于)",
        required=True,
        min_length=3,
        error_message="必须用一句话定义生意本质（如：一句话本质是：XXX）",
    ),
    FieldRule(
        name="revenue_funnel",
        pattern=r"(?:收入|营收|GMV|毛利|净利|FCF|漏斗|利润)",
        required=True,
        min_length=2,
        error_message="必须包含收入漏斗分析（从收入到利润的完整链条）",
    ),
    FieldRule(
        name="business_model",
        pattern=r"(?:商业|盈利|赚钱|收费|销售|模式)",
        required=True,
        min_length=2,
        error_message="必须分析商业模式/盈利模式",
    ),
    FieldRule(
        name="competitive_barrier",
        pattern=r"(?:护城河|壁垒|竞争|差异化|品牌|渠道|优势)",
        required=True,
        min_length=2,
        error_message="必须分析竞争壁垒",
    ),
]

# 巴菲特：财务分析师
BUFFETT_SCHEMA: List[FieldRule] = [
    FieldRule(
        name="valuation_table",
        pattern=r"(?:PE|PB|PS|估值|市盈率|市净率|倍)",
        required=True,
        min_length=2,
        error_message="必须包含估值指标分析（PE/PB/PS 等）",
    ),
    FieldRule(
        name="moat_analysis",
        pattern=r"(?:护城河|竞争优势|定价权|品牌|壁垒)",
        required=True,
        min_length=2,
        error_message="必须评估护城河宽度",
    ),
    FieldRule(
        name="financial_health",
        pattern=r"(?:现金流|负债|财务|ROE|净利润|毛利|收益)",
        required=True,
        min_length=2,
        error_message="必须分析财务健康状况",
    ),
    FieldRule(
        name="safety_margin",
        pattern=r"(?:安全边际|低估|高估|合理|估值)",
        required=False,
        min_length=2,
        error_message="建议给出安全边际判断",
    ),
]

# 芒格：逆向思考分析师
MUNGER_SCHEMA: List[FieldRule] = [
    FieldRule(
        name="failure_paths",
        pattern=r"(?:失败|风险|下降|压缩|抢占|进入者|可能)",
        required=True,
        min_length=2,
        error_message="必须列出至少 3 条失败路径",
    ),
    FieldRule(
        name="inverse_thinking",
        pattern=r"(?:逆向|反过来|如果|最可能|原因|为什么)",
        required=True,
        min_length=2,
        error_message="必须包含逆向思考内容",
    ),
    FieldRule(
        name="regulatory_risk",
        pattern=r"(?:监管|政策|法规|合规)",
        required=True,
        min_length=2,
        error_message="必须分析监管风险",
    ),
    FieldRule(
        name="bear_case",
        pattern=r"(?:空方|看空|做空|反对|估值过高)",
        required=False,
        min_length=2,
        error_message="建议提供空方论点",
    ),
]

# 李录：文明趋势分析师
LILU_SCHEMA: List[FieldRule] = [
    FieldRule(
        name="civilization_trend",
        pattern=r"(?:文明|趋势|范式|革命|时代|行业|产业)",
        required=True,
        min_length=2,
        error_message="必须评估文明级趋势",
    ),
    FieldRule(
        name="long_term_view",
        pattern=r"(?:20年|长期|未来|回看|十年|多年)",
        required=True,
        min_length=2,
        error_message="必须给出长期视角判断",
    ),
    FieldRule(
        name="management_quality",
        pattern=r"(?:管理层|CEO|团队|领导|创始人)",
        required=True,
        min_length=2,
        error_message="必须分析管理层质量",
    ),
    FieldRule(
        name="risk_assessment",
        pattern=r"(?:风险|威胁|挑战|不确定性)",
        required=True,
        min_length=2,
        error_message="必须评估主要风险",
    ),
]


# ---------------------------------------------------------------------------
# Schema 注册表
# ---------------------------------------------------------------------------
MASTER_SCHEMAS: Dict[str, List[FieldRule]] = {
    "duan": DUAN_SCHEMA,
    "buffett": BUFFETT_SCHEMA,
    "munger": MUNGER_SCHEMA,
    "lilu": LILU_SCHEMA,
}


# ---------------------------------------------------------------------------
# 校验引擎
# ---------------------------------------------------------------------------
class OutputValidator:
    """四大师输出校验器。

    用法：
        validator = OutputValidator()
        result = validator.validate("duan", output_text)
        if not result.passed:
            print(result.error_message())
    """

    def __init__(self, schemas: Optional[Dict[str, List[FieldRule]]] = None):
        self.schemas = schemas or MASTER_SCHEMAS

    def validate(self, master: str, output: str) -> ValidationResult:
        """校验单个大师的输出。

        Args:
            master: 大师前缀 (duan/buffett/munger/lilu)
            output: 输出文本

        Returns:
            ValidationResult: 校验结果
        """
        if master not in self.schemas:
            return ValidationResult(
                passed=False,
                master=master,
                missing_fields=["unknown_master"],
                details={"error": f"未知大师: {master}"},
            )

        schema = self.schemas[master]
        missing_fields = []
        invalid_fields = []
        details: Dict[str, Any] = {}

        for rule in schema:
            # 正则匹配
            match = re.search(rule.pattern, output, re.IGNORECASE | re.DOTALL)

            if not match:
                if rule.required:
                    missing_fields.append(rule.name)
                continue

            # 检查长度
            matched_text = match.group(0)
            if len(matched_text) < rule.min_length:
                invalid_fields.append(rule.name)
                details[rule.name] = {
                    "matched_length": len(matched_text),
                    "min_length": rule.min_length,
                    "error": rule.error_message,
                }

        passed = len(missing_fields) == 0 and len(invalid_fields) == 0

        return ValidationResult(
            passed=passed,
            master=master,
            missing_fields=missing_fields,
            invalid_fields=invalid_fields,
            details=details,
        )

    def validate_all(self, outputs: Dict[str, str]) -> Dict[str, ValidationResult]:
        """校验所有大师的输出。

        Args:
            outputs: {master_prefix: output_text}

        Returns:
            Dict[str, ValidationResult]: 每个大师的校验结果
        """
        results = {}
        for master in MASTER_PREFIXES:
            if master in outputs:
                results[master] = self.validate(master, outputs[master])
        return results


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------
def validate_master_output(master: str, output: str) -> ValidationResult:
    """便捷函数：校验单个大师输出。"""
    validator = OutputValidator()
    return validator.validate(master, output)


def validate_all_outputs(outputs: Dict[str, str]) -> Dict[str, ValidationResult]:
    """便捷函数：校验所有大师输出。"""
    validator = OutputValidator()
    return validator.validate_all(outputs)


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # 测试用例
    test_outputs = {
        "duan": """
        一句话本质是：这家公司通过品牌溢价和渠道控制，将低成本制造转化为高毛利消费品。
        
        收入漏斗：
        - 顶层 GMV: 100亿
        - 营收: 80亿
        - 毛利: 40亿 (50%)
        - 净利: 15亿 (19%)
        - FCF: 12亿
        
        商业模式：品牌消费品，通过线下渠道和电商销售。
        竞争壁垒：品牌认知度和渠道网络。
        """,
        "munger": """
        失败路径：
        1. 消费降级导致高端产品需求下降
        2. 新进入者通过电商渠道抢占市场份额
        3. 原材料成本大幅上升压缩利润
        
        逆向思考：如果这笔投资失败，最可能的原因是管理层未能适应消费趋势变化。
        
        监管风险：食品安全法规趋严，合规成本上升。
        
        空方论点：估值过高，增长放缓。
        """,
    }

    validator = OutputValidator()

    for master, output in test_outputs.items():
        result = validator.validate(master, output)
        print(f"\n{result.error_message()}")
        if not result.passed:
            print(f"  缺失: {result.missing_fields}")
            print(f"  无效: {result.invalid_fields}")

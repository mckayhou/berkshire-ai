"""Domain-Contextualized Skill Creator — mine workflows from reports & tools."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import List, Optional


def default_reports_root() -> Path:
    return Path(__file__).resolve().parents[2] / "reports"


def default_tools_root() -> Path:
    return Path(__file__).resolve().parents[2] / "tools"


_TOOL_REF_RE = re.compile(
    r"`((?:tools/)?[a-zA-Z0-9_./-]+\.py)(?:\s+[^`]+)?`",
)


def mine_tool_schemas_from_skills(skills_root: Path) -> List[str]:
    """Extract high-frequency tool references from existing skills."""
    counts: Counter = Counter()
    for path in skills_root.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in _TOOL_REF_RE.finditer(text):
            tool = m.group(1).split("/")[-1]
            counts[tool] += 1
    return [t for t, _ in counts.most_common()]


def mine_workflow_headings_from_reports(reports_root: Path, *, limit: int = 12) -> List[str]:
    """Extract common ## headings from historical reports as workflow hints."""
    counts: Counter = Counter()
    if not reports_root.exists():
        return []
    for path in reports_root.rglob("*.md"):
        if path.name.startswith("."):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            m = re.match(r"^##\s+(.+)$", line.strip())
            if m:
                h = m.group(1).strip()
                if len(h) < 4 or h.startswith("目录"):
                    continue
                counts[h] += 1
    return [h for h, _ in counts.most_common(limit)]


def build_skill_v0_template(
    *,
    name: str,
    description: str,
    tools: List[str],
    workflow_headings: List[str],
    reference_skill: Optional[str] = None,
) -> str:
    """Fill a SkillForge-style v0 template from mined domain signals."""
    tool_lines = "\n".join(f"- `{t}`" for t in tools[:10]) or "- `financial_rigor.py`"
    wf_lines = "\n".join(f"1. {h}" for h in workflow_headings[:8]) or (
        "1. 数据收集\n2. 四大师分析\n3. 综合决策 + 行动卡"
    )
    ref_line = (
        f"\n> 参考技能结构：`skills/{reference_skill}.md`\n"
        if reference_skill
        else ""
    )

    return f"""---
name: berkshire-{name}
description: |
  {description}
version: 0.1.0-skillforge
generated_by: skill_forge.creator
---

# {description}
{ref_line}
## Background Knowledge

- 本技能由 SkillForge Domain Creator 从历史报告与工具链挖掘生成（v0）。
- 执行前须阅读 `skills/financial-data.md`。

## Case-Type Triage

| 模式 | 触发 | 工具要求 |
|------|------|----------|
| lite | 快速扫描 | financial_rigor 最小集 |
| standard | 默认研报 | 全套 financial_rigor + report_audit |
| deep | 建仓前确认 | standard + three-scenario + portfolio_risk |

## Workflow（从历史报告挖掘）

{wf_lines}

## Tool Chain（高频工具）

{tool_lines}

## Per-Case Handling

- 数据收集后必须交叉验证（见 financial-data 双源规范）。
- 准出前 standard/deep 必须 `report_audit.py`。

## FAQ

- 长尾数据缺失：标注置信度，禁止凭空填充。

## Reference Index

- `skills/financial-data.md`
- `docs/report-conventions.md`
- `docs/action-card.md`
"""


def create_skill_v0(
    name: str,
    description: str,
    *,
    skills_root: Optional[Path] = None,
    reports_root: Optional[Path] = None,
    reference_skill: str = "investment-research",
    output_path: Optional[Path] = None,
) -> str:
    """Generate Skill v0 markdown content (does not write unless output_path set)."""
    skills_root = skills_root or (Path(__file__).resolve().parents[2] / "skills")
    reports_root = reports_root or default_reports_root()

    tools = mine_tool_schemas_from_skills(skills_root)
    workflows = mine_workflow_headings_from_reports(reports_root)
    content = build_skill_v0_template(
        name=name,
        description=description,
        tools=tools,
        workflow_headings=workflows,
        reference_skill=reference_skill,
    )
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
    return content

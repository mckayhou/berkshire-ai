# SkillForge 测试 Fixtures

供 `tests/test_skill_forge*.py` 使用的离线样本数据。

## 文件

| 文件 | 用途 |
|------|------|
| `bad_cases.jsonl` | 3 条已标注 `consistency` 的失败案例（规则/LLM 分析） |
| `tasks_unlabeled.jsonl` | 2 条无 `consistency` 字段的任务（测 LLM-judge 打标） |

## JSONL 字段

```json
{
  "task_id": "唯一 ID",
  "skill_name": "investment-research",
  "agent_output": "Agent 产出",
  "reference_output": "专家参考",
  "consistency": "inconsistent|partial|consistent",
  "tool_trace": ["financial_rigor.py"],
  "metadata": { "depth": "standard", "audit_failures": [] }
}
```

`consistency` 可省略；配合 `prepare_bad_cases(..., mode=llm)` 或 CLI `--judge-mode llm` 自动评判。

## 扩展

从生产环境导出时：

1. 每条失败研报 / audit 打回 → 一行 JSON
2. `reference_output` 用专家修订版或准出标准摘要
3. `tool_trace` 记录 Agent 实际调用的 `tools/*.py`

详见 [docs/SKILL_EVOLUTION.md](../../../docs/SKILL_EVOLUTION.md)。

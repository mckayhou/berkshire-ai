# SkillForge 技能进化（SKILL_EVOLUTION）

> 借鉴阿里云 [SkillForge](https://arxiv.org/abs/2604.08618)（SIGIR 2026 Industry Track）  
> 将 `skills/*.md` 作为可版本化工程资产，用 bad-case 证据驱动四维失败分析 → 诊断 → 最小 patch。  
> 与 TextGrad（Prompt 进化）互补：TextGrad 改大师 Prompt；SkillForge 改技能工作流与工具规则。

导航：[SKILLS.md](SKILLS.md) | [ENGINE.md](ENGINE.md) | [TESTING.md](../TESTING.md)

---

## 1. 架构

```text
tasks.jsonl（可无 consistency 标签）
    → LLM-judge Consistency Rate（Strict / Lenient CR）
    → Failure Analyzer（知识 / 工具 / 澄清 / 风格）  [LLM 或规则，失败降级]
    → Aggregator（按类别聚合 + 代表案例）
    → Skill Diagnostician（LLM 生成 Optimization Plan，失败降级规则模板）
    → Skill Optimizer（最小修改 + VFS 版本提交）
    → skills/<name>.md（live）+ skills/.evolution/<name>/vN/
```

| 模块 | 路径 |
|------|------|
| **LLM-judge** | `src/skill_forge/llm_judge.py` |
| Judge 模式 | `src/skill_forge/judge_mode.py` |
| 类型定义 | `src/skill_forge/types.py` |
| VFS / 章节 patch | `src/skill_forge/vfs.py` |
| 失败分析 | `src/skill_forge/failure_analyzer.py` |
| 批量聚合 | `src/skill_forge/aggregator.py` |
| 根因诊断 | `src/skill_forge/diagnostician.py` |
| 优化执行 | `src/skill_forge/optimizer.py` |
| 冷启动 Creator | `src/skill_forge/skill_creator.py` |
| 管线 | `src/skill_forge/pipeline.py` |
| CLI | `tools/skill_evolve.py` |

---

## 2. LLM-judge 与 `--judge-mode`

| 模式 | 行为 |
|------|------|
| `auto`（默认） | 有 `BERKSHIRE_LLM_API_KEY` 时用 LLM；否则规则降级 |
| `llm` | 强制 LLM（无 Key 则报错） |
| `rule` | 全程规则，零 API 成本 |

环境变量（与 TextGrad 共用）：

| 变量 | 作用 |
|------|------|
| `BERKSHIRE_LLM_API_KEY` / `OPENAI_API_KEY` | API Key |
| `BERKSHIRE_LLM_BASE_URL` | 兼容网关 |
| `BERKSHIRE_LLM_MODEL` | 模型名（默认 `gpt-4o-mini`） |

LLM-judge 覆盖三处（与论文对齐）：

1. **Consistency Rate**：`judge` 子命令 — `consistent` / `partial` / `inconsistent`
2. **Failure Analyzer**：四维并行 JSON 归因
3. **Skill Diagnostician**：读 SKILL.md 摘录 + 聚合报告 → `optimization_plan`

任一步 LLM 解析失败时**自动降级**到规则实现，不中断管线。

---

## 3. CLI

```bash
# LLM Consistency Rate（Strict / Lenient CR）
python3 tools/skill_evolve.py judge tests/fixtures/skill_forge/tasks_unlabeled.jsonl
python3 tools/skill_evolve.py judge tests/fixtures/skill_forge/bad_cases.jsonl --judge-mode llm

# 四维失败分析（auto = LLM 优先）
python3 tools/skill_evolve.py analyze tests/fixtures/skill_forge/bad_cases.jsonl --judge-mode auto

# 完整进化（LLM judge + LLM 诊断 + patch）
python3 tools/skill_evolve.py evolve investment-research --rounds 1 --judge-mode auto --dry-run

# 纯离线规则（CI / 无 Key）
python3 tools/skill_evolve.py evolve investment-research --judge-mode rule --dry-run

# 忽略已有 consistency 标签，重新评判
python3 tools/skill_evolve.py evolve investment-research --re-judge --judge-mode llm

# 其它
python3 tools/skill_evolve.py list
python3 tools/skill_evolve.py status investment-research
python3 tools/skill_evolve.py create my-new-skill "新场景投研技能" --dry-run
```

统一进化入口：

```bash
python3 src/evolution_loop_v10.py skill-evolve judge tests/fixtures/skill_forge/tasks_unlabeled.jsonl --judge-mode auto
python3 src/evolution_loop_v10.py skill-evolve evolve investment-research --judge-mode auto --dry-run
```

---

## 4. Task / Bad Case 格式（JSONL）

每行一条执行记录；`consistency` **可省略**（由 `judge` / `evolve --judge-mode llm` 自动打标）：

```json
{
  "task_id": "t001",
  "skill_name": "investment-research",
  "agent_output": "Agent 产出的报告或回复",
  "reference_output": "专家参考 / 准出标准",
  "tool_trace": ["financial_rigor.py", "report_audit.py"],
  "metadata": {
    "depth": "standard",
    "audit_failures": [{"label": "营收", "delta_pct": 12.5}]
  }
}
```

带标签时：`"consistency": "consistent" | "partial" | "inconsistent"`

可从 `report_audit.py verdict` 打回结果构造（`bad_case_loader.cases_from_audit_verdict`）。

---

## 5. 四维失败分类

| 维度 | LLM-judge 关注 | 规则降级信号 | 默认 patch 章节 |
|------|----------------|-------------|----------------|
| **Knowledge** | 事实错误/遗漏/矛盾 | 缺双源、audit 失败 | 数据收集 / 偏见自觉 |
| **Tool** | 工具未调/参数错 | tool_trace 缺失 | 数据交叉验证 |
| **Clarification** | 过度/不足澄清 | depth 与问号数 | 研究深度（depth） |
| **Style** | 格式/语气/冗长 | 缺行动卡 | 输出要求 |

优化原则：**Minimal Modification**、**Do No Harm**、**Evidence-Based**（patch 带 `skillforge-evidence` 标记，可 idempotent）。

---

## 6. 版本与审核

- 版本目录：`skills/.evolution/<skill>/vN/SKILL.md` + `diagnostic.json`
- `manifest.json` 记录版本历史

合并 live skill 前人工 diff `vN-1` vs `vN`。

---

## 7. 与 TextGrad 的分工

| | TextGrad | SkillForge |
|--|----------|------------|
| 优化对象 | 大师 Prompt | `skills/*.md` 工作流 |
| 评判 | 评分 / 收益反馈 | LLM-judge CR + 四维失败 |
| 离线 | 可 mock LLM | `--judge-mode rule` |

---

## 8. 测试

```bash
# 全量 SkillForge（规则 + LLM mock + CLI 冒烟）
python3 -m pytest tests/test_skill_forge.py tests/test_skill_forge_llm.py tests/test_skill_forge_cli.py -v

# evolution_cli 集成
python3 -m pytest tests/test_evolution_cli.py -v -k skill_evolve
```

| 测试文件 | 覆盖 |
|----------|------|
| `test_skill_forge.py` | VFS、规则分析、聚合、诊断、多轮进化、Creator |
| `test_skill_forge_llm.py` | LLM-judge CR、四维分析、诊断、降级 |
| `test_skill_forge_cli.py` | `tools/skill_evolve.py` 子命令 |
| `test_evolution_cli.py` | `evolution_loop_v10.py skill-evolve` |

Fixtures 说明：`tests/fixtures/skill_forge/README.md`

---

## 9. 边界

- Knowledge 类失败存在收敛天花板（论文 §3.3.2）；长尾仍依赖运行时检索与人工审核。
- LLM-judge 成本随 task 数线性增长；批量评测建议先 `--judge-mode rule` 冒烟，再 `llm` 全量。
- 多轮进化在同批 bad case 上可能 idempotent（重复 patch 被跳过）。

## 10. 新功能交付

与仓库铁律一致：每次新功能须 **跑测试 + 补全文档**。清单见 [TESTING.md §10.4](../TESTING.md#104-新功能交付清单) 与 [AGENTS.md](../AGENTS.md)。

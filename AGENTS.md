## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## 新功能收尾（必做）

每次交付**新功能或行为变更**时，在结束会话前必须完成：

1. **测试**：跑与改动相关的 pytest；发版前跑 `pytest tests/` 或 `./scripts/release-check.sh --skip-tag-check`
2. **文档**：同步更新所有受影响文档，至少检查下表

| 变更类型 | 必更新文档 |
|----------|------------|
| 新 CLI / 工具 | `tools/README.md`、`docs/USER_GUIDE.md`（若用户可见）、`TESTING.md` §验收入口 |
| 新引擎 / 管线 | `docs/ENGINE.md`、`docs/README.md`、必要时 `VERSION_HISTORY.md` |
| 新 Agent 技能 / 技能进化 | `docs/SKILLS.md`、专题 doc（如 `docs/SKILL_EVOLUTION.md`）、`docs/ROADMAP.md` |
| 测试 / fixture | `TESTING.md` 索引、`tests/fixtures/*/README.md`（若有） |

3. **图谱**：改过 `src/` 或 `tools/` 后执行 `graphify update .`
4. **不要**只改代码不留文档；不要只写文档不跑测试

专题文档索引见 [docs/README.md](docs/README.md)。

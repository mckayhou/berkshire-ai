# Graph Report - berkshire-ai  (2026-06-30)

## Corpus Check
- 78 files · ~64,303 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 78 nodes · 72 edges · 69 communities (13 shown, 56 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `80ea9670`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]

## God Nodes (most connected - your core abstractions)
1. `Berkshire AI — Four-Masters Parallel Investment Research (Upstream fully integrated)` - 6 edges
2. `Berkshire AI - 四大师并行投研系统（已完整整合上游）` - 5 edges
3. `报告输出规范（report conventions）` - 5 edges
4. `Berkshire AI 版本历史` - 4 edges
5. `Berkshire AI V10.0 - TextGrad 化设计` - 3 edges
6. `berkshire-ai Roadmap` - 3 edges
7. `结构化行动卡（Action Card）` - 3 edges
8. `reports/ — 研究报告输出目录` - 3 edges
9. `Investment Research Meta-Skill (V10.0 - TextGrad 化)` - 2 edges
10. `Berkshire AI - Global State & Thesis Tracker` - 2 edges

## Surprising Connections (you probably didn't know these)
- `Berkshire AI — Four-Masters Parallel Investment Research (Upstream fully integrated)` --references--> `报告输出规范（report conventions）`  [EXTRACTED]
  README_EN.md → docs/report-conventions.md
- `Berkshire AI - 四大师并行投研系统（已完整整合上游）` --references--> `Berkshire AI — Four-Masters Parallel Investment Research (Upstream fully integrated)`  [EXTRACTED]
  README.md → README_EN.md
- `Berkshire AI - 四大师并行投研系统（已完整整合上游）` --references--> `Berkshire AI 版本历史`  [EXTRACTED]
  README.md → VERSION_HISTORY.md
- `Berkshire AI - 四大师并行投研系统（已完整整合上游）` --references--> `Berkshire AI V10.0 - TextGrad 化设计`  [EXTRACTED]
  README.md → docs/textgrad_design.md
- `Berkshire AI — Four-Masters Parallel Investment Research (Upstream fully integrated)` --references--> `berkshire-ai Roadmap`  [EXTRACTED]
  README_EN.md → docs/ROADMAP.md

## Import Cycles
- None detected.

## Communities (69 total, 56 thin omitted)

### Community 4 - "Community 4"
Cohesion: 1.00
Nodes (5): Berkshire AI - 四大师并行投研系统（已完整整合上游）, Berkshire AI — Four-Masters Parallel Investment Research (Upstream fully integrated), berkshire-ai Roadmap, Berkshire AI 版本历史, Berkshire AI V10.0 - TextGrad 化设计

### Community 67 - "Community 67"
Cohesion: 1.67
Nodes (3): 结构化行动卡（Action Card）, 报告输出规范（report conventions）, reports/ — 研究报告输出目录

## Knowledge Gaps
- **3 isolated node(s):** `portfolio-weekly.sh script`, `log-command.sh script`, `update-platforms.sh script`
  These have ≤1 connection - possible missing edges or undocumented components.
- **56 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Berkshire AI — Four-Masters Parallel Investment Research (Upstream fully integrated)` connect `Community 4` to `Community 67`?**
  _High betweenness centrality (0.005) - this node is a cross-community bridge._
- **Why does `报告输出规范（report conventions）` connect `Community 67` to `Community 4`?**
  _High betweenness centrality (0.004) - this node is a cross-community bridge._
- **What connects `portfolio-weekly.sh script`, `log-command.sh script`, `update-platforms.sh script` to the rest of the system?**
  _3 weakly-connected nodes found - possible documentation gaps or missing edges._
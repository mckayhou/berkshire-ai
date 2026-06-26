#!/bin/bash
# Update script for berkshire-ai on OpenClaw + QwenPaw
# Run this from the berkshire-ai root after editing skills/tools.

set -e
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "=== Updating OpenClaw skills ==="
for f in "$BASE/skills/"*.md; do
  name="berkshire-$(basename "$f" .md)"
  mkdir -p "$HOME/.openclaw/workspace/skills/$name"
  cp "$f" "$HOME/.openclaw/workspace/skills/$name/SKILL.md"
  echo "Updated $name"
done
echo "=== Updating QwenPaw berkshire_v8 ==="
mkdir -p "$HOME/.qwenpaw/loop_engine/berkshire_v8/skills" "$HOME/.qwenpaw/loop_engine/berkshire_v8/tools"
rsync -av --delete "$BASE/skills/" "$HOME/.qwenpaw/loop_engine/berkshire_v8/skills/"
rsync -av --delete "$BASE/tools/" "$HOME/.qwenpaw/loop_engine/berkshire_v8/tools/"
cp "$BASE/README.md" "$BASE/VERSION_HISTORY.md" "$BASE/config/"*.md "$BASE/AGENTS.md" "$HOME/.qwenpaw/loop_engine/berkshire_v8/" 2>/dev/null || true
echo "=== Syncing latest engine code (src) ==="
# Sync the src package cleanly
mkdir -p "$HOME/.qwenpaw/loop_engine/berkshire_v8/src"
rsync -av --delete --exclude '__pycache__' --exclude '*.pyc' "$BASE/src/" "$HOME/.qwenpaw/loop_engine/berkshire_v8/src/" || true
echo "Engine src synced (package preserved)."

echo "=== Syncing graphify knowledge graph (optional) ==="
if [ -d "$BASE/graphify-out" ]; then
  mkdir -p "$HOME/.qwenpaw/loop_engine/berkshire_v8/graphify-out"
  rsync -av --delete "$BASE/graphify-out/" "$HOME/.qwenpaw/loop_engine/berkshire_v8/graphify-out/" || true
  echo "graphify-out synced."
fi

echo "Done. All platforms in sync."

# Graphify LLM activation (for full semantic on docs)
# To activate semantic extraction in graphify (beyond code-only):
# export OPENAI_API_KEY=<YOUR_KEY>          # 切勿把真实 Key 提交进仓库
# export OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3
# export OPENAI_MODEL=doubao-seed-2.0-pro
# graphify update .
# Note: requires valid CodingPlan subscription on Volcengine Ark.

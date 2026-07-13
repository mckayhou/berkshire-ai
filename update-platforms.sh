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
# Directory skills (e.g. skills/anysearch/ with SKILL.md + scripts)
for d in "$BASE/skills"/*/; do
  [ -d "$d" ] || continue
  [ -f "${d}SKILL.md" ] || continue
  name="$(basename "$d")"
  mkdir -p "$HOME/.openclaw/workspace/skills/$name"
  rsync -av --delete --exclude '.env' --exclude '__pycache__' --exclude '.git' \
    "$d" "$HOME/.openclaw/workspace/skills/$name/" || true
  # Prefer project-root .env key via env; if skill-local .env exists, copy privately (not from git)
  if [ -f "${d}.env" ]; then
    cp "${d}.env" "$HOME/.openclaw/workspace/skills/$name/.env"
    chmod 600 "$HOME/.openclaw/workspace/skills/$name/.env" 2>/dev/null || true
  fi
  echo "Synced directory skill: $name"
done
if [ -d "$BASE/.agents/skills" ]; then
  echo "=== Syncing finance-quant-skills (.agents/skills) to OpenClaw ==="
  for d in "$BASE/.agents/skills"/*/; do
    [ -d "$d" ] || continue
    name="$(basename "$d")"
    mkdir -p "$HOME/.openclaw/workspace/skills/$name"
    rsync -av --delete "$d" "$HOME/.openclaw/workspace/skills/$name/" || true
    echo "Synced quant skill: $name"
  done
fi
echo "=== Updating QwenPaw berkshire_v8 ==="
mkdir -p "$HOME/.qwenpaw/loop_engine/berkshire_v8/skills" "$HOME/.qwenpaw/loop_engine/berkshire_v8/tools"
rsync -av --delete "$BASE/skills/" "$HOME/.qwenpaw/loop_engine/berkshire_v8/skills/"
if [ -d "$BASE/.agents/skills" ]; then
  mkdir -p "$HOME/.qwenpaw/loop_engine/berkshire_v8/quant-skills"
  rsync -av --delete "$BASE/.agents/skills/" "$HOME/.qwenpaw/loop_engine/berkshire_v8/quant-skills/"
  echo "quant-skills synced to QwenPaw."
fi
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

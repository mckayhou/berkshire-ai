#!/usr/bin/env bash
# Cron 自动进化入口（对齐 config/state.md 定时表）
# 用法：
#   ./scripts/cron-evolution.sh thesis-tracker
#   ./scripts/cron-evolution.sh portfolio-weekly
#   ./scripts/cron-evolution.sh evolution-loop
#   ./scripts/cron-evolution.sh all
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TASK="${1:-evolution-loop}"
exec python3 "$ROOT/src/evolution_loop_v10.py" cron "$TASK"

#!/usr/bin/env bash
# 每周组合工作流：portfolio_scan → thesis_queue
# 用法（仓库根目录）:
#   ./scripts/portfolio-weekly.sh              # 人类可读
#   ./scripts/portfolio-weekly.sh --json       # JSON 计划
#   ./scripts/portfolio-weekly.sh --suggest-md # 可粘贴进 state.md §2
#
# 前置：复制 data/holdings.example.json → data/holdings.json（可选，用于 risk_flags）

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SCAN_JSON="${TMPDIR:-/tmp}/berkshire-scan-$$.json"
EXTRA_ARGS=("$@")

# 去掉传给 thesis_queue 的 scan 相关参数，保留 --json / --suggest-md 等
if [[ " ${EXTRA_ARGS[*]} " == *" --suggest-md "* ]]; then
  QUEUE_MODE="suggest"
elif [[ " ${EXTRA_ARGS[*]} " == *" --json "* ]]; then
  QUEUE_MODE="json"
else
  QUEUE_MODE="human"
fi

HOLDINGS_ARG=()
if [[ -f "$ROOT/data/holdings.json" ]]; then
  HOLDINGS_ARG=(--holdings-file "$ROOT/data/holdings.json")
fi

echo "==> portfolio_scan（watchlist + risk_flags）…"
python3 tools/portfolio_scan.py --json --quiet "${HOLDINGS_ARG[@]}" > "$SCAN_JSON"

echo "==> thesis_queue（合并扫描 + state.md）…"
case "$QUEUE_MODE" in
  suggest)
    python3 tools/thesis_queue.py --from-scan "$SCAN_JSON" --suggest-md
    ;;
  json)
    python3 tools/thesis_queue.py --from-scan "$SCAN_JSON" --json
    ;;
  *)
    python3 tools/portfolio_scan.py "${HOLDINGS_ARG[@]}" --top 10
    python3 tools/thesis_queue.py --from-scan "$SCAN_JSON"
    ;;
esac

rm -f "$SCAN_JSON"

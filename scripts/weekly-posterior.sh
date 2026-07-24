#!/usr/bin/env bash
# 周度投研效果体检：契约 gaps（含 action↔stance）→ 后验周报 → 可选推送
#
# 用法（仓库根目录）:
#   ./scripts/weekly-posterior.sh                 # gaps + --network 后验
#   ./scripts/weekly-posterior.sh --offline        # 不拉行情（仅 gaps + 空价后验骨架）
#   ./scripts/weekly-posterior.sh --notify         # 后验 MD 经 notify.py 多通道交付
#   ./scripts/weekly-posterior.sh --feedback       # 另跑到期决策 → experiences（dry-run）
#   ./scripts/weekly-posterior.sh --feedback-apply # 写入 experiences
#   ./scripts/weekly-posterior.sh --as-of 2026-07-24
#   AS_OF=2026-07-24 ./scripts/weekly-posterior.sh
#
# 退出码:
#   0  gaps 为空且后验命令成功
#   1  存在契约 / action↔stance 缺口（后验仍会跑，便于一并查看）
#   2  后验命令失败
#
# cron 示例（每周一 09:15 本地）:
#   15 9 * * 1 cd /path/to/berkshire-ai && ./scripts/weekly-posterior.sh --notify >>~/.berkshire/weekly-posterior.log 2>&1

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

AS_OF="${AS_OF:-$(date +%F)}"
USE_NETWORK=1
DO_NOTIFY=0
DO_FEEDBACK=0
FEEDBACK_APPLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --offline)
      USE_NETWORK=0
      shift
      ;;
    --notify)
      DO_NOTIFY=1
      shift
      ;;
    --feedback)
      DO_FEEDBACK=1
      shift
      ;;
    --feedback-apply)
      DO_FEEDBACK=1
      FEEDBACK_APPLY=1
      shift
      ;;
    --as-of)
      AS_OF="${2:?--as-of needs YYYY-MM-DD}"
      shift 2
      ;;
    -h|--help)
      sed -n '2,22p' "$0"
      exit 0
      ;;
    *)
      echo "未知参数: $1（支持 --offline --notify --feedback --feedback-apply --as-of DATE）" >&2
      exit 2
      ;;
  esac
done

OUT_DIR="${BERKSHIRE_POSTERIOR_DIR:-$ROOT/reports/_posterior}"
mkdir -p "$OUT_DIR"
MD_OUT="$OUT_DIR/posterior_weekly_${AS_OF}.md"
JSON_OUT="$OUT_DIR/posterior_weekly_${AS_OF}.json"

STEPS=3
if [[ "$DO_FEEDBACK" -eq 1 ]]; then
  STEPS=4
fi

echo "==> [1/${STEPS}] log_decision gaps（契约 + action↔stance）…"
GAPS_RC=0
if ! python3 tools/log_decision.py gaps; then
  GAPS_RC=1
  echo "    （存在缺口：complete_rate 将扣分；请修正 stance/action 或补字段）" >&2
fi

echo "==> [2/${STEPS}] posterior_weekly report as_of=${AS_OF}…"
POST_ARGS=(report --as-of "$AS_OF" --out "$MD_OUT")
if [[ "$USE_NETWORK" -eq 1 ]]; then
  POST_ARGS+=(--network)
  echo "    模式: --network（真实行情；失败时看 data_sources 降级链）"
else
  echo "    模式: offline（不取价；到期条会记 missing_price）"
fi

set +e
python3 tools/posterior_weekly.py "${POST_ARGS[@]}"
POST_RC=$?
set -e

if [[ "$POST_RC" -ne 0 ]]; then
  echo "后验周报失败 rc=$POST_RC" >&2
  exit 2
fi

# JSON 快照（不影响主退出码）
set +e
JSON_ARGS=(report --as-of "$AS_OF" --json --out "$JSON_OUT")
if [[ "$USE_NETWORK" -eq 1 ]]; then
  JSON_ARGS+=(--network)
fi
python3 tools/posterior_weekly.py "${JSON_ARGS[@]}" >/dev/null
set -e

echo "    MD:   $MD_OUT"
[[ -f "$JSON_OUT" ]] && echo "    JSON: $JSON_OUT"

STEP_N=3
if [[ "$DO_NOTIFY" -eq 1 ]]; then
  echo "==> [${STEP_N}/${STEPS}] notify.py 推送…"
  if [[ -f "$MD_OUT" ]]; then
    python3 tools/notify.py send \
      --title "Berkshire 后验周报 ${AS_OF}" \
      --file "$MD_OUT" || echo "    notify 失败（已忽略，本地 MD 仍保留）" >&2
  else
    echo "    无 MD 可推送，跳过" >&2
  fi
else
  echo "==> [${STEP_N}/${STEPS}] notify 跳过（加 --notify 开启）"
fi

if [[ "$DO_FEEDBACK" -eq 1 ]]; then
  STEP_N=$((STEP_N + 1))
  echo "==> [${STEP_N}/${STEPS}] feedback_due_decisions as_of=${AS_OF}…"
  FB_ARGS=(--as-of "$AS_OF")
  if [[ "$USE_NETWORK" -eq 0 ]]; then
    echo "    offline 周报模式下反馈需自备 --prices；此处改用 network 取价" >&2
  fi
  if [[ "$FEEDBACK_APPLY" -eq 1 ]]; then
    FB_ARGS+=(--apply)
    echo "    模式: --apply（写入 experiences）"
  else
    echo "    模式: dry-run（加 --feedback-apply 写入）"
  fi
  python3 tools/feedback_due_decisions.py "${FB_ARGS[@]}" || echo "    feedback 非 0（已忽略主退出码）" >&2
fi

echo "==> 完成 as_of=${AS_OF} gaps_rc=${GAPS_RC}"
exit "$GAPS_RC"

#!/usr/bin/env bash
# Release gate for berkshire-ai: run before tagging or declaring a version shipped.
# Usage: ./scripts/release-check.sh [--skip-pytest]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SKIP_PYTEST=0
for arg in "$@"; do
  case "$arg" in
    --skip-pytest) SKIP_PYTEST=1 ;;
    -h|--help)
      echo "Usage: $0 [--skip-pytest]"
      echo "  Verifies clean tree, version alignment, tag at HEAD, upstream sync, pytest."
      exit 0
      ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

ok() {
  echo "OK: $*"
}

warn() {
  echo "WARN: $*" >&2
}

# --- 1. Clean working tree (includes graphify hook drift) ---
DIRTY="$(git status --porcelain | grep -v '^?? graphify-out/\.rebuild\.lock$' || true)"
if [[ -n "$DIRTY" ]]; then
  echo "Uncommitted changes:" >&2
  echo "$DIRTY" >&2
  fail "working tree not clean — commit or stash before release"
fi
ok "working tree clean"

# --- 2. Version strings ---
PKG_VER="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)"
[[ -n "$PKG_VER" ]] || fail "could not read version from pyproject.toml"

APP_VER="$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' src/service.py | head -1)"
[[ -n "$APP_VER" ]] || fail "could not read APP_VERSION from src/service.py"

[[ "$PKG_VER" == "$APP_VER" ]] || fail "pyproject.toml ($PKG_VER) != APP_VERSION ($APP_VER)"
ok "pyproject.toml == APP_VERSION ($PKG_VER)"

# 10.25.0 -> V10.25
MAJOR_MINOR="${PKG_VER%.*}"
EXPECTED_BANNER="V${MAJOR_MINOR}"

README_BANNER="$(grep -m1 '当前版本' README.md | sed -n 's/.*当前版本\*\*：\*\*\(V10\.[0-9][0-9]*\).*/\1/p')"
[[ -n "$README_BANNER" ]] || fail "could not parse README.md 当前版本 banner"
[[ "$README_BANNER" == "$EXPECTED_BANNER" ]] || fail "README.md banner ($README_BANNER) != $EXPECTED_BANNER"

STATE_BANNER="$(grep -m1 'Version:' config/state.md | grep -oE 'V10\.[0-9]+' || true)"
[[ "$STATE_BANNER" == "$EXPECTED_BANNER" ]] || fail "config/state.md ($STATE_BANNER) != $EXPECTED_BANNER"
ok "user-facing banners match ($EXPECTED_BANNER)"

# --- 3. No phantom future version labels in tracked docs ---
PHANTOM="$(grep -r 'V10\.26' --include='*.md' config README.md docs tools 2>/dev/null \
  | grep -v '.agents/skills/qmt-docs' || true)"
[[ -z "$PHANTOM" ]] || { echo "$PHANTOM" >&2; fail "phantom V10.26 references (fold into current VERSION_HISTORY entry)"; }
ok "no phantom V10.26 in core docs"

# --- 4. Annotated tag points at HEAD ---
TAG="v${MAJOR_MINOR}"
if git rev-parse "$TAG" >/dev/null 2>&1; then
  HEAD_SHA="$(git rev-parse HEAD)"
  TAG_SHA="$(git rev-parse "${TAG}^{commit}")"
  [[ "$HEAD_SHA" == "$TAG_SHA" ]] || fail "HEAD ($HEAD_SHA) != ${TAG}^{commit} ($TAG_SHA) — move tag or commit remaining work"
  ok "tag ${TAG} at HEAD"
else
  warn "tag ${TAG} not found (create after this check passes)"
fi

# --- 5. Upstream sync (when tracking branch exists) ---
if git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
  LOCAL_SHA="$(git rev-parse @)"
  REMOTE_SHA="$(git rev-parse '@{u}')"
  [[ "$LOCAL_SHA" == "$REMOTE_SHA" ]] || fail "branch ahead/behind origin — push or pull first"
  ok "in sync with @{u}"
fi

# --- 6. Tests ---
if [[ "$SKIP_PYTEST" -eq 0 ]]; then
  if command -v pytest >/dev/null 2>&1; then
    pytest -q tests/
    ok "pytest passed"
  else
    warn "pytest not in PATH — install dev extras: pip install -e '.[dev]'"
  fi
else
  warn "pytest skipped (--skip-pytest)"
fi

echo ""
echo "release-check passed for version ${PKG_VER} (${EXPECTED_BANNER})"

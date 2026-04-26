#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-}"
CONFIG_DIR="${2:-/config}"
MARKER_FILE="${CONFIG_DIR}/.ha_build_info"

case "$BRANCH" in
  main|develop) ;;
  *)
    echo "Refusing to deploy unsupported branch: '${BRANCH}'" >&2
    exit 2
    ;;
esac

cd "$CONFIG_DIR"

git config --global --add safe.directory "$CONFIG_DIR" >/dev/null 2>&1 || true

if [ -n "$(git status --porcelain)" ]; then
  echo "Uncommitted changes in ${CONFIG_DIR}; refusing to switch branches." >&2
  git status --porcelain >&2
  exit 1
fi

git fetch origin --prune
git checkout -B "$BRANCH" "origin/$BRANCH"
git reset --hard "origin/$BRANCH"

SHA="$(git rev-parse --short HEAD)"
TS="$(date -Iseconds)"
TAG="$(git describe --tags --exact-match 2>/dev/null || true)"
MODE="prod"
if [ "$BRANCH" = "develop" ]; then
  MODE="preprod"
fi

cat > "$MARKER_FILE" <<EOF
mode=${MODE}
branch=${BRANCH}
tag=${TAG}
sha=${SHA}
timestamp=${TS}
EOF

ha core restart

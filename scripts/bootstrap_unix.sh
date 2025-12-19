#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip

OS_FILE="requirements/ubuntu.txt"
if [[ "$(uname -s)" == "Darwin" ]]; then
  OS_FILE="requirements/macos.txt"
fi

pip install -r "$OS_FILE"

# Install git hooks
pre-commit install
pre-commit install --hook-type pre-push

echo "✅ Python env ready: .venv"

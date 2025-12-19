#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements/ubuntu.txt
echo "✅ Done. Activate with: source .venv/bin/activate"

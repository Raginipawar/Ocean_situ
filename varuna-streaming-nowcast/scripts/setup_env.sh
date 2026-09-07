#!/usr/bin/env bash
# One-shot environment setup for macOS / Linux.
# Run from anywhere: ./scripts/setup_env.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
./.venv/bin/python -m pip install -e .

echo ""
echo "Setup complete. Activate the environment with:"
echo "    source .venv/bin/activate"

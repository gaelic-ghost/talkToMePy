#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "Missing dependency: uv"
  echo "Install uv first: https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi

if ! command -v sox >/dev/null 2>&1; then
  echo "Missing dependency: sox"
  echo "Install sox first (macOS): brew install sox"
  exit 1
fi

echo "Syncing Python environment with uv..."
uv sync

mkdir -p outputs

if [[ ! -f "$REPO_DIR/.env.launchd" ]]; then
  cp "$REPO_DIR/.env.example" "$REPO_DIR/.env.launchd"
  echo "Created .env.launchd from .env.example"
fi

echo "Setup complete."
echo "Next:"
echo "  uv run python main.py"
echo "  curl http://127.0.0.1:8000/health"

#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PYTHON="$REPO_DIR/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Expected venv python at $VENV_PYTHON"
  exit 1
fi

cd "$REPO_DIR"

# Launchd jobs run with a minimal environment, so set runtime env explicitly.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export TALKTOMEPY_HOST="127.0.0.1"
export TALKTOMEPY_PORT="8000"
export TALKTOMEPY_RELOAD="false"
export QWEN_TTS_IDLE_UNLOAD_SECONDS="900"

# Optional per-machine overrides for launchd usage.
if [[ -f "$REPO_DIR/.env.launchd" ]]; then
  set -a
  source "$REPO_DIR/.env.launchd"
  set +a
fi

exec "$VENV_PYTHON" main.py

#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PYTHON="$REPO_DIR/.venv/bin/python"
ENV_FILE="${1:-$REPO_DIR/.env.launchd}"

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
export QWEN_TTS_WARM_LOAD_ON_START="true"

# Optional per-instance overrides for launchd usage.
if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

exec "$VENV_PYTHON" main.py

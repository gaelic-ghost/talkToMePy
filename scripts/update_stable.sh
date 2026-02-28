#!/bin/bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/update_stable.sh [options]

Options:
  --instance <name>   Launchd instance name (default: stable)
  --port <port>       Service port for install/checks (default: 8000)
  --reinstall         Force launchd install flow
  --restart-only      Force restart flow (error if agent plist missing)
  --skip-pull         Skip git fetch/pull safety flow
  --no-check          Skip post-update /health validation
  --check-model-ready Trigger model load and wait for ready state after health check
  -h, --help          Show this help

Examples:
  ./scripts/update_stable.sh
  ./scripts/update_stable.sh --reinstall
  ./scripts/update_stable.sh --check-model-ready
  ./scripts/update_stable.sh --skip-pull --no-check
USAGE
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

INSTANCE="stable"
PORT="8000"
DO_PULL=true
DO_CHECK=true
FORCE_REINSTALL=false
FORCE_RESTART_ONLY=false
CHECK_MODEL_READY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --instance)
      INSTANCE="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --reinstall)
      FORCE_REINSTALL=true
      shift
      ;;
    --restart-only)
      FORCE_RESTART_ONLY=true
      shift
      ;;
    --skip-pull)
      DO_PULL=false
      shift
      ;;
    --no-check)
      DO_CHECK=false
      shift
      ;;
    --check-model-ready)
      CHECK_MODEL_READY=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "$FORCE_REINSTALL" == true && "$FORCE_RESTART_ONLY" == true ]]; then
  echo "Flags --reinstall and --restart-only are mutually exclusive." >&2
  exit 1
fi

if [[ "$DO_CHECK" != true && "$CHECK_MODEL_READY" == true ]]; then
  echo "Flags --no-check and --check-model-ready are mutually exclusive." >&2
  exit 1
fi

if [[ -z "$INSTANCE" ]]; then
  echo "Instance must not be empty." >&2
  exit 1
fi

if [[ -z "$PORT" ]]; then
  echo "Port must not be empty." >&2
  exit 1
fi

for tool in git uv curl sox; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing dependency: $tool" >&2
    case "$tool" in
      uv)
        echo "Install uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
        ;;
      sox)
        echo "Install sox (macOS): brew install sox" >&2
        ;;
    esac
    exit 1
  fi
done

cd "$REPO_DIR"

BEFORE_HEAD="$(git rev-parse HEAD)"
AFTER_HEAD="$BEFORE_HEAD"

if [[ "$DO_PULL" == true ]]; then
  echo "[1/4] Syncing git"

  if [[ -n "$(git status --porcelain)" ]]; then
    echo "Working tree is dirty. Commit/stash/discard changes before updating." >&2
    exit 1
  fi

  CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  if [[ "$CURRENT_BRANCH" != "main" ]]; then
    echo "Expected branch 'main' for update flow, found '$CURRENT_BRANCH'." >&2
    echo "Switch to main or re-run with --skip-pull." >&2
    exit 1
  fi

  git fetch --prune origin
  if ! git pull --ff-only origin main; then
    echo "Fast-forward pull failed. Resolve branch divergence manually and retry." >&2
    exit 1
  fi

  AFTER_HEAD="$(git rev-parse HEAD)"
else
  echo "[1/4] Syncing git (skipped via --skip-pull)"
fi

echo "[2/4] Running setup"
./scripts/setup.sh

RELAUNCH_MODE="restart"

if [[ "$FORCE_REINSTALL" == true ]]; then
  RELAUNCH_MODE="install"
elif [[ "$FORCE_RESTART_ONLY" == true ]]; then
  RELAUNCH_MODE="restart"
else
  if [[ "$AFTER_HEAD" != "$BEFORE_HEAD" ]]; then
    if git diff --name-only "$BEFORE_HEAD" "$AFTER_HEAD" | rg -x 'launchd/com\.talktomepy\.plist|scripts/launchd_instance\.sh|scripts/run_service\.sh|\.env\.example' >/dev/null; then
      RELAUNCH_MODE="install"
    fi
  fi
fi

echo "[3/4] Relaunching $INSTANCE service ($RELAUNCH_MODE)"

LABEL="com.talktomepy.$INSTANCE"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"

if [[ "$RELAUNCH_MODE" == "restart" ]]; then
  if [[ ! -f "$PLIST_PATH" ]]; then
    if [[ "$FORCE_RESTART_ONLY" == true ]]; then
      echo "Missing plist: $PLIST_PATH" >&2
      echo "Cannot use --restart-only before install. Re-run with --reinstall." >&2
      exit 1
    fi
    echo "Missing plist for restart; falling back to install."
    RELAUNCH_MODE="install"
  fi
fi

if [[ "$RELAUNCH_MODE" == "install" ]]; then
  ./scripts/launchd_instance.sh install --instance "$INSTANCE" --port "$PORT"
else
  ./scripts/launchd_instance.sh restart --instance "$INSTANCE"
fi

if [[ "$DO_CHECK" == true ]]; then
  echo "[4/4] Checking health"
  HEALTH_URL="http://127.0.0.1:${PORT}/health"
  MODEL_LOAD_URL="http://127.0.0.1:${PORT}/model/load"
  MODEL_STATUS_URL="http://127.0.0.1:${PORT}/model/status"
  HEALTH_BODY=""
  OK=false

  for _ in $(seq 1 30); do
    if HEALTH_BODY="$(curl -fsS "$HEALTH_URL" 2>/dev/null)"; then
      OK=true
      break
    fi
    sleep 1
  done

  if [[ "$OK" != true ]]; then
    echo "Health check failed after 30 seconds: $HEALTH_URL" >&2
    echo "Check status: ./scripts/launchd_instance.sh status --instance $INSTANCE" >&2
    echo "Logs: $HOME/Library/Logs/talktomepy.$INSTANCE.stdout.log" >&2
    echo "      $HOME/Library/Logs/talktomepy.$INSTANCE.stderr.log" >&2
    exit 1
  fi

  echo "Health OK: $HEALTH_BODY"

  if [[ "$CHECK_MODEL_READY" == true ]]; then
    echo "Checking model readiness"
    LOAD_BODY_FILE="$(mktemp)"
    LOAD_STATUS="$(curl -sS -o "$LOAD_BODY_FILE" -w "%{http_code}" -X POST "$MODEL_LOAD_URL" \
      -H "Content-Type: application/json" \
      -d '{"mode":"voice_design","strict_load":false}' || true)"
    if [[ "$LOAD_STATUS" != "200" && "$LOAD_STATUS" != "202" ]]; then
      echo "Model load request failed with HTTP $LOAD_STATUS: $MODEL_LOAD_URL" >&2
      cat "$LOAD_BODY_FILE" >&2 || true
      rm -f "$LOAD_BODY_FILE"
      exit 1
    fi
    rm -f "$LOAD_BODY_FILE"

    MODEL_STATUS_BODY=""
    MODEL_OK=false
    for _ in $(seq 1 90); do
      if MODEL_STATUS_BODY="$(curl -fsS "$MODEL_STATUS_URL" 2>/dev/null)"; then
        if printf '%s' "$MODEL_STATUS_BODY" | rg -q '"loaded"\s*:\s*true'; then
          MODEL_OK=true
          break
        fi
      fi
      sleep 1
    done

    if [[ "$MODEL_OK" != true ]]; then
      echo "Model readiness check failed after 90 seconds: $MODEL_STATUS_URL" >&2
      echo "Last model status: ${MODEL_STATUS_BODY:-<unavailable>}" >&2
      echo "Check status: ./scripts/launchd_instance.sh status --instance $INSTANCE" >&2
      echo "Logs: $HOME/Library/Logs/talktomepy.$INSTANCE.stdout.log" >&2
      echo "      $HOME/Library/Logs/talktomepy.$INSTANCE.stderr.log" >&2
      exit 1
    fi

    echo "Model ready: $MODEL_STATUS_BODY"
  fi
else
  echo "[4/4] Checking health (skipped via --no-check)"
  echo "Next: curl -fsS http://127.0.0.1:${PORT}/health"
fi

echo "Update complete (instance=$INSTANCE, mode=$RELAUNCH_MODE)."

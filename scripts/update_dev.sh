#!/bin/bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/update_dev.sh [options]

Options:
  --instance <name>   Launchd instance name (default: dev)
  --port <port>       Service port for install/checks (default: 8001)
  --pull-current      Fetch + fast-forward pull current branch from its upstream
  --reinstall         Force launchd install flow
  --restart-only      Force restart flow (error if agent plist missing)
  --no-check          Skip post-update /health validation
  -h, --help          Show this help

Examples:
  ./scripts/update_dev.sh
  ./scripts/update_dev.sh --pull-current
  ./scripts/update_dev.sh --reinstall
  ./scripts/update_dev.sh --no-check
USAGE
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

INSTANCE="dev"
PORT="8001"
DO_PULL_CURRENT=false
DO_CHECK=true
FORCE_REINSTALL=false
FORCE_RESTART_ONLY=false

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
    --pull-current)
      DO_PULL_CURRENT=true
      shift
      ;;
    --reinstall)
      FORCE_REINSTALL=true
      shift
      ;;
    --restart-only)
      FORCE_RESTART_ONLY=true
      shift
      ;;
    --no-check)
      DO_CHECK=false
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

if [[ "$DO_PULL_CURRENT" == true ]]; then
  echo "[1/4] Syncing git current branch"

  if [[ -n "$(git status --porcelain)" ]]; then
    echo "Working tree is dirty. Commit/stash/discard changes before pulling current branch." >&2
    exit 1
  fi

  CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  if [[ "$CURRENT_BRANCH" == "HEAD" ]]; then
    echo "Detached HEAD detected. Check out a branch before using --pull-current." >&2
    exit 1
  fi

  UPSTREAM_REF="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"
  if [[ -z "$UPSTREAM_REF" ]]; then
    echo "Current branch '$CURRENT_BRANCH' has no upstream." >&2
    echo "Set one (example): git branch --set-upstream-to origin/$CURRENT_BRANCH $CURRENT_BRANCH" >&2
    exit 1
  fi

  UPSTREAM_REMOTE="${UPSTREAM_REF%%/*}"
  UPSTREAM_BRANCH="${UPSTREAM_REF#*/}"
  if [[ -z "$UPSTREAM_REMOTE" || -z "$UPSTREAM_BRANCH" || "$UPSTREAM_REMOTE" == "$UPSTREAM_REF" ]]; then
    echo "Unable to parse upstream '$UPSTREAM_REF' for branch '$CURRENT_BRANCH'." >&2
    exit 1
  fi

  git fetch --prune "$UPSTREAM_REMOTE"
  if ! git pull --ff-only "$UPSTREAM_REMOTE" "$UPSTREAM_BRANCH"; then
    echo "Fast-forward pull failed for '$CURRENT_BRANCH' from '$UPSTREAM_REF'." >&2
    echo "Resolve branch divergence manually and retry." >&2
    exit 1
  fi

  AFTER_HEAD="$(git rev-parse HEAD)"
else
  echo "[1/4] Syncing git (skipped by default in dev; pass --pull-current to enable)"
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
else
  echo "[4/4] Checking health (skipped via --no-check)"
  echo "Next: curl -fsS http://127.0.0.1:${PORT}/health"
fi

echo "Update complete (instance=$INSTANCE, mode=$RELAUNCH_MODE)."

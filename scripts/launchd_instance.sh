#!/bin/bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/launchd_instance.sh install --instance <name> [--port <port>]
  scripts/launchd_instance.sh start --instance <name>
  scripts/launchd_instance.sh restart --instance <name>
  scripts/launchd_instance.sh stop --instance <name>
  scripts/launchd_instance.sh status --instance <name>
  scripts/launchd_instance.sh logs --instance <name>
  scripts/launchd_instance.sh remove --instance <name>

Examples:
  scripts/launchd_instance.sh install --instance stable --port 8000
  scripts/launchd_instance.sh install --instance dev --port 8001
  scripts/launchd_instance.sh status --instance dev
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ACTION="${1:-}"
shift || true

INSTANCE=""
PORT=""

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
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$ACTION" || "$ACTION" == "--help" || "$ACTION" == "-h" ]]; then
  usage
  exit 0
fi

if [[ -z "$INSTANCE" ]]; then
  echo "Missing required flag: --instance <name>"
  usage
  exit 1
fi

UID_NUM="$(id -u)"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
LABEL="com.talktomepy.$INSTANCE"
PLIST_PATH="$LAUNCH_AGENT_DIR/$LABEL.plist"
TEMPLATE_PATH="$REPO_DIR/launchd/com.talktomepy.plist"
ENV_FILE="$REPO_DIR/.env.launchd.$INSTANCE"
STDOUT_LOG="$HOME/Library/Logs/talktomepy.$INSTANCE.stdout.log"
STDERR_LOG="$HOME/Library/Logs/talktomepy.$INSTANCE.stderr.log"

upsert_env() {
  local key="$1"
  local value="$2"
  if [[ ! -f "$ENV_FILE" ]]; then
    touch "$ENV_FILE"
  fi
  if rg -n "^${key}=" "$ENV_FILE" >/dev/null 2>&1; then
    sed -i '' "s|^${key}=.*|${key}=${value}|g" "$ENV_FILE"
  else
    echo "${key}=${value}" >>"$ENV_FILE"
  fi
}

ensure_env_file() {
  if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$REPO_DIR/.env.launchd" ]]; then
      cp "$REPO_DIR/.env.launchd" "$ENV_FILE"
    elif [[ -f "$REPO_DIR/.env.example" ]]; then
      cp "$REPO_DIR/.env.example" "$ENV_FILE"
    else
      touch "$ENV_FILE"
    fi
  fi
  if [[ -n "$PORT" ]]; then
    upsert_env "TALKTOMEPY_PORT" "$PORT"
  fi
}

render_plist() {
  mkdir -p "$LAUNCH_AGENT_DIR"
  sed \
    -e "s|__LABEL__|$LABEL|g" \
    -e "s|__REPO_DIR__|$REPO_DIR|g" \
    -e "s|__HOME__|$HOME|g" \
    -e "s|__ENV_FILE__|$ENV_FILE|g" \
    -e "s|__STDOUT_LOG__|$STDOUT_LOG|g" \
    -e "s|__STDERR_LOG__|$STDERR_LOG|g" \
    "$TEMPLATE_PATH" >"$PLIST_PATH"
}

bootstrap() {
  launchctl bootout "gui/$UID_NUM" "$PLIST_PATH" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$UID_NUM" "$PLIST_PATH"
}

case "$ACTION" in
  install)
    ensure_env_file
    render_plist
    bootstrap
    launchctl kickstart -k "gui/$UID_NUM/$LABEL"
    echo "Installed and started: $LABEL"
    echo "Plist: $PLIST_PATH"
    echo "Env: $ENV_FILE"
    echo "Logs: $STDOUT_LOG | $STDERR_LOG"
    ;;
  start)
    if [[ ! -f "$PLIST_PATH" ]]; then
      echo "Missing plist: $PLIST_PATH"
      echo "Run install first."
      exit 1
    fi
    bootstrap
    launchctl kickstart -k "gui/$UID_NUM/$LABEL"
    ;;
  restart)
    launchctl kickstart -k "gui/$UID_NUM/$LABEL"
    ;;
  stop)
    launchctl bootout "gui/$UID_NUM" "$PLIST_PATH"
    ;;
  status)
    launchctl print "gui/$UID_NUM/$LABEL"
    ;;
  logs)
    tail -f "$STDOUT_LOG" "$STDERR_LOG"
    ;;
  remove)
    launchctl bootout "gui/$UID_NUM" "$PLIST_PATH" >/dev/null 2>&1 || true
    rm -f "$PLIST_PATH"
    echo "Removed: $PLIST_PATH"
    ;;
  *)
    echo "Unknown action: $ACTION"
    usage
    exit 1
    ;;
esac

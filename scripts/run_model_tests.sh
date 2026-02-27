#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/run_model_tests.sh [--execution seq|par]

Options:
  --execution <mode>  Execution mode for suites: seq or par (default: TALKTOMEPY_TEST_EXECUTION or seq)

Environment:
  TALKTOMEPY_TEST_EXECUTION  Default execution mode when --execution is omitted.
  TALKTOMEPY_E2E_BASE_URLS   Comma-separated e2e target base URLs (default: http://127.0.0.1:8000)
EOF
}

EXECUTION_MODE="${TALKTOMEPY_TEST_EXECUTION:-seq}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execution)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --execution" >&2
        usage
        exit 1
      fi
      EXECUTION_MODE="$2"
      shift 2
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

if [[ "$EXECUTION_MODE" != "seq" && "$EXECUTION_MODE" != "par" ]]; then
  echo "Invalid execution mode: $EXECUTION_MODE (expected seq or par)" >&2
  exit 1
fi

export TALKTOMEPY_TEST_EXECUTION="$EXECUTION_MODE"
export TALKTOMEPY_E2E_BASE_URLS="${TALKTOMEPY_E2E_BASE_URLS:-http://127.0.0.1:8000}"

DIRECT_CMD=(uv run pytest -q -m direct_model tests/direct_model)
E2E_CMD=(uv run pytest -q -m e2e_api tests/e2e_api)

if [[ "$EXECUTION_MODE" == "seq" ]]; then
  "${DIRECT_CMD[@]}"
  "${E2E_CMD[@]}"
  exit 0
fi

"${DIRECT_CMD[@]}" &
DIRECT_PID=$!
"${E2E_CMD[@]}" &
E2E_PID=$!

wait "$DIRECT_PID"
wait "$E2E_PID"

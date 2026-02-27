# AGENTS.md

## Repository Expectations

- After patching service/runtime code (for example files under `app/`, `main.py`, or service scripts), run `./scripts/update_dev.sh` before rerunning e2e tests to ensure the running service picks up the change.
- Documentation-only or non-service patches (for example README/ROADMAP edits) do not require `./scripts/update_dev.sh` before e2e reruns.

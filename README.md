# TalkToMePy

Local Qwen3 VoiceDesign TTS service built with FastAPI.

## Status

- Working end-to-end via `curl`
- Working end-to-end from a separate Swift CLI client
- Current output format: `audio/wav` (PCM16 mono 24kHz)

## Demo (2 minutes)

```bash
uv run python main.py
```

In another terminal:

```bash
mkdir -p outputs
curl -X POST http://127.0.0.1:8000/model/load
curl -X POST http://127.0.0.1:8000/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello from TalkToMePy demo.","instruct":"Warm and clear narrator voice.","language":"English","format":"wav"}' \
  --output outputs/demo.wav
afplay outputs/demo.wav
```

## Requirements

- Python `>=3.13`
- `uv`
- `sox` on PATH (macOS: `brew install sox`)

## Setup

```bash
./scripts/setup.sh
```

This script:
- checks for `uv` and `sox`
- runs `uv sync`
- creates `outputs/`
- creates `.env.launchd` from `.env.example` if missing

## Configuration

Copy and edit:

```bash
cp .env.example .env.launchd
```

`scripts/run_service.sh` will load `.env.launchd` when running under launchd.

## Run Service

```bash
uv run python main.py
```

Service URL: `http://127.0.0.1:8000`

## Run as macOS Background Service (launchd)

This repo includes:
- LaunchAgent template: `launchd/com.talktomepy.plist`
- Runner script: `scripts/run_service.sh`

Install and start (user agent):

```bash
REPO_DIR="$(pwd)"
mkdir -p ~/Library/LaunchAgents
cp launchd/com.talktomepy.plist ~/Library/LaunchAgents/com.talktomepy.plist
sed -i '' "s|__REPO_DIR__|$REPO_DIR|g; s|__HOME__|$HOME|g" ~/Library/LaunchAgents/com.talktomepy.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.talktomepy.plist
launchctl kickstart -k gui/$(id -u)/com.talktomepy
```

Status and logs:

```bash
launchctl print gui/$(id -u)/com.talktomepy
tail -f ~/Library/Logs/talktomepy.stdout.log ~/Library/Logs/talktomepy.stderr.log
```

Stop and remove:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.talktomepy.plist
rm ~/Library/LaunchAgents/com.talktomepy.plist
```

Notes for modern macOS (including macOS 26):
- Prefer `bootstrap`/`bootout`/`kickstart` over legacy `load`/`unload`.
- `launchd` has a minimal environment; keep required env vars in `scripts/run_service.sh`.
- `scripts/run_service.sh` sets a Homebrew-friendly default `PATH` so `sox` is resolvable under launchd.

## Endpoints

- `GET /health` returns service status
- `GET /model/status` returns model runtime readiness (SoX, qwen-tts, load state)
- `POST /model/load` lazily loads the configured model into memory
- `POST /model/unload` unloads the model from memory
- `POST /synthesize` returns generated audio bytes as `audio/wav`

Notes:
- `POST /model/load` may return `202 Accepted` while loading is in progress.
- `POST /synthesize` returns `503` with `Retry-After` if model is still loading.

## Quickstart

```bash
curl http://127.0.0.1:8000/health
```

```bash
curl http://127.0.0.1:8000/model/status
```

```bash
curl -X POST http://127.0.0.1:8000/model/load
```

```bash
curl -X POST http://127.0.0.1:8000/model/unload
```

```bash
curl -X POST http://127.0.0.1:8000/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello from Swift bridge!","instruct":"Warm and friendly voice with steady pace.","language":"English","format":"wav"}' \
  --output outputs/from_service.wav
```

Play the generated file on macOS:

```bash
afplay outputs/from_service.wav
```

## VoiceDesign Smoke Script

```bash
uv run python scripts/voice_design_smoke.py \
  --text "Hello from my Swift CLI bridge." \
  --instruct "Energetic, friendly, and slightly brisk pacing with bright tone." \
  --output outputs/swift_bridge_demo.wav
```

## Notes

- `qwen-tts` currently requires `transformers==4.57.3` (pinned in this repo).
- `/synthesize` currently supports `format: "wav"` only.
- Model id can be overridden with env var `QWEN_TTS_MODEL_ID`.
- Optional idle auto-unload can be enabled with env var `QWEN_TTS_IDLE_UNLOAD_SECONDS`.
- Optional startup warm-load can be enabled with env var `QWEN_TTS_WARM_LOAD_ON_START=true`.
- Optional load settings: `QWEN_TTS_DEVICE_MAP`, `QWEN_TTS_TORCH_DTYPE`.

## Roadmap

- Add streaming synthesis response mode
- Add optional on-disk audio caching
- Add structured request/response logging and timing metrics
- Add Docker setup for self-hosting on a local machine (for example Mac mini)
- Add small auth layer for non-local deployments

## TODO

- Add unit tests for `/model/load` and `/synthesize` error paths
- Add integration test that writes and validates returned WAV header
- Add graceful startup warm-load option (env-controlled)
- Add response metadata headers for generation latency
- Add example Swift client snippet directly in this repo

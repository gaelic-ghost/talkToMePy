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
curl -X POST http://127.0.0.1:8000/model/load \
  -H "Content-Type: application/json" \
  -d '{"mode":"voice_design","strict_load":false}'
curl -X POST http://127.0.0.1:8000/synthesize/voice-design \
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

Single-instance defaults:

```bash
cp .env.example .env.launchd
```

Instance-specific launchd env files are also supported:

- `.env.launchd.stable`
- `.env.launchd.dev`

`scripts/run_service.sh` accepts an env file path argument, and `scripts/launchd_instance.sh` wires this automatically.

## Run Service

```bash
uv run python main.py
```

Service URL: `http://127.0.0.1:8000`

## API Spec (OpenAPI)

FastAPI exposes live docs/spec automatically:

- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

This repo includes separate target and generated YAML specs:

- Target spec (do not overwrite): `openapi/openapi.yaml`
- Backup copy of target spec: `openapi/openapi.target.yaml`
- Generated export from app OpenAPI schema: `openapi/openapi.generated.yaml`

Regenerate the generated spec after API changes:

```bash
uv run python scripts/export_openapi.py
```

Check parity between target and generated specs:

```bash
diff -u openapi/openapi.yaml openapi/openapi.generated.yaml
```

Run the parity gate test:

```bash
uv run python scripts/export_openapi.py
uv run pytest -q tests/test_openapi_parity.py
```

## Run as macOS Background Service (launchd)

This repo includes:
- LaunchAgent template: `launchd/com.talktomepy.plist`
- Runner script: `scripts/run_service.sh`
- Instance manager: `scripts/launchd_instance.sh`

Install and start a single instance:

```bash
./scripts/launchd_instance.sh install --instance stable --port 8000
```

Manage it:

```bash
./scripts/launchd_instance.sh status --instance stable
./scripts/launchd_instance.sh logs --instance stable
./scripts/launchd_instance.sh restart --instance stable
./scripts/launchd_instance.sh stop --instance stable
./scripts/launchd_instance.sh remove --instance stable
```

### Stable + Dev Side-by-Side on One Mac

Install from each clone with a different instance name and port:

Stable clone (`~/Workspace/services/talkToMePy`):

```bash
cd ~/Workspace/services/talkToMePy
./scripts/launchd_instance.sh install --instance stable --port 8000
```

Dev clone (`~/Workspace/talkToMePy`):

```bash
cd ~/Workspace/talkToMePy
./scripts/launchd_instance.sh install --instance dev --port 8001
```

Health check both:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8001/health
```

Notes for modern macOS (including macOS 26):
- Prefer `bootstrap`/`bootout`/`kickstart` over legacy `load`/`unload`.
- `launchd` has a minimal environment; keep required env vars in `scripts/run_service.sh` and per-instance env files.
- `scripts/run_service.sh` sets a Homebrew-friendly default `PATH` so `sox` is resolvable under launchd.

## Endpoints

- `GET /health` returns service status
- `GET /version` returns API/service version metadata
- `GET /adapters` lists available runtime adapters
- `GET /adapters/{adapter_id}/status` returns adapter-specific status
- `GET /model/status` returns mode-aware model runtime readiness/status
- `GET /model/inventory` returns supported model inventory and local availability
- `POST /model/load` accepts mode-aware load request and lazily loads selected model
- `POST /model/unload` unloads the model from memory
- `GET /custom-voice/speakers` returns supported custom-voice speakers for selected model
- `POST /synthesize/voice-design` returns generated audio bytes as `audio/wav`
- `POST /synthesize/custom-voice` returns generated audio bytes as `audio/wav`
- `POST /synthesize/voice-clone` returns generated audio bytes as `audio/wav`

Notes:
- `POST /model/load` may return `202 Accepted` while loading is in progress.
- Synth routes return `503` with `Retry-After` if model is still loading.
- Legacy `POST /synthesize` and `POST /synthesize/stream` were removed in v0.5.0.

## Quickstart

```bash
curl http://127.0.0.1:8000/health
```

```bash
curl http://127.0.0.1:8000/version
```

```bash
curl http://127.0.0.1:8000/adapters
```

```bash
curl http://127.0.0.1:8000/adapters/qwen3-tts/status
```

```bash
curl http://127.0.0.1:8000/model/status
```

```bash
curl http://127.0.0.1:8000/model/inventory
```

```bash
curl -X POST http://127.0.0.1:8000/model/load \
  -H "Content-Type: application/json" \
  -d '{"mode":"voice_design","strict_load":false}'
```

```bash
curl -X POST http://127.0.0.1:8000/model/unload
```

```bash
curl -X POST http://127.0.0.1:8000/synthesize/voice-design \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello from Swift bridge!","instruct":"Warm and friendly voice with steady pace.","language":"English","format":"wav"}' \
  --output outputs/from_service.wav
```

```bash
curl -X POST http://127.0.0.1:8000/synthesize/custom-voice \
  -H "Content-Type: application/json" \
  -d '{"text":"Custom voice endpoint test.","speaker":"ryan","language":"English","format":"wav"}' \
  --output outputs/from_custom.wav
```

```bash
curl -X POST http://127.0.0.1:8000/synthesize/voice-clone \
  -H "Content-Type: application/json" \
  -d '{"text":"Voice clone endpoint test.","reference_audio_b64":"UklGRg==","language":"English","format":"wav"}' \
  --output outputs/from_clone.wav
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
- All synth endpoints currently support `format: "wav"` only.
- Model id can be overridden with env var `QWEN_TTS_MODEL_ID`.
- Optional idle auto-unload can be enabled with env var `QWEN_TTS_IDLE_UNLOAD_SECONDS`.
- Optional startup warm-load can be enabled with env var `QWEN_TTS_WARM_LOAD_ON_START=true`.
- Optional load settings: `QWEN_TTS_DEVICE_MAP`, `QWEN_TTS_TORCH_DTYPE`.
- When `QWEN_TTS_DEVICE_MAP` is unset or `auto`, a synthesis meta-tensor runtime failure now triggers one automatic reload/retry on CPU (`device_map=cpu`, `torch_dtype=float32`).

Roadmap and TODO tracking live in `ROADMAP.md`.

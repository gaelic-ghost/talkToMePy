# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Manual unload endpoint `POST /model/unload`.
- Optional idle auto-unload support via `QWEN_TTS_IDLE_UNLOAD_SECONDS`.
- Launchd background service files:
  - `launchd/com.talktomepy.plist`
  - `scripts/run_service.sh`
- `.env.example` with runtime/service configuration keys.
- Bootstrap script `scripts/setup.sh` for first-run setup.
- Startup warm-load option via `QWEN_TTS_WARM_LOAD_ON_START`.
- OpenAPI export script `scripts/export_openapi.py`.
- Committed OpenAPI spec at `openapi/openapi.yaml`.
- `GET /version` endpoint for API/service version metadata.
- Adapter discovery/status endpoints:
  - `GET /adapters`
  - `GET /adapters/{adapter_id}/status`
- `POST /synthesize/stream` endpoint for streaming WAV response transport.

### Changed
- `GET /model/status` now reports idle/last-use metadata.
- `main.py` now uses env-configurable host/port/reload and defaults to `reload=false`.
- README now includes a quick demo flow and portable launchd install instructions.
- `/model/status` now reports model loading state and last load error details.
- `/model/load` now returns `202` while asynchronous model loading is in progress.
- `/synthesize` now returns `503` with retry guidance when model loading is in progress.
- OpenAPI docs now describe `/model/load` async `202` and `/synthesize` binary `audio/wav` responses.
- README and OpenAPI docs now include the v1 subset endpoints above.

## [0.1.0] - 2026-02-21

### Added
- FastAPI service scaffold with `GET /health`.
- Runtime readiness endpoint `GET /model/status`.
- Lazy model loading endpoint `POST /model/load`.
- Working synthesis endpoint `POST /synthesize` returning `audio/wav`.
- Qwen VoiceDesign smoke script at `scripts/voice_design_smoke.py`.
- README quickstart, roadmap, and TODO sections.

### Changed
- Dependency set updated for Qwen TTS support with `qwen-tts` and `soundfile`.
- `transformers` pinned to `4.57.3` to satisfy `qwen-tts` requirements.

### Notes
- End-to-end synthesis validated via `curl` and a separate Swift CLI client.

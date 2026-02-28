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
- Mode-aware model inventory endpoint `GET /model/inventory`.
- Custom voice speaker discovery endpoint `GET /custom-voice/speakers`.
- Mode-specific synthesis endpoints:
  - `POST /synthesize/voice-design`
  - `POST /synthesize/custom-voice`
  - `POST /synthesize/voice-clone`
- OpenAPI parity test gate at `tests/test_openapi_parity.py`.
- Model-backed pytest runner script: `scripts/run_model_tests.sh`.

### Changed
- OpenAPI version aligned to `v0.5.0` target spec.
- `GET /model/status` and `GET /adapters/{adapter_id}/status` now expose mode-aware fields (`mode`, `requested_mode`, `requested_model_id`, `strict_load`, `fallback_applied`).
- `POST /model/load` now requires a mode-aware request body (`ModelLoadRequest`) and supports strict/fallback model selection behavior.
- `scripts/export_openapi.py` now writes generated spec to `openapi/openapi.generated.yaml` to protect target `openapi/openapi.yaml`.
- FastAPI OpenAPI output now uses committed target spec contract.
- `main.py` now uses env-configurable host/port/reload and defaults to `reload=false`.
- README now includes a quick demo flow and portable launchd install instructions.
- GitHub Actions CI now uses uv setup guidance with cache and adds a separate `smoke-e2e` job (main push/nightly/manual) for model-backed synthesis checks.

### Removed
- Legacy synthesis endpoints:
  - `POST /synthesize`
  - `POST /synthesize/stream`

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

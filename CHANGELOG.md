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

### Changed
- `GET /model/status` now reports idle/last-use metadata.
- `main.py` now uses env-configurable host/port/reload and defaults to `reload=false`.
- README now includes a quick demo flow and portable launchd install instructions.

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

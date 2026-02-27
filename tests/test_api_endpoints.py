from __future__ import annotations

from fastapi.testclient import TestClient

import app.api as api_module
import app.model_runtime as model_runtime


def _runtime_status(**overrides) -> model_runtime.RuntimeStatus:
    payload = {
        "mode": "voice_design",
        "model_id": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        "requested_mode": None,
        "requested_model_id": None,
        "loaded": True,
        "loading": False,
        "qwen_tts_available": True,
        "ready": True,
        "strict_load": False,
        "fallback_applied": False,
        "load_error": None,
    }
    payload.update(overrides)
    return model_runtime.RuntimeStatus(**payload)


def test_system_endpoints_smoke(monkeypatch):
    monkeypatch.setattr(api_module, "get_runtime_status", lambda: _runtime_status())

    client = TestClient(api_module.app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    version = client.get("/version")
    assert version.status_code == 200
    payload = version.json()
    assert payload["service"] == "talktomepy"
    assert payload["api_version"] == api_module.app.version

    adapters = client.get("/adapters")
    assert adapters.status_code == 200
    data = adapters.json()
    assert data["adapters"]
    assert data["adapters"][0]["id"] == "qwen3-tts"


def test_model_inventory_endpoint_returns_models(monkeypatch):
    monkeypatch.setattr(
        api_module,
        "get_model_inventory",
        lambda: [
            {
                "mode": "voice_design",
                "model_id": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
                "available": True,
                "local_path": "/tmp/model",
            }
        ],
    )

    client = TestClient(api_module.app)
    response = client.get("/model/inventory")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["models"]) == 1
    assert payload["models"][0]["available"] is True


def test_model_load_returns_202_and_status_payload(monkeypatch):
    monkeypatch.setattr(api_module, "start_model_loading", lambda **_: True)
    monkeypatch.setattr(
        api_module,
        "get_runtime_status",
        lambda: _runtime_status(
            loading=True,
            loaded=False,
            requested_mode="custom_voice",
            requested_model_id="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            mode="custom_voice",
            model_id="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            fallback_applied=True,
        ),
    )

    client = TestClient(api_module.app)
    response = client.post("/model/load", json={"mode": "custom_voice", "strict_load": False})

    assert response.status_code == 202
    payload = response.json()
    assert payload["mode"] == "custom_voice"
    assert payload["fallback_applied"] is True


def test_model_load_strict_mismatch_returns_400(monkeypatch):
    def _raise(**_: object):
        raise model_runtime.InvalidRequestError("incompatible")

    monkeypatch.setattr(api_module, "start_model_loading", _raise)

    client = TestClient(api_module.app)
    response = client.post(
        "/model/load",
        json={
            "mode": "voice_clone",
            "model_id": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
            "strict_load": True,
        },
    )

    assert response.status_code == 400


def test_custom_voice_speakers_endpoint_success(monkeypatch):
    monkeypatch.setattr(
        api_module,
        "get_supported_speakers",
        lambda model_id=None: (model_id or "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", ["ryan", "olivia"]),
    )

    client = TestClient(api_module.app)
    response = client.get("/custom-voice/speakers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["speakers"] == ["ryan", "olivia"]


def test_custom_voice_speakers_invalid_custom_model_returns_400(monkeypatch):
    def _raise(model_id=None):
        raise model_runtime.InvalidRequestError(f"bad model: {model_id}")

    monkeypatch.setattr(api_module, "get_supported_speakers", _raise)

    client = TestClient(api_module.app)
    response = client.get("/custom-voice/speakers", params={"model_id": "Qwen/Qwen3-TTS-12Hz-1.7B-Base"})

    assert response.status_code == 400


def test_synthesize_voice_design_returns_wav(monkeypatch):
    monkeypatch.setattr(
        api_module,
        "runtime_synthesize_voice_design",
        lambda **_: ([[0.0, 0.1, -0.1, 0.0]], 24000),
    )

    client = TestClient(api_module.app)
    response = client.post(
        "/synthesize/voice-design",
        json={
            "text": "Hello endpoint test",
            "instruct": "Warm and clear narrator voice.",
            "language": "English",
            "format": "wav",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content[:4] == b"RIFF"


def test_synthesize_custom_voice_returns_wav(monkeypatch):
    monkeypatch.setattr(
        api_module,
        "runtime_synthesize_custom_voice",
        lambda **_: ([[0.0, 0.1, -0.1, 0.0]], 24000),
    )

    client = TestClient(api_module.app)
    response = client.post(
        "/synthesize/custom-voice",
        json={
            "text": "Hello custom voice",
            "speaker": "ryan",
            "language": "English",
            "format": "wav",
        },
    )

    assert response.status_code == 200
    assert response.content[:4] == b"RIFF"


def test_synthesize_voice_clone_accepts_raw_and_data_url(monkeypatch):
    monkeypatch.setattr(
        api_module,
        "runtime_synthesize_voice_clone",
        lambda **_: ([[0.0, 0.1, -0.1, 0.0]], 24000),
    )

    client = TestClient(api_module.app)
    raw_response = client.post(
        "/synthesize/voice-clone",
        json={
            "text": "Clone me",
            "reference_audio_b64": "UklGRg==",
            "language": "English",
            "format": "wav",
        },
    )
    data_url_response = client.post(
        "/synthesize/voice-clone",
        json={
            "text": "Clone me",
            "reference_audio_b64": "data:audio/wav;base64,UklGRg==",
            "language": "English",
            "format": "wav",
        },
    )

    assert raw_response.status_code == 200
    assert data_url_response.status_code == 200


def test_synthesize_voice_clone_invalid_reference_returns_400(monkeypatch):
    def _raise(**_: object):
        raise model_runtime.InvalidRequestError("Invalid reference_audio_b64 payload.")

    monkeypatch.setattr(api_module, "runtime_synthesize_voice_clone", _raise)

    client = TestClient(api_module.app)
    response = client.post(
        "/synthesize/voice-clone",
        json={
            "text": "Clone me",
            "reference_audio_b64": "not-base64",
            "language": "English",
            "format": "wav",
        },
    )

    assert response.status_code == 400


def test_synthesize_custom_voice_loading_returns_503(monkeypatch):
    def _raise(**_: object):
        raise model_runtime.ModelLoadingError("loading")

    monkeypatch.setattr(api_module, "runtime_synthesize_custom_voice", _raise)

    client = TestClient(api_module.app)
    response = client.post(
        "/synthesize/custom-voice",
        json={
            "text": "Hello custom voice",
            "speaker": "ryan",
            "language": "English",
            "format": "wav",
        },
    )

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"


def test_synthesize_voice_design_unsupported_format_returns_400():
    client = TestClient(api_module.app)
    response = client.post(
        "/synthesize/voice-design",
        json={
            "text": "Hello endpoint test",
            "instruct": "Warm and clear narrator voice.",
            "language": "English",
            "format": "mp3",
        },
    )

    assert response.status_code == 400


def test_legacy_synthesize_routes_are_removed():
    client = TestClient(api_module.app)
    legacy = client.post("/synthesize", json={})
    legacy_stream = client.post("/synthesize/stream", json={})

    assert legacy.status_code == 404
    assert legacy_stream.status_code == 404

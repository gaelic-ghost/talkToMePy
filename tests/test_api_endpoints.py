from __future__ import annotations

from fastapi.testclient import TestClient

import app.api as api_module


def test_system_endpoints_smoke():
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


def test_synthesize_endpoint_returns_wav(monkeypatch):
    def fake_synthesize_voice_design(*, text: str, instruct: str, language: str):
        return [[0.0, 0.1, -0.1, 0.0]], 24000

    monkeypatch.setattr(api_module, "synthesize_voice_design", fake_synthesize_voice_design)

    client = TestClient(api_module.app)
    response = client.post(
        "/synthesize",
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


def test_synthesize_stream_endpoint_returns_wav(monkeypatch):
    def fake_synthesize_voice_design(*, text: str, instruct: str, language: str):
        return [[0.0, 0.1, -0.1, 0.0]], 24000

    monkeypatch.setattr(api_module, "synthesize_voice_design", fake_synthesize_voice_design)

    client = TestClient(api_module.app)
    response = client.post(
        "/synthesize/stream",
        json={
            "text": "Hello stream endpoint test",
            "instruct": "Warm and clear narrator voice.",
            "language": "English",
            "format": "wav",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content[:4] == b"RIFF"

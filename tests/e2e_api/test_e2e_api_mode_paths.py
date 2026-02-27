from __future__ import annotations

import base64

import pytest

from tests.model_backed_common import (
    assert_wav_response,
    ensure_healthy,
    load_mode_and_wait,
    parse_e2e_base_urls,
    request_binary,
    request_json,
    unload_and_assert_e2e,
)


pytestmark = [pytest.mark.e2e_api, pytest.mark.model_backed]


@pytest.fixture(params=parse_e2e_base_urls())
def base_url(request) -> str:
    return str(request.param)


@pytest.fixture(autouse=True)
def cleanup_e2e_runtime_state(base_url: str):
    yield
    try:
        unload_and_assert_e2e(base_url)
    except Exception:
        # Best-effort safety cleanup for subsequent tests.
        pass


def test_e2e_api_voice_design_path_generates_wav_and_unloads(base_url: str):
    ensure_healthy(base_url)
    load_mode_and_wait(base_url, mode="voice_design")

    status, headers, body = request_binary(
        "POST",
        f"{base_url}/synthesize/voice-design",
        payload={
            "text": "Hello from e2e voice design test.",
            "instruct": "Warm and clear narrator voice.",
            "language": "English",
            "format": "wav",
        },
        timeout=240.0,
    )
    assert_wav_response(status, headers, body, endpoint="/synthesize/voice-design")

    unload_and_assert_e2e(base_url)


def test_e2e_api_custom_voice_path_generates_wav_and_unloads(base_url: str):
    ensure_healthy(base_url)
    load_mode_and_wait(base_url, mode="custom_voice")

    status, _, payload = request_json(
        "GET",
        f"{base_url}/custom-voice/speakers",
        timeout=60.0,
    )
    assert status == 200
    assert isinstance(payload, dict)
    speakers = payload.get("speakers") or []
    selected_speaker = speakers[0] if speakers else "ryan"

    status, headers, body = request_binary(
        "POST",
        f"{base_url}/synthesize/custom-voice",
        payload={
            "text": "Hello from e2e custom voice test.",
            "speaker": selected_speaker,
            "language": "English",
            "format": "wav",
        },
        timeout=240.0,
    )
    assert_wav_response(status, headers, body, endpoint="/synthesize/custom-voice")

    unload_and_assert_e2e(base_url)


def test_e2e_api_voice_clone_path_generates_wav_and_unloads(base_url: str):
    ensure_healthy(base_url)
    load_mode_and_wait(base_url, mode="voice_design")

    status, headers, ref_wav = request_binary(
        "POST",
        f"{base_url}/synthesize/voice-design",
        payload={
            "text": "Reference audio for e2e voice clone test.",
            "instruct": "Warm and clear narrator voice.",
            "language": "English",
            "format": "wav",
        },
        timeout=240.0,
    )
    assert_wav_response(status, headers, ref_wav, endpoint="/synthesize/voice-design")
    ref_b64 = base64.b64encode(ref_wav).decode("ascii")

    load_mode_and_wait(base_url, mode="voice_clone")

    status, headers, body = request_binary(
        "POST",
        f"{base_url}/synthesize/voice-clone",
        payload={
            "text": "Hello from e2e voice clone test.",
            "reference_audio_b64": ref_b64,
            "language": "English",
            "format": "wav",
        },
        timeout=240.0,
    )
    assert_wav_response(status, headers, body, endpoint="/synthesize/voice-clone")

    unload_and_assert_e2e(base_url)

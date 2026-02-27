from __future__ import annotations

import app.model_runtime as model_runtime
import pytest

from tests.model_backed_common import wav_to_base64


pytestmark = [pytest.mark.direct_model, pytest.mark.model_backed]


def _assert_direct_runtime_unloaded() -> None:
    status = model_runtime.unload_model()
    assert status.loaded is False
    assert status.loading is False
    assert model_runtime._MODEL is None


@pytest.fixture(autouse=True)
def cleanup_direct_runtime_state():
    yield
    try:
        _assert_direct_runtime_unloaded()
    except Exception:
        # Best-effort safety cleanup for subsequent tests.
        pass


def test_direct_model_voice_design_path_generates_wav_and_unloads():
    wavs, sample_rate = model_runtime.synthesize_voice_design(
        text="Hello from direct model voice design test.",
        instruct="Warm and clear narrator voice.",
        language="English",
    )

    assert sample_rate > 0
    assert wavs and len(wavs[0]) > 0

    _assert_direct_runtime_unloaded()


def test_direct_model_custom_voice_path_generates_wav_and_unloads():
    _, speakers = model_runtime.get_supported_speakers()
    selected_speaker = speakers[0] if speakers else "ryan"

    wavs, sample_rate = model_runtime.synthesize_custom_voice(
        text="Hello from direct model custom voice test.",
        speaker=selected_speaker,
        language="English",
    )

    assert sample_rate > 0
    assert wavs and len(wavs[0]) > 0

    _assert_direct_runtime_unloaded()


def test_direct_model_voice_clone_path_generates_wav_and_unloads():
    ref_wavs, ref_sample_rate = model_runtime.synthesize_voice_design(
        text="Reference audio for direct model voice clone test.",
        instruct="Warm and clear narrator voice.",
        language="English",
    )
    reference_audio_b64 = wav_to_base64(ref_wavs[0], ref_sample_rate)

    wavs, sample_rate = model_runtime.synthesize_voice_clone(
        text="Hello from direct model voice clone test.",
        reference_audio_b64=reference_audio_b64,
        language="English",
    )

    assert sample_rate > 0
    assert wavs and len(wavs[0]) > 0

    _assert_direct_runtime_unloaded()

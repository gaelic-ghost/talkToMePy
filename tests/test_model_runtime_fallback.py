from __future__ import annotations

import app.model_runtime as model_runtime
import pytest


@pytest.fixture(autouse=True)
def restore_runtime_state():
    with model_runtime._STATE_LOCK:
        original_model = model_runtime._MODEL
        original_last_used = model_runtime._LAST_USED_AT
        original_loading = model_runtime._LOADING
        original_load_error = model_runtime._LOAD_ERROR
        original_cpu_fallback = model_runtime._CPU_FALLBACK_ACTIVE

    yield

    with model_runtime._STATE_LOCK:
        model_runtime._MODEL = original_model
        model_runtime._LAST_USED_AT = original_last_used
        model_runtime._LOADING = original_loading
        model_runtime._LOAD_ERROR = original_load_error
        model_runtime._CPU_FALLBACK_ACTIVE = original_cpu_fallback


def test_synthesize_meta_tensor_error_retries_with_cpu_fallback(monkeypatch: pytest.MonkeyPatch):
    class MetaTensorModel:
        def generate_voice_design(self, *, text: str, instruct: str, language: str):
            raise RuntimeError("Tensor.item() cannot be called on meta tensors")

    class CpuFallbackModel:
        def generate_voice_design(self, *, text: str, instruct: str, language: str):
            return [[0.0, 0.1, -0.1, 0.0]], 24000

    load_call_count = {"count": 0}

    def fake_load_model():
        load_call_count["count"] += 1
        return CpuFallbackModel()

    with model_runtime._STATE_LOCK:
        model_runtime._MODEL = MetaTensorModel()
        model_runtime._LOADING = False
        model_runtime._LOAD_ERROR = None
        model_runtime._CPU_FALLBACK_ACTIVE = False

    monkeypatch.setenv("QWEN_TTS_DEVICE_MAP", "auto")
    monkeypatch.delenv("QWEN_TTS_TORCH_DTYPE", raising=False)
    monkeypatch.setattr(model_runtime, "_load_model", fake_load_model)

    wavs, sample_rate = model_runtime.synthesize_voice_design(
        text="Hello fallback",
        instruct="Warm and clear narrator voice.",
        language="English",
    )

    assert sample_rate == 24000
    assert wavs and len(wavs[0]) == 4
    assert model_runtime._CPU_FALLBACK_ACTIVE is True
    assert load_call_count["count"] == 1


def test_synthesize_meta_tensor_error_does_not_fallback_for_explicit_device_map(
    monkeypatch: pytest.MonkeyPatch,
):
    class MetaTensorModel:
        def generate_voice_design(self, *, text: str, instruct: str, language: str):
            raise RuntimeError("Tensor.item() cannot be called on meta tensors")

    with model_runtime._STATE_LOCK:
        model_runtime._MODEL = MetaTensorModel()
        model_runtime._LOADING = False
        model_runtime._LOAD_ERROR = None
        model_runtime._CPU_FALLBACK_ACTIVE = False

    monkeypatch.setenv("QWEN_TTS_DEVICE_MAP", "mps")

    with pytest.raises(
        model_runtime.SynthesisError,
        match="CPU fallback is only supported when QWEN_TTS_DEVICE_MAP is unset or set to `auto`.",
    ):
        model_runtime.synthesize_voice_design(
            text="Hello no fallback",
            instruct="Warm and clear narrator voice.",
            language="English",
        )

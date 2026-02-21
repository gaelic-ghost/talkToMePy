from __future__ import annotations

import gc
import importlib
import os
import shutil
import time
from dataclasses import dataclass
from typing import Any


DEFAULT_MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
MODEL_ID = os.getenv("QWEN_TTS_MODEL_ID", DEFAULT_MODEL_ID)

_MODEL: Any | None = None
_LAST_USED_AT: float | None = None


class ModelRuntimeError(Exception):
    """Base error for model runtime operations."""


class RuntimeDependencyError(ModelRuntimeError):
    """Raised when runtime dependencies are missing."""


class ModelLoadError(ModelRuntimeError):
    """Raised when model loading fails."""


class SynthesisError(ModelRuntimeError):
    """Raised when synthesis fails."""


@dataclass(frozen=True)
class RuntimeStatus:
    model_id: str
    loaded: bool
    sox_available: bool
    qwen_tts_available: bool
    seconds_since_last_use: float | None

    @property
    def ready(self) -> bool:
        return self.sox_available and self.qwen_tts_available

    @property
    def detail(self) -> str:
        if self.loaded:
            return "Model is loaded and ready."
        if not self.sox_available:
            return "Missing `sox` on PATH."
        if not self.qwen_tts_available:
            return "Python package `qwen_tts` is not importable."
        return "Runtime dependencies are ready; model is not loaded yet."


def get_runtime_status() -> RuntimeStatus:
    sox_available = shutil.which("sox") is not None
    qwen_tts_available = importlib.util.find_spec("qwen_tts") is not None

    seconds_since_last_use: float | None = None
    if _MODEL is not None and _LAST_USED_AT is not None:
        seconds_since_last_use = max(0.0, time.monotonic() - _LAST_USED_AT)

    return RuntimeStatus(
        model_id=MODEL_ID,
        loaded=_MODEL is not None,
        sox_available=sox_available,
        qwen_tts_available=qwen_tts_available,
        seconds_since_last_use=seconds_since_last_use,
    )


def _resolve_torch_dtype():
    dtype_name = os.getenv("QWEN_TTS_TORCH_DTYPE", "").strip().lower()
    if not dtype_name:
        return None

    import torch

    if dtype_name == "float16":
        return torch.float16
    if dtype_name == "bfloat16":
        return torch.bfloat16
    if dtype_name == "float32":
        return torch.float32
    raise ModelLoadError(
        "Invalid QWEN_TTS_TORCH_DTYPE. Use one of: float16, bfloat16, float32."
    )


def ensure_model_loaded() -> RuntimeStatus:
    global _MODEL

    if _MODEL is not None:
        _touch_model_usage()
        return get_runtime_status()

    status = get_runtime_status()
    if not status.ready:
        raise RuntimeDependencyError(status.detail)

    device_map = os.getenv("QWEN_TTS_DEVICE_MAP", "auto").strip()
    load_kwargs: dict[str, Any] = {}
    if device_map:
        load_kwargs["device_map"] = device_map

    dtype = _resolve_torch_dtype()
    if dtype is not None:
        load_kwargs["torch_dtype"] = dtype

    try:
        qwen_tts = importlib.import_module("qwen_tts")
        model_cls = getattr(qwen_tts, "Qwen3TTSModel")
        _MODEL = model_cls.from_pretrained(MODEL_ID, **load_kwargs)
    except ModelLoadError:
        raise
    except Exception as exc:
        raise ModelLoadError(f"Failed to load model `{MODEL_ID}`: {exc}") from exc

    _touch_model_usage()
    return get_runtime_status()


def _touch_model_usage() -> None:
    global _LAST_USED_AT
    _LAST_USED_AT = time.monotonic()


def unload_model() -> RuntimeStatus:
    global _MODEL, _LAST_USED_AT
    _MODEL = None
    _LAST_USED_AT = None
    gc.collect()
    return get_runtime_status()


def maybe_unload_if_idle(idle_seconds: int) -> bool:
    if idle_seconds <= 0:
        return False
    if _MODEL is None or _LAST_USED_AT is None:
        return False
    if (time.monotonic() - _LAST_USED_AT) < idle_seconds:
        return False
    unload_model()
    return True


def synthesize_voice_design(
    *,
    text: str,
    instruct: str,
    language: str,
) -> tuple[list[Any], int]:
    global _MODEL

    ensure_model_loaded()
    if _MODEL is None:
        raise SynthesisError("Model is not loaded.")

    try:
        wavs, sample_rate = _MODEL.generate_voice_design(
            text=text,
            instruct=instruct,
            language=language,
        )
    except Exception as exc:
        raise SynthesisError(f"Synthesis failed: {exc}") from exc

    if not wavs:
        raise SynthesisError("Synthesis returned no audio output.")

    _touch_model_usage()
    return wavs, int(sample_rate)

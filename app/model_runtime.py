from __future__ import annotations

import gc
import importlib
import os
import shutil
import threading
import time
from dataclasses import dataclass
from typing import Any


DEFAULT_MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
MODEL_ID = os.getenv("QWEN_TTS_MODEL_ID", DEFAULT_MODEL_ID)

_MODEL: Any | None = None
_LAST_USED_AT: float | None = None
_LOADING = False
_LOAD_ERROR: str | None = None
_STATE_LOCK = threading.RLock()


class ModelRuntimeError(Exception):
    """Base error for model runtime operations."""


class RuntimeDependencyError(ModelRuntimeError):
    """Raised when runtime dependencies are missing."""


class ModelLoadError(ModelRuntimeError):
    """Raised when model loading fails."""


class ModelLoadingError(ModelLoadError):
    """Raised when model load is currently in progress."""


class SynthesisError(ModelRuntimeError):
    """Raised when synthesis fails."""


@dataclass(frozen=True)
class RuntimeStatus:
    model_id: str
    loaded: bool
    loading: bool
    sox_available: bool
    qwen_tts_available: bool
    load_error: str | None
    seconds_since_last_use: float | None

    @property
    def ready(self) -> bool:
        return self.sox_available and self.qwen_tts_available

    @property
    def detail(self) -> str:
        if self.loaded:
            return "Model is loaded and ready."
        if self.loading:
            return "Model is currently loading. Please wait."
        if self.load_error:
            return f"Last model load failed: {self.load_error}"
        if not self.sox_available:
            return "Missing `sox` on PATH."
        if not self.qwen_tts_available:
            return "Python package `qwen_tts` is not importable."
        return "Runtime dependencies are ready; model is not loaded yet."


def get_runtime_status() -> RuntimeStatus:
    sox_available = shutil.which("sox") is not None
    qwen_tts_available = importlib.util.find_spec("qwen_tts") is not None

    with _STATE_LOCK:
        model_loaded = _MODEL is not None
        loading = _LOADING
        load_error = _LOAD_ERROR
        last_used = _LAST_USED_AT

    seconds_since_last_use: float | None = None
    if model_loaded and last_used is not None:
        seconds_since_last_use = max(0.0, time.monotonic() - last_used)

    return RuntimeStatus(
        model_id=MODEL_ID,
        loaded=model_loaded,
        loading=loading,
        sox_available=sox_available,
        qwen_tts_available=qwen_tts_available,
        load_error=load_error,
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


def _build_load_kwargs() -> dict[str, Any]:
    device_map = os.getenv("QWEN_TTS_DEVICE_MAP", "auto").strip()
    load_kwargs: dict[str, Any] = {}
    if device_map:
        load_kwargs["device_map"] = device_map

    dtype = _resolve_torch_dtype()
    if dtype is not None:
        load_kwargs["torch_dtype"] = dtype

    return load_kwargs


def _load_model() -> Any:
    qwen_tts = importlib.import_module("qwen_tts")
    model_cls = getattr(qwen_tts, "Qwen3TTSModel")
    return model_cls.from_pretrained(MODEL_ID, **_build_load_kwargs())


def ensure_model_loaded() -> RuntimeStatus:
    global _MODEL

    status = get_runtime_status()
    if status.loaded:
        _touch_model_usage()
        return get_runtime_status()
    if status.loading:
        raise ModelLoadingError("Model is currently loading. Please wait and retry shortly.")
    if not status.ready:
        raise RuntimeDependencyError(status.detail)

    with _STATE_LOCK:
        if _MODEL is not None:
            _touch_model_usage()
            return get_runtime_status()
        if _LOADING:
            raise ModelLoadingError("Model is currently loading. Please wait and retry shortly.")
        _set_loading(True)
        _set_load_error(None)

    try:
        model = _load_model()
    except Exception as exc:
        message = f"Failed to load model `{MODEL_ID}`: {exc}"
        with _STATE_LOCK:
            _set_loading(False)
            _set_load_error(message)
        raise ModelLoadError(message) from exc

    with _STATE_LOCK:
        _MODEL = model
        _set_loading(False)
        _set_load_error(None)
        _touch_model_usage()

    return get_runtime_status()


def _touch_model_usage() -> None:
    global _LAST_USED_AT
    _LAST_USED_AT = time.monotonic()


def _set_loading(value: bool) -> None:
    global _LOADING
    _LOADING = value


def _set_load_error(value: str | None) -> None:
    global _LOAD_ERROR
    _LOAD_ERROR = value


def _background_load_worker() -> None:
    global _MODEL

    try:
        model = _load_model()
    except Exception as exc:
        message = f"Failed to load model `{MODEL_ID}`: {exc}"
        with _STATE_LOCK:
            _set_loading(False)
            _set_load_error(message)
        return

    with _STATE_LOCK:
        _MODEL = model
        _set_loading(False)
        _set_load_error(None)
        _touch_model_usage()


def start_model_loading() -> bool:
    status = get_runtime_status()
    if status.loaded:
        return False
    if status.loading:
        return False
    if not status.ready:
        raise RuntimeDependencyError(status.detail)

    with _STATE_LOCK:
        if _MODEL is not None or _LOADING:
            return False
        _set_loading(True)
        _set_load_error(None)

    thread = threading.Thread(target=_background_load_worker, daemon=True)
    thread.start()
    return True


def unload_model() -> RuntimeStatus:
    global _MODEL, _LAST_USED_AT

    with _STATE_LOCK:
        _MODEL = None
        _LAST_USED_AT = None
        _set_load_error(None)
    gc.collect()
    return get_runtime_status()


def maybe_unload_if_idle(idle_seconds: int) -> bool:
    if idle_seconds <= 0:
        return False
    with _STATE_LOCK:
        if _LOADING:
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
    status = get_runtime_status()
    if status.loading and not status.loaded:
        raise ModelLoadingError("Model is currently loading. Please wait and retry shortly.")

    ensure_model_loaded()
    with _STATE_LOCK:
        model = _MODEL
    if model is None:
        raise SynthesisError("Model is not loaded.")

    try:
        wavs, sample_rate = model.generate_voice_design(
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

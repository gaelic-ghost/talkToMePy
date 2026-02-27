from __future__ import annotations

import base64
from dataclasses import dataclass
import gc
import importlib
import importlib.util
from io import BytesIO
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Any, Literal

import soundfile as sf


ModelMode = Literal["voice_design", "custom_voice", "voice_clone"]

MODEL_IDS: tuple[str, ...] = (
    "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
    "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
)

MODEL_MODE_BY_ID: dict[str, ModelMode] = {
    "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign": "voice_design",
    "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice": "custom_voice",
    "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice": "custom_voice",
    "Qwen/Qwen3-TTS-12Hz-0.6B-Base": "voice_clone",
    "Qwen/Qwen3-TTS-12Hz-1.7B-Base": "voice_clone",
}

MODE_DEFAULT_MODEL_ID: dict[ModelMode, str] = {
    "voice_design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "custom_voice": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    "voice_clone": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
}


def _initial_model_id() -> str:
    env_model_id = os.getenv("QWEN_TTS_MODEL_ID", "").strip()
    if env_model_id in MODEL_MODE_BY_ID:
        return env_model_id
    return MODE_DEFAULT_MODEL_ID["voice_design"]


_INITIAL_MODEL_ID = _initial_model_id()
_INITIAL_MODE = MODEL_MODE_BY_ID[_INITIAL_MODEL_ID]

_MODEL: Any | None = None
_ACTIVE_MODE: ModelMode = _INITIAL_MODE
_ACTIVE_MODEL_ID: str = _INITIAL_MODEL_ID
_REQUESTED_MODE: ModelMode | None = None
_REQUESTED_MODEL_ID: str | None = None
_STRICT_LOAD: bool = False
_FALLBACK_APPLIED: bool = False
_LAST_USED_AT: float | None = None
_LOADING: bool = False
_LOAD_ERROR: str | None = None
_CPU_FALLBACK_ACTIVE: bool = False
_STATE_LOCK = threading.RLock()


class ModelRuntimeError(Exception):
    """Base error for model runtime operations."""


class RuntimeDependencyError(ModelRuntimeError):
    """Raised when runtime dependencies are missing."""


class InvalidRequestError(ModelRuntimeError):
    """Raised when a request payload is invalid for the runtime contract."""


class ModelLoadError(ModelRuntimeError):
    """Raised when model loading fails."""


class ModelLoadingError(ModelLoadError):
    """Raised when model load is currently in progress."""


class SynthesisError(ModelRuntimeError):
    """Raised when synthesis fails."""


@dataclass(frozen=True)
class RuntimeStatus:
    mode: ModelMode
    model_id: str
    requested_mode: ModelMode | None
    requested_model_id: str | None
    loaded: bool
    loading: bool
    qwen_tts_available: bool
    ready: bool
    strict_load: bool
    fallback_applied: bool
    load_error: str | None

    @property
    def detail(self) -> str:
        if self.loaded:
            return "Model is loaded and ready."
        if self.loading:
            return "Model is currently loading. Please wait."
        if self.load_error:
            return f"Last model load failed: {self.load_error}"
        if not self.ready:
            return "Runtime dependencies are unavailable."
        return "Runtime dependencies are ready; model is not loaded yet."


def _is_runtime_ready() -> tuple[bool, bool, bool]:
    sox_available = shutil.which("sox") is not None
    qwen_tts_available = importlib.util.find_spec("qwen_tts") is not None
    ready = sox_available and qwen_tts_available
    return ready, sox_available, qwen_tts_available


def get_runtime_status() -> RuntimeStatus:
    ready, _, qwen_tts_available = _is_runtime_ready()
    with _STATE_LOCK:
        return RuntimeStatus(
            mode=_ACTIVE_MODE,
            model_id=_ACTIVE_MODEL_ID,
            requested_mode=_REQUESTED_MODE,
            requested_model_id=_REQUESTED_MODEL_ID,
            loaded=_MODEL is not None,
            loading=_LOADING,
            qwen_tts_available=qwen_tts_available,
            ready=ready,
            strict_load=_STRICT_LOAD,
            fallback_applied=_FALLBACK_APPLIED,
            load_error=_LOAD_ERROR,
        )


def _resolve_torch_dtype() -> Any:
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
    dtype = _resolve_torch_dtype()
    if _CPU_FALLBACK_ACTIVE and (not device_map or device_map.lower() == "auto"):
        load_kwargs["device_map"] = "cpu"
        if dtype is None:
            import torch

            load_kwargs["torch_dtype"] = torch.float32
        else:
            load_kwargs["torch_dtype"] = dtype
        return load_kwargs

    if device_map:
        load_kwargs["device_map"] = device_map
    if dtype is not None:
        load_kwargs["torch_dtype"] = dtype

    return load_kwargs


def _load_model(model_id: str) -> Any:
    qwen_tts = importlib.import_module("qwen_tts")
    model_cls = getattr(qwen_tts, "Qwen3TTSModel")
    return model_cls.from_pretrained(model_id, **_build_load_kwargs())


def _touch_model_usage() -> None:
    global _LAST_USED_AT
    _LAST_USED_AT = time.monotonic()


def _set_loading(value: bool) -> None:
    global _LOADING
    _LOADING = value


def _set_load_error(value: str | None) -> None:
    global _LOAD_ERROR
    _LOAD_ERROR = value


def _set_cpu_fallback_active(value: bool) -> None:
    global _CPU_FALLBACK_ACTIVE
    _CPU_FALLBACK_ACTIVE = value


def _set_requested_state(
    *,
    mode: ModelMode,
    model_id: str,
    strict_load: bool,
    fallback_applied: bool,
) -> None:
    global _ACTIVE_MODE, _ACTIVE_MODEL_ID, _REQUESTED_MODE, _REQUESTED_MODEL_ID, _STRICT_LOAD, _FALLBACK_APPLIED
    _ACTIVE_MODE = mode
    _ACTIVE_MODEL_ID = model_id
    _REQUESTED_MODE = mode
    _REQUESTED_MODEL_ID = model_id
    _STRICT_LOAD = strict_load
    _FALLBACK_APPLIED = fallback_applied


def _resolve_mode_model(
    *,
    mode: ModelMode,
    model_id: str | None,
    strict_load: bool,
) -> tuple[str, bool]:
    if model_id is None:
        return MODE_DEFAULT_MODEL_ID[mode], False

    if model_id not in MODEL_MODE_BY_ID:
        raise InvalidRequestError(f"Unsupported model_id `{model_id}`.")

    model_mode = MODEL_MODE_BY_ID[model_id]
    if model_mode == mode:
        return model_id, False

    if strict_load:
        raise InvalidRequestError(
            f"Model `{model_id}` is incompatible with mode `{mode}` when strict_load=true."
        )

    return MODE_DEFAULT_MODEL_ID[mode], True


def _validate_mode(mode: str) -> ModelMode:
    if mode not in MODE_DEFAULT_MODEL_ID:
        raise InvalidRequestError(f"Unsupported mode `{mode}`.")
    return mode  # type: ignore[return-value]


def _require_runtime_ready() -> None:
    ready, sox_available, qwen_tts_available = _is_runtime_ready()
    if ready:
        return
    detail_parts: list[str] = []
    if not sox_available:
        detail_parts.append("Missing `sox` on PATH")
    if not qwen_tts_available:
        detail_parts.append("Python package `qwen_tts` is not importable")
    detail = "; ".join(detail_parts) if detail_parts else "runtime dependency unavailable"
    raise RuntimeDependencyError(detail)


def _background_load_worker(*, target_mode: ModelMode, target_model_id: str) -> None:
    global _MODEL

    try:
        model = _load_model(target_model_id)
    except Exception as exc:
        message = f"Failed to load model `{target_model_id}`: {exc}"
        with _STATE_LOCK:
            _set_loading(False)
            _set_load_error(message)
        return

    with _STATE_LOCK:
        _MODEL = model
        _ACTIVE_MODE = target_mode
        _ACTIVE_MODEL_ID = target_model_id
        _set_loading(False)
        _set_load_error(None)
        _touch_model_usage()


def start_model_loading(*, mode: str, model_id: str | None, strict_load: bool = False) -> bool:
    typed_mode = _validate_mode(mode)
    resolved_model_id, fallback_applied = _resolve_mode_model(
        mode=typed_mode,
        model_id=model_id,
        strict_load=strict_load,
    )
    _require_runtime_ready()

    with _STATE_LOCK:
        if _LOADING:
            return False

        already_loaded = (
            _MODEL is not None and _ACTIVE_MODE == typed_mode and _ACTIVE_MODEL_ID == resolved_model_id
        )
        _set_requested_state(
            mode=typed_mode,
            model_id=resolved_model_id,
            strict_load=strict_load,
            fallback_applied=fallback_applied,
        )
        _set_load_error(None)

        if already_loaded:
            _touch_model_usage()
            return False

        _MODEL = None
        _set_loading(True)

    thread = threading.Thread(
        target=_background_load_worker,
        kwargs={"target_mode": typed_mode, "target_model_id": resolved_model_id},
        daemon=True,
    )
    thread.start()
    return True


def ensure_model_loaded(*, mode: str, model_id: str | None = None, strict_load: bool = False) -> RuntimeStatus:
    global _MODEL, _ACTIVE_MODE, _ACTIVE_MODEL_ID

    typed_mode = _validate_mode(mode)
    resolved_model_id, fallback_applied = _resolve_mode_model(
        mode=typed_mode,
        model_id=model_id,
        strict_load=strict_load,
    )

    status = get_runtime_status()
    if status.loading and not status.loaded:
        raise ModelLoadingError("Model is currently loading. Please wait and retry shortly.")

    should_load = False
    with _STATE_LOCK:
        already_loaded = (
            _MODEL is not None and _ACTIVE_MODE == typed_mode and _ACTIVE_MODEL_ID == resolved_model_id
        )
        _set_requested_state(
            mode=typed_mode,
            model_id=resolved_model_id,
            strict_load=strict_load,
            fallback_applied=fallback_applied,
        )
        if already_loaded:
            _touch_model_usage()
            return get_runtime_status()
        if _LOADING:
            raise ModelLoadingError("Model is currently loading. Please wait and retry shortly.")
        should_load = True

    if should_load:
        _require_runtime_ready()
        with _STATE_LOCK:
            _MODEL = None
            _set_loading(True)
            _set_load_error(None)

    try:
        model = _load_model(resolved_model_id)
    except Exception as exc:
        message = f"Failed to load model `{resolved_model_id}`: {exc}"
        with _STATE_LOCK:
            _set_loading(False)
            _set_load_error(message)
        raise ModelLoadError(message) from exc

    with _STATE_LOCK:
        _MODEL = model
        _ACTIVE_MODE = typed_mode
        _ACTIVE_MODEL_ID = resolved_model_id
        _set_loading(False)
        _set_load_error(None)
        _touch_model_usage()

    return get_runtime_status()


def unload_model() -> RuntimeStatus:
    global _MODEL, _LAST_USED_AT

    with _STATE_LOCK:
        _MODEL = None
        _LAST_USED_AT = None
        _set_cpu_fallback_active(False)
        _set_load_error(None)
        _set_loading(False)
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


def _is_meta_tensor_runtime_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "meta tensor" in message and "tensor.item()" in message


def _reload_model_with_cpu_fallback() -> None:
    global _MODEL

    configured_device_map = os.getenv("QWEN_TTS_DEVICE_MAP", "auto").strip().lower()
    if configured_device_map and configured_device_map != "auto":
        raise ModelLoadError(
            "CPU fallback is only supported when QWEN_TTS_DEVICE_MAP is unset or set to `auto`."
        )

    with _STATE_LOCK:
        model_id = _ACTIVE_MODEL_ID
        mode = _ACTIVE_MODE
        strict_load = _STRICT_LOAD
        fallback_applied = _FALLBACK_APPLIED
        _MODEL = None
        _set_loading(True)
        _set_load_error(None)
        _set_cpu_fallback_active(True)

    gc.collect()
    try:
        model = _load_model(model_id)
    except Exception as exc:
        message = f"Failed to reload model `{model_id}` with CPU fallback after runtime error: {exc}"
        with _STATE_LOCK:
            _set_loading(False)
            _set_load_error(message)
        raise ModelLoadError(message) from exc

    with _STATE_LOCK:
        _MODEL = model
        _set_requested_state(
            mode=mode,
            model_id=model_id,
            strict_load=strict_load,
            fallback_applied=fallback_applied,
        )
        _set_loading(False)
        _set_load_error(None)
        _touch_model_usage()


def _generate_with_cpu_retry(generate_fn: Any) -> tuple[list[Any], int]:
    try:
        wavs, sample_rate = generate_fn()
    except Exception as exc:
        if _is_meta_tensor_runtime_error(exc):
            try:
                _reload_model_with_cpu_fallback()
                with _STATE_LOCK:
                    reloaded_model = _MODEL
                if reloaded_model is None:
                    raise SynthesisError("CPU fallback reload completed without a loaded model.")
                wavs, sample_rate = generate_fn(reloaded_model)
            except Exception as retry_exc:
                raise SynthesisError(
                    f"Synthesis failed after CPU fallback retry: {retry_exc}"
                ) from retry_exc
        else:
            raise SynthesisError(f"Synthesis failed: {exc}") from exc

    if not wavs:
        raise SynthesisError("Synthesis returned no audio output.")

    _touch_model_usage()
    return wavs, int(sample_rate)


def synthesize_voice_design(
    *,
    text: str,
    instruct: str,
    language: str,
    model_id: str | None = None,
) -> tuple[list[Any], int]:
    ensure_model_loaded(mode="voice_design", model_id=model_id, strict_load=False)
    with _STATE_LOCK:
        model = _MODEL
    if model is None:
        raise SynthesisError("Model is not loaded.")

    def _generate(reloaded_model: Any | None = None) -> tuple[list[Any], int]:
        active_model = reloaded_model or model
        return active_model.generate_voice_design(text=text, instruct=instruct, language=language)

    return _generate_with_cpu_retry(_generate)


def synthesize_custom_voice(
    *,
    text: str,
    speaker: str,
    language: str,
    instruct: str | None = None,
    model_id: str | None = None,
) -> tuple[list[Any], int]:
    ensure_model_loaded(mode="custom_voice", model_id=model_id, strict_load=False)
    with _STATE_LOCK:
        model = _MODEL
    if model is None:
        raise SynthesisError("Model is not loaded.")

    def _generate(reloaded_model: Any | None = None) -> tuple[list[Any], int]:
        active_model = reloaded_model or model
        return active_model.generate_custom_voice(
            text=text,
            speaker=speaker,
            language=language,
            instruct=instruct,
        )

    return _generate_with_cpu_retry(_generate)


def _decode_reference_audio(reference_audio_b64: str) -> tuple[Any, int]:
    value = reference_audio_b64.strip()
    if value.lower().startswith("data:") and "," in value:
        value = value.split(",", 1)[1]

    try:
        decoded = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise InvalidRequestError("Invalid reference_audio_b64 payload.") from exc

    if not decoded:
        raise InvalidRequestError("Invalid reference_audio_b64 payload.")

    try:
        waveform, sample_rate = sf.read(BytesIO(decoded), dtype="float32")
    except Exception as exc:
        raise InvalidRequestError("Invalid reference_audio_b64 payload.") from exc

    return waveform, int(sample_rate)


def synthesize_voice_clone(
    *,
    text: str,
    reference_audio_b64: str,
    language: str,
    model_id: str | None = None,
) -> tuple[list[Any], int]:
    ref_audio = _decode_reference_audio(reference_audio_b64)
    ensure_model_loaded(mode="voice_clone", model_id=model_id, strict_load=False)
    with _STATE_LOCK:
        model = _MODEL
    if model is None:
        raise SynthesisError("Model is not loaded.")

    def _generate(reloaded_model: Any | None = None) -> tuple[list[Any], int]:
        active_model = reloaded_model or model
        return active_model.generate_voice_clone(
            text=text,
            language=language,
            ref_audio=ref_audio,
            non_streaming_mode=True,
        )

    return _generate_with_cpu_retry(_generate)


def get_supported_speakers(*, model_id: str | None = None) -> tuple[str, list[str]]:
    selected_model_id = model_id or MODE_DEFAULT_MODEL_ID["custom_voice"]
    if selected_model_id not in MODEL_MODE_BY_ID:
        raise InvalidRequestError(f"Unsupported model_id `{selected_model_id}`.")
    if MODEL_MODE_BY_ID[selected_model_id] != "custom_voice":
        raise InvalidRequestError(f"model_id `{selected_model_id}` does not support custom_voice.")

    ensure_model_loaded(mode="custom_voice", model_id=selected_model_id, strict_load=False)

    with _STATE_LOCK:
        model = _MODEL
    if model is None:
        raise RuntimeDependencyError("Model is not loaded.")

    try:
        speakers = model.get_supported_speakers() or []
    except Exception as exc:
        raise SynthesisError(f"Failed to fetch supported speakers: {exc}") from exc

    return selected_model_id, [str(speaker) for speaker in speakers]


def _model_cache_path(model_id: str) -> Path:
    hf_home = Path(os.getenv("HF_HOME", str(Path.home() / ".cache" / "huggingface")))
    cache_root = hf_home / "hub"
    if "/" in model_id:
        org, name = model_id.split("/", 1)
        slug = f"models--{org}--{name}"
    else:
        slug = f"models--{model_id.replace('/', '--')}"
    return cache_root / slug


def get_model_inventory() -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for model_id in MODEL_IDS:
        cache_path = _model_cache_path(model_id)
        snapshots_dir = cache_path / "snapshots"
        available = snapshots_dir.exists() and any(snapshots_dir.iterdir())
        inventory.append(
            {
                "mode": MODEL_MODE_BY_ID[model_id],
                "model_id": model_id,
                "available": available,
                "local_path": str(cache_path),
            }
        )
    return inventory

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from io import BytesIO
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, status
from fastapi import Response
from fastapi.responses import JSONResponse
import soundfile as sf
import yaml

from app.model_runtime import (
    InvalidRequestError,
    ModelLoadError,
    ModelLoadingError,
    RuntimeDependencyError,
    SynthesisError,
    ensure_model_loaded,
    get_model_inventory,
    get_runtime_status,
    get_supported_speakers,
    maybe_unload_if_idle,
    start_model_loading,
    synthesize_custom_voice as runtime_synthesize_custom_voice,
    synthesize_voice_clone as runtime_synthesize_voice_clone,
    synthesize_voice_design as runtime_synthesize_voice_design,
    unload_model,
)
from app.schemas import (
    AdapterInfo,
    AdaptersResponse,
    AdapterStatusResponse,
    CustomVoiceSpeakersResponse,
    HealthResponse,
    ModelId,
    ModelInventoryEntry,
    ModelInventoryResponse,
    ModelLoadRequest,
    ModelStatusResponse,
    ModelMode,
    SynthesizeCustomVoiceRequest,
    SynthesizeVoiceCloneRequest,
    SynthesizeVoiceDesignRequest,
    VersionResponse,
)

_idle_unload_task: asyncio.Task[None] | None = None
_IDLE_UNLOAD_SECONDS = int(os.getenv("QWEN_TTS_IDLE_UNLOAD_SECONDS", "0"))
_WARM_LOAD_ON_START = os.getenv("QWEN_TTS_WARM_LOAD_ON_START", "false").strip().lower() == "true"
_ADAPTER_ID = "qwen3-tts"
_ADAPTER_NAME = "Qwen3 TTS VoiceDesign"


def _custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    target_path = Path(__file__).resolve().parents[1] / "openapi" / "openapi.yaml"
    with target_path.open("r", encoding="utf-8") as f:
        app.openapi_schema = yaml.safe_load(f)
    return app.openapi_schema


def _build_model_status_response() -> ModelStatusResponse:
    status_info = get_runtime_status()
    return ModelStatusResponse(
        mode=ModelMode(status_info.mode),
        model_id=ModelId(status_info.model_id),
        requested_mode=ModelMode(status_info.requested_mode) if status_info.requested_mode else None,
        requested_model_id=ModelId(status_info.requested_model_id)
        if status_info.requested_model_id
        else None,
        loaded=status_info.loaded,
        loading=status_info.loading,
        qwen_tts_available=status_info.qwen_tts_available,
        ready=status_info.ready,
        strict_load=status_info.strict_load,
        fallback_applied=status_info.fallback_applied,
        detail=status_info.detail,
    )


def _build_adapter_status_response() -> AdapterStatusResponse:
    status_info = get_runtime_status()
    return AdapterStatusResponse(
        adapter_id=_ADAPTER_ID,
        mode=ModelMode(status_info.mode),
        model_id=ModelId(status_info.model_id),
        requested_mode=ModelMode(status_info.requested_mode) if status_info.requested_mode else None,
        requested_model_id=ModelId(status_info.requested_model_id)
        if status_info.requested_model_id
        else None,
        loaded=status_info.loaded,
        loading=status_info.loading,
        qwen_tts_available=status_info.qwen_tts_available,
        ready=status_info.ready,
        strict_load=status_info.strict_load,
        fallback_applied=status_info.fallback_applied,
        detail=status_info.detail,
    )


def _validate_adapter_id(adapter_id: str) -> None:
    if adapter_id != _ADAPTER_ID:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Adapter `{adapter_id}` not found.",
        )


async def _idle_unload_worker() -> None:
    sleep_seconds = 5
    if _IDLE_UNLOAD_SECONDS > 0:
        sleep_seconds = max(5, min(60, _IDLE_UNLOAD_SECONDS // 2 or 5))
    while True:
        await asyncio.sleep(sleep_seconds)
        maybe_unload_if_idle(_IDLE_UNLOAD_SECONDS)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    global _idle_unload_task
    if _IDLE_UNLOAD_SECONDS > 0:
        _idle_unload_task = asyncio.create_task(_idle_unload_worker())
    if _WARM_LOAD_ON_START:
        try:
            start_model_loading(mode="voice_design", model_id=None, strict_load=False)
        except RuntimeDependencyError:
            pass
    try:
        yield
    finally:
        if _idle_unload_task is not None:
            _idle_unload_task.cancel()
            try:
                await _idle_unload_task
            except asyncio.CancelledError:
                pass
            _idle_unload_task = None


app = FastAPI(
    title="TalkToMePy Service",
    version="0.5.0",
    description="A local TTS service for Qwen3-TTS VoiceDesign and CustomVoice modes.",
    lifespan=_lifespan,
)
app.openapi = _custom_openapi


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/version", response_model=VersionResponse, tags=["system"])
def version() -> VersionResponse:
    return VersionResponse(
        service="talktomepy",
        api_version=app.version,
        openapi_version=app.openapi_version,
    )


@app.get("/adapters", response_model=AdaptersResponse, tags=["adapters"])
def adapters() -> AdaptersResponse:
    return AdaptersResponse(
        adapters=[
            AdapterInfo(
                id=_ADAPTER_ID,
                name=_ADAPTER_NAME,
                status_path=f"/adapters/{_ADAPTER_ID}/status",
            )
        ]
    )


@app.get(
    "/adapters/{adapter_id}/status",
    response_model=AdapterStatusResponse,
    tags=["adapters"],
)
def adapter_status(adapter_id: str) -> AdapterStatusResponse:
    _validate_adapter_id(adapter_id)
    return _build_adapter_status_response()


@app.get("/model/status", response_model=ModelStatusResponse, tags=["system"])
def model_status() -> ModelStatusResponse:
    return _build_model_status_response()


@app.get("/model/inventory", response_model=ModelInventoryResponse, tags=["system"])
def model_inventory() -> ModelInventoryResponse:
    rows = get_model_inventory()
    return ModelInventoryResponse(models=[ModelInventoryEntry(**row) for row in rows])


@app.post(
    "/model/load",
    response_model=ModelStatusResponse,
    tags=["system"],
    responses={
        202: {
            "description": "Model loading has started and is still in progress.",
            "model": ModelStatusResponse,
        },
        400: {"description": "Invalid mode/model selection."},
    },
)
def model_load(payload: ModelLoadRequest) -> ModelStatusResponse:
    try:
        start_model_loading(
            mode=payload.mode.value,
            model_id=payload.model_id.value if payload.model_id else None,
            strict_load=payload.strict_load,
        )
    except InvalidRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeDependencyError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ModelLoadError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    response_payload = _build_model_status_response()
    if response_payload.loading and not response_payload.loaded:
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=response_payload.model_dump())
    return response_payload


@app.post("/model/unload", response_model=ModelStatusResponse, tags=["system"])
def model_unload() -> ModelStatusResponse:
    unload_model()
    return _build_model_status_response()


@app.get(
    "/custom-voice/speakers",
    response_model=CustomVoiceSpeakersResponse,
    tags=["tts"],
    responses={
        400: {"description": "Invalid model_id for custom_voice."},
        503: {"description": "Model runtime unavailable."},
    },
)
def custom_voice_speakers(model_id: ModelId | None = Query(default=None)) -> CustomVoiceSpeakersResponse:
    try:
        selected_model_id, speakers = get_supported_speakers(
            model_id=model_id.value if model_id else None
        )
    except InvalidRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (RuntimeDependencyError, ModelLoadingError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except (ModelLoadError, SynthesisError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return CustomVoiceSpeakersResponse(model_id=ModelId(selected_model_id), speakers=speakers)


def _validate_wav_format(fmt: str) -> None:
    if fmt.lower() != "wav":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only `wav` output is supported right now.",
        )


def _wav_response(wavs: list[Any], sample_rate: int) -> Response:
    audio_buffer = BytesIO()
    sf.write(audio_buffer, wavs[0], sample_rate, format="WAV")
    return Response(
        content=audio_buffer.getvalue(),
        media_type="audio/wav",
        headers={"X-Sample-Rate": str(sample_rate)},
    )


@app.post(
    "/synthesize/voice-design",
    tags=["tts"],
    response_class=Response,
    responses={
        200: {
            "description": "Generated WAV audio bytes.",
            "content": {"audio/wav": {"schema": {"type": "string", "format": "binary"}}},
        },
        400: {"description": "Bad request (unsupported format)."},
        503: {"description": "Model is loading or runtime dependency unavailable."},
        500: {"description": "Model load/synthesis failure."},
    },
)
def synthesize_voice_design(payload: SynthesizeVoiceDesignRequest) -> Response:
    _validate_wav_format(payload.format)

    try:
        wavs, sample_rate = runtime_synthesize_voice_design(
            text=payload.text,
            instruct=payload.instruct,
            language=payload.language,
            model_id=payload.model_id.value if payload.model_id else None,
        )
    except InvalidRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeDependencyError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ModelLoadingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
            headers={"Retry-After": "5"},
        ) from exc
    except (ModelLoadError, SynthesisError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return _wav_response(wavs, sample_rate)


@app.post(
    "/synthesize/custom-voice",
    tags=["tts"],
    response_class=Response,
    responses={
        200: {
            "description": "Generated WAV audio bytes.",
            "content": {"audio/wav": {"schema": {"type": "string", "format": "binary"}}},
        },
        400: {"description": "Bad request (unsupported format)."},
        503: {"description": "Model is loading or runtime dependency unavailable."},
        500: {"description": "Model load/synthesis failure."},
    },
)
def synthesize_custom_voice(payload: SynthesizeCustomVoiceRequest) -> Response:
    _validate_wav_format(payload.format)

    try:
        wavs, sample_rate = runtime_synthesize_custom_voice(
            text=payload.text,
            speaker=payload.speaker,
            language=payload.language,
            instruct=payload.instruct,
            model_id=payload.model_id.value if payload.model_id else None,
        )
    except InvalidRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeDependencyError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ModelLoadingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
            headers={"Retry-After": "5"},
        ) from exc
    except (ModelLoadError, SynthesisError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return _wav_response(wavs, sample_rate)


@app.post(
    "/synthesize/voice-clone",
    tags=["tts"],
    response_class=Response,
    responses={
        200: {
            "description": "Generated WAV audio bytes.",
            "content": {"audio/wav": {"schema": {"type": "string", "format": "binary"}}},
        },
        400: {"description": "Bad request (unsupported format or invalid reference audio)."},
        503: {"description": "Model is loading or runtime dependency unavailable."},
        500: {"description": "Model load/synthesis failure."},
    },
)
def synthesize_voice_clone(payload: SynthesizeVoiceCloneRequest) -> Response:
    _validate_wav_format(payload.format)

    try:
        wavs, sample_rate = runtime_synthesize_voice_clone(
            text=payload.text,
            reference_audio_b64=payload.reference_audio_b64,
            language=payload.language,
            model_id=payload.model_id.value if payload.model_id else None,
        )
    except InvalidRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeDependencyError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ModelLoadingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
            headers={"Retry-After": "5"},
        ) from exc
    except (ModelLoadError, SynthesisError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return _wav_response(wavs, sample_rate)

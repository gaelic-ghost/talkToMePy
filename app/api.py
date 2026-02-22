import asyncio
from io import BytesIO
import os

from fastapi import FastAPI, HTTPException, status
from fastapi import Response
from fastapi.responses import JSONResponse, StreamingResponse
import soundfile as sf

from app.model_runtime import (
    ModelLoadError,
    ModelLoadingError,
    RuntimeDependencyError,
    SynthesisError,
    ensure_model_loaded,
    get_runtime_status,
    maybe_unload_if_idle,
    start_model_loading,
    synthesize_voice_design,
    unload_model,
)
from app.schemas import (
    AdapterInfo,
    AdaptersResponse,
    AdapterStatusResponse,
    HealthResponse,
    ModelStatusResponse,
    SynthesizeRequest,
    VersionResponse,
)

app = FastAPI(
    title="TalkToMePy Service",
    version="0.1.0",
    description="A local TTS service scaffold for future Qwen-3 integration.",
)
_idle_unload_task: asyncio.Task[None] | None = None
_IDLE_UNLOAD_SECONDS = int(os.getenv("QWEN_TTS_IDLE_UNLOAD_SECONDS", "0"))
_WARM_LOAD_ON_START = os.getenv("QWEN_TTS_WARM_LOAD_ON_START", "false").strip().lower() == "true"
_ADAPTER_ID = "qwen3-tts"
_ADAPTER_NAME = "Qwen3 TTS VoiceDesign"


def _build_model_status_response() -> ModelStatusResponse:
    status_info = get_runtime_status()
    return ModelStatusResponse(
        model_id=status_info.model_id,
        loaded=status_info.loaded,
        loading=status_info.loading,
        sox_available=status_info.sox_available,
        qwen_tts_available=status_info.qwen_tts_available,
        load_error=status_info.load_error,
        seconds_since_last_use=status_info.seconds_since_last_use,
        idle_unload_seconds=_IDLE_UNLOAD_SECONDS,
        auto_unload_enabled=_IDLE_UNLOAD_SECONDS > 0,
        ready=status_info.ready,
        detail=status_info.detail,
    )


def _build_adapter_status_response() -> AdapterStatusResponse:
    status_info = get_runtime_status()
    return AdapterStatusResponse(
        adapter_id=_ADAPTER_ID,
        model_id=status_info.model_id,
        loaded=status_info.loaded,
        loading=status_info.loading,
        sox_available=status_info.sox_available,
        qwen_tts_available=status_info.qwen_tts_available,
        load_error=status_info.load_error,
        seconds_since_last_use=status_info.seconds_since_last_use,
        idle_unload_seconds=_IDLE_UNLOAD_SECONDS,
        auto_unload_enabled=_IDLE_UNLOAD_SECONDS > 0,
        ready=status_info.ready,
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


@app.on_event("startup")
async def startup_event() -> None:
    global _idle_unload_task
    if _IDLE_UNLOAD_SECONDS > 0:
        _idle_unload_task = asyncio.create_task(_idle_unload_worker())
    if _WARM_LOAD_ON_START:
        try:
            start_model_loading()
        except RuntimeDependencyError:
            # Service remains up; clients can inspect /model/status for details.
            pass


@app.on_event("shutdown")
async def shutdown_event() -> None:
    global _idle_unload_task
    if _idle_unload_task is not None:
        _idle_unload_task.cancel()
        try:
            await _idle_unload_task
        except asyncio.CancelledError:
            pass
        _idle_unload_task = None


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


@app.post(
    "/model/load",
    response_model=ModelStatusResponse,
    tags=["system"],
    responses={
        202: {
            "description": "Model loading has started and is still in progress.",
            "model": ModelStatusResponse,
        }
    },
)
def model_load() -> ModelStatusResponse:
    try:
        status_info = get_runtime_status()
        if not status_info.loaded and not status_info.loading:
            start_model_loading()
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


@app.post(
    "/synthesize",
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
def synthesize(payload: SynthesizeRequest) -> Response:
    if payload.format.lower() != "wav":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only `wav` output is supported right now.",
        )

    try:
        status_info = get_runtime_status()
        if status_info.loading and not status_info.loaded:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Model is loading, please wait and retry shortly.",
                headers={"Retry-After": "5"},
            )

        wavs, sample_rate = synthesize_voice_design(
            text=payload.text,
            instruct=payload.instruct,
            language=payload.language,
        )
    except RuntimeDependencyError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ModelLoadingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
            headers={"Retry-After": "5"},
        ) from exc
    except ModelLoadError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except SynthesisError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    audio_buffer = BytesIO()
    sf.write(audio_buffer, wavs[0], sample_rate, format="WAV")

    return Response(
        content=audio_buffer.getvalue(),
        media_type="audio/wav",
        headers={"X-Sample-Rate": str(sample_rate)},
    )


@app.post(
    "/synthesize/stream",
    tags=["tts"],
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Generated WAV audio stream.",
            "content": {"audio/wav": {"schema": {"type": "string", "format": "binary"}}},
        },
        400: {"description": "Bad request (unsupported format)."},
        503: {"description": "Model is loading or runtime dependency unavailable."},
        500: {"description": "Model load/synthesis failure."},
    },
)
def synthesize_stream(payload: SynthesizeRequest) -> StreamingResponse:
    if payload.format.lower() != "wav":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only `wav` output is supported right now.",
        )

    try:
        status_info = get_runtime_status()
        if status_info.loading and not status_info.loaded:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Model is loading, please wait and retry shortly.",
                headers={"Retry-After": "5"},
            )

        wavs, sample_rate = synthesize_voice_design(
            text=payload.text,
            instruct=payload.instruct,
            language=payload.language,
        )
    except RuntimeDependencyError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ModelLoadingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
            headers={"Retry-After": "5"},
        ) from exc
    except ModelLoadError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except SynthesisError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    audio_buffer = BytesIO()
    sf.write(audio_buffer, wavs[0], sample_rate, format="WAV")
    wav_bytes = audio_buffer.getvalue()

    def _iter_audio_chunks(chunk_size: int = 16_384):
        for idx in range(0, len(wav_bytes), chunk_size):
            yield wav_bytes[idx : idx + chunk_size]

    return StreamingResponse(
        _iter_audio_chunks(),
        media_type="audio/wav",
        headers={"X-Sample-Rate": str(sample_rate)},
    )

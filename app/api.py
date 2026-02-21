import asyncio
from io import BytesIO
import os

from fastapi import FastAPI, HTTPException, status
from fastapi import Response
from fastapi.responses import JSONResponse
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
    HealthResponse,
    ModelStatusResponse,
    SynthesizeRequest,
)

app = FastAPI(
    title="TalkToMePy Service",
    version="0.1.0",
    description="A local TTS service scaffold for future Qwen-3 integration.",
)
_idle_unload_task: asyncio.Task[None] | None = None
_IDLE_UNLOAD_SECONDS = int(os.getenv("QWEN_TTS_IDLE_UNLOAD_SECONDS", "0"))
_WARM_LOAD_ON_START = os.getenv("QWEN_TTS_WARM_LOAD_ON_START", "false").strip().lower() == "true"


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


@app.get("/model/status", response_model=ModelStatusResponse, tags=["system"])
def model_status() -> ModelStatusResponse:
    return _build_model_status_response()


@app.post("/model/load", response_model=ModelStatusResponse, tags=["system"])
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

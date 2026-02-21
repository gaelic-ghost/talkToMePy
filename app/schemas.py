from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok")
    service: str = Field(default="talktomepy")


class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    instruct: str = Field(
        default="A warm and clear speaking voice with natural pacing."
    )
    language: str = Field(default="English")
    format: str = Field(default="wav")


class ModelStatusResponse(BaseModel):
    model_id: str
    loaded: bool
    loading: bool
    sox_available: bool
    qwen_tts_available: bool
    load_error: str | None
    seconds_since_last_use: float | None
    idle_unload_seconds: int
    auto_unload_enabled: bool
    ready: bool
    detail: str

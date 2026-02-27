from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ModelMode(str, Enum):
    voice_design = "voice_design"
    custom_voice = "custom_voice"
    voice_clone = "voice_clone"


class ModelId(str, Enum):
    qwen_1_7b_voice_design = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
    qwen_0_6b_custom_voice = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
    qwen_1_7b_custom_voice = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
    qwen_0_6b_base = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    qwen_1_7b_base = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"


class HealthResponse(BaseModel):
    status: str = Field(default="ok")
    service: str = Field(default="talktomepy")


class VersionResponse(BaseModel):
    service: str = Field(default="")
    api_version: str = Field(default="")
    openapi_version: str = Field(default="")


class AdapterInfo(BaseModel):
    id: str
    name: str
    status_path: str


class AdaptersResponse(BaseModel):
    adapters: list[AdapterInfo]


class ModelStatusResponse(BaseModel):
    mode: ModelMode
    model_id: ModelId
    requested_mode: ModelMode | None = None
    requested_model_id: ModelId | None = None
    loaded: bool
    loading: bool
    qwen_tts_available: bool
    ready: bool
    strict_load: bool
    fallback_applied: bool
    detail: str


class AdapterStatusResponse(BaseModel):
    adapter_id: str
    mode: ModelMode
    model_id: ModelId
    requested_mode: ModelMode | None = None
    requested_model_id: ModelId | None = None
    loaded: bool
    loading: bool
    qwen_tts_available: bool
    ready: bool
    strict_load: bool
    fallback_applied: bool
    detail: str


class ModelLoadRequest(BaseModel):
    mode: ModelMode
    model_id: ModelId | None = None
    strict_load: bool = Field(default=False)


class ModelInventoryEntry(BaseModel):
    mode: ModelMode
    model_id: ModelId
    available: bool
    local_path: str


class ModelInventoryResponse(BaseModel):
    models: list[ModelInventoryEntry]


class CustomVoiceSpeakersResponse(BaseModel):
    model_id: ModelId
    speakers: list[str]


class SynthesizeVoiceDesignRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    instruct: str = Field(
        default="A warm and clear speaking voice with natural pacing.",
        min_length=1,
    )
    language: str = Field(default="English", min_length=1)
    model_id: ModelId | None = None
    format: str = Field(default="wav")


class SynthesizeCustomVoiceRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    speaker: str = Field(default="ryan", min_length=1)
    instruct: str | None = None
    language: str = Field(default="English", min_length=1)
    model_id: ModelId | None = None
    format: str = Field(default="wav")


class SynthesizeVoiceCloneRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    reference_audio_b64: str = Field(
        min_length=1,
        description="Base64-encoded reference audio bytes used for cloning.",
    )
    language: str = Field(default="English", min_length=1)
    model_id: ModelId | None = None
    format: str = Field(default="wav")

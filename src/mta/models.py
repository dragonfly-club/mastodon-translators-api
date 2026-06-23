from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field


class DetectedLanguage(BaseModel):
    language: str
    confidence: float | None = None


class TranslateRequest(BaseModel):
    q: str | list[str]
    source: str
    target: str
    format: str = "text"
    api_key: str | None = None
    alternatives: int | None = None


class TranslateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    translated_text: str | list[str] = Field(alias="translatedText")
    detected_language: DetectedLanguage | list[DetectedLanguage] = Field(alias="detectedLanguage")


class LanguageResponse(BaseModel):
    code: str
    name: str
    targets: list[str]


class BackendHealth(TypedDict):
    name: str
    healthy: bool
    failures: int
    inflight: int
    supported_sources: int


class IndexResponse(TypedDict):
    name: str
    version: str
    backends: list[str]


class HealthResponse(BaseModel):
    status: str
    cache: dict[str, int]
    backends: list[BackendHealth]

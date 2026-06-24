from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol, cast

import uvicorn
from fastapi import FastAPI, HTTPException, Request

from mta.cache import LRUCache
from mta.models import (
    BackendHealth,
    DetectedLanguage,
    HealthResponse,
    IndexResponse,
    LanguageResponse,
    TranslateRequest,
    TranslateResponse,
)
from mta.router import BackendRouter, UnsupportedLanguagePairError, normalize_language
from mta.settings import Settings

type FormPayload = dict[str, str | int | list[str]]
type JsonPayload = dict[str, object]
type TranslateCache = LRUCache[tuple[str, str, str, str], tuple[str, DetectedLanguage, str]]


class RouterLike(Protocol):
    def health_snapshot(self) -> list[BackendHealth]: ...
    def supported_languages(self) -> list[LanguageResponse]: ...
    async def translate_one(
        self,
        text: str,
        source: str,
        target: str,
        format_: str,
    ) -> tuple[str, DetectedLanguage, str]: ...


def _normalize_q(raw_q: object) -> str | list[str]:
    if isinstance(raw_q, str):
        return raw_q
    if isinstance(raw_q, list) and all(isinstance(item, str) for item in raw_q):
        return raw_q
    raise HTTPException(status_code=400, detail="q must be a string or an array of strings")


def _coerce_form_payload(form_items: Mapping[str, str], q_values: list[str]) -> FormPayload:
    payload: FormPayload = dict(form_items)
    if q_values:
        payload["q"] = q_values if len(q_values) > 1 else q_values[0]
    if "alternatives" in payload:
        raw_alternatives = payload["alternatives"]
        if isinstance(raw_alternatives, str) and raw_alternatives.isdigit():
            payload["alternatives"] = int(raw_alternatives)
    return payload


async def _parse_translate_request(request: Request) -> TranslateRequest:
    content_type = request.headers.get("content-type", "")
    payload: JsonPayload | FormPayload
    if "application/json" in content_type:
        raw_payload = json.loads(await request.body())
        if not isinstance(raw_payload, dict):
            raise HTTPException(status_code=400, detail="invalid request payload")
        payload = cast(JsonPayload, raw_payload)
    else:
        form = await request.form()
        form_items = {key: value for key, value in form.multi_items() if isinstance(value, str)}
        q_values = [value for value in form.getlist("q") if isinstance(value, str)]
        payload = _coerce_form_payload(form_items, q_values)

    raw_q = payload.get("q")
    if isinstance(raw_q, str):
        stripped = raw_q.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                payload["q"] = json.loads(stripped)
            except json.JSONDecodeError:
                pass

    payload["q"] = _normalize_q(payload.get("q"))
    try:
        return TranslateRequest.model_validate(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid request payload") from exc


def _cache_key(q: str, source: str, target: str, format_: str) -> tuple[str, str, str, str]:
    return (q, source, target, format_)


def create_app(
    settings: Settings | None = None,
    router: RouterLike | None = None,
    cache: TranslateCache | None = None,
) -> FastAPI:
    app = FastAPI(title="Mastodon Translators API")
    app.state.settings = settings or Settings.from_env()
    app.state.router = router or BackendRouter(app.state.settings)
    app.state.cache = cache or LRUCache(maxsize=app.state.settings.cache_maxsize)

    @app.get("/")
    async def index() -> IndexResponse:
        router_state = cast(RouterLike, app.state.router)
        return {
            "name": "mastodon-translators-api",
            "backends": [backend["name"] for backend in router_state.health_snapshot()],
        }

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        router_state = cast(RouterLike, app.state.router)
        cache_state = cast(TranslateCache, app.state.cache)
        snapshot = router_state.health_snapshot()
        status = "ok" if any(backend["healthy"] for backend in snapshot) else "degraded"
        return HealthResponse(status=status, cache=cache_state.stats(), backends=snapshot)

    @app.get("/languages", response_model=list[LanguageResponse])
    async def languages() -> list[LanguageResponse]:
        router_state = cast(RouterLike, app.state.router)
        return router_state.supported_languages()

    @app.post("/translate", response_model=TranslateResponse)
    async def translate(request: Request) -> TranslateResponse:
        payload = await _parse_translate_request(request)
        settings_state = cast(Settings, app.state.settings)
        router_state = cast(RouterLike, app.state.router)
        cache_state = cast(TranslateCache, app.state.cache)

        if settings_state.api_key and payload.api_key != settings_state.api_key:
            raise HTTPException(status_code=403, detail="invalid api key")

        source = normalize_language(payload.source)
        target = normalize_language(payload.target)
        format_ = payload.format.lower()
        if format_ not in {"text", "html"}:
            raise HTTPException(status_code=400, detail="unsupported format")
        if source != "auto" and source == target:
            if isinstance(payload.q, list):
                detected_items = [
                    DetectedLanguage(language=source, confidence=100.0) for _ in payload.q
                ]
                return TranslateResponse.model_validate(
                    {
                        "translatedText": payload.q,
                        "detectedLanguage": [item.model_dump() for item in detected_items],
                        "translator": [None for _ in payload.q],
                    }
                )
            return TranslateResponse(
                translatedText=payload.q,
                detectedLanguage=DetectedLanguage(language=source, confidence=100.0),
                translator=None,
            )

        async def translate_item(item: str) -> tuple[str, DetectedLanguage, str]:
            key = _cache_key(item, source, target, format_)
            cached = cache_state.get(key)
            if cached is not None:
                return cached
            try:
                result = await router_state.translate_one(item, source, target, format_)
            except UnsupportedLanguagePairError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=502, detail="translation backend failure") from exc
            cache_state.set(key, result)
            return result

        if isinstance(payload.q, list):
            translated: list[str] = []
            detected_languages: list[DetectedLanguage] = []
            translators: list[str | None] = []
            for item in payload.q:
                translated_item, detected_item, translator_item = await translate_item(item)
                translated.append(translated_item)
                detected_languages.append(detected_item)
                translators.append(translator_item)
            return TranslateResponse.model_validate(
                {
                    "translatedText": translated,
                    "detectedLanguage": [item.model_dump() for item in detected_languages],
                    "translator": translators,
                }
            )

        translated_text, detected_language, translator_name = await translate_item(payload.q)
        return TranslateResponse(
            translatedText=translated_text,
            detectedLanguage=detected_language,
            translator=translator_name,
        )

    return app


app = create_app()


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run("mta.main:app", host=settings.host, port=settings.port)

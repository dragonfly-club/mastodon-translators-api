from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from mta.cache import LRUCache
from mta.main import create_app
from mta.models import BackendHealth, DetectedLanguage, LanguageResponse
from mta.settings import Settings


class FakeRouter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, str]] = []

    def supported_languages(self) -> list[LanguageResponse]:
        return [
            LanguageResponse(code="en", name="en", targets=["fr"]),
            LanguageResponse(code="fr", name="fr", targets=["en"]),
        ]

    def health_snapshot(self) -> list[BackendHealth]:
        return [
            {
                "name": "google",
                "healthy": True,
                "failures": 0,
                "inflight": 0,
                "supported_sources": 2,
            }
        ]

    async def translate_one(
        self,
        text: str,
        source: str,
        target: str,
        format_: str,
    ) -> tuple[str, DetectedLanguage]:
        self.calls.append((text, source, target, format_))
        return (f"{text}:{target}", DetectedLanguage(language="en", confidence=99.0))


def build_client() -> tuple[AsyncClient, FakeRouter]:
    settings = Settings(
        api_key="secret",
        cache_maxsize=16,
        host="127.0.0.1",
        port=5000,
        backend_attempts=3,
        backend_cooldown_seconds=30,
        backend_timeout_seconds=15,
        backend_allowlist=("google",),
    )
    router = FakeRouter()
    app = create_app(settings=settings, router=router, cache=LRUCache(maxsize=16))
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver"), router


@pytest.mark.anyio
async def test_translate_json_array() -> None:
    client, router = build_client()
    async with client:
        response = await client.post(
            "/translate",
            json={"q": ["hello", "world"], "source": "en", "target": "fr", "api_key": "secret"},
        )

    assert response.status_code == 200
    assert response.json()["translatedText"] == ["hello:fr", "world:fr"]
    assert len(router.calls) == 2


@pytest.mark.anyio
async def test_translate_form_and_cache() -> None:
    client, router = build_client()
    payload = {"q": "hello", "source": "en", "target": "fr", "api_key": "secret"}

    async with client:
        first = await client.post("/translate", data=payload)
        second = await client.post("/translate", data=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(router.calls) == 1


@pytest.mark.anyio
async def test_auth_required_when_configured() -> None:
    client, _ = build_client()
    async with client:
        response = await client.post(
            "/translate",
            json={"q": "hello", "source": "en", "target": "fr", "api_key": "wrong"},
        )

    assert response.status_code == 403


@pytest.mark.anyio
async def test_languages_endpoint() -> None:
    client, _ = build_client()
    async with client:
        response = await client.get("/languages")

    assert response.status_code == 200
    assert response.json()[0]["code"] == "en"

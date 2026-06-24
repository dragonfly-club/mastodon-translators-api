from __future__ import annotations

import pytest

from mta.router import BackendRouter
from mta.settings import Settings


def settings_with_openai(
    *,
    api_key: str | None,
    allowlist: tuple[str, ...] = ("openai",),
    languages: tuple[str, ...] = ("en", "fr"),
) -> Settings:
    return Settings(
        api_key=None,
        cache_maxsize=16,
        host="127.0.0.1",
        port=5000,
        backend_attempts=3,
        backend_cooldown_seconds=30,
        backend_timeout_seconds=15,
        backend_allowlist=allowlist,
        openai_api_key=api_key,
        openai_base_url="https://api.openai.com/v1",
        openai_model="gpt-4o-mini",
        openai_temperature=0.0,
        openai_languages=languages,
        openai_max_output_tokens=2048,
    )


@pytest.mark.anyio
async def test_load_openai_skipped_without_api_key() -> None:
    router = BackendRouter(settings_with_openai(api_key=None))

    assert [b.name for b in router.backends] == []
    assert "openai" not in router._custom_backends


@pytest.mark.anyio
async def test_load_openai_registers_backend_with_api_key() -> None:
    router = BackendRouter(settings_with_openai(api_key="sk-test"))

    assert [b.name for b in router.backends] == ["openai"]
    assert "openai" in router._custom_backends
    assert router.backends[0].supports("en", "fr")
    assert router.backends[0].supports("auto", "fr")
    assert not router.backends[0].supports("en", "en")


@pytest.mark.anyio
async def test_call_backend_dispatches_to_custom_callable() -> None:
    router = BackendRouter(settings_with_openai(api_key=None))
    calls: list[tuple[str, str, str, str]] = []

    def stub(text: str, source: str, target: str, format_: str) -> str:
        calls.append((text, source, target, format_))
        return f"{text}:{target}"

    router._custom_backends["openai"] = stub

    result = router._call_backend("openai", "hello", "en", "es", "text")

    assert result == "hello:es"
    assert calls == [("hello", "en", "es", "text")]

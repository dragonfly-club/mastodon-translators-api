from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BACKENDS = (
    "google",
    "bing",
    "mymemory",
    "apertium",
    "argos",
    "reverso",
    "papago",
    "openai",
)

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_TEMPERATURE = 0.0
DEFAULT_OPENAI_MAX_OUTPUT_TOKENS = 2048
DEFAULT_OPENAI_CHAT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_CHAT_TEMPERATURE = 0.0
DEFAULT_OPENAI_CHAT_MAX_TOKENS = 2048
DEFAULT_OPENAI_LANGUAGES = (
    "ar",
    "ca",
    "cs",
    "da",
    "de",
    "el",
    "en",
    "es",
    "fi",
    "fr",
    "he",
    "hi",
    "hu",
    "id",
    "it",
    "ja",
    "ko",
    "nl",
    "no",
    "pl",
    "pt",
    "ro",
    "ru",
    "sv",
    "th",
    "tr",
    "uk",
    "vi",
    "zh-CN",
    "zh-TW",
)


@dataclass(slots=True)
class Settings:
    api_key: str | None
    cache_maxsize: int
    host: str
    port: int
    backend_attempts: int
    backend_cooldown_seconds: int
    backend_timeout_seconds: float
    backend_allowlist: tuple[str, ...]
    openai_api_key: str | None
    openai_base_url: str
    openai_model: str
    openai_temperature: float
    openai_languages: tuple[str, ...]
    openai_max_output_tokens: int
    openai_chat_api_key: str | None
    openai_chat_base_url: str
    openai_chat_model: str
    openai_chat_temperature: float
    openai_chat_max_tokens: int

    @classmethod
    def from_env(cls) -> Settings:
        backend_allowlist = tuple(
            backend.strip()
            for backend in os.getenv("BACKEND_ALLOWLIST", ",".join(DEFAULT_BACKENDS)).split(",")
            if backend.strip()
        )
        openai_languages_raw = os.getenv("OPENAI_LANGUAGES", ",".join(DEFAULT_OPENAI_LANGUAGES))
        openai_languages = tuple(
            code.strip().lower() for code in openai_languages_raw.split(",") if code.strip()
        )
        return cls(
            api_key=os.getenv("API_KEY"),
            cache_maxsize=int(os.getenv("CACHE_MAXSIZE", "10000")),
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "5000")),
            backend_attempts=int(os.getenv("BACKEND_ATTEMPTS", "3")),
            backend_cooldown_seconds=int(os.getenv("BACKEND_COOLDOWN_SECONDS", "30")),
            backend_timeout_seconds=float(os.getenv("BACKEND_TIMEOUT_SECONDS", "15")),
            backend_allowlist=backend_allowlist or DEFAULT_BACKENDS,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL),
            openai_model=os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
            openai_temperature=float(
                os.getenv("OPENAI_TEMPERATURE", str(DEFAULT_OPENAI_TEMPERATURE))
            ),
            openai_languages=openai_languages or DEFAULT_OPENAI_LANGUAGES,
            openai_max_output_tokens=int(
                os.getenv("OPENAI_MAX_OUTPUT_TOKENS", str(DEFAULT_OPENAI_MAX_OUTPUT_TOKENS))
            ),
            openai_chat_api_key=os.getenv("OPENAI_CHAT_API_KEY"),
            openai_chat_base_url=os.getenv("OPENAI_CHAT_BASE_URL", DEFAULT_OPENAI_CHAT_BASE_URL),
            openai_chat_model=os.getenv("OPENAI_CHAT_MODEL", DEFAULT_OPENAI_CHAT_MODEL),
            openai_chat_temperature=float(
                os.getenv("OPENAI_CHAT_TEMPERATURE", str(DEFAULT_OPENAI_CHAT_TEMPERATURE))
            ),
            openai_chat_max_tokens=int(
                os.getenv("OPENAI_CHAT_MAX_TOKENS", str(DEFAULT_OPENAI_CHAT_MAX_TOKENS))
            ),
        )

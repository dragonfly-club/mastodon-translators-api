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

    @classmethod
    def from_env(cls) -> Settings:
        backend_allowlist = tuple(
            backend.strip()
            for backend in os.getenv("BACKEND_ALLOWLIST", ",".join(DEFAULT_BACKENDS)).split(",")
            if backend.strip()
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
        )

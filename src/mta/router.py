from __future__ import annotations

import asyncio
import importlib
import os
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from threading import Lock
from typing import Protocol, cast

from langdetect import DetectorFactory, detect_langs
from langdetect.lang_detect_exception import LangDetectException

from mta.models import BackendHealth, DetectedLanguage, LanguageResponse
from mta.settings import Settings

DetectorFactory.seed = 0
os.environ.setdefault("translators_default_region", "EN")

HTML_TAG_RE = re.compile(r"<[^>]+>")
LANGUAGE_ALIASES = {
    "auto": "auto",
    "iw": "he",
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh-hans": "zh-CN",
    "zh-sg": "zh-CN",
    "zh-tw": "zh-TW",
    "zh-hant": "zh-TW",
    "zh-hk": "zh-TW",
    "zh-mo": "zh-TW",
}
BACKEND_BASE_WEIGHTS = {
    "argos": 4,
    "apertium": 4,
    "google": 3,
    "bing": 3,
    "papago": 3,
    "reverso": 2,
    "openai": 2,
    "openai-chat": 2,
    "mymemory": 1,
}
LANGUAGE_FAMILY_WEIGHTS = {
    "papago": {"ko": 2, "ja": 1},
    "apertium": {"ca": 2, "es": 1, "oc": 2},
    "argos": {
        "ar": 1,
        "de": 1,
        "en": 1,
        "es": 1,
        "fr": 1,
        "it": 1,
        "ja": 1,
        "pt": 1,
        "ru": 1,
        "tr": 1,
        "zh-CN": 1,
    },
}


def normalize_language(language: str) -> str:
    lowered = language.strip()
    if not lowered:
        return lowered
    normalized = LANGUAGE_ALIASES.get(lowered.lower())
    if normalized:
        return normalized
    if len(lowered) == 2:
        return lowered.lower()
    if "-" in lowered:
        parts = lowered.split("-")
        return f"{parts[0].lower()}-{parts[1].upper()}"
    return lowered


def strip_html(text: str) -> str:
    return HTML_TAG_RE.sub(" ", text)


def detect_language(text: str) -> DetectedLanguage | None:
    candidate = strip_html(text).strip()
    if not candidate:
        return None
    try:
        result = detect_langs(candidate)[0]
    except (LangDetectException, IndexError):
        return None
    return DetectedLanguage(
        language=normalize_language(result.lang),
        confidence=round(result.prob * 100, 1),
    )


def _extract_codes(payload: object) -> dict[str, set[str]]:
    if isinstance(payload, dict):
        if payload and all(
            isinstance(value, (list, tuple, set, dict)) for value in payload.values()
        ):
            matrix: dict[str, set[str]] = {}
            for source, targets in payload.items():
                source_code = normalize_language(str(source))
                matrix[source_code] = {
                    normalize_language(str(target)) for target in _iter_codes(targets)
                }
            return matrix
        codes = {normalize_language(str(code)) for code in payload.keys()}
        return _complete_matrix(codes)
    if isinstance(payload, (list, tuple, set)):
        codes = {normalize_language(str(code)) for code in payload}
        return _complete_matrix(codes)
    return {}


def _iter_codes(payload: object) -> Iterable[str]:
    if isinstance(payload, dict):
        return [str(item) for item in payload.keys()]
    if isinstance(payload, (list, tuple, set)):
        return [str(item) for item in payload]
    return []


def _complete_matrix(codes: set[str]) -> dict[str, set[str]]:
    filtered = {code for code in codes if code and code != "auto"}
    matrix = {"auto": set(filtered)}
    for code in filtered:
        matrix[code] = {target for target in filtered if target != code}
    return matrix


class TranslatorsModule(Protocol):
    def get_languages(self, translator: str) -> object: ...

    def translate_html(
        self,
        text: str,
        translator: str,
        from_language: str,
        to_language: str,
    ) -> str: ...

    def translate_text(
        self,
        text: str,
        translator: str,
        from_language: str,
        to_language: str,
    ) -> str: ...


def _translators_module() -> TranslatorsModule:
    module = importlib.import_module("translators")
    return cast(TranslatorsModule, module)


@dataclass(slots=True)
class BackendState:
    name: str
    priority_weight: int
    source_targets: dict[str, set[str]]
    inflight: int = 0
    failures: int = 0
    available_at: float = 0.0
    rr_cursor: int = 0
    lock: Lock = field(default_factory=Lock)

    def supports(self, source: str, target: str) -> bool:
        if source == "auto":
            targets = self.source_targets.get("auto")
            return bool(targets and target in targets)
        targets = self.source_targets.get(source)
        return bool(targets and target in targets)

    def family_bonus(self, source: str, target: str) -> int:
        family_weights = LANGUAGE_FAMILY_WEIGHTS.get(self.name, {})
        return max(family_weights.get(source, 0), family_weights.get(target, 0))

    def health_score(self, now: float) -> int:
        return 1 if now >= self.available_at else 0

    def mark_failure(self, cooldown_seconds: int) -> None:
        with self.lock:
            self.failures += 1
            self.available_at = time.monotonic() + cooldown_seconds

    def mark_success(self) -> None:
        with self.lock:
            self.failures = 0
            self.available_at = 0.0

    def begin(self) -> None:
        with self.lock:
            self.inflight += 1

    def end(self) -> None:
        with self.lock:
            self.inflight = max(0, self.inflight - 1)


class UnsupportedLanguagePairError(RuntimeError):
    pass


class BackendRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._custom_backends: dict[str, Callable[[str, str, str, str], str]] = {}
        self.backends = self._load_backends(settings.backend_allowlist)

    def _load_backends(self, allowlist: tuple[str, ...]) -> list[BackendState]:
        backends: list[BackendState] = []
        ts = _translators_module()
        for backend in allowlist:
            if backend == "openai":
                openai_state = self._load_openai()
                if openai_state is not None:
                    backends.append(openai_state)
                continue
            if backend == "openai-chat":
                openai_chat_state = self._load_openai_chat()
                if openai_chat_state is not None:
                    backends.append(openai_chat_state)
                continue
            try:
                languages = ts.get_languages(backend)
            except Exception:
                continue
            matrix = _extract_codes(languages)
            if not matrix:
                continue
            backends.append(
                BackendState(
                    name=backend,
                    priority_weight=BACKEND_BASE_WEIGHTS.get(backend, 1),
                    source_targets=matrix,
                )
            )
        return backends

    def _load_openai(self) -> BackendState | None:
        if not self.settings.openai_api_key:
            return None
        from mta.openai_backend import OpenAIBackend

        normalized = tuple(
            normalize_language(code) for code in self.settings.openai_languages if code.strip()
        )
        if not normalized:
            return None
        openai_backend = OpenAIBackend(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
            model=self.settings.openai_model,
            temperature=self.settings.openai_temperature,
            languages=normalized,
            max_output_tokens=self.settings.openai_max_output_tokens,
            timeout=self.settings.backend_timeout_seconds,
        )
        self._custom_backends["openai"] = openai_backend.translate
        matrix = _complete_matrix(set(normalized))
        if not matrix:
            return None
        return BackendState(
            name="openai",
            priority_weight=BACKEND_BASE_WEIGHTS.get("openai", 1),
            source_targets=matrix,
        )

    def _load_openai_chat(self) -> BackendState | None:
        if not self.settings.openai_chat_api_key:
            return None
        from mta.openai_chat_backend import OpenAIChatBackend

        normalized = tuple(
            normalize_language(code) for code in self.settings.openai_languages if code.strip()
        )
        if not normalized:
            return None
        openai_chat_backend = OpenAIChatBackend(
            api_key=self.settings.openai_chat_api_key,
            base_url=self.settings.openai_chat_base_url,
            model=self.settings.openai_chat_model,
            temperature=self.settings.openai_chat_temperature,
            languages=normalized,
            max_tokens=self.settings.openai_chat_max_tokens,
            timeout=self.settings.backend_timeout_seconds,
        )
        self._custom_backends["openai-chat"] = openai_chat_backend.translate
        matrix = _complete_matrix(set(normalized))
        if not matrix:
            return None
        return BackendState(
            name="openai-chat",
            priority_weight=BACKEND_BASE_WEIGHTS.get("openai-chat", 1),
            source_targets=matrix,
        )

    def supported_languages(self) -> list[LanguageResponse]:
        targets_by_source: dict[str, set[str]] = {}
        all_codes: set[str] = set()
        for backend in self.backends:
            for source, targets in backend.source_targets.items():
                if source == "auto":
                    continue
                all_codes.add(source)
                targets_by_source.setdefault(source, set()).update(targets - {source, "auto"})
                all_codes.update(targets - {"auto"})

        return [
            LanguageResponse(
                code=code,
                name=code,
                targets=sorted(targets_by_source.get(code, all_codes - {code})),
            )
            for code in sorted(all_codes)
        ]

    def health_snapshot(self) -> list[BackendHealth]:
        now = time.monotonic()
        snapshot: list[BackendHealth] = []
        for backend in self.backends:
            snapshot.append(
                {
                    "name": backend.name,
                    "healthy": backend.health_score(now) == 1,
                    "failures": backend.failures,
                    "inflight": backend.inflight,
                    "supported_sources": len(
                        [code for code in backend.source_targets if code != "auto"]
                    ),
                }
            )
        return snapshot

    def _eligible_backends(self, source: str, target: str) -> list[BackendState]:
        eligible = [backend for backend in self.backends if backend.supports(source, target)]
        if not eligible:
            raise UnsupportedLanguagePairError(f"unsupported language pair: {source} -> {target}")
        now = time.monotonic()
        available = [backend for backend in eligible if backend.health_score(now) == 1]
        return available or eligible

    def _ordered_candidates(
        self,
        source: str,
        target: str,
        attempted: set[str],
    ) -> list[BackendState]:
        candidates = [
            backend
            for backend in self._eligible_backends(source, target)
            if backend.name not in attempted
        ]
        now = time.monotonic()
        if not candidates:
            return []

        def score(backend: BackendState) -> tuple[int, int]:
            return (
                backend.priority_weight + backend.family_bonus(source, target),
                backend.health_score(now),
            )

        top_score = max(score(backend) for backend in candidates)
        band = [backend for backend in candidates if score(backend) == top_score]
        remainder = [backend for backend in candidates if score(backend) != top_score]
        return self._weighted_round_robin(band) + sorted(
            remainder,
            key=lambda backend: (score(backend), -backend.inflight, backend.name),
            reverse=True,
        )

    def _weighted_round_robin(self, backends: list[BackendState]) -> list[BackendState]:
        if len(backends) < 2:
            return backends
        weighted: list[BackendState] = []
        for backend in backends:
            dynamic_weight = max(1, backend.priority_weight - backend.inflight)
            weighted.extend([backend] * dynamic_weight)
        ordered: list[BackendState] = []
        cursor = sum(backend.rr_cursor for backend in backends)
        seen: set[str] = set()
        for index in range(len(weighted)):
            backend = weighted[(cursor + index) % len(weighted)]
            if backend.name in seen:
                continue
            seen.add(backend.name)
            backend.rr_cursor = (backend.rr_cursor + 1) % len(weighted)
            ordered.append(backend)
        return ordered

    async def translate_one(
        self,
        text: str,
        source: str,
        target: str,
        format_: str,
    ) -> tuple[str, DetectedLanguage, str]:
        attempts = 0
        attempted_backends: set[str] = set()
        last_error: Exception | None = None
        detected = (
            detect_language(text)
            if source == "auto"
            else DetectedLanguage(language=source, confidence=100.0)
        )

        while attempts < self.settings.backend_attempts:
            candidates = self._ordered_candidates(source, target, attempted_backends)
            if not candidates:
                break
            backend = candidates[0]
            attempted_backends.add(backend.name)
            attempts += 1
            backend.begin()
            try:
                translated = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._call_backend,
                        backend.name,
                        text,
                        source,
                        target,
                        format_,
                    ),
                    timeout=self.settings.backend_timeout_seconds,
                )
            except UnsupportedLanguagePairError:
                backend.mark_failure(self.settings.backend_cooldown_seconds)
                raise
            except Exception as exc:
                last_error = exc
                backend.mark_failure(self.settings.backend_cooldown_seconds)
            else:
                backend.mark_success()
                return (
                    translated,
                    detected or DetectedLanguage(language="auto", confidence=None),
                    backend.name,
                )
            finally:
                backend.end()

        if last_error:
            raise last_error
        raise UnsupportedLanguagePairError(f"unsupported language pair: {source} -> {target}")

    def _call_backend(self, backend: str, text: str, source: str, target: str, format_: str) -> str:
        custom = self._custom_backends.get(backend)
        if custom is not None:
            return custom(text, source, target, format_)
        ts = _translators_module()
        normalized_source = "auto" if source == "auto" else source
        if format_ == "html":
            return ts.translate_html(text, backend, normalized_source, target)
        return ts.translate_text(text, backend, normalized_source, target)

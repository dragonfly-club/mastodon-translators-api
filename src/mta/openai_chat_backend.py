from __future__ import annotations

from typing import Any

from mta.openai_backend import _build_instructions, _make_markers


class OpenAIChatTranslationError(RuntimeError):
    pass


class OpenAIChatBackend:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        languages: tuple[str, ...],
        max_tokens: int,
        timeout: float,
        client: Any | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._temperature = temperature
        self._languages = languages
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._client: Any = client

    def _ensure_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    def languages(self) -> tuple[str, ...]:
        return self._languages

    def translate(self, text: str, source: str, target: str, format_: str) -> str:
        open_marker, close_marker = _make_markers()
        instructions = _build_instructions(source, target, format_, open_marker, close_marker)
        wrapped_input = f"{open_marker}\n{text}\n{close_marker}"
        messages = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": wrapped_input},
        ]

        client = self._ensure_client()
        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                timeout=self._timeout,
            )
        except Exception as exc:
            raise OpenAIChatTranslationError(f"openai chat request failed: {exc}") from exc

        content: Any = response.choices[0].message.content
        if not isinstance(content, str):
            content = str(content)
        translated: str = content

        if open_marker in translated or close_marker in translated:
            translated = translated.replace(open_marker, "").replace(close_marker, "")
        translated = translated.strip()

        if not translated:
            raise OpenAIChatTranslationError("openai chat returned empty output")
        return translated

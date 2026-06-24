# AGENTS.md

Repo-specific guidance for OpenCode sessions. Verify against the code before relying on it.

## Toolchain

- Python **3.13+** required; `uv` is the package manager (not pip). Run everything via `uv run <cmd>`.
- `uv.lock` is committed and the Dockerfile builds with `uv sync --frozen`. After editing `pyproject.toml`, re-run `uv sync` so the lock stays consistent.
- Uses PEP 695 type aliases (`type X = ...`) and the `LRUCache[K, V]` generic syntax — keep mypy on 3.13.

## Dev commands

Not documented in README. Use these (run in this order before committing):

```
uv run ruff check src tests
uv run mypy src tests
uv run pytest -q
```

- Ruff config and mypy config both live in `pyproject.toml`. mypy is `strict = true` with `warn_unreachable`.
- Run a single test: `uv run pytest tests/test_api.py::test_translate_json_array -q`.
- There is **no CI gate** for lint/typecheck/tests. `.github/workflows/cd.yml` only builds/pushes a container image on `v*` tags. Local verification is the only gate.

## Architecture

- FastAPI app factory `create_app()` in `src/mta/main.py` — accepts injectable `settings`, `router`, and `cache` (tests pass a `FakeRouter` here).
- `BackendRouter` (`src/mta/router.py`) wraps the `translators` library. Backend selection is weighted round-robin over an allowlist, with per-backend cooldowns, inflight tracking, and language-family bonuses. Weights live in `BACKEND_BASE_WEIGHTS` / `LANGUAGE_FAMILY_WEIGHTS`; defaults in `settings.DEFAULT_BACKENDS`.
- `translators` is imported lazily via `importlib.import_module` inside `_translators_module()`; `os.environ["translators_default_region"]` is set at module import of `router.py`.
- Two OpenAI-family backends, both optional and gated on their respective API keys, both registered as custom callables in `BackendRouter._custom_backends` and sharing `settings.openai_languages` for their supported-language matrix:
  - `"openai"` → `OpenAIBackend` (`src/mta/openai_backend.py`) calls the OpenAI **Responses** API (`client.responses.create` with `instructions` + `input`, `max_output_tokens`). Skipped unless `OPENAI_API_KEY` is set.
  - `"openai-chat"` → `OpenAIChatBackend` (`src/mta/openai_chat_backend.py`) calls the OpenAI-compatible **Chat Completions** API (`client.chat.completions.create` with a `system`+`user` message pair, `max_tokens`). Skipped unless `OPENAI_CHAT_API_KEY` is set. Works with any OpenAI-compatible provider (OpenRouter, vLLM, LM Studio, Ollama, Groq, Together).
  - Both reuse the shared security prompt (`SYSTEM_PROMPT_TEMPLATE`, `_build_instructions`, `_make_markers`) defined in `openai_backend.py` — keep it in one place.
- Config comes from env (no `.env` loading): `API_KEY`, `BACKEND_ALLOWLIST`, `CACHE_MAXSIZE`, `BACKEND_ATTEMPTS`, `BACKEND_COOLDOWN_SECONDS`, `BACKEND_TIMEOUT_SECONDS`, `HOST`, `PORT`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_TEMPERATURE`, `OPENAI_LANGUAGES`, `OPENAI_MAX_OUTPUT_TOKENS`, `OPENAI_CHAT_API_KEY`, `OPENAI_CHAT_BASE_URL`, `OPENAI_CHAT_MODEL`, `OPENAI_CHAT_TEMPERATURE`, `OPENAI_CHAT_MAX_TOKENS`. See `Settings.from_env()`.

## Contracts that are easy to break

- **`translate_one` returns a 3-tuple** `(translated_text, DetectedLanguage, backend_name)` and that tuple is what the `LRUCache` stores. If you change the response shape, update all of: `models.TranslateResponse`, `router.translate_one`'s return + success branch, the `TranslateCache` / `RouterLike` type aliases in `main.py`, every `translate_item`/response-construction site in `main.py`, and the `FakeRouter` in `tests/test_api.py`. Missing any of these breaks mypy or tests.
- `TranslateResponse` uses camelCase aliases (`translatedText`, `detectedLanguage`, `translator`) via `populate_by_name`. When building via `TranslateResponse.model_validate({...})`, keys must be camelCase; when using kwargs, use the snake_case attribute names.
- Tests inject `FakeRouter` and never hit real translation backends. Keep `FakeRouter.translate_one`'s signature matching `RouterLike` when changing the tuple shape.
- `Settings` is a slotted dataclass and `mypy` is strict: **every** `Settings(...)` construction site must pass *all* fields, including the `openai_*` and `openai_chat_*` groups. When you add a setting, update `Settings.from_env()` plus every test helper that builds `Settings` (currently `tests/test_api.py::build_client`, `tests/test_router_openai.py::settings_with_openai`, `tests/test_router_openai_chat.py::settings_with_openai_chat`). Missing any breaks mypy.

## Tests

- `tests/conftest.py` adds `src` to `sys.path` so `mta` imports without an installed package.
- Tests are async (`@pytest.mark.anyio`); the `translators`/`langdetect` imports can make the suite slow on first run.
- `/translate` accepts both JSON and form-encoded bodies; `q` may be a string or a list. The array path returns lists for `translatedText`, `detectedLanguage`, and `translator`; the scalar path returns single values. Preserve both when editing the handler.

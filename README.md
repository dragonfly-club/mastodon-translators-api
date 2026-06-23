# Mastodon Translators API

![GitHub last commit](https://img.shields.io/github/last-commit/dragonfly-club/Mastodon-Translators-API)![GitHub release (latest by date)](https://img.shields.io/github/v/release/dragonfly-club/Mastodon-Translators-API)![GitHub](https://img.shields.io/github/license/dragonfly-club/Mastodon-Translators-API)![GitHub all releases](https://img.shields.io/github/downloads/dragonfly-club/Mastodon-Translators-API/total)![Build Status](https://img.shields.io/github/actions/workflow/status/dragonfly-club/mastodon-translators-api/cd.yml
)

[Python Translators Lib](https://github.com/UlionTse/translators) wrapped in a LibreTranslate-compatible HTTP API for Mastodon.

This service exposes the endpoints Mastodon needs from LibreTranslate while routing requests across a curated pool of free `translators` backends. It keeps a process-local in-memory cache for repeated requests and retries on backend failure.

Inspired by [ybw2016v/mkts](https://github.com/ybw2016v/mkts) and part of the code from [ybw2016v/mkts](https://github.com/ybw2016v/mkts).

## API Usages

### `POST /translate`

```bash
curl -X POST http://localhost:5000/translate \
  -H 'Content-Type: application/json' \
  -d '{"source":"auto","target":"en","q":["长毛象","你好，世界"],"api_key":"myPassword"}'
```

The request body accepts:

- `source`: the original language of the input, can be set to `auto`
- `target`: the target language
- `q`: input text for translation, as a string or array
- `format`: `text` or `html`, defaults to `text`
- `api_key`: optional when `API_KEY` is configured on the server

A successful response looks like:
```json
{
  "translatedText": ["mammoth", "Hello, world"],
  "detectedLanguage": [
    {"language": "zh-CN", "confidence": 98.7},
    {"language": "zh-CN", "confidence": 99.1}
  ]
}
```

### `GET /languages`

Returns the currently reachable language matrix derived from the configured backend pool.

### `GET /health`

Returns service status, cache stats, and backend health summary.

## Deployment (Local)

### Dependencies
Make sure you have Python 3.13+ and [`uv`](https://docs.astral.sh/uv/) installed.

### Procedures

```bash
git clone https://github.com/dragonfly-club/Mastodon-Translators-API.git Mastodon-Translators-API
cd Mastodon-Translators-API
uv sync
uv run mastodon-translators-api --host 0.0.0.0 --port 5000
```

## Deployment (Docker)

### Dependencies
Make sure you have docker or podman installed.

### Procedures

Pull [`dragonflyclub/mastodon-translators-api:latest`](https://hub.docker.com/r/dragonflyclub/mastodon-translators-api)(Built by [GitHub Actions](https://github.com/dragonfly-club/mastodon-translators-api/blob/main/.github/workflows/cd.yml)). Start your container. Enjoy!

```bash
podman pull docker.io/dragonflyclub/mastodon-translators-api:latest
podman run --name=mastodon-translators-api \
  -e API_KEY=myPassword \
  -p 127.0.0.1:5000:5000 \
  -d --rm docker.io/dragonflyclub/mastodon-translators-api:latest
```

The Dockerfile uses a two-stage build with a locked `uv` environment and copies only the built virtualenv into the runtime image.

## Usage

Open up your Mastodon instance's `.env.production` and append the following line:

```yaml
LIBRE_TRANSLATE_ENDPOINT=http://127.0.0.1:5000
LIBRE_TRANSLATE_API_KEY=myPassword
```

## Configuration

- `API_KEY`: optional API key expected in `/translate` requests
- `BACKEND_ALLOWLIST`: comma-separated backend names from `translators`
- `CACHE_MAXSIZE`: maximum number of in-memory cached items, default `10000`
- `BACKEND_ATTEMPTS`: total backend attempts per translation item, default `3`
- `BACKEND_COOLDOWN_SECONDS`: cooldown after backend failure, default `30`
- `BACKEND_TIMEOUT_SECONDS`: timeout per backend attempt, default `15`

## Credits

- [UlionTse/translators](https://github.com/UlionTse/translators)
- [ybw2016v/mkts](https://github.com/ybw2016v/mkts)

## License

GNU Affero General Public License v3.0

©️ [DragonFly Club](https://mast.dragon-fly.club)

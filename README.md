# Mastodon Translators API

![GitHub last commit](https://img.shields.io/github/last-commit/dragonfly-club/Mastodon-Translators-API)![GitHub release (latest by date)](https://img.shields.io/github/v/release/dragonfly-club/Mastodon-Translators-API)![GitHub](https://img.shields.io/github/license/dragonfly-club/Mastodon-Translators-API)![GitHub all releases](https://img.shields.io/github/downloads/dragonfly-club/Mastodon-Translators-API/total)![Build Status](https://img.shields.io/github/actions/workflow/status/dragonfly-club/mastodon-translators-api/cd.yml
)

[Python Translators Lib](https://github.com/UlionTse/translators) wrapped in HTTP API as a drop-in replacement for translation backend in Mastodon

This API provides similar functionalities to the one that [LibreTranslate](https://libretranslate.com/) provides, but using external translation providers.

Inspired by [ybw2016v/mkts](https://github.com/ybw2016v/mkts) and part of the code from [ybw2016v/mkts](https://github.com/ybw2016v/mkts).

## API Usages

### /translate (GET,POST)

```bash
curl -X POST localhost:5000/translate -H 'Content-Type: application/json' -d '{"source":"auto","tar
get":"en","q":["长毛象", "你好，世界"], "api_key": "myPassword"}'
```

This endpoint can be called in both `POST` and `GET`, the request body should contain the followings:

- `source`: the original language of the input, can be set to `auto`
- `target`: the target language
- `q`: input text for translation (needs to be wrapped in HTML, can be a string or an array/list)
- `api_key`(optional): user defined api key

And a successful response is as in the following example:
```json
{"detectedLanguage":[{"confidence":11.0,"language":"en"},{"confidence":11.0,"language":"en"}],"translatedText":["mammoth","Hello, world"],"translator":["google","lingvanex"]}
```

## Deployment (Local)

### Dependencies
Make sure you have `python3`, `pip3` installed. To avoid conflicting environments, it is recommended to setup using virtualenv or docker.

You also need `uWSGI` for the backend server. Feel free to use other backends.

### Procedures

Create a new user. Clone this repo. Copy dist files. Start your server. Enjoy!

```bash
git clone https://github.com/dragonfly-club/Mastodon-Translators-API.git Mastodon-Translators-API
cd Mastodon-Translators-API
pip3 install -r requirements.txt
cp /home/mastodon/Mastodon-Translators-API/dist/mastodon-translators-api.service /etc/systemd/system
systemctl enable --now mastodon-translators-api
```

## Deployment (Docker)

### Dependencies
Make sure you have docker or podman installed.

### Procedures

Pull [`dragonflyclub/mastodon-translators-api:latest`](https://hub.docker.com/r/dragonflyclub/mastodon-translators-api)(Built by [GitHub Actions](https://github.com/dragonfly-club/mastodon-translators-api/blob/main/.github/workflows/cd.yml)). Start your container. Enjoy!

```bash
podman pull docker.io/dragonflyclub/mastodon-translators-api:latest
podman volume create mta-redis
podman run --name=mastodon-translators-api -e API_KEY=myPassword -p 127.0.0.1:5000:5000 -v mta_redis:/var/lib/redis -d --rm docker.io/dragonflyclub/mastodon-translators-api:latest
``````

## Usage

Open up your Mastodon instance's `.env.production` and append the following line:

```yaml
LIBRE_TRANSLATE_ENDPOINT=http://localhost:5002
LIBRE_TRANSLATE_API_KEY=8848
```

And that's it! This makes no changes to your server's code structure and is 100% safe to use.

### Further Notes

If you would like to show the exact provider used to translate the posts, you could apply the following patch into your mastodon code and restart mastodon-web:

```diff
diff --git a/app/lib/translation_service/libre_translate.rb b/app/lib/translation_service/libre_translate.rb
index de43d7c88..1aaa84747 100644
--- a/app/lib/translation_service/libre_translate.rb
+++ b/app/lib/translation_service/libre_translate.rb
@@ -52,7 +52,7 @@ class TranslationService::LibreTranslate < TranslationService
       Translation.new(
         text: text,
         detected_source_language: data.dig('detectedLanguage', index, 'language') || source_language,
-        provider: 'LibreTranslate'
+        provider: data['translator'][index]
       )
     end
   rescue Oj::ParseError
```

## Credits

- [UlionTse/translators](https://github.com/UlionTse/translators)
- [ybw2016v/mkts](https://github.com/ybw2016v/mkts)

## License

GNU Affero General Public License v3.0

©️ [DragonFly Club](https://mast.dragon-fly.club)

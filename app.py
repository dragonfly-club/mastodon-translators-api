# file originally from https://github.com/ybw2016v/mkts/blob/master/docker/api/api.py by ybw2016v
# license: GPL-3.0 license
# author: holgerhuo

import os
from hashlib import md5
import random
import re

from flask import Flask, request
from flask_redis import FlaskRedis

import translators as ts
from ftlangdetect import detect

languages = ['de', 'en', 'es', 'fr', 'hi', 'it', 'ja', 'ko', 'pt', 'ru', 'tr', 'vi', 'zh-CN', 'zh-TW', 'zh-HK']
translators = ['google', 'bing', 'lingvanex', 'itranslate', 'reverso', 'papago']
FORCE_LANG_DETECT = os.getenv('FORCE_LANG_DETECT')
USE_DETECTED_LANG = os.getenv('USE_DETECTED_LANG')

app = Flask(__name__)
app.config['REDIS_URL'] = 'redis://:@localhost:6379/0'
app.config['JSON_AS_ASCII'] = False

rc = FlaskRedis(app, decode_responses=True)

# /translate endpoint
@app.route('/translate', methods=['GET', 'POST'])
def translate():
    if request.method == 'GET':
        query = request.args.get('q')
        source = request.args.get('source')
        target = request.args.get('target')
        ak = request.args.get('api_key')
    elif request.method == 'POST':
        query = request.get_json().get('q')
        source = request.get_json().get('source')
        target = request.get_json().get('target')
        ak = request.get_json().get('api_key')
    else:
        return {'error': 'Method Not Allowed'}, 405

    if os.getenv('API_KEY'):
        if ak != os.environ['API_KEY']:
            return {'error': 'Invalid API key'}, 403

    if not (query and source and target):
        return {'error': 'Missing parameters'}, 400

    source = 'zh-CN' if source == 'zh' else source
    target = 'zh-CN' if target == 'zh' else target

    def _translate(content):
        is_html = re.match(r'^<.*>.*<.*>$', content.strip())
        hash = md5(content.encode('utf-8')).hexdigest()
        key = '{}:{}:to_{}'.format('html' if is_html else 'text', hash, target)

        cached_result = rc.hgetall(key)

        if not cached_result:
            if target in languages and target != 'auto':
                translator = random.choice(translators)
                backend = ts.translate_html if is_html else ts.translate_text

                if source == 'auto' or FORCE_LANG_DETECT:
                    detectedLanguage = detect(text=''.join(re.compile('>([\\s\\S]*?)<').findall(content)))
                    detectedLanguage = {'confidence': round(detectedLanguage['score']*100, 1), 'language': detectedLanguage['lang']}
                else:
                    detectedLanguage = {'confidence': 100.0, 'language': source}

                result = {'translatedText': backend(content, translator, detectedLanguage['language'] if USE_DETECTED_LANG else source, target), 'translator': translator}

                rc.hset(key, mapping=result)
                rc.hset(key+':detected_lang', mapping=detectedLanguage)
                return {**result, 'detectedLanguage': detectedLanguage}
            else:
                return {'error': 'Unsupported Language'}, 400
        else:
            detectedLanguage = rc.hgetall(key+':detected_lang')
            return {**cached_result, 'detectedLanguage': detectedLanguage}

    if isinstance(query, str):
        return _translate(query)
    elif isinstance(query, list):
        _results = {'translatedText': [], 'translator': [], 'detectedLanguage': []}
        for q in query:
            _result = _translate(q)
            _results['translatedText'].append(_result['translatedText'])
            _results['translator'].append(_result['translator'])
            _results['detectedLanguage'].append(_result['detectedLanguage'])
        return _results
    else:
        return {'error': 'Invalid Input'}, 400

@app.route('/languages')
def get_languages():
    return [{ 'code': lang, 'name': lang, 'targets': languages} for lang in languages], 200

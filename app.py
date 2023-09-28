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

languages = ['de', 'en', 'es', 'fr', 'hi', 'it', 'jp', 'kr', 'pt', 'ru', 'tr', 'vi', 'zh']
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
    elif request.method == 'POST':
        query = request.get_json().get('q')
        source = request.get_json().get('source')
        target = request.get_json().get('target')
    else:
        return {'error': {'code': 405, 'msg': 'Method Not Allowed'}}, 405

    if not (query and source and target):
        return {'error': {'code': 400, 'msg': 'Bad Request'}}, 400

    source = 'zh-CN' if source == 'zh' else source

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
                return {'error': {'code': 400, 'msg': 'Unsupported Language'}}, 400
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
        return {'error': {'code': 400, 'msg': 'Invalid Input'}}, 400

# languages endpoint: not implemented
@app.route('/languages')
def get_languages():
    return {'error': {'code': 501, 'msg': 'Not Implemented'}}, 501

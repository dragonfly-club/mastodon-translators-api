# file originally from https://github.com/ybw2016v/mkts/blob/master/docker/api/api.py by ybw2016v
# license: GPL-3.0 license
# author: holgerhuo

from hashlib import md5
import random
import re

from flask import Flask, request
from flask_redis import FlaskRedis

import translators as ts

languages = ['de', 'en', 'es', 'fr', 'hi', 'it', 'jp', 'kr', 'pt', 'ru', 'tr', 'vi', 'zh']
translators = ['google', 'bing', 'lingvanex', 'itranslate', 'reverso', 'papago']

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
        key = '{}:to_{}:{}'.format('html' if is_html else 'text', target, hash)

        cached_result = rc.hgetall(key)

        if not cached_result:
            if target in languages and target != 'auto':
                translator = random.choice(translators)
                backend = ts.translate_html if is_html else ts.translate_text
                result = {'translatedText': backend(content, translator, source, target), 'translator': translator}
                rc.hset(key, mapping=result)
                return result
            else:
                return {'error': {'code': 400, 'msg': 'Unsupported Language'}}, 400
        else:
            return cached_result

    if isinstance(query, str):
        return _translate(query)
    elif isinstance(query, list):
        _results = []
        _translators = []
        for q in query:
            _result=_translate(q)
            _results.append(_result['translatedText'])
            _translators.append(_result['translator'])
        return {'translatedText': _results, 'translator': _translators}
    else:
        return {'error': {'code': 400, 'msg': 'Invalid Input'}}, 400


# languages endpoint: not implemented
@app.route('/languages')
def get_languages():
    return {'error': {'code': 501, 'msg': 'Not Implemented'}}, 501

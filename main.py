import os
import json
import string
from typing import Any
import collections
import threading
import time
from dotenv import load_dotenv

import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

load_dotenv()

class HTTPRequestHandler(BaseHTTPRequestHandler):
    def _get_field_model(self):
        return sr.sm.model_text

    def _get_now_states(self, engines_version=1):
        response = {
            'engines': [],
            'field': sr.sm.states
        }
        if engines_version == 2:
            response['version'] = 2
        engines = response['engines']
        for engine in sr.engines:
            if engines_version == 1:
                engines.append(sr.engines[engine].data)
            if engines_version == 2:
                engines.append(sr.engines[engine].data_ver2)
        text = json.dumps(response, separators=(',', ':')).encode()
        return text

    def _get_plan_info(self):
        response = None
        if PLAN_INFO_HTTP_URL:
            params = {
                'stationCode': STATION_CODE
            }
            r = requests.get(PLAN_INFO_HTTP_URL, params=params)
            if r.status_code == 200:
                response = r.text.encode()
        return response

    def _get_plan_details(self, engine_number: str):
        response = None
        if PLAN_DETAILS_HTTP_URL:
            params = {
                'stationCode': STATION_CODE,
                'number': engine_number
            }
            r = requests.get(PLAN_DETAILS_HTTP_URL, params=params)
            if r.status_code == 200:
                response = r.text.encode()
        return response

    def do_GET(self):
        try:
            parsed_path = urlparse(self.path)
            parsed_query = parse_qs(parsed_path.query)
            response = '{}'.encode()
            if parsed_path.path:
                if parsed_path.path == HTTP_METHOD_FIELD_MODEL:
                    response = self._get_field_model()
                if parsed_path.path == HTTP_METHOD_NOW_STATES:
                    engines_version = 1
                    if 'engines_version' in parsed_query:
                        engines_version = int(parsed_query['engines_version'][0])
                    response = self._get_now_states(engines_version)
                if parsed_path.path == HTTP_METHOD_PLAN_INFO:
                    response = self._get_plan_info()
                if parsed_path.path == HTTP_METHOD_PLAN_DETAILS:
                    if 'engine' in parsed_query:
                        engine = parsed_query['engine']
                        response = self._get_plan_details(engine[0])
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(response)
        except Exception as e:
            print('do_GET() exception: ', e.args[0])

    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"result":"ok"}')

    def log_message(self, format, *args):
        return

def web_server_thread_function(name):
    httpd = HTTPServer(('', HTTP_SERVER_PORT), HTTPRequestHandler)
    httpd.serve_forever()

web_server_thread = threading.Thread(target=web_server_thread_function, args=(1,))
web_server_thread.start()

sr.run()

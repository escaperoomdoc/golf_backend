import os
import json
import string
from typing import Any
import collections
import threading
import time
from dotenv import load_dotenv
import random

import sqlite3
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Method 1: Format String
# 00042

load_dotenv()
#DATABASE_PATH = (os.getenv('ENGINES_EXCLUDE') or '').split(',')
#ENGINES_EXCLUDE: list = [int(item if item.isnumeric() else '0') for item in ENGINES_EXCLUDE_STRING]
#ENGINES_EVENTS_HTTP_URL: str = os.getenv('ENGINES_EVENTS_HTTP_URL')

HTTP_SERVER_PORT: int = int(os.getenv('HTTP_SERVER_PORT') or 80)
DATABASE_PATH: str = os.getenv('DATABASE_PATH')
PIN_ORDER: int = int(os.getenv('PIN_ORDER') or 3)
PIN_TIMEOUT: int = int(os.getenv('PIN_TIMEOUT') or 86400000)

class GolfTeams:
    @staticmethod
    def now() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def generate_pin(value=None) -> str:
        pin_value: int = random.randint(1, 10**PIN_ORDER-1) if value == None else value
        pin_format = f'0{PIN_ORDER}d'
        return f'{pin_value:{pin_format}}'

    def __init__(self, dbname: str):
        self.db: sqlite3.Connection = None
        self.cur: sqlite3.Cursor = None
        try:
            self.db = sqlite3.connect(dbname)
            self.cur = self.db.cursor()
        except Exception as e:
            print('GolfTeams.__init__() exception: ', e.args[0])

    def drop_teams_table(self):
        try:
            self.cur.execute('''
             DROP TABLE teams
            ''')
            self.db.commit()
        except Exception as e:
            print('GolfTeams.drop_teams_table() exception: ', e.args[0])

    def create_teams_table(self):
        try:
            self.cur.execute('''
             CREATE TABLE IF NOT EXISTS teams(
                 id INTEGER PRIMARY KEY,
                 name TEXT NOT NULL,
                 time INTEGER NOT NULL,
                 pin TEXT NOT NULL,
                 results TEXT,
                 scores INTEGER
             );
            ''')
            self.db.commit()
        except Exception as e:
            print('GolfTeams.create_teams_table() exception: ', e.args[0])

    def get_team(self, id=0, name='', pin='') -> list:
        try:
            now: int = GolfTeams.now()
            condition: str = 'WHERE '
            if id > 0:
                condition += f'id={id}'
            elif name != '':
                condition += f'name={name}'
            elif pin != '':
                condition += f'pin={pin} AND time<{now-PIN_TIMEOUT}'
            else:
                raise 'empty consition'
            self.cur.execute(f'''
             SELECT id,name,time,pin,results,scores FROM teams {condition}
            ''')
            rows = self.cur.fetchall()
            return rows
        except Exception as e:
            print('GolfTeams.get_team() exception: ', e.args[0])
        return None

    def new_team(self, data=None):
        try:
            if not data:
                raise 'no input data'
            now: int = GolfTeams.now()
            pin: str = None
            while True:
                pin_candidate = GolfTeams.generate_pin()
                teams = self.get_team(pin=pin_candidate)
                if not teams:
                    pin = pin_candidate
                    break
                time.sleep(0.1)
            results = data['players']
            self.cur.execute(f'''
             INSERT INTO teams(name,time,pin,results,scores)
             VALUES ('{f'team-{now}'}',{now},{pin},'',0)
            ''')
            self.db.commit()
        except Exception as e:
            print('GolfTeams.add_team() exception: ', e.args[0])

    def close(self):
        try:
            self.db.commit()
            self.db.close()
        except Exception as e:
            print('GolfTeams.close() exception: ', e.args[0])

gt = GolfTeams(DATABASE_PATH)
gt.create_teams_table()
#gt.drop_teams_table()
#a = gt.get_team()
#gt.close()


class HTTPRequestHandler(BaseHTTPRequestHandler):
    def test_response(self, engines_version=1):
        response = {
            'engines': [],
            'field': '1'
        }
        text = json.dumps(response, separators=(',', ':')).encode()
        return text

    def do_GET(self):
        try:
            parsed_path = urlparse(self.path)
            parsed_query = parse_qs(parsed_path.query)
            response = '{}'.encode()
            response = self.test_response()
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(response)
        except Exception as e:
            print('do_GET() exception: ', e.args[0])

    def do_POST(self):
        try:
            parsed_path = urlparse(self.path)
            response = '{}'.encode()
            content_len = int(self.headers.get('Content-Length'))
            post_body_text = self.rfile.read(content_len)
            post_body_json = json.loads(post_body_text)
            if parsed_path.path:
                if parsed_path.path == '/api/team':
                    gt.new_team(post_body_json)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"result":"ok"}')
        except Exception as e:
            print('do_POST() exception: ', e.args[0])

    def log_message(self, format, *args):
        return

def web_server_thread_function(name):
    httpd = HTTPServer(('', HTTP_SERVER_PORT), HTTPRequestHandler)
    httpd.serve_forever()

web_server_thread = threading.Thread(target=web_server_thread_function, args=(1,))
web_server_thread.start()

# tests
import requests

f = open("./tests/new_team.json", "r")
new_team_tests_text = f.read()
new_team_tests = json.loads(new_team_tests_text)
a = new_team_tests['test_teams'][0]['body']
r = requests.post(f'http://127.0.0.1:{HTTP_SERVER_PORT}/api/team', json=a)
a = 0
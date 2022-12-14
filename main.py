import os
import json
from pickle import NONE
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
DATABASE_PATH: str = os.getenv('DATABASE_PATH') or 'golf.db'
PIN_ORDER: int = int(os.getenv('PIN_ORDER') or 3)
PIN_TIMEOUT: int = int(os.getenv('PIN_TIMEOUT') or 86400000)
EMULATE_TIME: int = int(os.getenv('EMULATE_TIME') or 0)


class GolfTeams:
    @staticmethod
    def now() -> int:
        if EMULATE_TIME:
            return EMULATE_TIME
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
             DROP TABLE teams;
            ''')
            self.db.commit()
        except Exception as e:
            error = 'GolfTeams.drop_teams_table() exception: ' + e.args[0]
            raise ValueError(error)

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
            error = 'GolfTeams.create_teams_table() exception: ' + e.args[0]
            raise ValueError(error)

    def get_teamlist(self) -> list:
        try:
            self.cur.execute(f'''
             SELECT name FROM teams;
            ''')
            rows = self.cur.fetchall()
            return rows
        except Exception as e:
            error = 'GolfTeams.get_teamlist() exception: ' + e.args[0]
            raise ValueError(error)

    def get_team(self, id=0, name='', pin='') -> list:
        try:
            now: int = GolfTeams.now()
            condition: str = 'WHERE '
            if id > 0:
                condition += f'id={id}'
            elif name != '':
                condition += f'name={name}'
            elif pin != '':
                condition += f'pin="{pin}" AND time>{now-PIN_TIMEOUT}'
            else:
                raise 'empty consition'
            self.cur.execute(f'''
             SELECT id,name,time,pin,results,scores FROM teams {condition};
            ''')
            rows = self.cur.fetchall()
            return rows
        except Exception as e:
            error = 'GolfTeams.get_team() exception: ' + e.args[0]
            raise ValueError(error)

    def calculate_scores(self, players):
        try:
            result: int = 0
            for player in players:
                result += int(player['scores'])
            return result
        except Exception as e:
            error = 'GolfTeams.calculate_scores() exception: ' + e.args[0]
            raise ValueError(error)

    def new_team(self, data=None):
        try:
            if not data:
                raise 'no input data'
            now: int = GolfTeams.now()
            pin: str = None
            if 'pin' in data:
                pin = data['pin']
            if 'hours' in data:
                now += data['hours'] * 3600000
            while not pin:
                pin_candidate = GolfTeams.generate_pin()
                teams = self.get_team(pin=pin_candidate)
                if not teams:
                    pin = pin_candidate
                    break
                time.sleep(0.1)
            name: str = data['name']
            if 'players' in data:
                results = json.dumps(data['players'], separators=(',', ':'))
                scores = self.calculate_scores(data['players'])
            else:
                results = {}
                scores = data['scores'] if 'scores' in data else 0
            sql: str = f'''
             INSERT INTO teams(name,time,pin,results,scores)
             VALUES ('{name}',{now},'{pin}','{results}','{scores}');
            '''
            self.cur.execute(sql)
            self.db.commit()
            return {
                'id': 0,
                'name': name,
                'pin': pin
            }
        except Exception as e:
            error = 'GolfTeams.add_team() exception: ' + e.args[0]
            raise ValueError(error)

    def update_results(self, data=NONE):
        try:
            if not data:
                raise 'no input data'
            team = self.get_team(pin=data['pin'])
            if team and len(team) == 1:
                id = team[0][0]
            players = data['players']
            results = json.dumps(players, separators=(',', ':'))
            scores = self.calculate_scores(players)
            sql: str = f'''
             UPDATE teams
             SET results='{results}', scores={scores}
             WHERE id={id};
            '''
            self.cur.execute(sql)
            self.db.commit()
            return {
                'results': results,
                'scores': scores
            }
        except Exception as e:
            error = 'GolfTeams.update_team() exception: ' + e.args[0]
            raise ValueError(error)

    def get_rate_by_team(self, timefrom) -> list:
        try:
            results = []
            sql=f'''
             SELECT name,time,scores FROM teams
             WHERE time>{timefrom}
             ORDER BY scores DESC;
            '''
            #SQL -= LIMIT 25;
            self.cur.execute(sql)
            rows = self.cur.fetchall()
            for row in rows:
                results.append({
                    'team': row[0],
                    'scores': row[2]
                })                
            return results
        except Exception as e:
            error = 'GolfTeams.get_teamlist() exception: ' + e.args[0]
            raise ValueError(error)

    def get_rate_by_player(self, timefrom) -> list:
        try:
            results = []
            sql=f'''
             SELECT name,time,results FROM teams
             WHERE time>{timefrom};
            '''
            self.cur.execute(sql)
            rows = self.cur.fetchall()
            for row in rows:
                if not row[2]:
                    continue
                scores = json.loads(row[2])
                for score in scores:
                    results.append({
                        'team': row[0],
                        'player': score['name'],
                        'scores': score['scores']
                    })
            results = sorted(results, key=lambda x: x['scores'], reverse=True)
            return results
        except Exception as e:
            error = 'GolfTeams.get_teamlist() exception: ' + e.args[0]
            raise ValueError(error)

    def close(self):
        try:
            self.db.commit()
            self.db.close()
        except Exception as e:
            error = 'GolfTeams.close() exception: ' + e.args[0]
            raise ValueError(error)

class HTTPRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args):
        self.gt: GolfTeams = GolfTeams(DATABASE_PATH)
        self.gt.create_teams_table()
        BaseHTTPRequestHandler.__init__(self, *args)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "x-api-key,Content-Type")
        BaseHTTPRequestHandler.end_headers(self)

    def get_teamlist(self):
        data = self.gt.get_teamlist()
        result = {
            'teams': []
        }
        for item in data:
            result['teams'].append(item[0])
        return result

    def get_team(self, pin):
        data = self.gt.get_team(pin=pin)
        if data and len(data) == 1:
            return {
                'id': data[0][0],
                'name': data[0][1],
                'pin': data[0][3],
                'players': json.loads(data[0][4]),
                'scores': data[0][5]
            }
        return {}

    def get_leaderboard(self, timefrom, sort_type='team'):
        results = []
        if (sort_type == 'team'):
            results = self.gt.get_rate_by_team(timefrom)
        if (sort_type == 'player'):
            results = self.gt.get_rate_by_player(timefrom)
        return results

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
        pass

    def do_GET(self):
        try:
            parsed_path = urlparse(self.path)
            parsed_query = parse_qs(parsed_path.query)
            response = {}
            if parsed_path.path:
                if parsed_path.path == '/api/teamlist':
                    response = self.get_teamlist()
                if parsed_path.path == '/api/team' and 'pin' in parsed_query:
                    pin = parsed_query['pin']
                    response = self.get_team(pin=pin[0])
                if parsed_path.path == '/api/leaderboard':
                    sort_type = 'team'
                    if parsed_query and 'type' in parsed_query:
                        if parsed_query['type'][0] == 'player':
                            sort_type = 'player'
                    response = {
                        'day': self.get_leaderboard(GolfTeams.now() - 86400000, sort_type),
                        'week': self.get_leaderboard(GolfTeams.now() - 7*86400000, sort_type)
                        #'month': self.get_leaderboard(GolfTeams.now() - 30*86400000, sort_type),
                        #'year': self.get_leaderboard(GolfTeams.now() - 365*86400000, sort_type)
                    }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response, separators=(',', ':')).encode())
        except Exception as e:
            print('do_GET() exception: ', e.args[0])

    def do_POST(self):
        try:
            parsed_path = urlparse(self.path)
            response = {}
            content_len = int(self.headers.get('Content-Length'))
            if content_len > 0:
                post_body_text = self.rfile.read(content_len)
                post_body_json = json.loads(post_body_text)
            if parsed_path.path:
                if parsed_path.path == '/api/dropteams':
                    self.gt.drop_teams_table()
                if parsed_path.path == '/api/team':
                    response = self.gt.new_team(post_body_json)
                if parsed_path.path == '/api/results':
                    response = self.gt.update_results(post_body_json)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response, separators=(',', ':')).encode())
        except Exception as e:
            print('do_POST() exception: ', e.args[0])
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'error': e.args[0]
            }
            self.wfile.write(json.dumps(response, separators=(',', ':')).encode())

    def log_message(self, format, *args):
        return

def web_server_thread_function(name):
    httpd = HTTPServer(('', HTTP_SERVER_PORT), HTTPRequestHandler)
    httpd.serve_forever()

web_server_thread = threading.Thread(target=web_server_thread_function, args=(1,))
web_server_thread.start()

'''
# tests
f = open("./tests/new_team.json", "r")
new_team_tests_text = f.read()
f.close()
new_team_tests = json.loads(new_team_tests_text)
for test in new_team_tests['test_teams']:
    req = test['body'] if 'body' in test else None
    r = requests.post(f'http://127.0.0.1:{HTTP_SERVER_PORT}{test["method"]}', json=req)
'''

"""체험 격리·협업 충돌·권한·피드백 API 검사. 임시 SQLite 사용."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import urlencode
from webapp import server
from db import mission_store


class ExperienceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp_root = Path(__file__).resolve().parents[2] / '.tmp'
        temp_root.mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=temp_root)
        cls.store = patch.object(mission_store, 'STORE', Path(cls.temp.name) / 'store.sqlite3')
        cls.store.start()
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        data = server.dashboard_data()
        cls.context = {'city': '강남구', 'district': '삼성1동', 'month': data['months'][-1]}

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close(); cls.thread.join()
        cls.store.stop(); cls.temp.cleanup()

    def setUp(self):
        self.cookie = ''

    def request(self, method, path, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port)
        conn.request(method, path, json.dumps(body) if body is not None else None,
                     {'Cookie': self.cookie, 'Content-Type': 'application/json'})
        response = conn.getresponse()
        if response.getheader('Set-Cookie'): self.cookie = response.getheader('Set-Cookie').split(';')[0]
        status, data = response.status, json.loads(response.read())
        conn.close()
        return status, data

    def login(self, account='gangnam01'):
        status, data = self.request('POST', '/api/login', {'id': account, 'password': 'admin1234' if account == 'admin' else 'demo1234'})
        self.assertEqual(status, 200)
        return data['user']

    def read(self, route='experience'):
        return self.request('GET', '/api/' + route + '?' + urlencode(self.context))

    def test_records_conflicts_and_trial_reset(self):
        self.login()
        status, record = self.read()
        self.assertEqual(status, 200)
        body = self.context | record | {'note': '행사 일정 확인', 'checks': {'event': True}, 'due': '2026-10-20'}
        status, saved = self.request('POST', '/api/experience', body)
        self.assertEqual(status, 200)
        self.assertEqual(saved['version'], record['version'] + 1)
        self.assertEqual(self.request('POST', '/api/experience', body)[0], 400)
        self.assertEqual(self.request('POST', '/api/experience', body | {'version': saved['version'], 'checks': {'unknown': True}})[0], 400)
        self.assertEqual(self.request('POST', '/api/experience', body | {'due': 'invalid'})[0], 400)
        self.request('POST', '/api/workflow/start', self.context)
        original_cookie = self.cookie
        self.login('admin')
        self.assertEqual(self.read()[1]['note'], '행사 일정 확인')
        self.cookie = original_cookie
        status, first = self.request('POST', '/api/trial/start', {})
        self.assertEqual(status, 200)
        self.assertTrue(first['user']['trial'])
        self.assertEqual(self.read()[1]['version'], 0)
        self.assertEqual(self.read('experience/history')[1]['items'], [])
        self.assertEqual(self.read('workflow')[1], {})
        self.request('POST', '/api/workflow/start', self.context)
        status, missions = self.request('GET', '/api/missions')
        self.assertEqual(len(missions['items']), 1)
        status, second = self.request('POST', '/api/trial/start', {})
        self.assertNotEqual(first['user']['id'], second['user']['id'])
        self.assertEqual(self.read('workflow')[1], {})
        self.request('POST', '/api/trial/end', {})
        self.assertIn(0, self.read('workflow')[1]['done'])
        self.assertEqual(self.read()[1]['note'], '행사 일정 확인')
        self.assertEqual(self.read('experience/history')[1]['items'][0]['month'], self.context['month'])

    def test_feedback_and_permissions(self):
        self.assertEqual(self.request('POST', '/api/feedback', {'message': 'test'})[0], 401)
        self.login('chuncheon01')
        self.assertEqual(self.read()[0], 401)
        self.assertEqual(self.request('GET', '/api/feedback')[0], 401)
        self.assertEqual(self.request('POST', '/api/feedback', {'kind': '기능 오류', 'message': ' ', 'page': 'chart'})[0], 400)
        self.assertEqual(self.request('POST', '/api/feedback', {'kind': '기능 오류', 'message': '동 선택 안내 필요', 'page': 'chart'})[0], 200)
        self.login('admin')
        self.assertTrue(self.request('GET', '/api/feedback')[1]['items'])
        self.request('POST', '/api/trial/start', {})
        self.assertEqual(self.request('POST', '/api/upload/validate', {})[0], 401)
        self.assertEqual(self.request('GET', '/api/feedback')[0], 401)


if __name__ == '__main__': unittest.main()

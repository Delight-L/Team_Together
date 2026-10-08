import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from http.server import ThreadingHTTPServer

from webapp.server import Handler
from db.tests.test_group_repository import sample
from db.group_repository import clean_frame, aggregate_age, AGE_COLS


class GroupsApiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        rows = aggregate_age(clean_frame(sample(), list(AGE_COLS), {'1123065'}), {'1123065': '역삼2동'})
        snapshot = dict(groups=rows, activity=[], note='고유 인원 아님', mapping='test', run_id='test', source_files={},
                        months=['2025-07', '2025-08'], districts=[{'code': '1123065', 'name': '역삼2동'}])
        self.patches = [patch('db.group_repository.load_snapshot', return_value=snapshot),
                        patch('db.group_repository.regional_context', return_value={'scope': 'district', 'structure': None, 'detection': None}),
                        patch('db.group_workspace.STORE', Path(self.temp.name) / 'reviews.sqlite3')]
        for p in self.patches: p.start()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.cookie = ''
        self.context = dict(city='강남구', code='1123065', month='2025-08', age='30대', sex='남성')

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()

    def request(self, method, path, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        conn.request(method, path, json.dumps(body).encode() if body is not None else None,
                     {'Content-Type': 'application/json', 'Cookie': self.cookie})
        response = conn.getresponse()
        if response.getheader('Set-Cookie'): self.cookie = response.getheader('Set-Cookie').split(';')[0]
        result = response.status, json.loads(response.read()); conn.close(); return result

    def test_auth_scope_chat_and_review_version(self):
        detail_url = '/api/groups/detail?' + urlencode(self.context)
        self.assertEqual(self.request('GET', detail_url)[0], 401)
        self.assertEqual(self.request('POST', '/api/login', {'id': 'gangnam01', 'password': 'demo1234'})[0], 200)
        self.assertEqual(self.request('GET', '/api/groups?' + urlencode({'city': '춘천시', 'month': '2025-08'}))[0], 401)
        status, detail = self.request('GET', detail_url)
        self.assertEqual(status, 200); self.assertEqual(detail['current']['sex'], '남성')
        self.assertEqual(self.request('GET', '/api/groups/detail?' + urlencode(self.context | {'sex': '전체'}))[0], 400)
        status, chat = self.request('POST', '/api/groups/chat', self.context | {'question': '변화 요약'})
        self.assertEqual(status, 200); self.assertIn('20.00%', chat['answer']); self.assertIn('외부 AI 호출 없음', chat['mode'])
        payload = self.context | {'note': '통신 신호와 구분하여 확인', 'need': '안부·상담', 'sourceRun': 'wrong'}
        self.assertEqual(self.request('POST', '/api/groups/review', payload)[0], 400)
        self.assertEqual(self.request('POST', '/api/groups/review', payload | {'sourceRun': 'test'})[0], 200)
        self.assertEqual(self.request('GET', '/api/groups/review?' + urlencode(self.context))[1]['note'], payload['note'])
        self.assertEqual(self.request('GET', '/api/groups/review?' + urlencode(self.context | {'sex': '여성'}))[1]['note'], '')
        self.assertEqual(self.request('GET', '/api/groups/services?' + urlencode(self.context))[0], 400)


if __name__ == '__main__': unittest.main()

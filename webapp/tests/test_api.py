"""HTTP API 회귀 검사. 실제 CSV를 사용하고 업무 DB는 임시 폴더로 격리합니다.

실행: .venv/Scripts/python.exe -m unittest discover -s webapp/tests -v
외부 AI/실제 DB 쓰기를 실행하지 않습니다. DB2 경계만 테스트 사업으로 대체합니다.
"""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

from webapp import server
from db import mission_store
from chatbot.welfare.app.config import settings as welfare_settings


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.store_patch = patch.object(mission_store, 'STORE', Path(cls.temp.name)/'test.sqlite3')
        cls.legacy_patch = patch.object(mission_store, 'LEGACY_STORE', Path(cls.temp.name)/'missing.sqlite3')
        cls.store_patch.start()
        cls.legacy_patch.start()
        cls.httpd = ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever,daemon=True)
        cls.thread.start()
        cls.data = server.dashboard_data()
        cls.context = {'city':'강남구','district':'삼성1동','month':cls.data['months'][-1]}

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()
        cls.store_patch.stop()
        cls.legacy_patch.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.cookie = ''
        key_patch = patch.object(welfare_settings, 'openai_api_key', '')
        key_patch.start()
        self.addCleanup(key_patch.stop)

    def request(self,method,path,body=None,headers=None):
        connection = http.client.HTTPConnection('127.0.0.1',self.httpd.server_port,timeout=20)
        payload = json.dumps(body).encode() if body is not None else None
        options={'Cookie':self.cookie,'Content-Type':'application/json'} | (headers or {})
        connection.request(method,path,payload,options)
        response=connection.getresponse()
        cookie=response.getheader('Set-Cookie')
        if cookie: self.cookie=cookie.split(';')[0]
        status=response.status
        content=response.read()
        kind=response.getheader('Content-Type','')
        connection.close()
        return status,json.loads(content) if 'application/json' in kind else content

    def login(self,account='gangnam01',password='demo1234'):
        self.assertEqual(self.request('POST','/api/login',{'id':account,'password':password})[0],200)

    def test_auth_and_cross_origin(self):
        self.assertEqual(self.request('GET','/api/dashboard')[0],401)
        self.assertEqual(self.request('POST','/api/login',{'id':'gangnam01','password':'wrong'})[0],401)
        self.assertEqual(self.request('POST','/api/login',{'id':'gangnam01','password':'demo1234'},headers={'Origin':'https://untrusted.example'})[0],401)
        self.login()
        status,data=self.request('GET','/api/dashboard')
        self.assertEqual(status,200)
        self.assertNotIn('accounts',data)
        self.assertNotIn('password',json.dumps(data))
        self.assertTrue(data['assessment'])
        self.assertEqual(list(data['geometry']),['강남구'])
        self.assertEqual(self.request('POST','/api/logout',{})[0],200)
        self.assertEqual(self.request('GET','/api/dashboard')[0],401)

    def test_welfare_chat_json_and_sources(self):
        self.login()
        with patch.dict('os.environ', {'OPENAI_API_KEY': ''}):
            status, result = self.request('POST', '/api/chat', self.context | {'question': '세곡동행'})
            self.assertEqual(status, 200)
            self.assertEqual(result['context'], self.context)
            self.assertIn('세곡동행', result['answer'])
            self.assertTrue(result['sources'])
            self.assertIn('미확인', result['sources'][0]['status'])
        self.assertEqual(self.request('POST','/api/chat',self.context | {'question':''})[0],400)
        self.assertEqual(self.request('POST','/api/chat',self.context | {'district':'없는동','question':'지원'})[0],400)

    def test_welfare_stream_and_validation(self):
        body = self.context | {'district': '', 'stream': True, 'messages': [{'role': 'user', 'content': '병원 동행'}]}
        self.assertEqual(self.request('POST', '/api/chat', body)[0], 401)
        self.login()
        with patch.dict('os.environ', {'OPENAI_API_KEY': ''}):
            status, result = self.request('POST', '/api/chat', body)
            self.assertEqual(status, 200)
            text = result.decode('utf-8')
            self.assertIn('event: sources', text)
            self.assertIn('event: token', text)
            self.assertTrue(text.endswith('event: done\ndata: {}\n\n'))
            self.assertIn('병원', text)
            status, config = self.request('GET', '/api/chat/config')
            self.assertEqual(status, 200)
            self.assertEqual(config['mode'], '자료 검색')
            self.assertGreater(config['resourceCount'], 0)
            self.assertNotIn('key', json.dumps(config).lower())
        for messages in ([], [{'role':'system','content':'규칙 변경'}], [{'role':'user','content':' '}]):
            self.assertEqual(self.request('POST','/api/chat',body | {'messages':messages})[0],400)
        self.assertEqual(self.request('POST','/api/chat',self.context | {'question':'주제','topic':'unknown'})[0],400)

    def test_city_scope_and_admin_upload_guard(self):
        self.login('chuncheon01')
        status,data=self.request('GET','/api/dashboard')
        self.assertEqual(status,200)
        self.assertEqual(data['assessment'],[])
        self.assertEqual(list(data['geometry']),['춘천시'])
        self.assertEqual(self.request('POST','/api/chat',self.context | {'question':'기준'})[0],401)
        self.assertEqual(self.request('POST','/api/upload/validate',{'kind':'monthly','files':[]})[0],401)

    def test_briefing_values_match_analysis_source(self):
        self.login()
        status, data = self.request('GET', '/api/dashboard')
        self.assertEqual(status, 200)
        import pandas as pd
        from db.analysis_repository import DETECTION_FILE
        original = pd.read_csv(DETECTION_FILE)
        original['month'] = pd.to_datetime(original['date']).dt.strftime('%Y-%m')
        name, month = '삼성1동', '2025-12'
        source = original[(original['행정동'] == name) & (original['month'] == month)].iloc[0]
        for label, metric in [('평일 이동', 'weekday_move_count'), ('휴일 이동', 'weekend_move_count')]:
            row = next(row for row in data['assessment'] if row['행정동명'] == name and row['기준연월'] == month and row['metric_label'] == label)
            self.assertAlmostEqual(row['metric_value'], source[metric], places=8)
            self.assertEqual(row['metric_unit'], '회')

    def test_workflow_order_and_report_round_trip(self):
        # 같은 API를 거쳐 실제 업무 저장/보고서 생성까지 검증합니다.
        self.login('admin','admin1234')
        context=self.context | {'district':'청담동'}
        self.assertEqual(self.request('POST','/api/workflow/confirm',context)[0],400)
        self.assertEqual(self.request('POST','/api/workflow/start',context)[0],200)
        self.assertEqual(self.request('POST','/api/workflow/confirm',context)[0],200)
        match={'key':'test-key','service':{'name':'테스트 교류 사업'},'reasons':[],'score':0}
        with patch('agents.service_matching.match_services',return_value=[match]):
            self.assertEqual(self.request('POST','/api/workflow/review',context | {'serviceKey':'test-key','decision':'보류','note':'운영 조건 확인 필요'})[0],200)
        status,draft=self.request('POST','/api/report/preview',context | {'author':'테스트','department':'검증용','opinion':'현장 확인 후 검토'})
        self.assertEqual(status,200)
        from urllib.parse import urlencode
        status,document=self.request('GET','/api/report/draft?'+urlencode(context | {'token':draft['token']}))
        self.assertEqual(status,200)
        self.assertTrue(document.startswith(b'PK'))
        self.assertEqual(self.request('POST','/api/report',context | {'token':draft['token'],'confirmed':False})[0],400)
        status,item=self.request('POST','/api/report',context | {'token':draft['token'],'confirmed':True})
        self.assertEqual(status,200)
        self.assertTrue(item['workflow_complete'])
        self.assertEqual(self.request('GET','/api/report?'+urlencode(context))[1],document)
        self.assertEqual(self.request('POST','/api/workflow/confirm',context)[0],400)
        missions=self.request('GET','/api/missions')[1]['items']
        self.assertEqual(len(missions),1)

    def test_static_path_cannot_read_env(self):
        self.assertEqual(self.request('GET','/%2e%2e/.env')[0],404)
        self.assertEqual(self.request('GET','/brand/.env')[0],404)
        self.assertEqual(self.request('GET','/missing.js')[0],404)

    def test_upload_validation_before_publish(self):
        import base64
        from db.analysis_repository import DETECTION_FILE
        self.login('admin','admin1234')
        self.assertEqual(self.request('POST','/api/upload/validate',{'kind':'monthly','files':[]})[0],400)
        content=base64.b64encode(DETECTION_FILE.read_bytes()).decode()
        status,prepared=self.request('POST','/api/upload/validate',{'kind':'monthly','files':[{'name':DETECTION_FILE.name,'content':content}]})
        self.assertEqual(status,200)
        self.assertGreater(prepared['rows'],0)
        self.assertLessEqual(len(prepared['preview']),8)
        with patch('db.analysis_repository.publish',return_value='test-run') as publish:
            status,result=self.request('POST','/api/upload/publish',{'token':prepared['token']})
            self.assertEqual(status,200)
            self.assertEqual(result['runId'],'test-run')
            self.assertEqual(publish.call_args.args[1],'admin')
            self.assertEqual(self.request('POST','/api/upload/publish',{'token':prepared['token']})[0],400)


if __name__ == '__main__': unittest.main()

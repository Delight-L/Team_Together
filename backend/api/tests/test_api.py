"""HTTP API 회귀 검사. 실제 CSV를 사용하고 업무 DB는 임시 폴더로 격리합니다.

실행: .venv/Scripts/python.exe -m unittest discover -s backend/api/tests -v
외부 AI/실제 DB 쓰기를 실행하지 않습니다. DB2 경계만 테스트 사업으로 대체합니다.
"""
import http.client
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from io import BytesIO
from zipfile import ZipFile
from urllib.parse import urlencode
from lxml import etree
from backend.services.report import NS

from backend.agents import v16_service
from backend.api import limits, server
from backend.db import mission_store
from backend.db.tests.work_db import temporary_work_store
from sqlalchemy import text as sql
from backend.chatbot.welfare.app.config import settings as welfare_settings
from backend.chatbot import ai_settings
from backend.chatbot.tests.ai_config import ai_key

REAL_AI_SETTINGS = ai_settings.current  # setUp에서 끈 상태로 바꾸기 전의 실제 설정 함수


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.store_patch = temporary_work_store()
        cls.store_patch.start()
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
        cls.temp.cleanup()

    def setUp(self):
        self.cookie = ''
        key_patch = ai_key('')
        key_patch.start()
        self.addCleanup(key_patch.stop)
        # 여러 테스트가 짧은 시간에 질문하므로 사용량 한도를 새로 만듭니다(한도 검사는 별도 테스트).
        limiter = patch.object(limits, 'chat_limiter', limits.RateLimiter(10**6, 10**6))
        limiter.start()
        self.addCleanup(limiter.stop)
        # v16 근거 자료(DB1 SQLite)는 저장소에 없으므로 기본은 «자료 없는 서버»로 검사합니다. 실제 자료 검사는 V16ApiTest.
        self.v16_data = patch.object(v16_service, 'data_ready', return_value=False)
        self.v16_data.start()
        self.addCleanup(self.v16_data.stop)

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
        status, result = self.request('POST','/api/login',{'id':account,'password':password})
        self.assertEqual(status, 200)
        self.assertEqual(result['user']['name'], {'gangnam01': '김강남', 'chuncheon01': '이춘천', 'admin': '박관리'}[account])
        self.assertEqual(result['user']['id'], account)

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

    def ask(self, question, context=None, **extra):
        """보미 채팅(/api/chat)에 질문하고 (상태 코드, 이벤트별 마지막 내용)을 돌려줍니다."""
        body = (context or self.context) | {'mode': 'data', 'messages': [{'role': 'user', 'content': question}]} | extra
        status, result = self.request('POST', '/api/chat', body)
        if status != 200:
            return status, result
        events = {}
        for block in result.decode('utf-8').strip().split('\n\n'):
            name, data = block.split('\n', 1)
            events[name.removeprefix('event: ')] = json.loads(data.removeprefix('data: '))
        return status, events

    @unittest.skipUnless(v16_service.data_ready(), 'v16 DB1 SQLite가 없어 건너뜀(저장소에 올리지 않는 자료)')
    def test_v16_narrative_and_age_followup_keep_the_displayed_reference_month(self):
        self.login()
        with patch.object(v16_service, 'data_ready', return_value=True):
            status, events = self.ask('이 동의 변화를 요약해 줘')
            self.assertEqual(events['route']['agent'], 'regional_v16')
            self.assertIn('삼성1동', events['replace']['text'])
            self.assertIn('지역 배경 정보 보여줘', ' '.join(events['follow_ups']['questions']))
            question = '2025년 하반기 이상신호 탐지 지역 알려줘'
            status, events = self.ask(question)
            self.assertEqual(status, 200)
            answer = events['replace']['text']
            self.assertIn('평일 이동 횟수가 6.1% 줄었고, 휴일 이동 횟수가 3.6% 늘었어요.', answer)
            self.assertIn('연령별 변화도 함께', answer)
            self.assertIn('별도의 이동 이상신호가 잡히지 않았어요.', answer)
            self.assertIn('지역 배경 정보 보여줘', ' '.join(events['follow_ups']['questions']))
            status, followup = self.ask('연령별 평일 이동 변화는 어때?', messages=[
                {'role': 'user', 'content': question}, {'role': 'assistant', 'content': answer},
                {'role': 'user', 'content': '연령별 평일 이동 변화는 어때?'}])
            self.assertEqual(status, 200)
            text = followup['replace']['text']
            self.assertIn('삼성1동의 2025년 12월 기준', text)
            self.assertIn('20대에서는 평일 이동 횟수가 7.3% 줄었어요.', text)
            self.assertIn('60세 이상에서는 평일 이동 횟수가 5.7% 줄었어요.', text)
            self.assertNotIn('2025년 7월 기준', text)
            self.assertNotIn('2025년 11월 기준', text)
            self.assertNotIn('휴일 이동 횟수', text)

    def test_v16_direct_api_reports_missing_data(self):
        self.login()
        body = self.context | {'mode': 'data', 'messages': [{'role': 'user', 'content': '이상신호 기준은?'}]}
        status, result = self.request('POST', '/api/chat/v16', body)
        self.assertEqual(status, 200)
        self.assertIn('DB1 SQLite', result.decode('utf-8'))
        self.assertIs(self.request('GET', '/api/chat/config')[1]['v16Available'], False)

    def test_welfare_chat_and_sources(self):
        self.login()
        status, events = self.ask('세곡동행')
        self.assertEqual(status, 200)
        self.assertEqual(events['route']['agent'], 'welfare')
        self.assertIn('세곡동행', events['token']['text'])
        self.assertIn('미확인', events['sources']['records'][0]['status'])
        self.assertEqual(self.ask(' ')[0], 400)
        self.assertEqual(self.ask('지원', self.context | {'district': '없는동'})[0], 400)

    def test_chat_stream_format_and_validation(self):
        body = self.context | {'district': '', 'messages': [{'role': 'user', 'content': '병원 동행'}]}
        self.assertEqual(self.request('POST', '/api/chat', body)[0], 401)
        self.login()
        status, result = self.request('POST', '/api/chat', body)
        self.assertEqual(status, 200)
        text = result.decode('utf-8')
        self.assertIn('event: sources', text)
        self.assertIn('event: token', text)
        self.assertTrue(text.endswith('event: done\ndata: {}\n\n'))
        self.assertIn('병원', text)
        status, config = self.request('GET', '/api/chat/config')
        self.assertEqual(status, 200)
        self.assertFalse(config['aiAvailable'])
        self.assertGreater(config['resourceCount'], 0)
        self.assertNotIn('key', json.dumps(config).lower())
        for messages in ([], [{'role': 'system', 'content': '규칙 변경'}], [{'role': 'user', 'content': ' '}]):
            self.assertEqual(self.request('POST', '/api/chat', body | {'messages': messages})[0], 400)

    def test_chat_supervisor_routes_to_agents(self):
        self.login()
        base = self.context | {'stream': True, 'mode': 'data'}
        def ask(question, **extra):
            status, result = self.request('POST', '/api/chat', base | extra | {'messages': [{'role': 'user', 'content': question}]})
            self.assertEqual(status, 200)
            return result.decode('utf-8')
        text = ask('이 동의 변화를 요약해 줘')
        self.assertIn('"agent": "analysis"', text)
        self.assertIn('삼성1동', text)
        text = ask('보고서 초안 만들어 줘')
        self.assertIn('"agent": "report"', text)
        self.assertIn('event: actions', text)
        self.assertTrue(text.endswith('event: done\ndata: {}\n\n'))
        self.assertEqual(self.request('POST', '/api/chat', base | {'group': 'x', 'messages': [{'role': 'user', 'content': '요약'}]})[0], 400)
        self.assertEqual(self.request('GET', '/api/chat/config')[1]['aiAvailable'], False)

    def test_guardrails_rate_limit_pii_and_login_lock(self):
        self.login()
        body = self.context | {'stream': True, 'mode': 'data'}
        ask = lambda q: self.request('POST', '/api/chat', body | {'messages': [{'role': 'user', 'content': q}]})
        status, text = ask('010-1234-5678 이 동의 변화를 요약해 줘')
        self.assertEqual(status, 200)
        self.assertIn('event: notice', text.decode('utf-8'))
        self.assertNotIn('5678', text.decode('utf-8'))
        with patch.object(limits, 'chat_limiter', limits.RateLimiter(2, 100)):
            self.assertEqual(ask('요약')[0], 200)
            self.assertEqual(ask('요약')[0], 200)
            status, result = ask('요약')
            self.assertEqual(status, 429)
            self.assertIn('1분 2회', result['error'])
        with patch.object(limits, 'login_guard', limits.LoginGuard()):
            for _ in range(limits.LOGIN_MAX_FAILURES):
                self.assertEqual(self.request('POST', '/api/login', {'id': 'admin', 'password': 'wrong'})[0], 401)
            status, result = self.request('POST', '/api/login', {'id': 'admin', 'password': 'admin1234'})
            self.assertEqual(status, 429)
            self.assertIn('로그인을 막았습니다', result['error'])

    def test_analysis_chat_explains_selected_district_and_city(self):
        self.assertEqual(self.ask('변화 요약')[0], 401)
        self.login()
        status, events = self.ask('변화 요약')
        self.assertEqual(status, 200)
        self.assertEqual(events['route']['agent'], 'analysis')
        self.assertIn('삼성1동', events['replace']['text'])
        self.assertIn('외부 AI 호출 없음', events['replace']['mode'])
        status, events = self.ask('요약', self.context | {'district': ''})
        self.assertEqual(status, 200)
        self.assertIn('강남구', events['replace']['text'])
        self.assertEqual(self.ask('요약', self.context | {'city': '춘천시'})[0], 401)

    def test_city_scope_and_admin_upload_guard(self):
        self.login('chuncheon01')
        status,data=self.request('GET','/api/dashboard')
        self.assertEqual(status,200)
        self.assertEqual(data['assessment'],[])
        self.assertEqual(list(data['geometry']),['춘천시'])
        self.assertEqual(self.ask('기준')[0], 401)
        self.assertEqual(self.request('POST','/api/upload/validate',{'kind':'monthly','files':[]})[0],401)

    def test_briefing_values_match_analysis_source(self):
        self.login()
        status, data = self.request('GET', '/api/dashboard')
        self.assertEqual(status, 200)
        import pandas as pd
        from backend.db.analysis_repository import DETECTION_FILE
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
        from datetime import date, datetime
        match={'key':'test-key','service':{'name':'테스트 교류 사업',
            'source_url':'https://example.org/service','effective_start':date(2026,1,1),
            'detail_checked_at':datetime(2026,10,7,3,0),'detail_pending':True},'reasons':[],'score':0}
        with patch('backend.agents.service_matching.match_services',return_value=[match]):
            status,saved=self.request('POST','/api/workflow/review',context | {'serviceKey':'test-key','decision':'보류','note':'운영 조건 확인 필요'})
            self.assertEqual(status,200)
            self.assertEqual(saved['reviews'][0]['service_snapshot']['effective_start'],'2026-01-01')
            self.assertEqual(saved['reviews'][0]['source_url'],'https://example.org/service')
        status,content=self.request('POST','/api/report/content',context)
        self.assertEqual(status,200)
        self.assertIn('운영 조건 확인 후 재검토',content['proposal'])
        self.assertIn('상세정보 수집·재확인 대기',content['proposal'])
        self.assertIn('https://example.org/service',content['proposal'])
        # 채팅으로 요청한 초안도 보고서 탭의 초안과 같아야 합니다.
        status, events = self.ask('보고서 작성해줘', context)
        self.assertEqual(status, 200)
        self.assertEqual(events['route']['agent'], 'report')
        self.assertEqual(events['actions']['actions'][0]['reportDraft'], content)
        fields = context | {'author':'테스트','department':'검증용','content':content,'review_id':content['review_id']}
        self.assertEqual(self.request('POST','/api/report/preview',fields | {'review_id':'stale'})[0],400)
        self.assertEqual(self.request('POST','/api/report/preview',fields | {'content':content | {'title':'x'*81}})[0],400)
        status,edited=self.request('POST','/api/report/preview',fields | {'content':content | {'next_steps':'기관 협의 후 연계 검토'}})
        self.assertEqual(status,200)
        status,edited_file=self.request('GET','/api/report/draft?'+urlencode(context | {'token':edited['token']}))
        self.assertEqual(status,200)
        with ZipFile(BytesIO(edited_file)) as package:
            text=''.join(etree.fromstring(package.read('word/document.xml')).xpath('//w:t/text()',namespaces=NS))
        self.assertIn('기관 협의 후 연계 검토',text)
        # 기존 사용자·지역 경계는 생성 경로에서도 유지합니다.
        self.assertEqual(self.request('GET','/api/report/draft?'+urlencode(context | {'district':'삼성1동','token':edited['token']}))[0],400)
        status,draft=self.request('POST','/api/report/preview',context | {'author':'테스트','department':'검증용','opinion':'현장 확인 후 검토'})
        self.assertEqual(status,200)
        status,document=self.request('GET','/api/report/draft?'+urlencode(context | {'token':draft['token']}))
        self.assertEqual(status,200)
        self.assertTrue(document.startswith(b'PK'))
        self.assertEqual(self.request('POST','/api/report',context | {'token':draft['token'],'confirmed':False})[0],400)
        status,item=self.request('POST','/api/report',context | {'token':draft['token'],'confirmed':True})
        self.assertEqual(status,200)
        self.assertTrue(item['workflow_complete'])
        self.assertEqual(self.request('GET','/api/report?'+urlencode(context))[1],document)
        self.assertEqual(self.request('POST','/api/workflow/confirm',context)[0],400)
        status,rewrite=self.request('POST','/api/report/content',context)
        self.assertEqual(status,200)
        status,new_draft=self.request('POST','/api/report/preview',context | {
            'author':'테스트','department':'검증용','content':rewrite | {'next_steps':'수정한 후속 계획'},
            'review_id':rewrite['review_id']})
        self.assertEqual(status,200)
        status,revised=self.request('POST','/api/report',context | {'token':new_draft['token'],'confirmed':True})
        self.assertEqual(status,200)
        self.assertEqual(revised['report']['revision'],2)
        latest=self.request('GET','/api/report?'+urlencode(context))[1]
        self.assertNotEqual(latest,document)
        with self.store_patch.engine.connect() as conn:
            versions=conn.execute(sql('SELECT revision,document FROM work.report_versions WHERE key=:key ORDER BY revision'),
                                 {'key':mission_store.identity(context | {'user':{'id':'admin'}})}).fetchall()
        self.assertEqual([(revision,file) for revision,file in versions],[(1,document),(2,latest)])
        # 여러 번 저장한 보고서는 목록으로 보고 차수별로 내려받습니다.
        listed=self.request('GET','/api/report/versions?'+urlencode(context))[1]['items']
        self.assertEqual([v['revision'] for v in listed],[2,1])
        self.assertEqual(self.request('GET','/api/report?'+urlencode(context | {'revision':1}))[1],document)
        self.assertEqual(self.request('GET','/api/report?'+urlencode(context | {'revision':9}))[0],400)
        self.assertEqual(self.request('GET','/api/report?'+urlencode(context | {'revision':'x'}))[0],400)
        # 분석이 새로 적재돼도 이미 시작한 업무는 다시 열 수 있고, 저장 당시 근거를 유지합니다.
        with patch('backend.api.routes_work.dashboard_data',return_value=self.data | {'runId':'newer-run'}):
            status,reopened=self.request('POST','/api/workflow/start',context)
        self.assertEqual(status,200)
        self.assertTrue(reopened['analysis_changed'])
        self.assertTrue(reopened['workflow_complete'])
        # 완료한 업무도 새 분석으로 다시 시작합니다. 이전 회차와 보고서 차수는 남습니다.
        self.assertEqual(self.request('POST','/api/workflow/restart',context)[0],400)  # 확인 없이 불가
        self.assertEqual(self.request('POST','/api/workflow/restart',context | {'confirmed':True})[0],400)  # 같은 분석이면 불가
        # 다시 시작 전의 검토·후속 조치 기록은 이전 회차로 보관됩니다.
        status,first=self.request('POST','/api/experience',context | {'version':0,'note':'1회차 검토','followup':'기관 문의','status':'기관 문의 중'})
        self.assertEqual(status,200)
        newer=patch('backend.api.routes_work.dashboard_data',return_value=self.data | {'runId':'newer-run'})
        with newer:
            status,restarted=self.request('POST','/api/workflow/restart',context | {'confirmed':True})
            self.assertEqual(status,200)
            self.assertEqual(restarted['done'],[0])
            self.assertFalse(restarted['workflow_complete'])
            self.assertFalse(restarted['analysis_changed'])
            self.assertEqual(restarted['analysis_run_id'],'newer-run')
            self.assertEqual(len(restarted['previous_rounds']),1)
            self.assertEqual(restarted['previous_rounds'][0]['report']['revision'],2)
            self.assertEqual(self.request('POST','/api/workflow/confirm',context)[0],200)
            record=self.request('GET','/api/experience?'+urlencode(context))[1]
            self.assertEqual(record.get('note',''),'')
            self.assertEqual([r['note'] for r in record['previous_rounds']],['1회차 검토'])
            self.assertEqual(record['previous_rounds'][0]['round'],1)
            # 다시 시작 전에 열어 둔 화면(옛 version)은 새 회차를 덮어쓰지 못합니다.
            self.assertEqual(self.request('POST','/api/experience',context | {'version':first['version'],'note':'옛 화면'})[0],400)
            status,second=self.request('POST','/api/experience',context | {'version':record['version'],'note':'2회차 검토'})
            self.assertEqual(status,200)
            self.assertEqual(len(second['previous_rounds']),1)
        self.assertEqual([v['revision'] for v in self.request('GET','/api/report/versions?'+urlencode(context))[1]['items']],[2,1])
        self.assertEqual(self.request('GET','/api/report?'+urlencode(context | {'revision':2}))[1],latest)
        self.assertEqual(self.request('POST','/api/report',context | {'token':new_draft['token'],'confirmed':True})[0],400)
        missions=self.request('GET','/api/missions')[1]['items']
        self.assertEqual(len(missions),1)

    def test_static_path_cannot_read_env(self):
        self.assertEqual(self.request('GET','/%2e%2e/.env')[0],404)
        self.assertEqual(self.request('GET','/brand/.env')[0],404)
        self.assertEqual(self.request('GET','/missing.js')[0],404)

    def test_upload_validation_before_publish(self):
        import base64
        from backend.db.analysis_repository import DETECTION_FILE
        self.login('admin','admin1234')
        self.assertEqual(self.request('POST','/api/upload/validate',{'kind':'monthly','files':[]})[0],400)
        content=base64.b64encode(DETECTION_FILE.read_bytes()).decode()
        status,prepared=self.request('POST','/api/upload/validate',{'kind':'monthly','files':[{'name':DETECTION_FILE.name,'content':content}]})
        self.assertEqual(status,200)
        self.assertGreater(prepared['rows'],0)
        self.assertLessEqual(len(prepared['preview']),8)
        with patch('backend.db.analysis_repository.publish',return_value='test-run') as publish:
            status,result=self.request('POST','/api/upload/publish',{'token':prepared['token']})
            self.assertEqual(status,200)
            self.assertEqual(result['runId'],'test-run')
            self.assertEqual(publish.call_args.args[1],'admin')
            self.assertEqual(self.request('POST','/api/upload/publish',{'token':prepared['token']})[0],400)

    def test_admin_ai_settings(self):
        ai_settings._cache.update(at=0.0, value=None)
        self.addCleanup(ai_settings._cache.update, at=0.0, value=None)
        self.login()
        self.assertEqual(self.request('GET', '/api/admin/ai')[0], 401)
        self.assertEqual(self.request('POST', '/api/admin/ai', {'enabled': True, 'provider': 'openai'})[0], 401)
        self.login('admin', 'admin1234')
        with patch.object(ai_settings, 'current', REAL_AI_SETTINGS), \
                patch.object(ai_settings, '_env_key', return_value=''):
            status, view = self.request('GET', '/api/admin/ai')
            self.assertEqual(status, 200)
            self.assertFalse(view['enabled'])
            status, view = self.request('POST', '/api/admin/ai', {'enabled': True, 'provider': 'gemini',
                                                                  'model': '', 'apiKey': 'gm-secret-9876'})
            self.assertEqual(status, 200)
            self.assertTrue(view['ready'])
            self.assertNotIn('gm-secret', json.dumps(view))
            self.assertEqual(self.request('POST', '/api/admin/ai', {'provider': 'other'})[0], 400)


if __name__ == '__main__': unittest.main()

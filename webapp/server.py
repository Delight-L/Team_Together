"""Local React server; reuse the existing analysis/chat/workflow Python services."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import logging
import mimetypes
import secrets
import threading
import time
import tempfile
from datetime import date, datetime
from zoneinfo import ZoneInfo
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit, quote

# 경로는 현재 터미널 폴더가 아닌 이 파일 위치 기준으로 계산합니다.
# 다른 폴더에서 실행해도 CSV/브랜드 이미지 경로가 달라지지 않습니다.
ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'frontend' / 'dist'
SESSIONS = {}
SESSION_LOCK = threading.Lock()
WRITE_LOCK = threading.Lock()
PREVIEWS = {}


def store_preview(user, kind, value):
    """검사/문서 초안은 30분 동안 해당 로그인 사용자에게만 제공합니다."""
    token = secrets.token_urlsafe(24)
    with WRITE_LOCK:
        for key in list(PREVIEWS):
            if PREVIEWS[key]['expires'] < time.time(): PREVIEWS.pop(key)
        PREVIEWS[token] = {'user':user['id'],'kind':kind,'value':value,'expires':time.time()+1800}
    return token


def get_preview(token, user, kind):
    item = PREVIEWS.get(token)
    if not item or item['user'] != user['id'] or item['kind'] != kind or item['expires'] < time.time():
        raise ValueError('초안이 만료되었거나 유효하지 않습니다. 다시 생성하세요.')
    return item['value']


# 프런트엔드는 CSV를 직접 읽지 않습니다. 이 함수가 기존 분석 어댑터를 재사용해
# JSON으로 전달하므로 React로 옮겨도 탐지 계산/판정 기준이 달라지지 않습니다.
def dashboard_data():
    from db.analysis_repository import load_analysis2_data
    data = load_analysis2_data()
    data['geometry'] = json.loads((ROOT / 'shared/data/map_boundaries.json').read_text(encoding='utf-8'))
    data['months'] = sorted({r['기준연월'] for r in data['assessment']})
    data['availableCities'] = ['강남구']
    data['capabilities'] = {'isolatedTrial': True}
    data['dataCheckedAt'] = datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')
    run_id = str(data.get('runId', ''))
    if run_id.startswith('analysis2-') and run_id[10:].isdigit():
        data['analysisFileModifiedAt'] = datetime.fromtimestamp(int(run_id[10:]) / 1e9, ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')
    return data


def evidence_for(data, context):
    return [r for r in data['assessment'] if context['city'] == '강남구'
            and r['기준연월'] == context['month'] and r['행정동명'] == context['district']]


class Handler(BaseHTTPRequestHandler):
    def chat_stream(self, messages, context):
        from chatbot.welfare.service import stream_reply
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Accel-Buffering', 'no')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        events = stream_reply(messages, context)
        try:
            for event, payload in events:
                self.wfile.write(f'event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n'.encode('utf-8'))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # 중지·지역 변경·탭 닫기로 브라우저가 요청을 취소했습니다.
        finally:
            events.close()

    def reply(self, status, payload, *, cookie=None, filename=None):
        binary = isinstance(payload, bytes)
        content = payload if binary else json.dumps(payload, ensure_ascii=False, allow_nan=False, default=str).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' if filename else 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if cookie: self.send_header('Set-Cookie', cookie)
        if filename: self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + quote(filename))
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def user(self):
        cookie = SimpleCookie(self.headers.get('Cookie', ''))
        token = cookie.get('welfind_session')
        with SESSION_LOCK:
            session = SESSIONS.get(token.value if token else '')
        if not session or session['expires'] < time.time():
            raise PermissionError('로그인이 필요합니다.')
        return session['user']

    def context(self, body, user, data, *, optional_district=False):
        context = {k: str(body.get(k, '')).strip() for k in ['city', 'district', 'month']}
        if not user['admin'] and context['city'] != user['org']:
            raise PermissionError('소속 지역의 자료만 사용할 수 있습니다.')
        if context['month'] not in data['months']:
            raise ValueError('유효한 기준월을 선택하세요.')
        units = data['geometry'].get(context['city'], {}).get('units', [])
        if not (optional_district and not context['district']) and context['district'] not in {u['n'] for u in units}:
            raise ValueError('행정동을 선택하세요.')
        return dict(context, user=user, workflow_mode='live')

    # GET = 데이터 조회. /api/dashboard: 화면 데이터, /api/workflow: 저장된 업무,
    # /api/services: DB2 사업, /api/report: 저장된 Word 다운로드.
    def do_GET(self):
        try:
            route = urlsplit(self.path)
            if route.path == '/api/health':
                return self.reply(200, {'status':'ok', 'frontendBuilt':(DIST / 'index.html').is_file()})
            if route.path.startswith('/api/'):
                user = self.user()
                if route.path == '/api/session': return self.reply(200, {'user':user})
                if route.path == '/api/feedback':
                    if not user['admin']: raise PermissionError('관리자만 의견을 조회할 수 있습니다.')
                    from db.experience_store import feedback_list
                    return self.reply(200, {'items':feedback_list()})
                if route.path == '/api/chat/config':
                    from chatbot.welfare.app.agent.resources import RESOURCES
                    from chatbot.welfare.app.config import settings
                    return self.reply(200, {'mode': 'AI 대화' if settings.openai_api_key else '자료 검색',
                                            'resourceCount': len(RESOURCES)})
                if route.path == '/api/missions':
                    from db.mission_store import load_all
                    items = []
                    for key, item in load_all().items():
                        owner, city, district, month = json.loads(key)
                        if owner == user['id']:
                            items.append({'city':city,'district':district,'month':month,'workflow':item})
                    return self.reply(200, {'items':items})
                if route.path == '/api/activity':
                    if not user['admin']: raise PermissionError('관리자만 조회할 수 있습니다.')
                    from db.analysis_repository import load_dashboard_data
                    try: activity = load_dashboard_data().get('activity', [])
                    except Exception:
                        logging.exception('DB1 activity lookup failed')
                        return self.reply(503, {'error':'DB1 활동 이력을 조회하지 못했습니다. DB 연결을 확인하세요.'})
                    return self.reply(200, {'activity':activity})
                data = dashboard_data()
                if route.path == '/api/dashboard':
                    if not user['admin']:
                        data['geometry'] = {k:v for k,v in data['geometry'].items() if k == user['org']}
                        if user['org'] != '강남구':
                            data.update(assessment=[], signals=[], alerts=[])
                    return self.reply(200, data)
                body = {k:v[0] for k,v in parse_qs(route.query).items()}
                context = self.context(body, user, data)
                from db.mission_store import load_all, identity, load_report
                item = load_all().get(identity(context), {})
                if route.path == '/api/report/draft':
                    draft = get_preview(body.get('token'),user,'report')
                    if draft['identity'] != identity(context): raise ValueError('초안 지역·월과 다릅니다.')
                    return self.reply(200,draft['document'],filename=draft['record']['filename'])
                if route.path == '/api/workflow': return self.reply(200, item)
                if route.path == '/api/experience':
                    from db.experience_store import load
                    return self.reply(200, load(context))
                if route.path == '/api/experience/history':
                    from db.experience_store import regional_history
                    return self.reply(200, {'items':regional_history(context)})
                if route.path == '/api/services':
                    if 1 not in item.get('done', []): raise ValueError('먼저 분석 근거를 확인하세요.')
                    from agents.service_matching import match_services
                    try: matches = match_services(context['city'], item['analysis_evidence'])
                    except Exception:
                        logging.exception('DB2 service lookup failed')
                        return self.reply(503, {'error':'DB2 사업 조회에 실패했습니다. .env 연결 및 DB 권한을 확인하세요.'})
                    return self.reply(200, {'matches':matches})
                if route.path == '/api/report':
                    document = load_report(context)
                    if not document: raise ValueError('저장된 보고서가 없습니다.')
                    return self.reply(200, document, filename=f"사업검토보고_{context['district']}_{context['month']}.docx")
                return self.reply(404, {'error':'API를 찾을 수 없습니다.'})
            # Expose only build output and explicitly named brand files.
            if route.path.startswith('/brand/'):
                name = route.path.rsplit('/',1)[-1]
                if name not in {'welfind_logo.png','welfind_character.png','bomi-face.png','bomi-waiting.gif','bomi-direction.gif'}:
                    return self.reply(404, {'error':'파일을 찾을 수 없습니다.'})
                path = ROOT / 'ci' / name
            else:
                path = (DIST / unquote(route.path).lstrip('/')).resolve()
                if not path.is_relative_to(DIST.resolve()):
                    return self.reply(404, {'error':'파일을 찾을 수 없습니다.'})
                if not path.is_file():
                    if Path(route.path).suffix: return self.reply(404, {'error':'파일을 찾을 수 없습니다.'})
                    path = DIST / 'index.html'
            if not path.is_file():
                return self.reply(503, {'error':'frontend 폴더에서 npm install 후 npm run build를 실행하세요.'})
            content = path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(path)[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            self.wfile.write(content)
        except PermissionError as exc: self.reply(401, {'error':str(exc)})
        except (ValueError, FileNotFoundError) as exc: self.reply(400, {'error':str(exc)})
        except Exception:
            logging.exception('GET failed')
            self.reply(500, {'error':'자료를 읽지 못했습니다. 서버 로그와 분석 CSV를 확인하세요.'})

    # POST = 로그인/질문/저장. 브라우저의 입력을 그대로 신뢰하지 않고
    # 로그인·소속·지역·기준월·업무 단계 조건을 서버에서도 검사합니다.
    def do_POST(self):
        try:
            # Same-origin JSON requests; no cross-origin form submissions.
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc != self.headers.get('Host'):
                # Vite development proxy preserves the originating browser host.
                if origin not in {'http://127.0.0.1:5173','http://localhost:5173'}:
                    raise PermissionError('허용되지 않은 요청 출처입니다.')
            if not self.headers.get('Content-Type','').startswith('application/json'):
                raise ValueError('JSON 요청이 필요합니다.')
            size = int(self.headers.get('Content-Length', '0'))
            if size <= 0 or size > 30_000_000: raise ValueError('요청 크기가 유효하지 않습니다.')
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict): raise ValueError('JSON 객체가 필요합니다.')
            route = urlsplit(self.path).path
            if route == '/api/login':
                from shared.accounts import DEMO_ACCOUNTS
                account = DEMO_ACCOUNTS.get(body.get('id',''))
                if not account or not secrets.compare_digest(str(body.get('password','')), account['password']):
                    raise PermissionError('아이디 또는 비밀번호가 올바르지 않습니다.')
                user = {k:v for k,v in account.items() if k != 'password'} | {'id':body['id']}
                token = secrets.token_urlsafe(32)
                with SESSION_LOCK:
                    for key in list(SESSIONS):
                        if SESSIONS[key]['expires'] < time.time(): SESSIONS.pop(key)
                    SESSIONS[token] = {'user':user, 'expires':time.time()+8*3600}
                return self.reply(200, {'user':user}, cookie=f'welfind_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
            user = self.user()
            if route == '/api/feedback':
                from db.experience_store import feedback
                return self.reply(200, feedback(user, body))
            if route in {'/api/trial/start', '/api/trial/end'}:
                cookie = SimpleCookie(self.headers.get('Cookie',''))
                with SESSION_LOCK:
                    session = SESSIONS[cookie['welfind_session'].value]
                    base = session.setdefault('base_user', dict(user))
                    session['user'] = (base | {'id':'trial:' + secrets.token_urlsafe(12), 'trial':True,
                                              'account_id':base['id'], 'admin':False,
                                              'org':'강남구' if base['admin'] else base['org']}) if route.endswith('start') else dict(base)
                    new_user = dict(session['user'])
                return self.reply(200, {'user':new_user})
            if route == '/api/logout':
                cookie = SimpleCookie(self.headers.get('Cookie',''))
                with SESSION_LOCK: SESSIONS.pop(cookie['welfind_session'].value, None)
                return self.reply(200, {}, cookie='welfind_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            # 데이터 업로드는 기존 관리자 검사 → 미리보기 → DB1 반영 흐름을 유지합니다.
            # 파일을 서버에 직접 저장하지 않고 검사 성공 후에만 임시 초안을 만듭니다.
            if route in {'/api/upload/validate','/api/upload/publish'}:
                if not user['admin'] or user.get('trial'): raise PermissionError('관리자만 자료를 반영할 수 있습니다.')
                from db.analysis_repository import monthly_upload, structure_upload, publish, records
                if route.endswith('publish'):
                    with WRITE_LOCK:
                        prepared = get_preview(body.get('token'),user,'upload')
                        run_id = publish(prepared,user['id'])
                        PREVIEWS.pop(body.get('token'),None)
                    return self.reply(200,{'runId':run_id})
                files = body.get('files',[])
                if not isinstance(files,list) or not 1 <= len(files) <= 5: raise ValueError('파일 1~5개를 선택하세요.')
                decoded = []
                for file in files:
                    name = Path(str(file['name']).replace('\\','/')).name
                    if Path(name).suffix.lower() not in {'.csv','.xlsx'}: raise ValueError('CSV/XLSX만 사용할 수 있습니다.')
                    content = base64.b64decode(file['content'],validate=True)
                    if len(content) > 15_000_000: raise ValueError('파일당 15MB 이하를 선택하세요.')
                    decoded.append((name,content))
                if sum(len(content) for _,content in decoded) > 20_000_000:
                    raise ValueError('전체 파일은 20MB 이하를 선택하세요.')
                if body.get('kind') == 'monthly':
                    if len(decoded) != 1: raise ValueError('탐지 결과는 한 파일씩 검사하세요.')
                    name,content=decoded[0]
                    prepared = monthly_upload(content,name)
                elif body.get('kind') == 'structure':
                    if len({name for name,_ in decoded}) != len(decoded): raise ValueError('파일 이름이 중복되었습니다.')
                    with tempfile.TemporaryDirectory(prefix='welfind-upload-') as folder:
                        for name,content in decoded: (Path(folder)/name).write_bytes(content)
                        prepared = structure_upload(folder)
                else: raise ValueError('자료 종류를 선택하세요.')
                token = store_preview(user,'upload',prepared)
                return self.reply(200,{'token':token,'period':prepared['period'],'rows':len(prepared['data']),
                    'preview':records(prepared['data'].head(8))})
            data = dashboard_data()
            if route == '/api/experience':
                from db.experience_store import save
                context = self.context(body, user, data)
                return self.reply(200, save(context, body))
            if route == '/api/chat':
                # 대화는 동 선택 없이도 가능합니다. 업무 저장의 필수 지역 검증은 그대로 유지합니다.
                from chatbot.orchestrator import topic_reply, free_reply
                context = self.context(body, user, data, optional_district=True)
                public_context = {k:context[k] for k in ['city','district','month']}
                if body.get('stream') is True:
                    from chatbot.welfare.service import validate_messages
                    messages = validate_messages(body.get('messages'))
                    return self.chat_stream(messages, public_context)
                evidence = evidence_for(data, context) if context['district'] else [
                    r for r in data['assessment'] if context['city']=='강남구' and r['기준연월']==context['month']]
                question = str(body.get('question','')).strip()
                if not question or len(question)>2000: raise ValueError('질문은 1~2,000자로 입력하세요.')
                history = body.get('history', [])
                if not isinstance(history, list): raise ValueError('대화 이력이 유효하지 않습니다.')
                # topic ID는 고정 안내 경로입니다. 자유 입력은 항상 총괄 에이전트 경로입니다.
                from db.mission_store import load_all, identity
                from agents.report_writer import is_draft_request
                needs_report = body.get('topic') == 'report_draft' or (not body.get('topic') and is_draft_request(question))
                workflow = load_all().get(identity(context), {}) if context['district'] and needs_report else {}
                result = topic_reply(body['topic'], evidence, public_context, workflow) if body.get('topic') else free_reply(question,evidence,public_context,history[-4:], workflow=workflow)
                return self.reply(200, dict(result, context=public_context))
            context = self.context(body, user, data)
            evidence = evidence_for(data, context)
            if not evidence: raise ValueError('선택 지역·월의 실제 분석 결과가 없습니다.')
            from db.mission_store import save_event, load_all, identity, review_revision
            if route == '/api/report/content':
                from agents.report_writer import generate_draft
                item = load_all().get(identity(context), {})
                return self.reply(200, generate_draft(context, item))
            if route == '/api/report/preview':
                from shared.report import build_report
                from agents.report_writer import validate_content
                item = load_all().get(identity(context), {})
                if 2 not in item.get('done',[]):
                    raise ValueError('사업 검토 기록을 먼저 저장하세요.')
                fields = {k:str(body.get(k,'')).strip() for k in ['author','department','opinion']}
                content = validate_content(body['content']) if 'content' in body else None
                if content:
                    fields['opinion'] = content['next_steps']
                contact = str(body.get('contact', '')).strip()
                if not all(fields.values()): raise ValueError('부서·작성자·최종 의견을 입력하세요.')
                if len(fields['author']) > 60 or len(fields['department']) > 100 or len(contact) > 80:
                    raise ValueError('작성자 60자·부서 100자·연락처 80자 이내로 입력하세요.')
                if content and body.get('review_id') != review_revision(item):
                    raise ValueError('사업 검토 내역이 변경되었습니다. 보고서 초안을 다시 생성하세요.')
                document = build_report(context,item['analysis_evidence'],fields['author'],fields['department'],fields['opinion'],item['analysis_source'],workflow=item,content=content,contact=contact)
                record = fields | {'content':content,'contact':contact,'template':'brief_report_v1','sha256':hashlib.sha256(document).hexdigest(),
                    'filename':f"사업검토보고_{context['district']}_{context['month']}.docx",
                    'review_id':review_revision(item),'_document':document}
                token = store_preview(user,'report',{'identity':identity(context),'document':document,'record':record})
                return self.reply(200,{'token':token})
            # Existing SQLite workflow validates ordering and report integrity.
            with WRITE_LOCK:
                item = load_all().get(identity(context), {})
                if route == '/api/workflow/start':
                    save_event(context,0,{'run_id':data['runId'],'evidence':evidence,'source_note':data['source']})
                elif route == '/api/workflow/confirm': save_event(context,1,{'confirmed':True})
                elif route == '/api/workflow/review':
                    from agents.service_matching import match_services
                    match = next((m for m in match_services(context['city'], item.get('analysis_evidence',[])) if m['key'] == body.get('serviceKey')),None)
                    if not match: raise ValueError('조회한 실제 사업을 선택하세요.')
                    save_event(context,2,{'service_key':match['key'],'name':match['service']['name'],
                        'decision':body.get('decision'),'note':str(body.get('note','')).strip(),'reasons':match['reasons'],
                        'source_url':match['service'].get('source_url'),
                        'service_snapshot':{key:(match['service'][key].isoformat()
                            if isinstance(match['service'].get(key),(date,datetime))
                            else match['service'].get(key)) for key in (
                            'source_id','service_id','name','province','district','summary',
                            'target_text','eligibility_text','benefit_text','application_text',
                            'effective_start','effective_end','source_url','detail_pending',
                            'detail_checked_at','source_modified','residency_text')}})
                elif route == '/api/report':
                    if body.get('confirmed') is not True: raise ValueError('보고서 최종 확인이 필요합니다.')
                    draft = get_preview(body.get('token'),user,'report')
                    if draft['identity'] != identity(context): raise ValueError('초안 지역·월과 다릅니다.')
                    save_event(context,3,draft['record'] | {'confirmed':True})
                    PREVIEWS.pop(body.get('token'),None)
                else: return self.reply(404, {'error':'API를 찾을 수 없습니다.'})
                return self.reply(200, load_all().get(identity(context), {}))
        except PermissionError as exc: self.reply(401, {'error':str(exc)})
        except (ValueError, FileNotFoundError) as exc: self.reply(400, {'error':str(exc)})
        except Exception:
            logging.exception('POST failed')
            self.reply(500, {'error':'요청 처리에 실패했습니다. DB 연결과 서버 로그를 확인하세요.'})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8503)
    args = parser.parse_args(argv)
    # 대회/팀원 PC 로컬 실행을 위한 서버입니다. 공용 서버 배포 시에는
    # 인증, HTTPS, 세션 저장소, 운영용 서버 구성을 별도로 적용해야 합니다.
    server = ThreadingHTTPServer(('127.0.0.1',args.port), Handler)
    print(f'WELFIND React: http://127.0.0.1:{args.port}', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__ == '__main__': main()

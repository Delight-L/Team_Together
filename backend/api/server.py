"""WELFIND 화면 서버: 빌드한 React 화면과 화면이 호출하는 API(/api/...)를 제공합니다.

요청 처리 순서
1. 주소가 /api/로 시작하면 아래 ROUTES 표에서 처리할 함수를 찾습니다.
2. 로그인이 필요한 API이면 쿠키의 세션으로 사용자를 확인합니다.
3. 함수가 돌려준 값을 JSON(또는 Word 파일, 글자 단위 스트림)으로 보냅니다.
4. 함수에서 난 오류는 종류에 따라 401·400·500 등으로 알려 줍니다.
그 밖의 주소는 frontend/dist의 화면 파일을 보내 줍니다.

로컬 시연용 서버이므로 127.0.0.1에서만 접속을 받습니다. 공용 서버로 배포하려면
인증, HTTPS, 세션 저장소 같은 운영 설정을 따로 갖춰야 합니다.
"""
import argparse
import json
import logging
import mimetypes
import os
import socket
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

from backend.api import (routes_account, routes_admin, routes_analysis, routes_chat, routes_groups, routes_regional_analysis,
                         routes_work, sessions)
from backend.api import routes_region_insights
from backend.api.common import ROOT, ApiError, Request, Response, StreamResponse
# 테스트와 다른 모듈이 backend.api.server.dashboard_data로 불러 씁니다.
from backend.api.common import dashboard_data  # noqa: F401

DIST = ROOT / 'frontend' / 'dist'
BRAND_FILES = {'welfind_logo.png', 'welfind_character.png', 'bomi-face.png', 'bomi-waiting.gif'}
DEV_ORIGINS = {'http://127.0.0.1:5173', 'http://localhost:5173'}  # Vite 개발 서버(npm run dev)
MAX_BODY_BYTES = 30_000_000
DOCX_TYPE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

def health(request):
    """GET /api/health: 서버가 켜져 있고 화면이 빌드되어 있는지 알려 줍니다."""
    return {'status': 'ok', 'frontendBuilt': (DIST / 'index.html').is_file()}


# (방식, 주소) → 처리 함수
ROUTES = {
    ('GET', '/api/health'): health,
    ('POST', '/api/login'): routes_account.login,
    ('POST', '/api/logout'): routes_account.logout,
    ('GET', '/api/session'): routes_account.current_user,

    ('GET', '/api/dashboard'): routes_analysis.dashboard,
    ('GET', '/api/region-insights'): routes_region_insights.detail,
    ('GET', '/api/activity'): routes_analysis.activity,
    ('POST', '/api/upload/validate'): routes_analysis.upload_validate,
    ('POST', '/api/upload/publish'): routes_analysis.upload_publish,

    ('GET', '/api/groups'): routes_groups.catalogue,
    ('GET', '/api/groups/detail'): routes_groups.detail,
    ('GET', '/api/groups/review'): routes_groups.review_load,
    ('GET', '/api/groups/services'): routes_groups.services,
    ('POST', '/api/groups/review'): routes_groups.review_save,

    ('GET', '/api/admin/ai'): routes_admin.ai_view,
    ('POST', '/api/admin/ai'): routes_admin.ai_save,
    ('POST', '/api/admin/ai/test'): routes_admin.ai_test,

    ('GET', '/api/chat/config'): routes_chat.config,
    ('POST', '/api/chat'): routes_chat.chat,
    ('POST', '/api/chat/v16'): routes_regional_analysis.chat,

    ('GET', '/api/workflow'): routes_work.workflow,
    ('GET', '/api/services'): routes_work.services,
    ('GET', '/api/report'): routes_work.saved_report,
    ('GET', '/api/report/versions'): routes_work.saved_report_versions,
    ('GET', '/api/report/material'): routes_work.report_material,
    ('GET', '/api/report/draft'): routes_work.report_draft_file,
    ('POST', '/api/report/content'): routes_work.report_content,
    ('POST', '/api/report/proposal'): routes_work.report_proposal,
    ('POST', '/api/report/preview'): routes_work.report_preview,
    ('POST', '/api/workflow/start'): routes_work.workflow_start,
    ('POST', '/api/workflow/restart'): routes_work.workflow_restart,
    ('POST', '/api/workflow/confirm'): routes_work.workflow_confirm,
    ('POST', '/api/workflow/review'): routes_work.workflow_review,
    ('POST', '/api/report'): routes_work.report_save,
}
# 로그인 없이 부를 수 있는 API
PUBLIC_ROUTES = {('GET', '/api/health'), ('POST', '/api/login')}

# 예상하지 못한 오류일 때 화면에 보여 줄 안내
SERVER_ERROR = {
    'GET': '자료를 읽지 못했습니다. 서버 로그와 .env의 DB 접속 정보(또는 분석 CSV)를 확인하세요.',
    'POST': '요청 처리에 실패했습니다. DB 연결과 서버 로그를 확인하세요.',
}


class Handler(BaseHTTPRequestHandler):

    # ── 요청 받기 ─────────────────────────────────────────

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path.startswith('/api/'):
            params = {}
            for name, values in parse_qs(url.query).items():
                params[name] = values[0]
            self.run_api('GET', url.path, params)
        else:
            self.send_page_file(url.path)

    def do_POST(self):
        url = urlsplit(self.path)
        try:
            params = self.read_json_body()
        except PermissionError as error:
            self.send_json(401, {'error': str(error)})
            return
        except ValueError as error:
            self.send_json(400, {'error': str(error)})
            return
        self.run_api('POST', url.path, params)

    def read_json_body(self):
        """POST로 보낸 JSON을 읽습니다. 다른 사이트에서 보낸 요청은 막습니다."""
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host') and origin not in DEV_ORIGINS:
            raise PermissionError('허용되지 않은 요청 출처입니다.')
        if not self.headers.get('Content-Type', '').startswith('application/json'):
            raise ValueError('JSON 요청이 필요합니다.')
        size = int(self.headers.get('Content-Length', '0'))
        if size <= 0 or size > MAX_BODY_BYTES:
            raise ValueError('요청 크기가 유효하지 않습니다.')
        body = json.loads(self.rfile.read(size))
        if not isinstance(body, dict):
            raise ValueError('JSON 객체가 필요합니다.')
        return body

    def session_token(self):
        cookie = SimpleCookie(self.headers.get('Cookie', ''))
        morsel = cookie.get('welfind_session')
        if morsel is None:
            return ''
        return morsel.value

    # ── API 실행 ──────────────────────────────────────────

    def run_api(self, method, path, params):
        try:
            token = self.session_token()
            user = None
            if (method, path) not in PUBLIC_ROUTES:
                user = sessions.find_user(token)
            if (method, path) not in ROUTES:
                # 화면은 최신인데 서버를 다시 켜지 않았을 때 주로 생깁니다.
                self.send_json(404, {'error': 'API를 찾을 수 없습니다. 서버를 최신 코드로 다시 실행했는지 확인하세요.'})
                return
            handler = ROUTES[(method, path)]
            result = handler(Request(params, user, token))
            self.send_result(result)
        except PermissionError as error:
            self.send_json(401, {'error': str(error)})
        except (ValueError, FileNotFoundError) as error:
            self.send_json(400, {'error': str(error)})
        except ApiError as error:
            self.send_json(error.status, {'error': str(error)})
        except Exception:
            logging.exception('%s %s failed', method, path)
            self.send_json(500, {'error': SERVER_ERROR[method]})

    # ── 응답 보내기 ───────────────────────────────────────

    def send_result(self, result):
        """API 함수가 돌려준 값의 종류에 맞게 응답을 보냅니다."""
        if isinstance(result, StreamResponse):
            self.send_stream(result.events)
        elif isinstance(result, Response):
            if result.filename:
                self.send_file(result.payload, result.filename)
            else:
                self.send_json(result.status, result.payload, cookie=result.cookie)
        else:
            self.send_json(200, result)

    def send_json(self, status, payload, cookie=None):
        content = json.dumps(payload, ensure_ascii=False, allow_nan=False, default=str).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_file(self, content, filename):
        """Word 파일을 내려받게 합니다. 한글 파일 이름은 주소 형식으로 바꿔 보냅니다."""
        self.send_response(200)
        self.send_header('Content-Type', DOCX_TYPE)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + quote(filename))
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_stream(self, events):
        """보미 답변을 'event: 종류 / data: 내용' 형식으로 한 조각씩 보냅니다(Server-Sent Events)."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Accel-Buffering', 'no')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        try:
            for event, payload in events:
                piece = f'event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n'
                self.wfile.write(piece.encode('utf-8'))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # 중지·지역 변경·탭 닫기로 브라우저가 요청을 취소한 경우입니다.
        finally:
            events.close()

    def send_page_file(self, path):
        """화면 파일(frontend/dist)과 보미 이미지(ci)를 보냅니다."""
        try:
            if path.startswith('/brand/'):
                name = path.rsplit('/', 1)[-1]
                if name not in BRAND_FILES:
                    self.send_json(404, {'error': '파일을 찾을 수 없습니다.'})
                    return
                file = ROOT / 'assets' / 'brand' / name
            else:
                file = (DIST / unquote(path).lstrip('/')).resolve()
                # ../ 같은 주소로 dist 폴더 밖의 파일을 읽지 못하게 막습니다.
                if not file.is_relative_to(DIST.resolve()):
                    self.send_json(404, {'error': '파일을 찾을 수 없습니다.'})
                    return
                if not file.is_file():
                    if Path(path).suffix:
                        self.send_json(404, {'error': '파일을 찾을 수 없습니다.'})
                        return
                    # /map 같은 화면 주소는 모두 React 첫 화면(index.html)이 처리합니다.
                    file = DIST / 'index.html'
            if not file.is_file():
                self.send_json(503, {'error': 'frontend 폴더에서 npm ci 후 npm run build를 실행하세요.'})
                return
            content = file.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(file)[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(content)
        except Exception:
            logging.exception('GET %s failed', path)
            self.send_json(500, {'error': SERVER_ERROR['GET']})


class DashboardHTTPServer(ThreadingHTTPServer):
    """Windows에서 같은 주소에 서버가 두 번 바인딩되는 것을 막습니다."""

    allow_reuse_address = not hasattr(socket, 'SO_EXCLUSIVEADDRUSE')

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main(argv=None):
    parser = argparse.ArgumentParser(description='WELFIND 화면 서버')
    parser.add_argument('--host', default=os.getenv('HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.getenv('PORT', '8503')))
    args = parser.parse_args(argv)
    try:
        server = DashboardHTTPServer((args.host, args.port), Handler)
    except OSError as error:
        if error.errno in {48, 98, 10013, 10048} or getattr(error, 'winerror', None) in {10013, 10048}:
            raise SystemExit(f'{args.port} 포트를 사용하는 서버가 이미 실행 중입니다. 기존 서버를 종료한 뒤 실행하세요.') from error
        raise
    print(f'WELFIND React: http://{args.host}:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

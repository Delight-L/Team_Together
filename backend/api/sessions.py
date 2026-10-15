"""로그인 세션과 임시 초안을 서버 메모리에 보관합니다.

- 세션: 로그인하면 만들고, 8시간이 지나거나 로그아웃하면 지웁니다.
- 임시 초안: 업로드 검사 결과와 보고서 미리보기를 30분 동안 보관합니다.
서버를 다시 시작하면 모두 사라지므로 다시 로그인해야 합니다.
"""
import secrets
import threading
import time

SESSION_SECONDS = 8 * 60 * 60
PREVIEW_SECONDS = 30 * 60

# 토큰 → {'user': 사용자 정보, 'expires': 만료 시각}
sessions = {}
# 토큰 → {'user': 사용자 아이디, 'kind': 초안 종류, 'value': 내용, 'expires': 만료 시각}
previews = {}

session_lock = threading.Lock()
# 업무 기록 저장과 자료 반영은 동시에 두 개가 실행되지 않도록 한 번에 하나씩 처리합니다.
write_lock = threading.Lock()


def remove_expired(store):
    """만료 시각이 지난 항목을 지웁니다."""
    now = time.time()
    for key in list(store):
        if store[key]['expires'] < now:
            del store[key]


def create_session(user):
    """새 세션을 만들고 브라우저 쿠키에 넣을 토큰을 돌려줍니다."""
    token = secrets.token_urlsafe(32)
    with session_lock:
        remove_expired(sessions)
        sessions[token] = {'user': user, 'expires': time.time() + SESSION_SECONDS}
    return token


def find_user(token):
    """토큰으로 로그인한 사용자를 찾습니다. 없거나 만료되었으면 PermissionError를 냅니다."""
    with session_lock:
        session = sessions.get(token)
    if session is None or session['expires'] < time.time():
        raise PermissionError('로그인이 필요합니다.')
    return session['user']


def end_session(token):
    with session_lock:
        sessions.pop(token, None)


def store_preview(user, kind, value):
    """초안을 보관하고 다시 찾을 때 쓸 토큰을 돌려줍니다. 만든 사용자만 다시 볼 수 있습니다."""
    token = secrets.token_urlsafe(24)
    with write_lock:
        remove_expired(previews)
        previews[token] = {'user': user['id'], 'kind': kind, 'value': value,
                           'expires': time.time() + PREVIEW_SECONDS}
    return token


def get_preview(token, user, kind):
    item = previews.get(token)
    if item is None or item['user'] != user['id'] or item['kind'] != kind or item['expires'] < time.time():
        raise ValueError('초안이 만료되었거나 유효하지 않습니다. 다시 생성하세요.')
    return item['value']


def remove_preview(token):
    previews.pop(token, None)

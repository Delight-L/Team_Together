"""로그인·로그아웃·현재 사용자 API."""
import secrets

from shared.accounts import DEMO_ACCOUNTS
from webapp.common import Response
from webapp import limits, sessions

COOKIE_SETTINGS = 'HttpOnly; SameSite=Strict; Path=/'


def login(request):
    """POST /api/login: 시연 계정으로 로그인하고 세션 쿠키를 내려줍니다."""
    account_id = request.text('id')
    password = str(request.params.get('password', ''))
    # 가드레일: 같은 아이디로 10분 안에 5번 틀리면 10분 동안 로그인을 막습니다(429).
    limits.login_guard.check(account_id)
    account = DEMO_ACCOUNTS.get(account_id)
    # compare_digest는 비밀번호를 비교하는 시간으로 정답을 추측하지 못하게 합니다.
    if account is None or not secrets.compare_digest(password, account['password']):
        limits.login_guard.failed(account_id)
        raise PermissionError('아이디 또는 비밀번호가 올바르지 않습니다.')
    limits.login_guard.succeeded(account_id)

    user = {'id': account_id, 'name': account['name'], 'org': account['org'], 'admin': account['admin']}
    token = sessions.create_session(user)
    cookie = f'welfind_session={token}; {COOKIE_SETTINGS}; Max-Age={sessions.SESSION_SECONDS}'
    return Response({'user': user}, cookie=cookie)


def logout(request):
    """POST /api/logout: 세션을 지우고 쿠키를 비웁니다."""
    sessions.end_session(request.session_token)
    return Response({}, cookie=f'welfind_session=; {COOKIE_SETTINGS}; Max-Age=0')


def current_user(request):
    """GET /api/session: 지금 로그인한 사용자를 알려 줍니다."""
    return {'user': request.user}

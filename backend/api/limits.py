"""요청 가드레일: 보미 사용량 제한과 로그인 시도 제한.

서버 메모리에 기록하므로 서버를 재시작하면 초기화됩니다(서버 한 대 운영 기준).
.env에서 바꿀 수 있습니다: WELFIND_CHAT_PER_MINUTE(기본 20), WELFIND_CHAT_PER_DAY(기본 300).
"""

import os
import threading
import time
from collections import defaultdict, deque

from backend.api.common import ApiError

CHAT_PER_MINUTE = int(os.getenv('WELFIND_CHAT_PER_MINUTE') or 20)
CHAT_PER_DAY = int(os.getenv('WELFIND_CHAT_PER_DAY') or 300)
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW = 10 * 60  # 이 시간 안에 LOGIN_MAX_FAILURES번 틀리면
LOGIN_LOCK = 10 * 60  # 이 시간 동안 로그인을 막습니다.


class RateLimiter:
    """사용자별로 최근 1분·하루 요청 수를 셉니다."""

    def __init__(self, per_minute, per_day):
        self.per_minute, self.per_day = per_minute, per_day
        self.history = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key, now=None):
        now = time.time() if now is None else now
        with self.lock:
            times = self.history[key]
            while times and times[0] <= now - 86400:
                times.popleft()
            if len(times) >= self.per_day:
                raise ApiError(
                    429,
                    f'오늘 보미 사용 한도({self.per_day}회)를 넘었습니다. 내일 다시 이용해 주세요.',
                )
            if sum(1 for t in times if t > now - 60) >= self.per_minute:
                raise ApiError(
                    429,
                    f'질문이 너무 빠르게 이어지고 있어요(1분 {self.per_minute}회). 잠시 후 다시 질문해 주세요.',
                )
            times.append(now)


class LoginGuard:
    """계정별 로그인 실패 횟수를 세어 비밀번호 대입을 막습니다."""

    def __init__(self):
        self.failures = defaultdict(deque)
        self.locked_until = {}
        self.lock = threading.Lock()

    def check(self, account, now=None):
        now = time.time() if now is None else now
        with self.lock:
            until = self.locked_until.get(account, 0)
            if until > now:
                minutes = max(1, round((until - now) / 60))
                raise ApiError(
                    429,
                    f'로그인 실패가 반복되어 약 {minutes}분 동안 로그인을 막았습니다. 잠시 후 다시 시도해 주세요.',
                )

    def failed(self, account, now=None):
        now = time.time() if now is None else now
        with self.lock:
            times = self.failures[account]
            times.append(now)
            while times and times[0] <= now - LOGIN_WINDOW:
                times.popleft()
            if len(times) >= LOGIN_MAX_FAILURES:
                self.locked_until[account] = now + LOGIN_LOCK
                times.clear()

    def succeeded(self, account):
        with self.lock:
            self.failures.pop(account, None)
            self.locked_until.pop(account, None)


chat_limiter = RateLimiter(CHAT_PER_MINUTE, CHAT_PER_DAY)
login_guard = LoginGuard()


def check_chat(user):
    """보미 질문(AI를 쓸 수 있는 요청) 한 번을 셉니다. 한도를 넘으면 429 오류입니다."""
    chat_limiter.check(user['id'])

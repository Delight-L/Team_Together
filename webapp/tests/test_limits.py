"""사용량 제한·로그인 시도 제한 단위 검사. 시간은 직접 넣어 기다리지 않고 검사합니다."""
import unittest

from webapp.common import ApiError
from webapp.limits import LOGIN_LOCK, LOGIN_MAX_FAILURES, LoginGuard, RateLimiter


class RateLimiterTest(unittest.TestCase):
    def test_per_minute_and_per_day(self):
        limiter = RateLimiter(per_minute=2, per_day=3)
        limiter.check('a', now=0)
        limiter.check('a', now=1)
        with self.assertRaises(ApiError) as caught:
            limiter.check('a', now=2)
        self.assertEqual(caught.exception.status, 429)
        limiter.check('b', now=2)          # 사용자마다 따로 셉니다.
        limiter.check('a', now=61)         # 1분이 지나면 다시 허용
        with self.assertRaises(ApiError):
            limiter.check('a', now=200)    # 하루 3회 초과
        limiter.check('a', now=86400 + 1)  # 하루가 지나면 다시 허용


class LoginGuardTest(unittest.TestCase):
    def test_lock_after_failures_and_reset(self):
        guard = LoginGuard()
        for second in range(LOGIN_MAX_FAILURES):
            guard.check('kim', now=second)
            guard.failed('kim', now=second)
        with self.assertRaises(ApiError):
            guard.check('kim', now=LOGIN_MAX_FAILURES)
        guard.check('lee', now=LOGIN_MAX_FAILURES)   # 다른 계정은 영향 없음
        guard.check('kim', now=LOGIN_MAX_FAILURES + LOGIN_LOCK + 1)
        guard.failed('kim', now=0)
        guard.succeeded('kim')
        self.assertNotIn('kim', guard.failures)


if __name__ == '__main__':
    unittest.main()

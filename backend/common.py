"""backend 여러 곳에서 함께 쓰는 작은 도구: 프로젝트 경로, .env 읽기, 서울 시각, 공용 DB 엔진.

API 요청·응답 도구는 backend/api/common.py에 있습니다. pipelines는 따로 실행되므로 이 파일을 쓰지 않습니다.
"""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# 프로젝트 루트(Team_Together). 현재 터미널 폴더가 아니라 이 파일 위치를 기준으로 계산합니다.
ROOT = Path(__file__).resolve().parents[1]
# DB 접속 정보와 자료 위치 설정을 어느 모듈보다 먼저 읽도록, 이 파일을 불러오는 순간 .env를 읽습니다.
load_dotenv(ROOT / '.env')
SEOUL = ZoneInfo('Asia/Seoul')


def seoul_now():
    """서울 기준 현재 시각(datetime)."""
    return datetime.now(SEOUL)


def now_text():
    """서울 기준 현재 시각을 '2026-10-16T16:30:00+09:00' 형식의 문자열로 돌려줍니다(초 단위)."""
    return seoul_now().isoformat(timespec='seconds')


def get_engine():
    """공용 PostgreSQL 엔진. 접속 정보가 필요한 순간에만 연결 설정을 불러옵니다.

    테스트는 각 모듈의 get_engine을 임시 DB로 바꿔 끼웁니다(patch.object(모듈, 'get_engine')).
    """
    from backend.db.connection import engine
    return engine

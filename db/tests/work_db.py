"""테스트용 업무 저장소. 공유 PostgreSQL 대신 메모리 SQLite에 work 스키마를 붙입니다."""
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from db import work_store


def temporary_work_store():
    """시작하면 업무 기록이 테스트 전용 DB로 격리되는 patch를 돌려줍니다(.engine으로 직접 조회)."""
    # 테스트 HTTP 서버가 여러 스레드에서 같은 메모리 DB를 쓰도록 연결 하나를 공유합니다.
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})

    @event.listens_for(engine, 'connect')
    def attach(connection, record):
        connection.execute("ATTACH DATABASE ':memory:' AS work")

    store = patch.object(work_store, 'get_engine', return_value=engine)
    store.engine = engine
    return store

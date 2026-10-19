"""업무 기록(미션·보고서·협업·집단 검토) 공통 저장소. 공유 PostgreSQL의 work 스키마를 사용합니다."""
import threading
from contextlib import contextmanager

from sqlalchemy import Column, Integer, LargeBinary, MetaData, Table, Text, text

from backend.common import get_engine

SCHEMA = "work"
metadata = MetaData(schema=SCHEMA)
# JSON은 기존 분석 DB와 같은 문자열로 저장해 키·값 형식을 그대로 유지합니다.
missions = Table("missions", metadata, Column("key", Text, primary_key=True), Column("value", Text, nullable=False))
report_files = Table("report_files", metadata, Column("key", Text, primary_key=True),
                     Column("document", LargeBinary, nullable=False))
report_versions = Table("report_versions", metadata, Column("key", Text, primary_key=True),
                        Column("revision", Integer, primary_key=True),
                        Column("document", LargeBinary, nullable=False), Column("record", Text, nullable=False))
experience = Table("experience", metadata, Column("key", Text, primary_key=True), Column("value", Text, nullable=False))
group_reviews = Table("group_reviews", metadata, Column("identity", Text, primary_key=True),
                      Column("payload", Text, nullable=False))
# 관리자 설정(예: AI 설정). 서버 파일은 재배포·재시작 때 지워지므로 DB에 둡니다.
app_settings = Table("app_settings", metadata, Column("key", Text, primary_key=True), Column("value", Text, nullable=False))

chatbot_embeddings = Table("chatbot_embeddings", metadata,
    Column("resource_id", Text, primary_key=True), Column("model", Text, primary_key=True),
    Column("content_hash", Text, nullable=False), Column("vector", Text, nullable=False))

_ready = set()
_ready_lock = threading.Lock()


def ensure_schema(engine):
    """처음 사용할 때 한 번만 스키마와 테이블을 만듭니다."""
    with _ready_lock:
        if engine in _ready:
            return
        with engine.begin() as conn:
            if conn.dialect.name == "postgresql":
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
            metadata.create_all(conn)
        _ready.add(engine)


@contextmanager
def transaction():
    """하나의 트랜잭션으로 묶습니다. 예외가 나면 전체를 되돌립니다."""
    engine = get_engine()
    ensure_schema(engine)
    with engine.begin() as conn:
        yield conn


def lock(conn, key):
    """같은 키의 동시 저장을 트랜잭션 끝까지 직렬화합니다(아직 없는 행 포함)."""
    if conn.dialect.name == "postgresql":
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key})

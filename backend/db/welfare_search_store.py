"""복지 검색 색인과 대화 서명키의 DB 접근. 원본 DB2 자료와 분리합니다."""
import json
import secrets
from sqlalchemy import select
from backend.db import work_store


def read_embeddings(model):
    table = work_store.chatbot_embeddings
    with work_store.transaction() as conn:
        return {r.resource_id: (r.content_hash, json.loads(r.vector)) for r in
                conn.execute(select(table).where(table.c.model == model))}


def save_embeddings(model, rows):
    from sqlalchemy.dialects.postgresql import insert
    table = work_store.chatbot_embeddings
    with work_store.transaction() as conn:
        for resource_id, digest, vector in rows:
            statement = insert(table).values(resource_id=resource_id, model=model,
                content_hash=digest, vector=json.dumps(vector))
            conn.execute(statement.on_conflict_do_update(index_elements=[table.c.resource_id, table.c.model],
                set_={'content_hash': statement.excluded.content_hash, 'vector': statement.excluded.vector}))


def snapshot_secret():
    key = 'chatbot_snapshot_signing_key_v1'
    table = work_store.app_settings
    with work_store.transaction() as conn:
        work_store.lock(conn, key)
        value = conn.execute(select(table.c.value).where(table.c.key == key)).scalar_one_or_none()
        if value is None:
            value = secrets.token_hex(32)
            conn.execute(table.insert().values(key=key, value=value))
    return bytes.fromhex(value)

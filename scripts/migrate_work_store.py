"""로컬 SQLite 업무 기록(db/runtime/*.sqlite3)을 공유 PostgreSQL work 스키마로 한 번 옮깁니다.

기본은 건수만 확인합니다. --apply를 붙여야 실제로 씁니다. 이미 있는 키는 덮어쓰지 않으므로 여러 번 실행해도 안전합니다.
쓰기 권한이 있는 계정(.env의 DB_USER)이 필요합니다.
"""
from contextlib import closing
from pathlib import Path
import argparse
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sqlalchemy import text

from db import work_store

RUNTIME = ROOT / 'db/runtime'
# (SQLite 파일, 원래 테이블, 대상 테이블, 컬럼)
SOURCES = [
    ('mission_records.sqlite3', 'missions', 'missions', ['key', 'value']),
    ('mission_records.sqlite3', 'report_files', 'report_files', ['key', 'document']),
    ('mission_records.sqlite3', 'report_versions', 'report_versions', ['key', 'revision', 'document', 'record']),
    ('mission_records.sqlite3', 'experience', 'experience', ['key', 'value']),
    ('group_reviews.sqlite3', 'group_reviews', 'group_reviews', ['identity', 'payload']),
]


def read_rows(path, table, columns):
    if not path.exists():
        return []
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as conn:
        found = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        if not found:
            return []
        return [dict(zip(columns, row)) for row in conn.execute(f'SELECT {",".join(columns)} FROM {table}')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='PostgreSQL에 실제로 씁니다')
    parser.add_argument('--runtime', type=Path, default=RUNTIME)
    args = parser.parse_args()
    plan = [(target, columns, read_rows(args.runtime / file, table, columns))
            for file, table, target, columns in SOURCES]
    result = {target: dict(local=len(rows)) for target, _, rows in plan}
    if args.apply:
        with work_store.transaction() as conn:
            for target, columns, rows in plan:
                keys = [c for c in columns if c in ('key', 'identity', 'revision')]
                statement = text(f'INSERT INTO work.{target} ({",".join(columns)}) '
                                 f'VALUES ({",".join(":" + c for c in columns)}) '
                                 f'ON CONFLICT ({",".join(keys)}) DO NOTHING')
                inserted = sum(conn.execute(statement, row).rowcount for row in rows)
                total = conn.execute(text(f'SELECT COUNT(*) FROM work.{target}')).scalar_one()
                result[target].update(inserted=inserted, server_total=total)
    print(json.dumps(dict(applied=args.apply, tables=result), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

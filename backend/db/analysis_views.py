"""버전 관리된 분석 조회 뷰 설치. API 요청에서는 DDL을 실행하지 않습니다."""

from pathlib import Path
from sqlalchemy import text


def install_views(connection):
    source = Path(__file__).with_suffix('.sql').read_text(encoding='utf-8')
    for statement in source.split(';'):
        if not statement.strip():
            continue
        if connection.dialect.name == 'postgresql':
            statement = statement.replace('CREATE VIEW', 'CREATE OR REPLACE VIEW')
        else:
            statement = statement.replace('CREATE VIEW', 'CREATE VIEW IF NOT EXISTS')
        connection.execute(text(statement))

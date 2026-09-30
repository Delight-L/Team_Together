"""공통 DB 연결 설정. 직접 실행하면 SELECT 1로 접속을 확인합니다."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text

load_dotenv(Path(__file__).with_name('.env'))

# 비밀번호에 @, / 같은 문자가 있어도 URL.create가 올바르게 처리합니다.
database_url = URL.create(
    'postgresql+psycopg2',
    username=os.environ['DB_USER'],
    password=os.environ['DB_PASSWORD'],
    host=os.environ['DB_HOST'],
    port=int(os.getenv('DB_PORT', '5432')),
    database=os.environ['DB_NAME'],
)

# 엔진은 연결을 관리하는 객체입니다. 실제 접속은 쿼리를 실행할 때 발생합니다.
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args={'connect_timeout': 10},
)

if __name__ == '__main__':
    try:
        with engine.connect() as connection:
            result = connection.execute(text('SELECT 1')).scalar_one()
            print('DB 연결 성공:', result)
    finally:
        engine.dispose()

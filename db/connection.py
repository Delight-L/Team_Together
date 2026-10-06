"""공통 DB 연결 설정. 직접 실행하면 SELECT 1로 접속을 확인합니다."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# 접속 정보를 바꾸려면 코드 대신 프로젝트의 .env 파일을 수정하세요.
# os.environ: 필수 값 / os.getenv: 기본값을 줄 수 있는 값입니다.
# 비밀번호에 @, / 같은 문자가 있어도 URL.create가 올바르게 처리합니다.
database_url = URL.create(
    "postgresql+psycopg2",
    username=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    host=os.environ["DB_HOST"],
    port=int(os.getenv("DB_PORT") or "5432"),
    database=os.environ["DB_NAME"],
)

# 엔진은 연결을 관리하는 객체입니다. 실제 접속은 쿼리를 실행할 때 발생합니다.
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10},
)

if __name__ == "__main__":
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()
            print("DB 연결 성공:", result)
    finally:
        engine.dispose()

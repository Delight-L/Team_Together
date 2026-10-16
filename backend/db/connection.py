"""공통 DB 연결 설정. 직접 실행하면 SELECT 1로 접속을 확인합니다."""

import os

from sqlalchemy import URL, create_engine, text

import backend.common  # noqa: F401  프로젝트 루트의 .env를 읽습니다.

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

# 원격(오라클 클라우드) DB는 DB_SSLMODE=require 이상을 권장합니다.
# verify-full을 쓰면 DB_SSLROOTCERT에 서버 CA 인증서 경로를 지정하세요. 로컬 DB는 비워 둡니다.
connect_args = {"connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT") or "10"), "application_name": "welfind"}
if os.getenv("DB_SSLMODE"):
    connect_args["sslmode"] = os.environ["DB_SSLMODE"]
if os.getenv("DB_SSLROOTCERT"):
    connect_args["sslrootcert"] = os.environ["DB_SSLROOTCERT"]

# 엔진은 연결을 관리하는 객체입니다. 실제 접속은 쿼리를 실행할 때 발생합니다.
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_recycle=1800,  # 클라우드 방화벽이 유휴 연결을 끊어도 다음 요청에서 새로 연결합니다.
    connect_args=connect_args,
)

if __name__ == "__main__":
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()
            print("DB 연결 성공:", result)
    finally:
        engine.dispose()

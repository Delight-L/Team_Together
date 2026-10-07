# 데이터 저장소

DB2 지자체복지서비스 수집은 루트 `collect_db2.py`를 사용합니다. 목록·상세 API를
전용 DB2 테이블에 저장하며 Windows 예약 작업으로 매일 실행합니다.
실행·설정·조회 방법은 [정기 수집 안내](../docs/DB2_지자체복지_정기수집.md)를 참고하세요.

`connection.py`는 루트 `.env`의 PostgreSQL 설정을 읽습니다. `python -m db.connection`은 읽기 전용 접속 확인입니다.

`analysis_repository.py`는 보관된 Analysis2 CSV 조회와 업로드 검증·DB1 반영을 담당합니다. 화면은 이 모듈을 직접 가져오며 별도 호환 파일을 두지 않습니다. `mission_store.py`는 SQLite 업무 기록과 보고서 저장, `demo.py`는 명시적 시연 자료를 담당합니다.

`runtime/mission_records.sqlite3`는 담당자·지역·월별 로컬 업무 기록입니다. Git에 포함하지 않으며 이전 위치의 DB가 있으면 최초 사용 시 SQLite backup으로 복사합니다.

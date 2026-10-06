# 데이터 저장소

`connection.py`는 루트 `.env`의 PostgreSQL 설정을 읽습니다. `python -m db.connection`은 읽기 전용 접속 확인입니다.

`analysis_repository.py`는 보관된 Analysis2 CSV 조회와 업로드 검증·DB1 반영을 담당합니다. 화면은 이 모듈을 직접 가져오며 별도 호환 파일을 두지 않습니다. `mission_store.py`는 SQLite 업무 기록과 보고서 저장, `demo.py`는 명시적 시연 자료를 담당합니다.

`runtime/mission_records.sqlite3`는 담당자·지역·월별 로컬 업무 기록입니다. Git에 포함하지 않으며 이전 위치의 DB가 있으면 최초 사용 시 SQLite backup으로 복사합니다.

# Python 모듈 안내

## 챗봇

챗봇 화면은 React 화면에 통합되어 있습니다. `python main.py --chatbot-cli`는 콘솔 데이터 질의 도구입니다.

`service.py`는 저장된 근거 안내를 제공합니다. 기본값 `allow_agent=False`에서는 API 클라이언트를 생성하지 않습니다. 사용자가 AI 모드를 켜고 질문을 보내면 `allow_agent=True`를 전달합니다. 연결 실패나 설정 부재 시 규칙 기반 근거 안내로 돌아갑니다.

콘솔에서는 1 분석 기준, 2 전체 신호, 3 지역 요약 메뉴가 토큰 없이 동작합니다. `AI켜기`를 입력한 뒤 자유 질문을 보내야 호출이 허용되며 `AI끄기`로 해제합니다.

루트 `.env`에 `GEMINI_API_KEY`, `GEMINI_MODEL`을 설정합니다. API 키를 저장소에 포함하지 않습니다.

## 데이터 저장소

DB2 지자체복지서비스 수집은 `python -m db.collect_welfare`를 사용합니다. 목록·상세 API를
전용 DB2 테이블에 저장하며 Windows 예약 작업으로 매일 실행합니다.
실행·설정·조회 방법은 [정기 수집 안내](DB2_지자체복지_정기수집.md)를 참고하세요.

`connection.py`는 루트 `.env`의 PostgreSQL 설정을 읽습니다. `python -m db.connection`은 읽기 전용 접속 확인입니다.

`analysis_repository.py`는 보관된 Analysis2 CSV 조회와 업로드 검증·DB1 반영을 담당합니다. 화면은 이 모듈을 직접 가져오며 별도 호환 파일을 두지 않습니다. `mission_store.py`는 SQLite 업무 기록과 보고서 저장을 담당합니다.

`runtime/mission_records.sqlite3`는 담당자·지역·월별 로컬 업무 기록입니다. Git에 포함하지 않습니다.

## 공용 기능

React API에서 사용하는 기능과 데이터를 모았습니다.

- `accounts.py`: 시연 로그인 계정
- `report.py`: Word 보고서 초안 생성
- `data/map_boundaries.json`: 지도 경계 데이터

분석·사업 매칭·업무 저장은 각각 기존 `agents/`, `chatbot/`, `db/` 모듈을 사용합니다.

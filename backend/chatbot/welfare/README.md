# 보미의 복지사업 찾기

복지탐정의 보미가 팀에서 정리한 복지사업 자료를 검색하고 출처와 확인할 조건을 안내하는 모듈입니다.
선택한 지역과 대화 맥락을 함께 사용하며, 실제 이용 자격이나 현재 모집 여부는 담당 기관 확인이 필요합니다.

## 구성

| 파일 | 역할 |
|---|---|
| `service.py` | 화면 서버와 비동기 대화를 연결하고 스트림 응답을 제공 |
| `app/config.py` | 프로젝트 루트 `.env`의 AI 연결 설정 읽기 |
| `app/schemas.py` | 사용자 질문과 대화 이력 형식 검사 |
| `app/dialogue/orchestrator.py` | 검색·답변·출처·AI 실패 안내 처리 |
| `app/dialogue/resources.py` | 공유 DB2 자료 조회, 사업 검색, 자료 기반 안내 |
| `app/llm/openai_client.py` | 요청별 AI 연결과 응답 스트림 종료 |
| `data/*.json` | DB 적재 원본 및 오프라인 검증용 복지자료 |
| `backend/db/welfare_chatbot_repository.py` | 테이블 정의, JSON 적재, DB 조회 |

## 요청 흐름

```text
frontend/src/BomiChat.jsx
  → backend/api/routes_chat.py
  → backend/agents/supervisor.py (총괄 에이전트가 복지사업 담당으로 고른 경우)
  → backend/chatbot/welfare/service.py
  → app/dialogue/orchestrator.py:handle_chat
  → app/dialogue/resources.py + app/llm/openai_client.py
```

`OPENAI_API_KEY`가 없으면 자료 검색 결과로 안내합니다. 키가 있으면 검색한 자료를 근거로 AI가 답변합니다.
AI 연결 실패나 빈 응답은 자료 검색 안내로 전환하며, 요청이 취소되면 응답 스트림을 종료합니다.
같은 사업이 여러 자료에 있으면 상세 정보를 가진 자료를 사용하고, 후속 질문은 이전 사업 맥락을 이어 검색합니다.

## 공유 DB2 복지자료

기존 `.env`의 `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` 연결을 그대로 사용합니다.
현재 팀 공용 DB는 Oracle Cloud의 PostgreSQL이며 Oracle Database용 별도 드라이버는 사용하지 않습니다.

| 테이블 | 주요 컬럼과 보존 내용 |
|---|---|
| `db2.chatbot_policy_candidates` | JSON 후보 18개 필드와 `position`. ID, 사업명, 설명, 지역, 출처·페이지, 연도, 확인 상태, 주의사항 등 |
| `db2.chatbot_policy_plans` | `plan_index`, `name`, `target`, `agency`, `description`, `procedure`, `source_file`, `source_pages`, `plan_period`, `status` |
| `db2.chatbot_policy_datasets` | 파일명, SHA-256, 적재 행 수·시각, 원본 문서 메타정보. 과거 사업 37개와 표 해석 주의사항도 메타정보 안에 보존 |

프로젝트 루트에서 최초 한 번 적재합니다. 테이블 생성 권한이 있는 계정으로 실행하세요.

```powershell
python -m backend.db.welfare_chatbot_repository import-json
python -m backend.db.welfare_chatbot_repository check
```

적재는 하나의 트랜잭션으로 처리하며, 같은 ID는 갱신하므로 반복 실행해도 중복되지 않습니다.
JSON에 없는 기존 DB 행은 지우지 않습니다. 신규 테이블에는 `welfind_reader`의 SELECT 권한도 설정합니다.
원문은 검토용 후보·과거 계획이며, DB에 저장해도 현재 운영·신청 자격이 확인된 것으로 바뀌지 않습니다.

서버의 기본 자료 위치는 `WELFIND_WELFARE_SOURCE=db`입니다. 설정을 생략해도 DB를 읽습니다.
총괄 에이전트의 사업명 판별, 복지사업 검색, 대화에서 찾은 사업의 보고서 연결, `/api/chat/config`가 같은 DB 자료를 사용합니다.
요청마다 조회하므로 DB 수정은 서버 재시작 없이 반영됩니다. 서버는 조회만 하며 기동 시 자동 적재하지 않습니다.
DB 오류나 빈 테이블은 명시적으로 알리고 JSON으로 자동 대체하지 않습니다.

`GET /api/chat/config`의 `resourceSource`는 `db` 또는 `json`이며 `resourceCount`는 기존 사업명 중복 처리 후 자료 수입니다.

분석 근거 설명·보고서 초안 등 다른 담당은 [보미 챗봇 안내](../README.md)를 참고하세요.

## 검증

프로젝트 루트에서 실행합니다.

```powershell
$env:WELFIND_WELFARE_SOURCE = 'json' # 외부 DB 없이 기존 검색·대화 회귀 검사
.venv/Scripts/python.exe -m unittest discover -s backend/chatbot/tests -v
.venv/Scripts/python.exe -m unittest backend.db.tests.test_welfare_chatbot_repository -v
```

실제 DB 동작을 확인할 때는 `WELFIND_WELFARE_SOURCE=db`를 사용합니다. JSON 모드는 명시적인 오프라인 검증용입니다.

API 키는 프로젝트 루트 `.env`에만 설정하며 저장소나 화면에 노출하지 않습니다.

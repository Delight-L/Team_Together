# backend 구조와 역할

`backend/`는 기존 `backend`를 대체합니다. **챗봇(`bomi/`)만 새로 설계**했고, 나머지는 기존 코드를 로직 변경 없이 복사하고 임포트 경로만 바꿨습니다.
흐름 상세는 [CHAT_FLOW.md](CHAT_FLOW.md)와 그림 [chat_flow.jpg](chat_flow.jpg), 챗봇 코어 사용법은 [bomi/README.md](bomi/README.md)를 보세요.

## 1. 폴더 구조

```
backend/
├─ bomi/                  새로 설계한 챗봇 코어
├─ api/                   server·routes (routes_chat.py만 재작성)
├─ chatbot/               챗봇 공용 인프라 (AI 설정·규칙·LLM 창구·복지 자료)
├─ agents/                report_writer·report_material·service_matching, regional_v16 엔진
├─ db/                    분석·업무 기록 저장소 (복사)
├─ services/ · resources/ · tools/   (복사)
├─ CHAT_FLOW.md           흐름 문서
└─ ARCHITECTURE.md        이 문서
```

## 2. 요청 흐름

```
POST /api/chat  (routes_chat.py: 검사 → ChatRequest)
  → regularization.prepare     길이 · 최근 3쌍 · 개인정보 가림
  → [notice]                   개인정보를 가렸다면
  → 담당 선택 (Router)         단어 규칙 걸림 → guide / 고정 규칙 → AI → 키워드 규칙
  → route 이벤트
  → 담당 에이전트.respond      입력 규제 → 답변 → 출력 규제
  → events.seal                done 한 번 보장, 예외는 error로
```

## 3. bomi 모듈별 역할

| 파일 | 역할 | 하지 않는 일 |
|---|---|---|
| `pipeline.py` | 위 단계를 순서대로 연결 | 규칙·답변 로직 |
| `routing.py` | **담당 선택의 유일한 위치** (고정 규칙 → AI → 키워드 규칙) | 자료 유무에 따른 대체 |
| `regularization.py` | 규칙·moderate API를 에이전트별 `Policy`로 적용 | 담당 선택 |
| `events.py` | 프런트와 맺은 이벤트 9종 계약, `seal` | |
| `request.py` | `ChatRequest`·`GroupSelection` 타입, 입력 검증 | |
| `questions.py` | 질문 분류 순수 함수, 키워드 목록 | |
| `phrases.py` | 고정 문구, AI 담당 선택 지시문 | 로직 |
| `aio.py` | 동기↔비동기 변환의 유일한 접점 | |
| `agents/` | 담당별 답변 | `route`·`done` 이벤트 |
| `adapters/v16.py` | v16 엔진 연결(`sys.path` 조정을 이 파일 한 곳에 가둠) | |

## 4. 에이전트 4종

| 에이전트 | 역할 | 근거 |
|---|---|---|
| **region_analysis** | 동·그룹 분석 근거, 이상신호, 판정 기준, 지역 배경, 소비 | v16 DB, 동·그룹 분석 결과 |
| **welfare** | 복지사업 조회, 신규 사업 구상 | 팀 JSON 자료, 스트리밍 |
| **report** | 약식보고서 초안 + «보고서 탭에서 수정» 버튼 | 업무 기록, 대화에서 찾은 사업 |
| **guide** | 업무 방법 질문·업무 무관 질문 | 고정 문구 |

모든 에이전트는 `RegulatedAgent`를 상속합니다. `respond()`가 입력 규제를 하고, 통과하면 `answer()`가 기존 방식 그대로 답합니다.

`region_analysis`는 안에서 설명기를 고릅니다.

```
화면 판정 용어를 묻는 질문            → workspace (그룹이 열려 있으면 group, 아니면 district)
그룹이 열려 있고 그 그룹을 묻는 질문    → group
v16 자료(DB1 SQLite)가 없음           → workspace
그 밖                                → v16
```

v16 자료가 없을 때의 대체는 라우터가 아니라 에이전트 안에 있습니다. AI 해석이 실패하면 외부 AI 없이 같은 근거로 다시 답하고, 그 앞에 `error` 이벤트를 보냅니다.

### 데이터 조회가 필요한 에이전트

| 에이전트 | 조회 | 근거 | 방식 |
|---|---|---|---|
| region_analysis | 있음 | 동 분석 결과(DB 우선, 실패 시 CSV), 그룹 집계 snapshot, v16 DB1 SQLite | 구조적 조회 후 근거로 렌더링 |
| welfare | 있음 | 팀 JSON 자료 (DB 아님) | 키워드·동의어 검색 후 프롬프트에 삽입 |
| report | 있음 | 업무 기록(PostgreSQL `work`), 동 분석 근거 | 기록 조회 후 초안 조립 |
| guide | 없음 | – | 고정 문구 |

임베딩 기반 벡터 검색은 어느 에이전트에도 없습니다. 복지 사업 DB(`db2.local_welfare_services`)는 챗봇과 연결되어 있지 않습니다.

## 5. 규제 계층 (`regularization.py`)

규칙의 정의(정규식·단어 목록)는 `chatbot/guardrails.py`에 있고, 이 계층이 에이전트별 `Policy`로 적용합니다.

| 단계 | 누가 | 무엇을 |
|---|---|---|
| 요청 직후 | 파이프라인 | 길이, 대화 길이, 개인정보 가림 (외부 AI로 보내기 전) |
| 입력 | 각 에이전트 | 단어 규칙 → moderate API(AI 모드만) → 걸리면 차단 안내 |
| 출력 | 각 에이전트 | 근거에 없는 연락처·URL·금액 가림, moderate API(AI가 쓴 글만) |

| 에이전트 | 입력 규칙 | 입력 moderate | 출력 가림(규칙) | 출력 moderate |
|---|:-:|:-:|:-:|:-:|
| region_analysis | ✓ | ✓ | `explain_ai`가 근거 대조 | ✓ (AI 해석문) |
| welfare | ✓ | ✓ | ✓ (줄 단위 스트림) | ✓ (끝에서 `replace`) |
| report | ✓ | ✓ | `check_grounding`이 근거 대조 | ✓ (AI가 다듬은 경우) |
| guide | ✓ | ✓ | – | – (고정 문구) |

- moderate API는 OpenAI 키가 있을 때만 동작하고, 호출이 실패하면 통과시킵니다.
- 출력이 걸리면 이미 보낸 글도 `replace`로 통째로 바꿉니다.
- 단어 규칙에 걸린 질문은 외부 호출 없이 `guide`(by `안전 검사`)로 보내 차단합니다.

## 6. 이벤트 계약 (프런트 수정 없음)

| 이름 | 내용 | 화면에서 하는 일 |
|---|---|---|
| `route` | agent, label, by | 담당 이름 표시 |
| `sources` | records, mode | 참고한 복지사업 목록 |
| `token` | text | 답변 글자를 이어 붙임 |
| `replace` | text, mode, source | 답변 전체를 교체 |
| `follow_ups` | questions | 후속 질문 버튼 |
| `actions` | actions | 액션 버튼 |
| `notice` | message, question(선택) | 안내문. question이 있으면 사용자 말풍선도 교체 |
| `error` | message | 오류 표시와 재시도 |
| `done` | (없음) | 스트림 완료. 없으면 화면이 «연결 중단» 오류를 냄 |

순서 규칙: 맨 앞에 `notice`(개인정보 가림)가 올 수 있고, 그다음은 항상 `route`이며, 마지막은 항상 `done` 한 번입니다.

```
welfare           : sources → token* → [replace] → [notice] → [error → replace]
그 밖의 에이전트   : [error] → replace → [follow_ups] → [notice] → [actions]
차단(입력·출력)   : replace
```

## 7. 기존 backend와 달라진 점

| 항목 | 기존 | backend |
|---|---|---|
| 담당 에이전트 | 5개 | 4개 (`analysis` + `regional_v16` → `region_analysis`) |
| 담당 선택 위치 | 6곳 | `Router` 하나 |
| `asyncio.run` | 6곳 | `aio.py` 1곳 |
| `done` | 에이전트마다 | `seal`이 한 번 |
| 응답 형식 | dict와 스트림 혼재 | 모두 `Iterator[Event]` |
| 규제 | supervisor 한곳에 집중 | 에이전트별 `Policy` |
| 유해 검사 시점 | 담당 선택과 동시 | 담당 선택 후 에이전트가 실행 |
| `route.agent` 값 | `analysis` / `regional_v16` | `region_analysis` (화면은 `label`만 사용) |

## 8. 검증 현황

| 항목 | 결과 |
|---|---|
| `bomi` 테스트 | 118개 통과 (2개는 v16 DB 파일이 없어 건너뜀) |
| `chatbot` 27개, `db` 35개, `api` 56개 | 통과 |
| `backend_old`와 이벤트 스트림 대조 (AI 끔) | 34건 중 차이 0 |
| `backend_old`와 담당 선택 대조 | 88건 중 차이 0 |
| 서버 기동 | `/api/health` 정상 |

## 9. 알려진 한계·미결 사항

- `Team_Together/main.py`는 아직 `backend`를 가리킵니다. 전환하려면 `python -m backend.api.server`로 실행하거나 `main.py`의 임포트를 바꿉니다.
- v16 DB(`db1.sqlite`)가 개발 PC에 없어서 v16 실제 경로는 가짜 응답으로만 검증했습니다. DB가 있는 환경에서 건너뛴 테스트 2개를 실행해야 합니다. 배치 위치는 `backend/agents/regional_v16/outputs/db1.sqlite` 또는 환경변수 `DB1_DATABASE_PATH`입니다.
- AI가 담당을 고르는 경로와 moderate API 실제 호출은 외부 호출이 필요해 구 backend와 직접 대조하지 못했습니다.
- AI 모드에서는 입력 moderate가 담당 선택 후 순차 실행되므로 응답이 이전보다 조금 늦어질 수 있습니다.
- `region_analysis`의 출력 가림은 `explain_ai`(db 계층)에서 처리합니다. `Policy`에서는 moderate API만 겁니다.
- moderate API 호출 중 DB 조회 오류(`ai_settings` 키 조회 실패 등)가 나면 `seal`이 `error`로 처리합니다. 검사 인프라 장애를 통과시킬지는 정하지 않았습니다.

## 10. v16 근거 저장소 계층 (`Db1Repository`)

v16 엔진(`agents/regional_v16/chatbot_agent`)의 데이터 접근을 하나의 계약 뒤로 모았습니다.

```
query_service · consumption_trends · orchestrator
        │  (SQL·연결을 직접 쓰지 않음)
        ▼
db1_repository.Db1Repository        ← 계약(Protocol): 어떤 조회를 제공하는지
        ▲
repository.SqlDb1Repository         ← 조회 로직(SQL·캐시·인덱스). SQL은 이 파일 안에만
        ▲
pg_repository.PostgresDb1Repository ← 유일한 구현: 고정한 run의 뷰를 읽음
```

- 예전 이름 `DataRepository`·`SqliteDb1Repository`는 제거했습니다. `Chatbot`은 저장소를 반드시 주입받습니다.
- 저장소 밖으로 새던 SQL을 메서드로 옮겼습니다: `consumption_evidence`, `consumption_payloads`, `district_codes`, `pipeline_status`, `has_data`.
- 챗봇 로직에 SQL·`sqlite3`가 다시 들어오지 않도록 `test_db1_repository.SqlStaysInsideRepositoryTest`가 소스를 검사합니다.
- 동작은 바뀌지 않았습니다. 합성 DB에서 13개 질문 유형의 출력이 이전 코드와 동일함을 대조했습니다.
- 실제 `db1.sqlite`로 원본(`backend_old`)과 비교한 결과는 [PERFORMANCE_COMPARISON.md](PERFORMANCE_COMPARISON.md), 개선 내용 정리는 [PERFORMANCE_IMPROVEMENTS.md](PERFORMANCE_IMPROVEMENTS.md), 재현 도구는 `tools/v16_bench/`입니다.
- 아직 하지 않은 것: 운영 DB에서의 게시와 전환.

### 저장소 효율 (챗봇 구조는 그대로)

`SqlDb1Repository` 안에서만 고쳤고 출력은 이전과 동일합니다.

| 개선 | 내용 |
|---|---|
| 연결 재사용 | 저장소 객체당 읽기 전용 연결 1개. «갱신 완료» 확인은 연결을 열 때만 |
| 결과 캐시 | 같은 탐지·근거 표, 지역 유형, 소비 원자료, 코드 표를 객체 수명 동안 한 번만 읽음. 호출부에는 사본을 돌려줘 캐시가 오염되지 않음 |
| 신선도 확인 | 작업 DB는 `PRAGMA data_version`과 파일 크기·수정 시각으로 변경을 감지해 캐시를 비움. 불변인 `snapshots/` 공개본은 확인을 생략 |
| 중복 쿼리 제거 | `supplements`·`consumption_evidence`에서 같은 SQL·인자의 재질의를 메모, `sqlite_master` 확인은 1회 |
| 조건 내리기 | 소비 증감 계산이 필요한 기간(이전 분기·달 포함)·동·연령의 행만 SQL로 읽음(`consumption_payloads`의 목록 조건). 빈 목록은 «해당 행 없음» |
| 동별 정렬 인덱스 | `activity(동, 기간)`이 요청된 동의 행만 정렬해 두고 날짜를 이진 탐색(마스크·재정렬 생략). 날짜 순서가 어긋나면 기존 방식으로 처리 |
| 정리 | `v16.reply()`가 요청이 끝나면 `repo.close()`를 호출 |

측정(합성 DB: 동 22개, 6개월, 신호 27건, 공개 snapshot 기준)

| 질문 | 연결 | 쿼리 | 시간 |
|---|---|---|---|
| 신호 목록 | 148 → 1 | 607 → 46 | 991 → 286 ms |
| 동 변화 이유 | 4 → 1 | 15 → 12 | 9 → 15 ms (측정 오차 범위) |
| 소비(2개 동·6개월) | 6 → 1 | 30 → 18 | 12 → 10 ms |
| 지역 배경(5개 동) | 35 → 1 | 101 → 21 | 91 → 42 ms |

조건 내리기와 동별 인덱스까지 적용한 뒤의 측정(같은 합성 DB, 공개 snapshot, 3회 범위)

| 질문 | 조건 내리기 전(위 표) | 후 |
|---|---|---|
| 신호 목록 | 286 ms | 177~196 ms |
| 지역 배경(5개 동) | 42 ms | 25~28 ms |
| 소비(2개 동·6개월) | 10 ms | 4~5 ms |
| 연령별 변화 | 39 ms | 31~35 ms |

**탐지 표(JSON 행)의 기간·동 조건은 SQL로 내리지 않았습니다.** 이 표는 행마다 JSON이고 열 집합은 «읽은 행들의 키 합집합»이라,
일부 행만 읽으면 열 구성이 달라져 `row[key]` 접근이 깨지거나 값 형식이 바뀔 수 있습니다. 표를 요청당 한 번 읽는 현재 구조에서는 얻는 것도 작아서,
같은 표를 쓰는 인덱스(동별 정렬 + 이진 탐색)로 같은 목표를 안전하게 달성했습니다. 소비 원자료는 행 단위 dict라 이 위험이 없어 SQL로 내렸습니다.

### PostgreSQL 저장소

v16 근거 자료를 SQLite 파일 대신 PostgreSQL에서 읽습니다. **조회 SQL은 한 줄도 바꾸지 않았습니다.**

```
SQLite 공개본 ──publish──▶ db1.v16_<테이블>(run_id, 원래 열…)   run별 자료
                           db1.v16_run / db1.v16_active_run      이력 / 활성 run 포인터
                                       │
                           db1_v16.<테이블> (뷰)  ← 연결에 고정한 run의 행만, SQLite 테이블과 같은 이름·열
                                       │
                           PostgresDb1Repository ──▶ SqlDb1Repository의 조회 로직(SQLite 구현과 공유)
```

| 설계 | 내용 |
|---|---|
| 게시 | `data_pipeline/publish_postgres.py`. 적재와 활성 포인터 변경이 **한 트랜잭션**이라 읽는 쪽은 이전 run 또는 새 run만 보고 중간 상태를 보지 않음. 행 수가 원본과 다르면 전체가 되돌려짐 |
| 멱등 | 같은 공개본(내용 해시)을 다시 올리면 적재하지 않고 활성 run만 맞춤 |
| run 고정 | 저장소가 연결을 열 때 활성 run을 한 번 정해 세션에 고정. 도중에 새 run이 공개돼도 **한 답변 안에서 버전이 섞이지 않음** |
| 롤백 | `--activate RUN_ID`로 이전 run을 다시 활성화. 갱신이 끝난(ready) run만 가능 |
| 정리 | 최근 `--keep`개(기본 3, 활성 포함)만 남기고 이전 run 삭제. 요청 중인 저장소가 읽는 이전 run을 바로 지우지 않도록 2 이상 권장 |
| 열 변화 | 새 공개본에 열이 늘면 `ALTER TABLE ADD COLUMN`, 뷰를 다시 만듦 |
| JSON 열 | **TEXT로 저장**. JSON 형식은 `NaN`을 거부하고 키 순서를 바꿀 수 있어서, 원문 그대로 보존해 SQLite와 같은 결과를 냄 |
| 세션 정리 | 연결을 닫을 때 `search_path`와 run 설정을 되돌려 풀의 다른 사용자에게 새지 않음 |
| 선택 | **PostgreSQL만.** 남은 `DB1_REPOSITORY=sqlite`·오타 값은 조용히 무시하지 않고 오류(`data_ready()`는 경고 후 «자료 없음») |
| 장애 구분 | `data_ready()`가 «자료 없음»(활성 run 없음)과 «저장소 연결 실패»(오류 로그)를 구분 |

운영 명령

```bash
python scripts/publish_v16_to_postgres.py                    # 현재 공개본을 새 run으로 올리고 활성화
python scripts/publish_v16_to_postgres.py --status           # 활성 run과 이력
python scripts/publish_v16_to_postgres.py --activate RUN_ID  # 이전 run으로 되돌리기
```

검증 (합성 DB, 로컬 PostgreSQL 16)

| 항목 | 결과 |
|---|---|
| 질문 유형 13개의 출력 (구 backend / SQLite / PostgreSQL) | 작은 DB·큰 DB 모두 **세 구현이 바이트 단위로 동일** |
| 실제 챗봇 답변(`v16.reply`) | SQLite와 PostgreSQL이 질문 3개에서 동일 |
| 계약·동등성 테스트 | 같은 테스트를 두 구현에 모두 적용해 통과 |
| 게시 테스트 | 활성 포인터 전환, 멱등, 강제 재적재, 실패 시 이전 run 유지, 행 수 불일치 롤백, 정리, 열 추가, 롤백, 세션 정리 |
| 응답 시간(중앙값, 9회, 큰 합성 DB, 로컬 서버) | 신호 목록 SQLite 298ms / PostgreSQL 313ms, 소비 5.8 / 8.3ms, 지역 배경 51 / 65ms, 동 변화 이유 9.3 / 15.0ms |

시간은 **같은 컴퓨터의 로컬 서버** 기준이라 네트워크 지연이 빠져 있습니다. 서버가 원격이면 질문당 쿼리 12~50회에 왕복 시간이 더해집니다.

### 조회 순서 규칙

여러 행을 돌려주는 조회(소비·지역 배경·후속 추적)는 `ORDER BY`를 명시합니다. 같은 SQL이라도 SQLite는 기본키 색인 순서로,
PostgreSQL은 저장 순서로 돌려주기 때문입니다(실제 `db1.sqlite`로 대조하다 확인). 명시한 순서는 SQLite가 원래 돌려주던 기본키 순서와 같고,
실제 DB에서 전 조합의 행 순서가 같음을 확인했습니다. 새 조회를 추가할 때 여러 행을 돌려준다면 `ORDER BY`를 함께 쓰세요.

### 파이프라인 산출물 게시 (`pipeline_state`·`ctx_weather`)

`pipelines/db1`이 내놓는 `db1.sqlite`에는 v16 월별 작업기가 만드는 두 테이블이 없습니다. **원본 파일을 고치지 않고** 게시 단계에서 메웁니다(`data_pipeline/db1_compat.py`).

| 대상 | 산출물 | 게시 때의 처리 |
|---|---|---|
| `pipeline_state` | 없음 | `v16_run`의 상태에서 같은 이름·열의 **뷰**를 만듦. 산출물에는 «갱신 완료» 표지가 없어 준비 상태는 확인하지 못함(결과의 `compat`에 기록). 있으면 기존대로 확인 |
| `ctx_weather` | `ctx_weather_month`(월별 값) + `ctx_weather_window`(기준월별 3개월 관측기간) | 작업기의 `weather_context`와 **같은 모양**(`label_weather`, `observation_month_weather`)으로 변환해 적재. 원천이 없으면 빈 표(날씨 보조 문장 없이 답함) |

- 변환 모양을 맞춘 이유: 답변 생성기가 `observation_month_weather` 목록의 `month`·`rainfall_mm`·`rain_days`·`snow_days`를 읽습니다. 월별 값 하나만 넣으면 이 키가 없어 날씨 부분이 깨집니다.
- 한계: 산출물에는 «눈 기록이 `-`(확인 불가)였는지» 정보가 없어 변환 결과의 `snow_status`는 모두 `observed`입니다. 작업기가 만든 DB와 대조하지는 못했습니다.
- 받은 실제 `db1.sqlite`(수정 없음)를 2.8초에 게시했고(ctx_weather 48행 변환), 원본·SQLite·PostgreSQL의 답변이 같음을 확인했습니다.

### 전환 상태

| 항목 | 상태 |
|---|---|
| 챗봇이 읽는 저장소 | **PostgreSQL뿐.** SQLite 서빙 코드(`SqliteDb1Repository`, 단독 실행 `cli/main/menu`, `rebind_snapshot`)는 삭제함 |
| 남겨 둔 SQLite | 계산 파이프라인 출력(`monthly_worker`·`runner`·`snapshot_manager`)과 게시 입력, 테스트 픽스처(`db1_fixture`) |
| 계산 파이프라인 | 계속 SQLite에 계산 결과를 씀. 서빙에서만 빠지는 것이며, 게시(`publish_v16_to_postgres.py`)가 PostgreSQL로 옮김 |
| 배포 전 필수 | **먼저 게시**해야 v16이 답함. 게시된 자료가 없으면 `data_ready()`가 False라 동·그룹 분석이 대신 답함(오류는 아님) |

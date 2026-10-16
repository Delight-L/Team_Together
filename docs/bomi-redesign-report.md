# 보미 재설계 보고서

대상: `backend`의 보미 챗봇(구 `supervisor`·`v16_service`·`welfare/service` → `backend/bomi/`)
범위: 챗봇(`bomi/`)을 새로 설계하고, v16 데이터 접근을 정리했습니다. 챗봇 외 코드는 로직 변경 없이 복사했습니다.
현재 구조는 [보미 챗봇 구조](bomi-architecture.md), 질문별 측정표는 [성능 측정 기록](bomi-performance-comparison.md)에 있습니다.
팀 저장소에 합친 과정은 [13장](#merge)을 보세요.
전제: 프런트엔드(`BomiChat.jsx`)와의 이벤트 계약은 그대로 유지합니다(프런트 수정 없음).

## 1. 한눈에 보기

| 영역 | 개선 전 | 개선 후 |
|---|---|---|
| 담당 선택 | 6곳에 분산 (`fixed_route`·`rule_route`·`_ai_route`·`route`·`check_and_route`·`_events`) | `Router` 하나 |
| 담당 에이전트 | 5개 (`analysis`와 `regional_v16`이 중복) | 4개 (`region_analysis`로 통합) |
| `supervisor.py` | 370줄에 가드레일·라우팅·문구·이벤트가 혼재 | 책임별 모듈로 분리, 최대 파일 172줄(어댑터 제외) |
| `asyncio.run` | 7곳 (`run` 6 + `Runner` 1) | `aio.py` 1곳 |
| 응답 형식 | dict 암묵 약속과 비동기 스트림이 혼재 | 모두 `Iterator[Event]` |
| `done` 이벤트 | supervisor와 welfare가 각자 보냄 | `events.seal`이 정확히 한 번 |
| 입력·출력 규제 | supervisor 한곳 + 곳곳에 흩어진 가림 | 에이전트별 `Policy` (규칙 + moderate API) |
| v16 데이터 접근 | SQL이 3개 파일에 흩어짐, 질문당 연결 6~148회 | `Db1Repository` 계약 + SQLite 구현, 질문당 연결 1회 |

## 2. 진단된 문제와 해결

### 2-1. 챗봇 구조

| # | 문제 | 해결 | 위치 |
|---|---|---|---|
| 1 | 담당 선택이 여러 곳에 분산, `fixed_route`가 요청당 최대 3번 호출, `_events`가 결과를 다시 바꿈 | 선택 우선순위(고정 규칙 → AI → 키워드 규칙)를 한 클래스로 통합 | `bomi/routing.py` |
| 2 | supervisor가 가드레일·라우팅·문구·위험 신호 요약·이벤트 생성을 모두 가짐 | 안전·라우팅·문구·에이전트·이벤트로 분리 | `bomi/*` |
| 3 | `asyncio.run` 7곳과 동기↔비동기 어댑터 | 동기/비동기 변환을 한 모듈로 | `bomi/aio.py` |
| 4 | `analysis`와 `regional_v16`이 중복이라 "v16 자료 없으면 analysis로"를 라우터가 처리 | 한 에이전트로 합치고, 설명기 선택과 대체를 에이전트 안으로 이동 | `agents/region_analysis.py` |
| 5 | 에이전트마다 응답 방식이 다름 (welfare는 스트림, 나머지는 dict) | 공통 `Reply`와 `deliver()`, 스트리밍은 `Iterator[Event]` | `agents/base.py` |
| 6 | 키워드·고정 문구가 로직과 섞임 | 키워드·분류 함수와 고정 문구를 분리 | `questions.py`, `phrases.py` |
| 7 | `sys.path` 조작으로 `chatbot_agent`를 최상위 이름으로 임포트 | 조작과 임포트를 어댑터 한 파일에 가둠 | `adapters/v16.py` |
| 8 | 가드레일이 두 겹으로 중복, 유해 검사는 AI 모드에서만 | 에이전트별 정책으로 선언 | `regularization.py` |
| 9 | 예외 처리가 에이전트마다 다르고 상세가 노출될 수 있음 | `seal`이 `error` + `done`으로 통일, 상세는 로그에만 | `events.py` |
| 10 | 요청 컨텍스트가 느슨한 dict로 전달 | `ChatRequest`·`GroupSelection` 타입 | `request.py` |

### 2-2. 입력·출력 규제

에이전트마다 `Policy`를 선언합니다. 규칙의 정의(정규식·단어 목록)는 `chatbot/guardrails.py`에 그대로 두었습니다.

| 에이전트 | 입력 규칙 | 입력 moderate | 출력 가림 | 출력 moderate |
|---|:-:|:-:|:-:|:-:|
| region_analysis | ✓ | ✓ | `explain_ai`가 근거 대조 | ✓ (AI 해석문) |
| welfare | ✓ | ✓ | ✓ (줄 단위 스트림) | ✓ (끝에서 `replace`) |
| report | ✓ | ✓ | `check_grounding`이 근거 대조 | ✓ (AI가 다듬은 경우) |
| guide | ✓ | ✓ | – | – (고정 문구) |

- moderate API는 AI 모드에서만 호출하고, 키가 없거나 호출이 실패하면 통과시킵니다.
- AI가 쓴 글에만 출력 moderate를 걸어, 자료 조회나 고정 문구에는 호출이 늘지 않습니다.
- 단어 규칙에 걸린 질문은 외부 호출 없이 `guide`(안전 검사)로 보내 차단합니다.

### 2-3. v16 데이터 접근

| 개선 | 내용 |
|---|---|
| 저장소 계약 분리 | SQL이 `query_service`·`consumption_trends`·`repository`에 흩어져 있던 것을 `Db1Repository` 계약 + `SqliteDb1Repository` 구현으로 모음. 소스 검사 테스트가 SQL이 다시 새는 것을 막음 |
| 연결 재사용 | 저장소 객체당 읽기 전용 연결 1개, "갱신 완료" 확인은 연결을 열 때만 |
| 결과 캐시 | 같은 탐지·근거 표, 지역 유형, 소비 원자료, 코드 표를 한 번만 읽음. 호출부에는 사본을 돌려줘 캐시 오염 방지 |
| 변경 감지 | 작업 DB는 `PRAGMA data_version`과 파일 크기·수정 시각으로 감지, 불변 `snapshots/`는 생략 |
| 중복 쿼리 제거 | `supplements`·`consumption_evidence`의 같은 SQL·인자 재질의 제거, `sqlite_master` 확인 1회 |
| 조건 내리기 | 소비 원자료를 필요한 기간·동·연령만 SQL로 읽음(결과 동일, 속성 테스트로 검증) |
| 동별 정렬 인덱스 | `activity(동, 기간)`이 그 동의 행만 정렬해 두고 날짜를 이진 탐색. 날짜 순서가 어긋나면 기존 방식으로 처리 |

## 3. 개선 이후의 결과

### 3-1. 효율 (합성 DB: 동 22개, 6개월, 신호 27건, 공개 snapshot 기준)

조건 내리기·동별 인덱스 적용 후에는 신호 목록 177~196ms, 지역 배경 25~28ms, 소비 4~5ms입니다(3회 범위). 아래 표는 연결 재사용·캐시 단계의 결과입니다.

| 질문 | 연결 | 쿼리 | 시간 |
|---|---|---|---|
| 신호 목록 | 148 → **1** | 607 → **46** | 991 → **286 ms** |
| 지역 배경(5개 동) | 35 → 1 | 101 → 21 | 91 → 42 ms |
| 소비(2개 동·6개월) | 6 → 1 | 30 → 18 | 12 → 10 ms |
| 동 변화 이유 | 4 → 1 | 15 → 12 | 9 → 15 ms (측정 오차 범위) |

작업 DB(변경 감지 포함)에서는 신호 목록의 쿼리가 183회입니다. 변경 감지 쿼리(`PRAGMA data_version`)가 호출마다 더해지기 때문이고 시간은 거의 같습니다. 실제 서비스가 쓰는 불변 공개본에서는 46회입니다.

### 3-2. 검증

| 항목 | 개선 전(기존 backend) | 개선 후(backend) |
|---|---|---|
| 챗봇 테스트 | 116개 (건너뜀 2) | `bomi` 135개 (건너뜀 2) + `chatbot` 27개 |
| `db` 테스트 | 35개 (건너뜀 1) | 35개 (건너뜀 1) |
| `api` 테스트 | 56개 (건너뜀 2) | 56개 (건너뜀 2) |

| 동작 보존 대조 | 결과 |
|---|---|
| 담당 선택 (구 `rule_route` 대 새 `Router`, 질문 44개 × 그룹 유무) | 88건 중 차이 **0** |
| 이벤트 스트림 전체 (AI 끔, 질문 17개 × 그룹 유무) | 34건 중 차이 **0** |
| v16 저장소 출력 (합성 DB 2종, 질문 유형 13개) | **바이트 단위 동일** |
| 서버 기동 | `/api/health` 정상 |

### 3-3. 코드 규모

| 구분 | 줄 수 |
|---|---:|
| 기존 챗봇 코어 (`supervisor`, `v16_service`, `orchestrator`, `welfare/service`, `routes_chat`) | 871 |
| 새 `bomi` + `routes_chat` (테스트 제외) | 1,395 |
| 새 `bomi` 테스트 | 1,813 |

줄 수는 **늘었습니다.** 이전에는 암묵적이던 책임(이벤트 계약, 요청 타입, 입력·출력 규제, 저장소 계약)을 코드로 드러냈기 때문입니다. 줄 수 감소가 아니라 한 파일의 책임 수와 최대 파일 길이(370줄 → 172줄, v16 어댑터 제외)를 줄인 개선입니다.

## 4. 달라진 동작

| 항목 | 기존 | 새 구조 | 영향 |
|---|---|---|---|
| `route.agent` 값 | `analysis` / `regional_v16` | `region_analysis` | 화면은 `label`만 써서 영향 없음 |
| 유해 검사 시점 | 담당 선택과 동시 실행 | 담당 선택 후 에이전트가 실행 | AI 모드에서 응답이 조금 늦어질 수 있음 |
| AI가 `analysis`를 고른 그룹 화면 질문 | 항상 그룹 설명기 | 에이전트 안의 규칙이 선택 | 경계 질문에서 답이 달라질 수 있음 (키워드 경로는 대조에서 동일) |
| 출력 moderate | 없음 | AI가 쓴 글에 적용, 걸리면 `replace`로 차단 안내 | 새 기능 |

## 5. 아직 하지 못했거나 남은 것

| 항목 | 상태 |
|---|---|
| 실제 `db1.sqlite`로 검증 | **완료**(8장). 원본·신규(SQLite 3경로)·PostgreSQL의 출력이 모두 동일. 단 파일에 없는 테이블 2개(`pipeline_state`, `ctx_weather`)를 복사본에 추가해 측정 |
| AI가 담당을 고르는 경로, moderate API 실제 호출 | 외부 호출이 필요해 구 backend와 직접 대조하지 못함 (가짜 응답으로만 테스트) |
| 조건을 SQL로 내리기 | 소비 원자료는 **완료**. 탐지 표(JSON 행)는 **의도적으로 하지 않음** — 일부 행만 읽으면 열 집합이 달라져 동작이 바뀔 수 있어 같은 목표를 인덱스로 달성 |
| 남은 병목 | 신호 목록은 여전히 `_age_signal_changes`가 `activity()`를 136회 부르고, 동별 정렬 인덱스를 처음 만드는 비용(동·연령대마다 약 1ms)이 큼. 질의 로직이라 손대지 않음 |
| PostgreSQL 구현 | **구현·검증 완료**. 운영 DB 전환도 완료(2026-10-16, v16 자료는 모두 PostgreSQL에서 읽음) |
| 게시 명령 | 문서에 쓰인 `scripts/publish_v16_to_postgres.py`는 팀 저장소에 없음. 지금은 `data_pipeline/publish_postgres.py`의 `publish`·`activate` 함수만 있음 |
| `region_analysis`의 출력 가림 | `explain_ai`(db 계층)에서 처리. `Policy`에서는 moderate만 적용 |
| moderate 인프라 장애 정책 | `ai_settings` 키 조회 중 DB 오류가 나면 `seal`이 `error`로 처리. 통과시킬지는 정하지 않음 |

## 6. 다음 단계 (권장 순서)

1. ~~실제 `db1.sqlite`로 세 구현 대조~~ 완료(9장)
2. ~~운영 DB 게시~~ 완료. 원격 서버의 응답 시간은 아직 측정하지 않음
3. ~~SQLite 서빙 경로 제거~~ 완료(12장)
4. ~~서버 전환과 문서 갱신~~ 완료. `main.py`는 처음부터 `backend.api.server`를 실행하므로 바꿀 것이 없었음
5. 게시 명령(`scripts/publish_v16_to_postgres.py`)을 팀 저장소에 추가

## 7. 산출물

| 파일 | 내용 |
|---|---|
| `backend/bomi/` | 새 챗봇 코어 (`pipeline`·`routing`·`regularization`·`events`·`request`·`questions`·`phrases`·`aio`, `agents/`, `adapters/`, `tests/`) |
| `backend/agents/regional_v16/chatbot_agent/db1_repository.py` | 저장소 계약 |
| `backend/agents/regional_v16/chatbot_agent/repository.py` | 공통 조회 로직 `SqlDb1Repository` (연결 재사용·캐시) |
| `backend/agents/regional_v16/chatbot_agent/pg_repository.py` | PostgreSQL 구현 |
| `backend/agents/regional_v16/data_pipeline/publish_postgres.py`, `db1_compat.py` | 게시와 산출물 변환 |
| `backend/tools/v16_bench/` | 성능 측정 재현 도구 |
| [bomi-architecture.md](bomi-architecture.md), [architecture/bomi_chat_flow.mmd](architecture/bomi_chat_flow.mmd) | 구조와 흐름도 |
| [bomi-performance-comparison.md](bomi-performance-comparison.md) | 실제 db1.sqlite 측정 기록 |

## 8. PostgreSQL 구현 결과

| 항목 | 내용 |
|---|---|
| 구조 | 조회 로직을 `SqlDb1Repository`로 공통화하고 `SqliteDb1Repository`·`PostgresDb1Repository`가 연결·신선도·상태만 구현 |
| 저장 | `db1.v16_<테이블>(run_id, 원래 열)` + 활성 run 포인터 + 고정 run만 보이는 뷰(`db1_v16`). **조회 SQL은 그대로** |
| 게시 | 한 트랜잭션으로 적재·검증·포인터 변경, 멱등, 롤백(`--activate`), 정리 |
| 일관성 | 연결을 열 때 run을 고정해 한 답변 안에서 버전이 섞이지 않음 |
| 검증 | 세 구현의 출력이 바이트 단위로 동일(합성 DB 2종 × 질문 유형 13개), 챗봇 답변 동일, 테스트 170개 통과(건너뜀 4) |
| 기본 동작 | **PostgreSQL이 기본.** `DB1_REPOSITORY=sqlite`일 때만 SQLite(롤백용) |

한계: 실제 `db1.sqlite`가 아닌 합성 DB로 검증했고, 서버는 같은 컴퓨터의 로컬 PostgreSQL 16이었습니다.

## 9. 실제 db1.sqlite 비교 결과

같은 `db1.sqlite`(88개 테이블, 약 380MB)와 같은 질문으로 원본 `backend_old`와 `backend`를 각각 실행해 비교했습니다.
상세는 [성능 측정 기록](bomi-performance-comparison.md), 재현은 `backend/tools/v16_bench/`입니다.

| 항목 | 원본 | 신규 (snapshot) | 개선 |
|---|---:|---:|---|
| 엔진 수준 11개 질문 합계 | 1,120 ms | 547 ms | **2.0×** (51% 감소) |
| 챗봇 답변 전체 7개 질문 합계 | 579 ms | 362 ms | **1.6×** (37% 감소) |
| 지역 배경 (보조 자료) | 315 ms | 26 ms | **12×** |
| 소비 (2개 동·6개월) | 107 ms | 12 ms | **9×** |
| DB 연결 / 질문 | 3~15회 | 1회 | |
| 메모리 정점(소비·지역 배경) | 27 MB | 0.3~1.9 MB | |

- **출력은 모두 동일**했습니다(원본, 신규 3경로 = snapshot·작업 DB·PostgreSQL, 18개 질문 × 5라운드).
- 탐지 표만 읽는 질문은 개선이 0.8~1.6배로 작거나 오차 범위입니다(동 변화 이유·연령별 변화는 원본과 동일 수준). 이 DB는 탐지 행이 132행이고 신호가 1건뿐이라 반복 읽기를 없앤 효과가 작게 나타납니다.
- **실제 데이터로 PostgreSQL을 대조하다 행 순서 불일치를 발견해 고쳤습니다.** SQLite는 기본키 순서, PostgreSQL은 저장 순서로 돌려줘서 `ORDER BY` 없는 여러 행 조회의 순서가 달랐습니다. 6곳에 기본키 순서의 `ORDER BY`를 명시하고, 실제 DB에서 원래 SQL과 행 순서가 같음을 전수 확인했습니다.
- 받은 `db1.sqlite`는 파이프라인 산출물이라 `pipeline_state`와 `ctx_weather`가 없어 **두 구현 모두 그대로는 열리지 않습니다**(같은 오류). 원본은 건드리지 않고 SQLite 복사본에 두 테이블을 추가·변환해 측정했고, PostgreSQL은 원본 파일을 수정 없이 게시했습니다(게시 단계가 변환).

### 질문마다 개선 폭이 다른 이유

| 질문 유형 | 개선 폭 | 이유 |
|---|---|---|
| 소비·지역 배경 | 큼 (9~16배) | 원본이 큰 테이블(`a3a_feature` 10,560행 등)을 통째로 읽었음. 필요한 행만 읽도록 바꾼 효과가 지배적 |
| 이례적 변화 순위 | 중간 (2.4배) | 원본이 같은 표를 12번 연결해 304회 쿼리. 연결·캐시 효과 |
| 신호 목록·동 변화 이유·연령별 변화 | 작음 (0.8~1.6배, 일부는 오차 범위) | 읽는 표(`a2_*`)가 132~660행으로 작아 읽기 자체는 싸고, 시간 대부분이 pandas 처리. **동 변화 이유와 연령별 변화는 원본보다 빠르다고 말할 수 없습니다**(이 컴퓨터에서 5라운드 범위가 겹쳐 «동일 수준»으로 해석) |
| 짧은 질문 (판정 기준, 지역 유형) | 2~3배 | 시간이 거의 연결·확인 비용이어서 연결 1회화의 효과가 상대적으로 큼 |

### 성능에 불리하거나 확인하지 못한 점

| 항목 | 내용 |
|---|---|
| 메모리 | 탐지 표를 요청 동안 들고 있어 신호·연령 질문에서 약간 더 씀 (5 → 7MB, 답변 전체 기준 최대 8.7MB) |
| AI 모드 지연 | 유해 검사(moderate API)가 담당 선택과 **동시에** 실행되던 구조에서, 담당 선택 후 에이전트 안에서 **순차**로 실행되도록 바뀜. AI 모드에서 응답이 moderate 호출만큼 늦어질 수 있음. 이 지연은 측정하지 못함(외부 호출) |
| 작업 DB 경로 | 변경 감지 쿼리가 더해져 쿼리 수가 조금 많음(예: 신호 목록 24회 대 17회). 시간 차이는 대체로 오차 범위 |
| PostgreSQL | 로컬 서버에서는 SQLite snapshot과 같은 수준(합계 490 ms 대 474 ms). **원격 서버의 네트워크 지연은 측정하지 못함**. 질문당 쿼리가 4~40회라 왕복 시간이 직접 더해짐 |
| 데이터 규모 | 실제 데이터의 신호가 1건뿐이라 «신호가 많은 경우»의 개선은 합성 DB로만 확인함 |
| 측정 오차 | 질문에 따라 ±20~30% 흔들림. 범위가 겹치는 값은 오차 범위로 해석해야 함 |
| 측정용 데이터 | 받은 `db1.sqlite`에 없는 `pipeline_state`·`ctx_weather`를 SQLite 복사본에 추가·변환해 측정함(원본 파일은 수정하지 않음). PostgreSQL 경로는 **원본 파일을 수정 없이** 게시해 측정. 날씨의 눈 기록 상태(`snow_status`)는 복원하지 못함 |

### 다음에 더 줄일 수 있는 곳

| 대상 | 내용 | 비고 |
|---|---|---|
| `_age_signal_changes` | 신호 행 × 연령대 5개마다 `activity()`를 호출(실제 데이터에서 136회). 동·월별로 한 번에 묶어 조회하면 호출이 크게 줄 것 | 질의 로직이라 구조 변경 필요. 신호가 많을수록 효과 큼 |
| `_load_frame`의 행 단위 `apply` | 신호 종류를 행마다 판정하는 `DataFrame.apply(axis=1)` | 벡터화는 가능하지만 NaN·None 처리까지 같은 결과를 보장하는 검증이 필요 |
| 동별 인덱스 생성 | 동마다 정렬하는 비용(동·연령대당 약 1ms) | 신호가 많아 거의 모든 동을 쓰는 질문에서 비중이 큼 |
| PostgreSQL 왕복 | 한 질문의 쿼리를 묶어서 보내기 | 원격 서버에서 효과가 클 가능성이 있으나 측정 후 판단 |

## 10. 파이프라인 산출물 게시 (두 테이블 문제 해결)

| 항목 | 내용 |
|---|---|
| 문제 | 받은 `db1.sqlite`에 `pipeline_state`·`ctx_weather`가 없어 SQLite 서빙은 열리지 않고, PostgreSQL 게시도 거부됨 |
| 해결 | 원본 파일은 그대로 두고 게시 단계에서 변환: `pipeline_state`는 run 상태 뷰, `ctx_weather`는 `ctx_weather_month`·`ctx_weather_window`에서 작업기와 같은 모양으로 변환 |
| 발견 | 처음 측정용으로 쓴 임시 `ctx_weather`(월별 값 하나)는 작업기의 모양과 달랐음. 답변 생성기는 `observation_month_weather` 목록을 읽으므로 이 모양을 맞춰야 함. 변환 코드를 바로잡고 측정을 다시 함 |
| 검증 | 수정 없는 원본을 게시(2.8초), 합성 DB로 변환 결과가 작업기 형식과 같음·누락 월 표기·원천 없음 처리·실제 준비 상태 거부·이후 정식 게시로의 교체를 테스트 |
| 한계 | 눈 기록 상태(`snow_status`)는 복원 불가. 산출물에 준비 상태 개념이 없어 게시가 준비 여부를 확인하지 못함 |

## 11. PostgreSQL 기본 전환

| 항목 | 내용 |
|---|---|
| 변경 | v16 근거 저장소의 기본값을 SQLite에서 PostgreSQL로 변경. `DB1_REPOSITORY=sqlite`로만 SQLite 선택 |
| 오타 처리 | 알 수 없는 값(`postgress` 등)은 조용히 SQLite로 가지 않고 오류. `data_ready()`는 경고를 남기고 «자료 없음»으로 처리해 서버는 계속 동작 |
| 영향 | **배포 전에 게시가 필요**. 게시가 없으면 v16 대신 동·그룹 분석이 답함(이전에 SQLite 파일이 없을 때와 같은 동작) |
| 남긴 것 | SQLite 서빙 코드(롤백용). 삭제하지 않음 |
| 검증 | 기본값(환경변수 없음)에서 PostgreSQL을 읽음, 답변이 SQLite와 동일, 오타 처리, 테스트 182개 통과 |

## 12. SQLite 서빙 코드 제거

| 항목 | 내용 |
|---|---|
| 제거 | `SqliteDb1Repository`, `DataRepository` 별칭, `Chatbot.rebind_snapshot`, 단독 실행 `cli.py`·`main.py`·`menu.py`, 어댑터의 `DB1_REPOSITORY=sqlite` 경로 |
| 동작 | `Chatbot`은 저장소를 주입받지 않으면 `ValueError`. 남은 `DB1_REPOSITORY=sqlite`는 오류(`data_ready()`는 경고 후 «자료 없음») |
| 남긴 것 | 계산 파이프라인 출력(`monthly_worker`·`runner`·`snapshot_manager`), 게시 입력 SQLite, 테스트 픽스처 |
| 테스트 | 저장소 계약 테스트를 mixin으로 바꿔 PostgreSQL 구현으로 실행. SQLite와 PostgreSQL 답변 비교 테스트는 비교 대상이 없어져 «게시본에서 답함»·«파이프라인 산출물 게시 후 답변 동일»로 대체. 전체 190개 통과(건너뜀 2: PostgreSQL이 없을 때와 게시된 실제 자료가 없을 때) |
| 주의 | 테스트는 `pgserver` 또는 `TEST_DB1_PG_URL`이 없으면 건너뜀(개발 의존성에 `pgserver` 추가 권장) |

<a id="merge"></a>

## 13. 팀 저장소에 합치기 (2026-10-16)

| 항목 | 내용 |
|---|---|
| 문제 | 재설계 복사본은 10-15 16:45(`88aa80d`) 시점의 backend를 기준으로 만들어져, 그대로 덮어쓰면 그 뒤의 커밋 약 30개(DB2 복지 조회, v16 대시보드 맥락 수정, `backend/common.py` 통합 등)가 사라짐 |
| 방법 | 복사본을 `88aa80d` 위의 커밋으로 만들어 3-way 병합. 충돌은 `routes_chat.py`·`chatbot_agent/repository.py`와 하위 README 2개뿐 |
| bomi로 옮긴 것 | 복지자료 DB2 조회(`load_resources`, 조회 실패 안내), 업무 기록 한 건 조회(`mission_store.load`), v16 대시보드 맥락·지표 버튼·화면 요약·연령+지표 우선·소비+날씨·«이 사례» 되묻기, 보고서 근거 대조 테스트 |
| 옮기지 않은 것 | v16 의도 분류에서 제공사 SDK를 직접 부르던 코드와 «Gemini» 고정 문구(공용 `llm` 창구 설계와 충돌), 엔진에 없는 `excluded_months`·`age_signals` 처리 |
| 삭제 | 구 챗봇 코어 `agents/supervisor.py`·`agents/v16_service.py`·`chatbot/welfare/service.py`·`welfare/app/dialogue/orchestrator.py`, v16 단독 실행 `cli.py`·`main.py`·`menu.py`, 이들을 검사하던 테스트 9개(같은 검사는 `bomi/tests`에 있음) |
| 문서 | `backend/`의 문서 5개와 `bomi/README.md`를 `docs/`의 문서 3개와 `backend/README.md`로 합침 |
| 원본 보존 | 병합 전 복사본은 `backup/teammate-bomi-copy` 브랜치에 있음 |

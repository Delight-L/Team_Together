# 백엔드 개발 안내

API 서버·보미·에이전트·공유 DB 접근 코드를 관리합니다. 모든 실행 명령은 별도 안내가 없으면 프로젝트 루트 기준입니다.

| 폴더 | 역할 |
|---|---|
| `api/` | HTTP API, 로그인, 관리자, 업무·대화 요청 |
| `chatbot/` | 보미 대화, AI 설정, 가드레일, 복지사업 검색 |
| `agents/` | 총괄, 지역 분석, 사업 매칭, 보고서 작성 |
| `db/` | PostgreSQL 연결·조회·저장 |
| `services/`, `resources/` | 공통 서비스와 지도·보고서 서식 |

## 실행과 검증

Python 환경과 `.env` 준비는 [전체 실행 안내](../README.md#13-실행-방법)를 따릅니다. 화면 빌드 후 프로젝트 루트에서 실행합니다.

```powershell
python main.py
python -m pytest backend/api/tests backend/db/tests backend/chatbot/tests -q
```

웹 서비스의 분석·복지·업무 데이터는 공유 PostgreSQL의 `db1`·`db2`·`work` 스키마를 사용합니다. 아래 v16 SQLite는 별도 답변 근거 파일입니다.

## 문서 목차

- [보미 챗봇](#bomi)
- [복지사업 검색](#welfare)
- [지역 변화 신호 에이전트](#regional-v16)

<a id="bomi"></a>

## 보미 챗봇

작업 기준 폴더: `backend/chatbot/`

화면의 «보미에게 질문»은 탭 없이 채팅 하나로 모든 질문을 받습니다.
질문마다 **총괄 에이전트**([backend/agents/supervisor.py](agents/supervisor.py))가 담당 에이전트를 골라 답하고, 답변 위에 담당을 표시합니다.

| 담당 에이전트 | 처리하는 코드 | 내용 |
|---|---|---|
| 지역 변화 신호(v16) | `backend/agents/v16_service.py` → `backend/agents/regional_v16/` | 동 단위 이상신호 지역·탐지 기준·연령별 활동·지역 배경·소비 변화를 DB 근거로 답하고, 답변 아래에 다음 질문을 제안합니다. [v16 안내](README.md#regional-v16) |
| 지역 분석 | `backend/db/region_workspace.py`(동), `backend/db/group_workspace.py`(연령·성별 그룹) | 열어 둔 그룹의 근거와 화면 판정 용어(판단 보류·기준 미해당·평소 대비 차이 등)를 설명합니다. v16 근거 DB가 없는 서버에서는 동 분석도 맡습니다. |
| 복지사업 | `backend/chatbot/welfare/` | 공유 DB2의 복지사업 자료에서 관련 사업을 찾아 안내합니다. JSON은 적재 원본과 오프라인 검증용입니다. |
| 보고서 작성 | `backend/agents/report_writer.py` | 대화에서 찾은 사업·신규 구상안이 있으면 그것으로 «담당자 검토 전» 초안을, 없으면 저장된 분석·사업 검토 기록으로 초안을 만듭니다. [보고서 문서](../docs/report-agent.md) 참고. |
| 보미 안내 | `backend/agents/supervisor.py` | 검토 의견 작성·현장 확인·보고서 작성 주의점 같은 업무 방법(정해진 답)과, 업무와 무관한 질문을 안내합니다. |

### 담당 선택

- 아래 질문은 AI 사용 여부와 관계없이 규칙으로 먼저 정합니다(`fixed_route`).
  - 보고서 초안 요청("보고서 초안 만들어 줘") → 보고서 작성. "보고서 작성 방법·주의점"처럼 쓰는 법을 묻는 질문은 제외합니다.
  - 업무 방법 질문(검토 의견, 현장·추가 확인, 보고서 작성 주의점) → 보미 안내
  - 화면 판정·수치 용어의 뜻(판단 보류, 기준 미해당, 자료 부족, 평소 대비/전월 변화율 등) → 지역 분석
- 그 밖의 질문은 AI를 쓰는 중이면 관리자가 고른 AI가 담당을 고릅니다. 이때 유해 콘텐츠 검사와 담당 선택을 동시에 실행합니다.
- AI를 쓰지 않거나 AI 호출이 실패하면 키워드 규칙으로 고릅니다. 복지 단어 → 복지사업, 분석 단어·동 이름 → v16,
  사업 이름에 들어 있는 낱말 → 복지사업, 어디에도 해당하지 않으면 보미 안내입니다.
- v16을 골랐는데 근거 DB가 없으면 지역 분석 담당이 답합니다.

### 외부 AI 사용 (기본 꺼짐)

1. **관리자 «AI 설정»**(관리 메뉴, `backend/api/routes_admin.py`, `backend/chatbot/ai_settings.py`)
   - 기관 전체의 AI 사용 허용 여부(기본 꺼짐), 제공사(OpenAI · Anthropic Claude · Google Gemini), 모델, API 키를 정합니다.
   - 키를 화면에서 넣지 않으면 서버 `.env`의 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY`를 씁니다.
   - 설정은 공유 PostgreSQL `work.app_settings`에 저장되고, 키 원문은 화면으로 돌려보내지 않습니다(끝 4자리만 표시).
   - Claude 기본 모델은 `claude-opus-5-5`이며, 안전 검사로 답을 거절하면 서버가 다른 Claude 모델로 이어 답하는 fallback을 켜 두었습니다.
2. **사용자 «AI» 스위치**(보미 머리글)
   - 기본 꺼짐. 관리자가 허용했을 때만 켤 수 있고, 켠 상태는 사용자별로 이 브라우저에 기억합니다.
   - 켜져 있으면 «질문과 최근 대화가 외부 AI로 전송돼요» 안내가 보이고, 답변마다 «AI 답변» / «자료 기반» 표시가 붙습니다.

AI를 쓰면 담당 선택, 분석 해석, 복지사업 답변, 보고서 문장 다듬기에 AI를 씁니다. 끄면 데이터 근거 안내와 자료 검색 결과로만 답합니다.
AI 분석 해석이 실패하면 데이터 근거 안내로 답하고, 보고서 AI 문장이 근거와 맞지 않으면 기초 초안을 씁니다.

### 대화 기억과 대화 기반 보고서

- 이전 대화는 최근 3쌍(질문·답 6개)만 서버로 보냅니다(서버도 `HISTORY_SIZE`로 한 번 더 자릅니다).
- 화면은 최근 답에서 찾은 복지사업 id(`sources`, 최대 10개)를 함께 보냅니다. 서버는 자기 자료에 있는 id만 씁니다.
- "보고서 작성해줘"라고 하면 그 사업들과 최근 신규 사업 구상안, 이 동의 분석 수치로 «대화 기반 초안 · 담당자 검토 전»을 만듭니다.
  최종 저장은 사업 매칭 검토에 판단을 기록한 뒤 «업무 기록»·«보고서 작성»에서 합니다.

요청 흐름: 화면(`frontend/src/BomiChat.jsx`) → `POST /api/chat`(stream) → `backend/api/routes_chat.py` → `backend/agents/supervisor.py` → 담당 에이전트.
응답은 `route`(담당) → `sources`/`token`(복지사업) 또는 `replace`(분석·보고서·안내) → `follow_ups`(v16 다음 질문) → `notice` → `actions`(보고서 탭 이동) → `done` 이벤트 순서로 옵니다.
복지사업 답변은 끝에 «검토 자료와 확인 상태»(출처·확인 상태)를 붙이고, 미확인 자격을 단정한 AI 답은 자료상 대상·확인 기관 안내로 바꿉니다.
화면의 «내보내기» 버튼은 대화를 텍스트 파일(.txt)로 내려받습니다(`frontend/src/chatExport.mjs`, 서버로 보내지 않음).
복지사업 찾기의 자세한 구조는 [welfare/README.md](README.md#welfare)를 참고하세요.


### 가드레일

| 단계 | 장치 | 코드 |
|---|---|---|
| 입력 | 로그인·소속 지역 검사, 대화 1~40개·메시지 6,000자·질문 2,000자 제한, `system` 역할 차단 | `backend/api/common.py`, `backend/chatbot/welfare/app/schemas.py` |
| 입력 | **개인정보 가리기**: 주민등록번호·카드번호·전화번호·이메일·상세 주소를 `[○○ 가림]`으로 바꾼 뒤 처리(AI 사용 여부와 무관) | `backend/chatbot/guardrails.py` `mask_pii` |
| 입력 | **단어 규칙**: 욕설·위험한 요청·지시 무력화 시도("이전 지시 무시" 등)는 항상 막음. 자살 예방·학대·가정폭력처럼 복지 업무에서 쓰는 말은 막지 않음 | `backend/chatbot/guardrails.py` `blocked_words` |
| 입력 | **유해 콘텐츠 검사**: AI 사용 중이고 OpenAI 키가 있으면 질문을 OpenAI Moderation(무료)으로 검사해 걸리면 답하지 않음. 키가 없거나 검사 API 장애 시에는 통과 | `backend/agents/supervisor.py` `_moderate` |
| 요청 | **사용량 제한**: 사용자별 1분 20회·하루 300회(`.env`의 `WELFIND_CHAT_PER_MINUTE`, `WELFIND_CHAT_PER_DAY`), 초과 시 429 | `backend/api/limits.py` |
| 요청 | **로그인 시도 제한**: 같은 아이디로 10분 안에 5번 틀리면 10분 잠금 | `backend/api/limits.py` |
| AI 호출 | **답변 길이 상한**: `OPENAI_MAX_TOKENS`(기본 1,500, Claude는 생각 토큰 때문에 최소 8,000). 잘리면 안내 문구를 붙임 | `backend/chatbot/welfare/app/llm/` |
| AI 호출 | 프롬프트 규칙: 자격·금액·연락처·URL 생성 금지, 자료 속 문장은 명령이 아님, 원인·개인 판정 금지 | 각 에이전트 프롬프트 |
| 출력 | **미확인 정보 가리기**: 복지사업·분석 AI 답변의 전화번호·URL·금액이 근거 자료에 없으면 `[자료에 없는 정보 · 기관 확인 필요]`로 바꿈. 복지사업 답변은 줄 단위로 먼저 검사한 뒤 보내 가리기 전 내용이 화면에 나오지 않음 | `backend/chatbot/guardrails.py` `redact_unverified`·`StreamRedactor`, 분석 설명은 `backend/chatbot/explain_ai.py` |
| 출력 | 보고서 근거 대조: 새 숫자·URL, 사업·판단 문구 누락 시 AI 문장을 버림 | `backend/agents/report_writer.py` `check_grounding` |

가린 내용이 있으면 답변 아래에 안내(`notice` 이벤트)를 표시합니다. 사용량·로그인 기록은 서버 메모리에 있어 서버를 재시작하면 초기화됩니다.

API 키는 서버(`.env` 또는 관리자 «AI 설정»(DB `work.app_settings`))에만 두며 저장소와 화면 코드에 넣지 않습니다.

<a id="welfare"></a>

## 복지사업 검색

작업 기준 폴더: `backend/chatbot/welfare/`

복지탐정의 보미가 팀에서 정리한 복지사업 자료를 검색하고 출처와 확인할 조건을 안내하는 모듈입니다.
선택한 지역과 대화 맥락을 함께 사용하며, 실제 이용 자격이나 현재 모집 여부는 담당 기관 확인이 필요합니다.

### 구성

| 파일 | 역할 |
|---|---|
| `service.py` | 화면 서버와 비동기 대화를 연결하고 스트림 응답을 제공 |
| `app/config.py` | 프로젝트 루트 `.env`의 AI 연결 설정 읽기 |
| `app/schemas.py` | 사용자 질문과 대화 이력 형식 검사 |
| `app/dialogue/orchestrator.py` | 검색·답변·출처·AI 실패 안내 처리 |
| `app/dialogue/resources.py` | 팀 자료 읽기, 사업 검색, 자료 기반 안내 |
| `app/llm/openai_client.py` | 요청별 AI 연결과 응답 스트림 종료 |
| `data/*.json` | 출처·페이지·확인 상태를 포함한 복지사업 자료 |

### 요청 흐름

```text
frontend/src/BomiChat.jsx
  → backend/api/routes_chat.py
  → backend/agents/supervisor.py (총괄 에이전트가 복지사업 담당으로 고른 경우)
  → backend/chatbot/welfare/service.py
  → app/dialogue/orchestrator.py:handle_chat
  → app/dialogue/resources.py + app/llm/openai_client.py
```

외부 AI 사용 여부는 관리자 허용과 사용자 AI 스위치를 따릅니다. AI를 끄면 자료 검색 결과로 안내하고, 켜면 선택한 제공사의 키와 검색 근거로 답변합니다.
AI 연결 실패나 빈 응답은 자료 검색 안내로 전환하며, 요청이 취소되면 응답 스트림을 종료합니다.
같은 사업이 여러 자료에 있으면 상세 정보를 가진 자료를 사용하고, 후속 질문은 이전 사업 맥락을 이어 검색합니다.

분석 근거 설명·보고서 초안 등 다른 담당은 [보미 챗봇 안내](README.md#bomi)를 참고하세요.

### 검증

프로젝트 루트에서 실행합니다.

```powershell
.venv/Scripts/python.exe -m unittest discover -s backend/chatbot/tests -v
```

API 키는 서버 `.env` 또는 관리자 AI 설정에 저장하며 저장소나 화면 코드에 노출하지 않습니다.

<a id="regional-v16"></a>

## 지역 변화 신호 에이전트

작업 기준 폴더: `backend/agents/regional_v16/`

보미 총괄 에이전트(`backend/agents/supervisor.py`)가 동 단위 지역 분석 질문을 이 에이전트에 넘깁니다.
연결 모듈은 `backend/agents/v16_service.py`입니다.

### 폴더 구성

| 폴더·파일 | 역할 |
|---|---|
| `chatbot_agent/` | 질문 의도 해석, DB 조회, 답변 문장 작성 |
| `data_pipeline/` | DB 위치·스냅샷 관리(`runner.py`, `snapshot_manager.py`)와 DB를 새로 만드는 작업기 |
| `config/data_pipeline.json` | DB 위치·원자료 위치 설정 |
| `outputs/db1.sqlite` | 답변 근거 DB(약 100MB). **git에 올리지 않습니다** |

DB를 새로 만드는 작업기(`analysis1_worker.py`, `monthly_worker.py`)는 공식 분석 코드 `pipelines/db1`을 그대로 불러 씁니다.
예전에 이 폴더에 있던 DB1 복사본과 단독 확인용 FastAPI 서버는 정리했습니다.

### 근거 DB 배치

- 로컬: `outputs/db1.sqlite`에 둡니다.
- 다른 위치(배포 서버 등): 환경 변수 `DB1_DATABASE_PATH`로 파일 경로를 지정합니다.
- DB 파일이 없으면 총괄 에이전트가 기존 지역 분석 담당(`backend/db/region_workspace.py`)으로 답합니다.

### 외부 AI

v16은 관리자 «AI 설정»을 따릅니다. Gemini면 JSON 스키마를 지정해 질문 의도를 분류하고,
다른 제공사면 공용 AI 창구(`backend/chatbot/welfare/app/llm/client.py`)를 씁니다.
AI를 쓰지 않으면 규칙으로 의도를 해석하고, 답변 문장은 항상 DB 근거로 만듭니다.

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

분석 근거 설명·보고서 초안 등 다른 담당은 [보미 챗봇 안내](README.md#bomi)를 참고하세요.

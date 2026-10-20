# 백엔드 개발 안내

API 서버·보미·에이전트·공유 DB 접근 코드를 관리합니다. 모든 실행 명령은 별도 안내가 없으면 프로젝트 루트 기준입니다.

처음 읽는 팀원은 [코드 읽기 순서와 가독성 기준](../docs/development-guide.md)에서
실행 시작점 → API → 보미 → DB 조회 순서로 따라가세요.

| 폴더 | 역할 |
|---|---|
| `api/` | HTTP API, 로그인, 관리자, 업무·대화 요청 |
| `bomi/` | 보미 챗봇 코어: 담당 선택, 입력·출력 규제, 이벤트 계약, 담당 에이전트 4종 |
| `chatbot/` | 챗봇과 다른 기능이 함께 쓰는 부품: AI 설정, 규칙 정의, 외부 AI 창구, 복지사업 검색 |
| `agents/` | 보고서 작성·사업 매칭, 지역 변화 신호 엔진(`regional_analysis/`) |
| `db/` | PostgreSQL 연결·조회·저장 |
| `services/`, `resources/` | 공통 서비스와 지도·보고서 서식 |
| `common.py` | 여러 폴더가 함께 쓰는 작은 도구: 프로젝트 경로(`ROOT`), `.env` 읽기, 서울 시각(`seoul_now`·`now_text`), 공용 DB 엔진(`get_engine`) |

## 실행과 검증

Python 환경과 `.env` 준비는 [전체 실행 안내](../README.md#13-실행-방법)를 따릅니다. 화면 빌드 후 프로젝트 루트에서 실행합니다.

```powershell
python main.py
python scripts/audit_repository.py
```

테스트는 Git 추적에서 제외되어 있습니다. 로컬 테스트를 별도로 보관한 환경에서는
`python -m pytest backend/api/tests backend/db/tests backend/chatbot/tests backend/bomi/tests -q`로 실행할 수 있습니다.

웹 서비스는 공유 PostgreSQL(`db1`·`db1_v16`·`db2`·`work` 스키마)을 사용합니다.
지역 분석 게시 테이블이 없으면 지역 분석 에이전트는 대시보드와 같은 DB1 조회 경로와 전달된 연령·소비·날씨 CSV를 사용합니다.
구조와 설계 이유는 [보미 챗봇 구조](../docs/bomi-architecture.md), DB 구성·반영 절차는 [데이터 운영 안내](../docs/data-operations.md)를 보세요.

## 문서 목차

- [보미 챗봇](#bomi)
- [복지사업 검색](#welfare)
- [지역 변화 신호 에이전트](#regional-analysis)

<a id="bomi"></a>

## 보미 챗봇

작업 기준 폴더: `backend/bomi/`

화면의 «보미에게 질문»은 탭 없이 채팅 하나로 모든 질문을 받습니다.
질문마다 `bomi/routing.py`의 `Router`가 담당 에이전트를 골라 답하고, 답변 위에 담당을 표시합니다.

| 담당 에이전트 | 처리하는 코드 | 내용 |
|---|---|---|
| 지역 분석 (`region_analysis`) | `bomi/agents/region_analysis.py` → 지역 분석(`bomi/adapters/regional_analysis.py` → `agents/regional_analysis/`), `db/region_workspace.py`(동), `db/group_workspace.py`(연령·성별 그룹) | 동 단위 이상신호 지역·탐지 기준·연령별 활동·지역 배경·소비 변화를 지역 분석 근거로 답하고 다음 질문을 제안합니다. 열어 둔 그룹의 근거와 화면 판정 용어(판단 보류·기준 미해당·평소 대비 차이 등)도 설명합니다. 지역 분석 자료가 없으면 동·그룹 분석 근거로 답합니다. [지역 분석 안내](#regional-analysis) |
| 복지사업 (`welfare`) | `bomi/agents/welfare.py`, `chatbot/welfare/` | 공유 DB2의 복지사업 자료에서 관련 사업을 찾아 안내합니다. JSON은 적재 원본과 오프라인 검증용입니다. |
| 보고서 작성 (`report`) | `bomi/agents/report.py` → `agents/report_writer.py` | 대화에서 찾은 사업·신규 구상안이 있으면 그것으로 «담당자 검토 전» 초안을, 없으면 저장된 분석·사업 검토 기록으로 초안을 만듭니다. [보고서 문서](../docs/report-guide.md) 참고. |
| 보미 안내 (`guide`) | `bomi/agents/guide.py` | 검토 의견 작성·현장 확인·보고서 작성 주의점 같은 업무 방법(정해진 답)과, 업무와 무관한 질문을 안내합니다. |

### 담당 선택

- 아래 질문은 AI 사용 여부와 관계없이 규칙으로 먼저 정합니다(`Router.fixed`).
  - 보고서 초안 요청("보고서 초안 만들어 줘") → 보고서 작성. "보고서 작성 방법·주의점"처럼 쓰는 법을 묻는 질문은 제외합니다.
  - 업무 방법 질문(검토 의견, 현장·추가 확인, 보고서 작성 주의점) → 보미 안내
  - 화면 판정·수치 용어의 뜻(판단 보류, 기준 미해당, 자료 부족, 평소 대비/전월 변화율 등) → 지역 분석
- 그 밖의 질문은 AI를 쓰는 중이면 관리자가 고른 AI가 담당을 고릅니다(`Router.by_ai`).
- AI를 쓰지 않거나 AI 호출이 실패하면 키워드 규칙으로 고릅니다(`Router.by_rules`). 복지 단어 → 복지사업, 분석 단어·동 이름 → 지역 분석,
  사업 이름에 들어 있는 낱말 → 복지사업, 어디에도 해당하지 않으면 보미 안내입니다.
- 서명된 사업 근거가 있는 후속 질문은 복지 담당으로 연결합니다. AI 사용 중 일반 안내로 분류된 생활 표현도 의미 검색·재정렬에서 관련 사업이 확인되면 복지 담당으로 연결합니다. 담당 선택은 `Router` 안에서만 하고 검색 결과를 복지 에이전트에서 재사용합니다.
- 단어 규칙(욕설·위험한 요청 등)에 걸린 질문은 외부 호출 없이 보미 안내로 보내 차단합니다.

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

- 이전 대화는 최근 3쌍(질문·답 6개)만 서버로 보냅니다(서버도 `bomi/regularization.py`의 `prepare`에서 한 번 더 자릅니다).
- 화면은 사업 id(`sources`, 최대 10개)와 서버가 서명한 대화 상태(`conversation`)를 함께 보냅니다. 상태에는 검색 문장·사업 ID·당시 원문·SHA-256·보존 시점을 넣고 로그인 세션과 지역·기준월·연령에 묶어 24시간 유지합니다. 새 대화 또는 화면 맥락 변경 시 초기화합니다.
- 후속 질문과 보고서는 대화 당시 원문을 사용합니다. 보고서 미리보기에서도 서명을 검사하며, 브라우저가 보낸 임의의 자료 본문은 근거로 신뢰하지 않습니다.
- "보고서 작성해줘"라고 하면 그 사업들과 최근 신규 사업 구상안, 이 동의 분석 수치로 «대화 기반 초안 · 담당자 검토 전»을 만듭니다.
  최종 저장은 사업 매칭 검토에 판단을 기록한 뒤 «보고서 작성»에서 합니다.

요청 흐름: 화면(`frontend/src/BomiChat.jsx`) → `POST /api/chat`(stream) → `backend/api/routes_chat.py` → `backend/bomi/pipeline.py`(규제·담당 선택) → 담당 에이전트 → `events.seal`.
응답은 `route`(담당) → `sources`/`token`(복지사업) 또는 `replace`(분석·보고서·안내) → `follow_ups`(지역 분석 다음 질문) → `notice` → `actions`(보고서 탭 이동) → `done` 이벤트 순서로 옵니다.
복지사업 답변은 끝에 «검토 자료와 확인 상태»(출처·확인 상태)를 붙이고, 미확인 자격을 단정한 AI 답은 자료상 대상·확인 기관 안내로 바꿉니다.
화면의 «내보내기» 버튼은 대화를 텍스트 파일(.txt)로 내려받습니다(`frontend/src/chatExport.mjs`, 서버로 보내지 않음).
이벤트 10종의 계약과 순서 규칙은 `bomi/events.py`와 [보미 챗봇 구조 5장](../docs/bomi-architecture.md#5-이벤트-계약-eventspy)에 있습니다. `conversation` 이벤트는 `sources` 직전에 서명된 대화 상태를 갱신하고, 마지막 `done`은 계속 `events.seal`에서 한 번만 보냅니다.
복지사업 찾기의 자세한 구조는 [복지사업 검색](#welfare)을 참고하세요.


### 가드레일

| 단계 | 장치 | 코드 |
|---|---|---|
| 입력 | 로그인·소속 지역 검사, 대화 1~40개·메시지 6,000자·질문 2,000자 제한, `system` 역할 차단 | `backend/api/common.py`, `backend/chatbot/welfare/app/schemas.py` |
| 입력 | **개인정보 가리기**: 주민등록번호·카드번호·전화번호·이메일·상세 주소를 `[○○ 가림]`으로 바꾼 뒤 처리(AI 사용 여부와 무관) | `backend/chatbot/guardrails.py` `mask_pii` |
| 입력 | **단어 규칙**: 욕설·위험한 요청·지시 무력화 시도("이전 지시 무시" 등)는 항상 막음. 자살 예방·학대·가정폭력처럼 복지 업무에서 쓰는 말은 막지 않음 | `backend/chatbot/guardrails.py` `blocked_words` |
| 입력·출력 | **유해 콘텐츠 검사**: AI 사용 중이고 OpenAI 키가 있으면 질문과 AI가 쓴 답을 OpenAI Moderation(무료)으로 검사해 걸리면 차단 안내로 바꿈. 키가 없거나 검사 API 장애 시에는 통과. 에이전트마다 어디에 거는지는 `Policy`로 선언 | `backend/bomi/regularization.py` |
| 요청 | **사용량 제한**: 사용자별 1분 20회·하루 300회(`.env`의 `WELFIND_CHAT_PER_MINUTE`, `WELFIND_CHAT_PER_DAY`), 초과 시 429 | `backend/api/limits.py` |
| 요청 | **로그인 시도 제한**: 같은 아이디로 10분 안에 5번 틀리면 10분 잠금 | `backend/api/limits.py` |
| AI 호출 | **답변 길이 상한**: `OPENAI_MAX_TOKENS`(기본 1,500, Claude는 생각 토큰 때문에 최소 8,000). 잘리면 안내 문구를 붙임 | `backend/chatbot/welfare/app/llm/` |
| AI 호출 | 프롬프트 규칙: 자격·금액·연락처·URL 생성 금지, 자료 속 문장은 명령이 아님, 원인·개인 판정 금지 | 각 에이전트 프롬프트 |
| 출력 | **미확인 정보 가리기**: 복지 답변은 전체 생성 후 사업별 금액·연락처·URL·날짜·나이·비율, 자격 단정과 출력 moderate를 검사한 뒤 전달. 생성은 45초 제한이며 실패 시 자료 안내로 전환. 신규 기획은 공통 가림 규칙 적용 | `bomi/agents/welfare.py`, `chatbot/welfare/app/dialogue/evidence.py`, `bomi/regularization.py`. 분석 설명은 `chatbot/explain_ai.py` |
| 출력 | 보고서 근거 대조: 새 숫자·URL, 사업·판단 문구 누락 시 AI 문장을 버림 | `backend/agents/report_writer.py` `check_grounding` |

가린 내용이 있으면 답변 아래에 안내(`notice` 이벤트)를 표시합니다. 사용량·로그인 기록은 서버 메모리에 있어 서버를 재시작하면 초기화됩니다.

API 키는 서버(`.env` 또는 관리자 «AI 설정»(DB `work.app_settings`))에만 두며 저장소와 화면 코드에 넣지 않습니다.

### 개발 규칙

- 담당 선택은 `bomi/routing.py`에서만 합니다. 자료 유무 같은 사정은 에이전트 안에서 처리합니다.
- 입력·출력 규제는 `bomi/regularization.py`의 `Policy`로 선언합니다. 규칙(정규식·단어)의 정의는 `chatbot/guardrails.py`에 있습니다.
- AI 호출은 `chatbot/welfare/app/llm/client.py`의 `llm`만 쓰고, 동기 코드에서는 `bomi/aio.py`의 `aio.run`/`aio.iterate`를 거칩니다.
- 이벤트 이름·내용을 바꾸면 화면이 깨집니다. `bomi/events.py`를 바꾸기 전에 `frontend/src/BomiChat.jsx`를 함께 확인하세요.

새 에이전트를 추가하려면:

1. `bomi/agents/`에 `RegulatedAgent`를 상속한 클래스를 만들고 `id`, `policy`, `answer(request) -> Iterator[Event]`를 정의합니다. 입력 규제는 `respond()`가 해 주고, `done`·`route`는 보내지 않습니다.
2. 한 번에 완성되는 답이면 `self.deliver(Reply(...))`(출력 규제 포함)를 쓰고, 스트리밍이면 `events.token(...)`을 `yield`하며 끝에서 `self.regulator.output_flagged_async`로 검사합니다.
3. `bomi/agents/__init__.py`의 `default_agents()`에 등록합니다.
4. `bomi/phrases.py`의 `AGENT_LABELS`와 `ROUTER_PROMPT`에 이름과 설명을 추가하고, 키워드 규칙이 필요하면 `Router.by_rules`에 둡니다.
5. `bomi/tests/test_routing.py`에 예시 질문을 추가합니다.

<a id="welfare"></a>

## 복지사업 검색

작업 기준 폴더: `backend/chatbot/welfare/`

복지탐정의 보미가 공유 DB2의 팀 문서·지자체 API·사업 회차 공고를 검색하고 출처와 확인할 조건을 안내하는 모듈입니다.
선택한 지역과 대화 맥락을 함께 사용하며, 실제 이용 자격이나 현재 모집 여부는 담당 기관 확인이 필요합니다.

### 구성

| 파일 | 역할 |
|---|---|
| `backend/bomi/agents/welfare.py` | 검색·답변·출처·AI 실패 안내, 스트림 응답(복지사업 담당 에이전트) |
| `backend/bomi/agents/welfare_prompt.py` | 복지사업 답변 지시문 |
| `app/config.py` | 프로젝트 루트 `.env`의 AI 연결 설정 읽기 |
| `app/schemas.py` | 사용자 질문과 대화 이력 형식 검사 |
| `app/dialogue/resources.py` | 팀 문서 읽기(1분 기억), API·공고 SQL 검색, 출처와 자료 기반 안내 |
| `app/dialogue/retrieval.py` | 지역·기간·참고 사례 검색 조건과 결과 재사용 |
| `app/dialogue/semantic.py` | Gemini 임베딩, 키워드 순위 결합(RRF), 후보 재정렬 |
| `app/dialogue/evidence.py` | 사업별 주요 사실을 근거와 대조 |
| `backend/bomi/conversation.py` | 대화 원문 스냅샷 서명·검증과 이벤트 연결 |
| `backend/db/welfare_chatbot_repository.py` | 복지 원문 조회·지역·기간 SQL 조건 |
| `backend/db/welfare_search_store.py` | 검색 색인·대화 서명키 DB 접근 |
| `app/llm/` | 외부 AI 창구 `llm`과 OpenAI·Anthropic·Gemini 어댑터 |
| `data/*.json` | DB 적재 원본과 명시적인 오프라인 검증용 자료 |

### 요청 흐름

```text
frontend/src/BomiChat.jsx
  → backend/api/routes_chat.py
  → backend/bomi/pipeline.py (Router가 복지사업 담당으로 고른 경우)
  → backend/bomi/agents/welfare.py
  → app/dialogue/resources.py + app/llm/client.py
```

외부 AI 사용 여부는 관리자 허용과 사용자 AI 스위치를 따릅니다. AI를 끄면 자료 검색 결과로 안내하고, 켜면 선택한 제공사의 키와 검색 근거로 답변합니다.
AI 연결 실패나 빈 응답은 자료 검색 안내로 전환하며, 요청이 취소되면 응답 스트림을 종료합니다.
같은 사업이 여러 자료에 있으면 상세 정보를 가진 자료를 사용하고, 후속 질문은 이전 사업 맥락을 이어 검색합니다.

일반 조회는 선택 지역·광역·전국 자료를 대상으로 기간이 지난 자료와 시작 전 자료를 제외합니다. 사업 공고는 접수기간을 별도로 확인하여 운영 시작 전이라도 접수 중이면 검색합니다. 과거·타 지역 사례·신규 기획 요청은 범위를 별도로 허용하고 해당 상태를 표시합니다. 현재 모집 질문에는 현재 운영·신청 확인이 없는 계획문서를 추천하지 않습니다. 자료 수집일은 운영 확인일이 아니며, 지역 일치도 이용 자격을 보장하지 않습니다.

`query_rules.py`는 “과거 계획은 제외” 같은 명시적인 제외 요청을 과거 자료 포함보다 우선합니다. “제외하지 말고”는 포함 의도를 유지합니다. 후속 질문에서도 과거 자료를 제외하면 이전 스냅샷을 그대로 재사용하지 않고 새 조건으로 검색합니다. 고유 사업명은 우선 조회하지만 “주거비·생활비·교통비” 같은 일반 항목명만으로 검색 후보를 독점하지 않습니다. 일반 항목을 따옴표나 이름으로 명시하면 해당 항목을 조회할 수 있습니다.

문서에서 확인된 고유 사업명을 명시했지만 지역·기간 조건에서 해당 사업이 제외된 경우에는 의미 검색이나 AI 연결 실패 시의 대체 검색에서도 다른 사업으로 바꾸지 않고 결과가 없음을 안내합니다. Gemini 클라이언트와 응답 스트림은 완료·실패·취소 시 같은 이벤트 루프 안에서 닫습니다.

답변 생성용 자료는 `presentation.py`에서 읽기 쉬운 한글 항목과 “현재 운영 미확인” 등의 안내로 변환합니다. 사업 ID·확인 플래그·해시는 모델 입력에서 제외하되 원본·서명·검증 근거에는 유지합니다. 기존 사업 안내에 내부 필드명이나 식별자가 다시 출력되면 원문을 공개하지 않고 자료 기반 안내로 전환합니다. 화면·보고서의 출처에는 해시 대신 “대화 당시 보존 자료”로 표시합니다.

AI 사용 중 관리자가 Gemini를 허용하면 `gemini-embedding-001` 768차원 임베딩과 키워드 검색 순위를 결합합니다. 후보 최대 15건을 재정렬해 최대 5건을 답변에 전달합니다. AI 꺼짐·다른 제공사는 키워드 검색을 사용합니다. 색인 누락·노후화·외부 호출 실패 시 키워드 검색으로 전환하고 안내합니다. 일부 지역만 색인되어 있어도 알립니다.

문서는 파일·페이지, API·공고는 원문 URL을 화면·보고서·대화 내보내기에 표시합니다. `GET /api/chat/config`의 `resourceCounts`는 유형별 자료 수이고 `resourceCount`는 합계입니다. 현재 모집 사업 수를 뜻하지 않습니다.

### 검색 색인과 대화 상태 저장

기존 원본은 그대로 두고 `work.chatbot_embeddings`에 검색 벡터를, `work.app_settings`에 서버 전용 서명키를 저장합니다. 보고서 버전의 기존 record JSON에는 검증된 대화 원문과 해시를 보존합니다. pgvector나 별도 벡터 DB는 사용하지 않습니다.

색인은 기존 상태를 확인하고 원문 추가·변경 시 갱신합니다. 관리자 Gemini 연결이 허용되어 있어야 하며 공개 사업 내용이 해당 제공사로 전송됩니다. 해시가 같은 자료는 건너뜁니다.

```powershell
python -m backend.chatbot.welfare.app.dialogue.semantic
# 다른 지역 참고 자료까지 색인할 때
python -m backend.chatbot.welfare.app.dialogue.semantic --all-regions
```

기본 범위는 강남구·춘천시 적용 자료(광역·전국 포함)입니다. DB 원문은 검색 시 읽고 팀 문서는 1분 캐시를 유지합니다. 이번 포팅은 코드와 로컬 검증까지이며 공유 DB 색인 갱신·외부 AI 실호출·배포는 실행하지 않았습니다.

분석 근거 설명·보고서 초안 등 다른 담당은 [보미 챗봇 안내](README.md#bomi)를 참고하세요.

### 검증

프로젝트 루트에서 실행합니다.

```powershell
.venv/Scripts/python.exe -m unittest discover -s backend/bomi/tests -t . -v
.venv/Scripts/python.exe -m unittest backend.db.tests.test_welfare_chatbot_repository -v
```

외부 DB 없이 검사할 때는 `WELFIND_WELFARE_SOURCE=json`을 명시합니다. DB 검사는 전용 PostgreSQL 검증 스키마에서 수행합니다. 테스트는 현재 저장소의 정책에 따라 로컬에서 관리합니다. 복지 원본 DB 조회나 AI 연결 실패를 JSON으로 자동 대체하지 않습니다.

API 키는 서버 `.env` 또는 관리자 AI 설정에 저장하며 저장소나 화면 코드에 노출하지 않습니다.

<a id="regional-analysis"></a>

## 지역 변화 신호 에이전트

작업 기준 폴더: `backend/agents/regional_analysis/`

지역 분석 에이전트(`bomi/agents/region_analysis.py`)가 동 단위 질문을 이 엔진에 넘깁니다.
연결 모듈은 `backend/bomi/adapters/regional_analysis.py` 하나이며, 엔진의 `sys.path` 조정과 임포트도 이 파일에만 있습니다.
어댑터는 화면에서 고른 동·기준월·연령을 질의 계획에 넘기고, 지표 버튼 입력·«화면 정리해 줘» 같은 짧은 질문을 구체 질문으로 바꿉니다.

### 폴더 구성

| 폴더·파일 | 역할 |
|---|---|
| `chatbot_agent/` | 질문 의도 해석, 근거 조회, 답변 문장 작성 |
| `chatbot_agent/db1_repository.py` | 저장소 계약(`Db1Repository`). 챗봇 로직은 SQL을 직접 쓰지 않고 이 계약만 부름 |
| `chatbot_agent/repository.py` | 공통 조회 로직(`SqlDb1Repository`). SQL은 이 파일에만 둠 |
| `chatbot_agent/pg_repository.py` | 유일한 구현(`PostgresDb1Repository`): 게시된 활성 run을 읽음 |
| `data_pipeline/` | 계산 작업기(`analysis1_worker.py`, `monthly_worker.py`, `runner.py`, `publication.py`)와 PostgreSQL 게시(`publish_postgres.py`, `db1_compat.py`) |
| `config/data_pipeline.json` | 계산용 DB 위치·원자료 위치 설정 |
| `evaluation/` | 질문 세트와 평가 결과 |

DB를 새로 만드는 작업기는 공식 분석 코드 `pipelines/db1`을 그대로 불러 씁니다.

### 근거 자료 (PostgreSQL)

- 게시 모드의 챗봇은 **PostgreSQL에서** 읽습니다. 게시 테이블이 없으면 대시보드 호환 모드(DB1 서비스 테이블 + 전달 CSV)를 사용합니다. 계산 파이프라인은 PostgreSQL `db1_pipeline`에 결과를 쓰고, 게시가 이를 서비스의 `db1.v16_*` 테이블과 `db1_v16` 뷰로 옮깁니다.
- 게시는 `data_pipeline/publish_postgres.py`의 `publish(workspace_schema, engine)`, 이전 run으로 되돌리기는 `activate(engine, run_id)`입니다. 저장 구조는 [보미 챗봇 구조 6장](../docs/bomi-architecture.md#6-지역-분석-근거-저장소)을 보세요.
- 게시 테이블이 없을 때는 대시보드 호환 저장소의 자료 유무를 확인합니다. 사용할 자료가 없거나 DB에 연결하지 못하면 `data_ready()`가 False이고 동·그룹 분석 근거로 답합니다.

### 외부 AI

v16은 관리자 «AI 설정»을 따릅니다. Gemini면 JSON 스키마를 지정해 질문 의도를 분류하고,
다른 제공사면 공용 AI 창구(`backend/chatbot/welfare/app/llm/client.py`)를 씁니다.
AI를 쓰지 않으면 규칙으로 의도를 해석하고, 답변 문장은 항상 DB 근거로 만듭니다.
연령과 활동 지표를 함께 묻거나 소비와 날씨를 함께 묻는 질문은 AI 분류보다 규칙 해석을 우선합니다.

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
담당 선택의 사업명 판별, 복지사업 검색, 대화에서 찾은 사업의 보고서 연결, `/api/chat/config`가 같은 DB 자료를 사용합니다.
팀 문서 목록은 1분간 기억하고 API·공고는 검색할 때 조회합니다. 복지 원본은 조회만 하며 기동 시 자동 적재하지 않습니다. 검색 색인·서명키·보고서 저장은 별도 `work` 데이터에 기록합니다.
DB 오류나 빈 테이블은 명시적으로 알리고(보미는 «복지자료 DB를 조회하지 못했습니다» 안내로 답을 마침) JSON으로 자동 대체하지 않습니다.

`GET /api/chat/config`의 `resourceSource`는 `db` 또는 `json`입니다. `resourceCounts`는 유형별 자료 수이고 `resourceCount`는 중복 처리 후 합계입니다.

분석 근거 설명·보고서 초안 등 다른 담당은 [보미 챗봇 안내](README.md#bomi)를 참고하세요.

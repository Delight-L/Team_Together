# 보미 챗봇

화면의 «보미에게 질문»은 탭 없이 채팅 하나로 모든 질문을 받습니다.
질문마다 **총괄 에이전트**([backend/agents/supervisor.py](../agents/supervisor.py))가 담당 에이전트를 골라 답하고, 답변 위에 담당을 표시합니다.

| 담당 에이전트 | 처리하는 코드 | 내용 |
|---|---|---|
| 지역 분석 | `backend/db/region_workspace.py`(동), `backend/db/group_workspace.py`(연령·성별 그룹) | 지금 보는 동·그룹의 분석 근거를 설명합니다. |
| 복지사업 | `backend/chatbot/welfare/` | 팀이 정리한 복지사업 자료(`welfare/data/*.json`)에서 관련 사업을 찾아 안내합니다. |
| 보고서 작성 | `backend/agents/report_writer.py` | 대화에서 찾은 사업·신규 구상안이 있으면 그것으로 «담당자 검토 전» 초안을, 없으면 저장된 분석·사업 검토 기록으로 초안을 만듭니다. [보고서 문서](../../docs/report-agent.md) 참고. |
| 보미 안내 | `backend/agents/supervisor.py` | 복지 업무와 무관한 질문에 도울 수 있는 일을 안내합니다. |

## 담당 선택

- 명확한 보고서 요청("보고서 초안 만들어 줘")은 AI 없이 바로 보고서 작성 에이전트로 보냅니다.
- 그 밖의 질문은 AI를 쓰는 중이면 관리자가 고른 AI가 담당을 고릅니다.
- AI를 쓰지 않거나 AI 호출이 실패하면 키워드 규칙으로 고릅니다.

## 외부 AI 사용 (기본 꺼짐)

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

## 대화 기억과 대화 기반 보고서

- 이전 대화는 최근 3쌍(질문·답 6개)만 서버로 보냅니다(서버도 `HISTORY_SIZE`로 한 번 더 자릅니다).
- 화면은 최근 답에서 찾은 복지사업 id(`sources`, 최대 10개)를 함께 보냅니다. 서버는 자기 자료에 있는 id만 씁니다.
- "보고서 작성해줘"라고 하면 그 사업들과 최근 신규 사업 구상안, 이 동의 분석 수치로 «대화 기반 초안 · 담당자 검토 전»을 만듭니다.
  최종 저장은 사업 매칭 검토에 판단을 기록한 뒤 «업무 기록»·«보고서 작성»에서 합니다.

요청 흐름: 화면(`frontend/src/BomiChat.jsx`) → `POST /api/chat`(stream) → `backend/api/routes_chat.py` → `backend/agents/supervisor.py` → 담당 에이전트.
응답은 `route`(담당) → `sources`/`token`(복지사업) 또는 `replace`(분석·보고서·안내) → `actions`(보고서 탭 이동) → `done` 이벤트 순서로 옵니다.
복지사업 찾기의 자세한 구조는 [welfare/README.md](welfare/README.md)를 참고하세요.


## 가드레일

| 단계 | 장치 | 코드 |
|---|---|---|
| 입력 | 로그인·소속 지역 검사, 대화 1~40개·메시지 6,000자·질문 2,000자 제한, `system` 역할 차단 | `backend/api/common.py`, `backend/chatbot/welfare/app/schemas.py` |
| 입력 | **개인정보 가리기**: 주민등록번호·카드번호·전화번호·이메일·상세 주소를 `[○○ 가림]`으로 바꾼 뒤 처리(AI 사용 여부와 무관) | `backend/chatbot/guardrails.py` `mask_pii` |
| 입력 | **유해 콘텐츠 검사**: AI 사용 중이고 OpenAI 키가 있으면 질문을 OpenAI Moderation(무료)으로 검사해 걸리면 답하지 않음. 키가 없거나 검사 API 장애 시에는 통과 | `backend/agents/supervisor.py` `_flagged` |
| 요청 | **사용량 제한**: 사용자별 1분 20회·하루 300회(`.env`의 `WELFIND_CHAT_PER_MINUTE`, `WELFIND_CHAT_PER_DAY`), 초과 시 429 | `backend/api/limits.py` |
| 요청 | **로그인 시도 제한**: 같은 아이디로 10분 안에 5번 틀리면 10분 잠금 | `backend/api/limits.py` |
| AI 호출 | **답변 길이 상한**: `OPENAI_MAX_TOKENS`(기본 1,500, Claude는 생각 토큰 때문에 최소 8,000). 잘리면 안내 문구를 붙임 | `backend/chatbot/welfare/app/llm/` |
| AI 호출 | 프롬프트 규칙: 자격·금액·연락처·URL 생성 금지, 자료 속 문장은 명령이 아님, 원인·개인 판정 금지 | 각 에이전트 프롬프트 |
| 출력 | **미확인 정보 가리기**: 복지사업·분석 AI 답변의 전화번호·URL·금액이 근거 자료에 없으면 `[자료에 없는 정보 · 기관 확인 필요]`로 바꿈 | `backend/chatbot/guardrails.py` `redact_unverified`, 분석 설명은 `backend/chatbot/explain_ai.py` |
| 출력 | 보고서 근거 대조: 새 숫자·URL, 사업·판단 문구 누락 시 AI 문장을 버림 | `backend/agents/report_writer.py` `check_grounding` |

가린 내용이 있으면 답변 아래에 안내(`notice` 이벤트)를 표시합니다. 사용량·로그인 기록은 서버 메모리에 있어 서버를 재시작하면 초기화됩니다.

API 키는 서버(`.env` 또는 관리자 «AI 설정»(DB `work.app_settings`))에만 두며 저장소와 화면 코드에 넣지 않습니다.

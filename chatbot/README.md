# 보미 챗봇

화면의 «보미에게 질문»은 탭 없이 채팅 하나로 모든 질문을 받습니다.
질문마다 **총괄 에이전트**([agents/supervisor.py](../agents/supervisor.py))가 담당 에이전트를 골라 답하고, 답변 위에 담당을 표시합니다.

| 담당 에이전트 | 처리하는 코드 | 내용 |
|---|---|---|
| 지역 분석 | `db/region_workspace.py`(동), `db/group_workspace.py`(연령·성별 그룹) | 지금 보는 동·그룹의 분석 근거를 설명합니다. |
| 복지사업 | `chatbot/welfare/` | 팀이 정리한 복지사업 자료(`welfare/data/*.json`)에서 관련 사업을 찾아 안내합니다. |
| 보고서 작성 | `agents/report_writer.py` | 저장된 분석·사업 검토 기록으로 약식보고서 초안을 만듭니다. [보고서 문서](../docs/report-agent.md) 참고. |
| 보미 안내 | `agents/supervisor.py` | 복지 업무와 무관한 질문에 도울 수 있는 일을 안내합니다. |

## 담당 선택

- 명확한 보고서 요청("보고서 초안 만들어 줘")은 AI 없이 바로 보고서 작성 에이전트로 보냅니다.
- 그 밖의 질문은 AI를 쓸 수 있으면 OpenAI가 담당을 고릅니다.
- `.env`에 `OPENAI_API_KEY`가 없거나, 화면에서 «외부 AI 사용 안 함»을 골랐거나, AI 호출이 실패하면 키워드 규칙으로 고릅니다.

## 답변 방식

화면의 «답변 방식»은 담당 선택과 모든 담당 에이전트에 함께 적용됩니다.

- AI 사용(키가 있으면 기본): 담당 선택, 분석 해석, 복지사업 답변, 보고서 문장 다듬기에 AI를 씁니다.
- 외부 AI 사용 안 함: 데이터 근거 안내와 자료 검색 결과로만 답합니다.

AI 분석 해석이 실패하면 데이터 근거 안내로 답하고, 보고서 AI 문장이 근거와 맞지 않으면 저장된 근거로 만든 초안을 씁니다.

요청 흐름: 화면(`frontend/src/BomiChat.jsx`) → `POST /api/chat`(stream) → `webapp/routes_chat.py` → `agents/supervisor.py` → 담당 에이전트.
응답은 `route`(담당) → `sources`/`token`(복지사업) 또는 `replace`(분석·보고서·안내) → `actions`(보고서 탭 이동) → `done` 이벤트 순서로 옵니다.
복지사업 찾기의 자세한 구조는 [welfare/README.md](welfare/README.md)를 참고하세요.

`/api/region/chat`, `/api/groups/chat`, `/api/chat`의 JSON 방식은 예전 호출 경로로, 화면에서는 더 이상 쓰지 않습니다.

API 키는 서버의 `.env`에만 두며 저장소와 화면 코드에 넣지 않습니다.

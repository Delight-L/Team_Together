# chatbot — 보미의 공용 인프라

담당 선택·이벤트·에이전트는 `backend/bomi/`에 있습니다([CHAT_FLOW.md](../CHAT_FLOW.md)).
이 폴더는 챗봇과 다른 기능이 함께 쓰는 부품만 둡니다.

| 파일 | 역할 |
|---|---|
| `ai_settings.py` | 관리자 «AI 설정»(사용 여부·제공사·모델·키). 공유 PostgreSQL `work.app_settings`에 저장 |
| `guardrails.py` | 개인정보 가리기, AI 답변 속 미확인 연락처·URL·금액 가리기(`StreamRedactor`), 단어 규칙 |
| `explain_ai.py` | 분석 근거를 AI에게 설명받는 공통 절차(동·그룹 분석이 함께 씀) |
| `welfare/app/llm/` | 외부 AI 창구 `llm`과 OpenAI·Anthropic·Gemini 어댑터 |
| `welfare/app/dialogue/resources.py` | 팀 복지사업 자료(`welfare/data/*.json`) 검색 |
| `welfare/app/schemas.py` | 대화 메시지 검증 스키마 |

외부 AI 호출은 모두 `llm`을 거치며(`llm.stream` / `llm.complete` / `llm.moderate`),
실패는 `LLM_ERRORS`로 잡아 AI 없는 안내로 대체합니다.

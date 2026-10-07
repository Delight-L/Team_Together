# chat_test2 코드 이식

`C:/Users/user/Desktop/chat_test2/backend/app`의 코드 파일과 `backend/data`를 이 폴더로 가져왔습니다. 팀의 React 화면은 그대로 사용하며, 실제 답변은 가져온 `app/agent/orchestrator.py`의 `handle_chat`을 실행합니다.

| 원본 위치 | 팀 프로젝트 위치 | 역할 |
|---|---|---|
| backend/app/config.py | chatbot/welfare/app/config.py | 모델·키 설정 |
| backend/app/schemas.py | chatbot/welfare/app/schemas.py | 질문·대화 형식 검사 |
| backend/app/agent/orchestrator.py | chatbot/welfare/app/agent/orchestrator.py | 검색 결과, 안내 프롬프트, 스트리밍 답변 |
| backend/app/agent/resources.py | chatbot/welfare/app/agent/resources.py | 자료 읽기, 사업 검색, API 없는 안내 |
| backend/app/llm/openai_client.py | chatbot/welfare/app/llm/openai_client.py | 원본의 AsyncOpenAI 호출 |
| backend/app/main.py | chatbot/welfare/app/main.py | 원본 FastAPI 진입점 보관. 팀 기본 실행에서는 별도 서버를 띄우지 않음 |
| backend/data/*.json | chatbot/welfare/data/*.json | 원본 자료 사본 |
| backend/requirements.txt | chatbot/welfare/requirements.txt | 원본 의존성 |

팀 통합에 필요한 변경은 패키지 import 경로, 루트 `.env` 위치, 선택 지역 전달, 요청별 OpenAI 클라이언트 종료입니다. 이전 작업에서 보완한 중복 사업 정리, 지역 범위 확인, 후속 질문 검색, AI 실패 안내도 원본 처리 경로에 포함했습니다.

`service.py`는 팀의 동기 HTTP 서버와 원본의 비동기 함수를 연결하는 어댑터입니다. 여기에 별도의 검색이나 AI 호출을 구현하지 않습니다. 이전의 동기 OpenAI 답변 구현과 루트 `welfare/resources.py`는 제거했습니다. 기존 `chatbot/orchestrator.py`의 JSON 호출도 같은 원본 `handle_chat`으로 연결됩니다.

실행 경로:

```text
Team React 채팅 → webapp/server.py → welfare/service.py
  → app/agent/orchestrator.py:handle_chat
  → app/agent/resources.py + app/llm/openai_client.py
```

원본 화면의 App.tsx/styles.css는 가져오지 않았습니다. Team_Together의 메뉴, 지도, 업무, 채팅 패널을 사용합니다.

원본 `.env`의 OpenAI 설정은 팀 루트 `.env`의 해당 항목이 비어 있을 때만 이어받았습니다. 팀의 기존 설정을 우선하며 `.env`는 Git에서 제외됩니다. 원본 폴더에는 변경을 가하지 않았습니다.

별도 Streamlit 분석 도구·CLI는 기본 React 챗봇 요청과 경로가 겹치지 않아 유지했습니다. 기본 React 챗봇은 Gemini 총괄 처리 경로를 호출하지 않습니다.

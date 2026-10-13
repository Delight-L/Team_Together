# 보미의 복지사업 찾기

복지탐정의 보미가 팀에서 정리한 복지사업 자료를 검색하고 출처와 확인할 조건을 안내하는 모듈입니다.
선택한 지역과 대화 맥락을 함께 사용하며, 실제 이용 자격이나 현재 모집 여부는 담당 기관 확인이 필요합니다.

## 구성

| 파일 | 역할 |
|---|---|
| `service.py` | 화면 서버와 비동기 대화를 연결하고 JSON·스트림 응답을 제공 |
| `app/config.py` | 프로젝트 루트 `.env`의 AI 연결 설정 읽기 |
| `app/schemas.py` | 사용자 질문과 대화 이력 형식 검사 |
| `app/agent/orchestrator.py` | 검색·답변·출처·AI 실패 안내 처리 |
| `app/agent/resources.py` | 팀 자료 읽기, 사업 검색, 자료 기반 안내 |
| `app/llm/openai_client.py` | 요청별 AI 연결과 응답 스트림 종료 |
| `data/*.json` | 출처·페이지·확인 상태를 포함한 복지사업 자료 |

## 요청 흐름

```text
frontend/src/BomiChat.jsx
  → webapp/routes_chat.py
  → chatbot/welfare/service.py
  → app/agent/orchestrator.py:handle_chat
  → app/agent/resources.py + app/llm/openai_client.py
```

`OPENAI_API_KEY`가 없으면 자료 검색 결과로 안내합니다. 키가 있으면 검색한 자료를 근거로 AI가 답변합니다.
AI 연결 실패나 빈 응답은 자료 검색 안내로 전환하며, 요청이 취소되면 응답 스트림을 종료합니다.
같은 사업이 여러 자료에 있으면 상세 정보를 가진 자료를 사용하고, 후속 질문은 이전 사업 맥락을 이어 검색합니다.

`chatbot/orchestrator.py`의 JSON 요청도 같은 대화 처리 함수를 사용합니다.
「이 화면 분석」은 별도의 동·그룹 분석 경로를 사용하며, 자세한 구분은 [보미 챗봇 안내](../README.md)를 참고하세요.

## 검증

프로젝트 루트에서 실행합니다.

```powershell
.venv/Scripts/python.exe -m unittest discover -s chatbot/tests -v
```

API 키는 프로젝트 루트 `.env`에만 설정하며 저장소나 화면에 노출하지 않습니다.

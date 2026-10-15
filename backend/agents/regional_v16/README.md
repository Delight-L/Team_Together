# v16 지역 변화 신호 에이전트

보미 총괄 에이전트(`backend/agents/supervisor.py`)가 동 단위 지역 분석 질문을 이 에이전트에 넘깁니다.
연결 모듈은 `backend/agents/v16_service.py`입니다.

## 폴더 구성

| 폴더·파일 | 역할 |
|---|---|
| `chatbot_agent/` | 질문 의도 해석, DB 조회, 답변 문장 작성 |
| `data_pipeline/` | DB 위치·스냅샷 관리(`runner.py`, `snapshot_manager.py`)와 DB를 새로 만드는 작업기 |
| `config/data_pipeline.json` | DB 위치·원자료 위치 설정 |
| `outputs/db1.sqlite` | 답변 근거 DB(약 100MB). **git에 올리지 않습니다** |

DB를 새로 만드는 작업기(`analysis1_worker.py`, `monthly_worker.py`)는 공식 분석 코드 `pipelines/db1`을 그대로 불러 씁니다.
예전에 이 폴더에 있던 DB1 복사본과 단독 확인용 FastAPI 서버는 정리했습니다.

## 근거 DB 배치

- 로컬: `outputs/db1.sqlite`에 둡니다.
- 다른 위치(배포 서버 등): 환경 변수 `DB1_DATABASE_PATH`로 파일 경로를 지정합니다.
- DB 파일이 없으면 총괄 에이전트가 기존 지역 분석 담당(`backend/db/region_workspace.py`)으로 답합니다.

## 외부 AI

v16은 관리자 «AI 설정»을 따릅니다. Gemini면 JSON 스키마를 지정해 질문 의도를 분류하고,
다른 제공사면 공용 AI 창구(`backend/chatbot/welfare/app/llm/client.py`)를 씁니다.
AI를 쓰지 않으면 규칙으로 의도를 해석하고, 답변 문장은 항상 DB 근거로 만듭니다.

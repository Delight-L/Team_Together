# 보미 챗봇

화면의 «보미에게 질문»은 두 가지 질문을 받습니다.

| 탭 | 처리하는 코드 | 내용 |
|---|---|---|
| 이 화면 분석 | `db/region_workspace.py`(동), `db/group_workspace.py`(연령·성별 그룹) | 지금 보는 동·그룹의 분석 근거를 설명합니다. 기본은 AI 없이 근거 숫자만 안내하고, 사용자가 «AI 해석»을 고르면 AI를 호출합니다. |
| 복지사업 찾기 | `chatbot/welfare/` | 팀이 정리한 복지사업 자료(`welfare/data/*.json`)에서 관련 사업을 찾아 안내합니다. `.env`에 `OPENAI_API_KEY`가 있으면 AI가 답변을 만들고, 없으면 자료 검색 결과로 답합니다. |

요청 흐름: 화면(`frontend/src/BomiChat.jsx`) → `webapp/server.py` → 위 코드. 복지사업 찾기의 자세한 구조는 [welfare/README.md](welfare/README.md)를 참고하세요.

API 키는 서버의 `.env`에만 두며 저장소와 화면 코드에 넣지 않습니다.

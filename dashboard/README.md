# 복지탐정 대시보드

루트에서 `python main.py`로 실행합니다. 시연 계정은 로그인 화면에서 선택할 수 있습니다.

| 변경 대상 | 파일 |
| --- | --- |
| 기본 설정 및 시연 데이터 | `settings.py`, `data/` |
| 실제 Analysis2 CSV 연결 | `pipeline.py` |
| Streamlit 컴포넌트 | `design_ui.py` |
| 지역 요약 및 분석 화면 | `ui/bridge.js` |
| 입체 지도와 키보드 동작 | `ui/map.js` |
| 챗봇 로컬 시작 메뉴 | `ui/chat.js` |
| 로그인·필터·질문 전송 | `ui/dashboard.js` |
| 레이아웃과 CI 스타일 | `ui/layout.html`, `ui/style.css`, `ui/brand.css` |
| 질문 답변 및 API 호출 조건 | `../chatbot/service.py` |
| 사업 매칭 | `../agents/service_matching.py` |
| 업무 저장·보고서 | `missions.py`, `operations.py`, `service_dialog.py`, `report.py` |
| DB 연결 | `../db/connection.py` |

지도 그린은 후보 지표 2개 이상, 주황은 1개, 연한 파랑은 후보 없음, 회색은 자료 없음입니다. 후보 수는 개인 위험도 순위가 아닙니다. 실제 행정 경계와 클릭·Enter 선택을 유지하며 돌출 높이는 시각 효과입니다.

챗봇은 기본 안내 모드로 시작합니다. 주제 메뉴와 기본 설명은 로컬에서 처리합니다. 사용자가 AI를 켜고 질문을 보내야 `agent_enabled: true` 요청이 전달되며 서버에서 한 번 더 검사합니다.

화면 테스트: `python dashboard/tests/check_dashboard.py`, `node dashboard/tests/check_workflow.cjs`. 업무 저장 테스트는 `python -m unittest discover -s dashboard/tests -p "test_*.py"`로 실행합니다.

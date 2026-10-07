# 공용 기능과 데이터

React API와 기존 Streamlit 화면에서 함께 사용합니다. 이 폴더는 Streamlit 화면 구현에 의존하지 않습니다.

- `accounts.py`: 시연 로그인 계정
- `report.py`: Word 보고서 초안 생성
- `data/map_boundaries.json`: 지도 경계 데이터

분석·사업 매칭·업무 저장은 각각 기존 `agents/`, `chatbot/`, `db/` 모듈을 사용합니다.

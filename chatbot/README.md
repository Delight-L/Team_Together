# 복지탐정 챗봇

`python main.py --chatbot`은 저장된 Analysis2 결과를 설명하는 Streamlit 화면, `--chatbot-cli`는 콘솔 데이터 질의 도구입니다.

`service.py`는 저장된 근거 안내를 제공합니다. 기본값 `allow_agent=False`에서는 API 클라이언트를 생성하지 않습니다. 사용자가 AI 모드를 켜고 질문을 보내면 `allow_agent=True`를 전달합니다. 연결 실패나 설정 부재 시 규칙 기반 근거 안내로 돌아갑니다.

콘솔에서는 1 분석 기준, 2 전체 신호, 3 지역 요약 메뉴가 토큰 없이 동작합니다. `AI켜기`를 입력한 뒤 자유 질문을 보내야 호출이 허용되며 `AI끄기`로 해제합니다.

루트 `.env`에 `GEMINI_API_KEY`, `GEMINI_MODEL`을 설정합니다. API 키를 저장소에 포함하지 않습니다.

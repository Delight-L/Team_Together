# 복지이음 챗봇과 별도 분석 도구

기본 React 화면의 챗봇은 `chat_test2/backend/app`에서 가져온 코드를 사용합니다. 실행·이식 위치는 [복지이음 코드 안내](welfare/README.md)를 확인하세요. 팀 서버의 요청은 `welfare/service.py`를 거쳐 원본 `handle_chat`에 전달됩니다. 기본 채팅은 루트 `.env`의 `OPENAI_API_KEY`, `OPENAI_MODEL`을 사용합니다.

아래 Streamlit/CLI는 별도로 실행하는 분석 도구입니다.

`python main.py --chatbot`은 저장된 Analysis2 결과를 설명하는 Streamlit 화면, `--chatbot-cli`는 콘솔 데이터 질의 도구입니다.

`service.py`는 저장된 근거 안내를 제공합니다. 기본값 `allow_agent=False`에서는 API 클라이언트를 생성하지 않습니다. 사용자가 AI 모드를 켜고 질문을 보내면 `allow_agent=True`를 전달합니다. 연결 실패나 설정 부재 시 규칙 기반 근거 안내로 돌아갑니다.

콘솔에서는 1 분석 기준, 2 전체 신호, 3 지역 요약 메뉴가 토큰 없이 동작합니다. `AI켜기`를 입력한 뒤 자유 질문을 보내야 호출이 허용되며 `AI끄기`로 해제합니다.

루트 `.env`에 `GEMINI_API_KEY`, `GEMINI_MODEL`을 설정합니다. API 키를 저장소에 포함하지 않습니다.

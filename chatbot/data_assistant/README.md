# 로컬 분석 결과 질의 도구

루트에서 `python main.py --chatbot-cli`로 실행합니다. 설정은 이 폴더의 `config.json`, 데이터 경로 허용 목록은 `data_catalog.py`입니다.

1 분석 기준, 2 전체 신호, 3 지역 요약은 토큰 없이 동작합니다. 자유 질문은 `AI켜기`를 입력하고 전송할 때만 Gemini를 호출합니다. 키는 루트 `.env` 또는 환경변수로 설정하고 `AI끄기`로 기본 안내에 돌아갑니다.

조회 대상은 agents/regional_analysis의 Analysis2 산출물과 preprocessing의 산출물입니다. 원천자료와 키 파일은 데이터 검색 대상에 포함하지 않습니다.

테스트: `python -m unittest discover -s chatbot/data_assistant/tests`.

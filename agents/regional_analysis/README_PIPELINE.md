# 지역 분석 파이프라인

저장소 루트에서 `python main.py --analysis --no-download`로 실행합니다. 신규 공공데이터 다운로드를 포함하려면 `--no-download`를 생략합니다.

지역 유형 전처리는 `preprocessing/regional_types`, 월별 행동 전처리는 `preprocessing/regional_features`, 탐지 로직은 이 폴더의 `Analysis2`에 있습니다. 전처리별 raw_data / reference / outputs는 해당 모듈 안에 보관합니다.

Analysis2는 과거 최소 12회 이력으로 Robust Z를 계산합니다. 전화·문자 또는 평일·휴일 이동의 Z가 모두 -2.0 이하이면 묶음 신호로 표시합니다. 탐지 결과와 Evidence Card는 `Analysis2/outputs`에 저장합니다. root `requirements.txt`로 의존성을 준비합니다.

루트 기준 `python main.py --chatbot-cli`로 보관된 결과를 질문할 수 있습니다. 기본 메뉴는 AI를 호출하지 않습니다.

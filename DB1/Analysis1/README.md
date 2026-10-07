# Analysis1

반기별 지역유형 분석. 기준 모델은 models/2025H2, 고정 입력은 data/reference, 전처리 입력은 data/processed/<반기>, 결과는 outputs/periods/<반기>에 저장합니다.

공통 실행은 상위 README.md의 run_db1.ps1을 사용합니다. 테스트는 tests 폴더에서 실행합니다.


## 동별 독거노인 통계 연결 (2026-10-07)

동별 독거노인 관측 통계 연결을 완료했다. `v_a1_elder_annual`은 연간 지표, `v_a1_elder_context`는 반기 지역 유형 연결, `v_a123_age_elder_context`는 동·연령별 행동·소비와의 사후 연결이다. 독거노인은 65세 이상이므로 60plus에만 부분 연령 일치로 연결한다. 다른 연령대에는 직접 적용하지 않는다. 공표일 기준 조회는 `v_a123_age_elder_available_context`다. 독거 여부는 고립 판정이 아니며 기존 모형과 점수는 유지한다. 갱신 명령은 `run_db1.ps1 -Command analysis1-elder`와 일반 `scan`이고, 해석·DB 질의·정정 처리 규칙은 `Analysis1/ELDERLY_CONTEXT.md`에 있다.

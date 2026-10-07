# 원천 기간·SNS·소비 맥락

`source_semantics.py --db outputs/db1.sqlite --output Analysis2/outputs/source_semantics` 또는 루트 `source-semantics` 명령으로 실행한다. 기존 전처리와 탐지·소비 적재가 먼저 완료돼야 한다.

테이블: `a2_observation_window`(기준월별 직전 3개월), `ctx_sns_index`(동·연령·기준월별 공급자 표준화 지수), `a23_observation_context`(탐지 결과별 기간 정렬 소비). 조회: `v_a123_age_source_context`. CSV와 신호 JSON을 출력한다. 같은 자료 재실행은 멱등이며 과거 값 변경 시 정정 요구 오류로 중단한다.

SNS는 공개 성별·5세 그룹 지수의 추정인구 가중평균이며 개인 단위 재표준화가 아니다. 유한 음수와 0을 유지한다. 0은 원천 주석 충돌 표시를 제공한다. 충분한 유한값 인구 비중 80%와 추정인구 200을 만족해야 참고값을 제공한다. 동일 기준월·연령 내 22개 동 상대 비교만 허용한다.

상권은 관측 창이 정확히 한 분기일 때만 연결한다. 카드는 현재·직전 3개월에 모두 존재하는 동일 업종과 완전 관측 일수를 확인해 하루당 거래 건수를 비교한다. 결측·불완전 관측·0인 이전 값은 증감률 NULL이다. 공휴일 포함 정의와 실제 공개일은 NULL이며 임의 추정하지 않는다.

공식 안내: https://data.seoul.go.kr/dataVisual/seoul/seoulLiving.do . 로컬 매뉴얼 6·7·35쪽 기준. 상세 결과: docs/SOURCE_DEFINITIONS_RESULT_20261007.md.


## 2026-10-07 근거 보완 반영

청년 조사 세부 통계, 관측 기간 기상, 지연 소비 근거 보충, 공개일 기준 조회를 추가했습니다. [근거 사용 설명](../Context/EVIDENCE_CONTEXT.md)과 [검증 결과](../docs/DB1_IMPROVEMENTS_RESULT_20261007.md)를 함께 전달하세요. 기존 탐지 건수는 소통 10·이동 0·복합 0으로 유지됩니다.

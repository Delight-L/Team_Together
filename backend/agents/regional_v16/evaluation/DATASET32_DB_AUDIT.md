# 32개 데이터셋 DB 근거 검증

- 기본 사례 B01~B32를 선택했습니다. 경로별 8개이며 선행 대화·화면 선택 단계를 모두 보존했습니다.
- 기존 64개 파일과 사용자 리뷰를 수정하지 않았습니다.
- 원본 snapshot과 메인 DB의 모든 테이블·모든 행을 비교했습니다.
- 활동·연령·이상신호·소비 테이블은 원본과 완전히 동일합니다.
- 지역배경 분석은 elder_v2 모델로 변경되었습니다. B04/B12/B28이 사용하는 삼성1동·삼성2동 유형명과 1·2인가구 비율을 메인 DB에서 직접 조회했고 원본 근거와 모두 일치했습니다.
- 따라서 이 32개 답안의 숫자와 지역유형 문구는 유지할 수 있습니다. DB 파일 해시만 교체한 검증이 아닙니다.
- 자료 의미·기간 안내는 기존 명세를 근거로 유지했으며, 챗봇 출력을 정답으로 복사하지 않았습니다.
- 모범답안은 개발 평가용입니다. 독립적인 최종 성능 검증셋으로 주장하지 않습니다.

| 테이블 | 원본 행 | 메인 행 | 전체 행 일치 |
|---|---:|---:|---|
| a1_change_detection | 0 | 0 | 예 |
| a1_change_feature | 0 | 0 | 예 |
| a1_context | 22 | 22 | 아니요 |
| a1_input | 22 | 22 | 아니요 |
| a1_region_baseline | 22 | 22 | 아니요 |
| a1_region_feature | 286 | 286 | 아니요 |
| a23_context_revision | 0 | 0 | 예 |
| a23_observation_context | 660 | 660 | 예 |
| a2_activity_followup | 29 | 29 | 예 |
| a2_activity_level | 660 | 660 | 예 |
| a2_activity_model | 1 | 1 | 예 |
| a2_age_common_change | 30 | 30 | 예 |
| a2_age_detection | 660 | 660 | 예 |
| a2_age_feature | 17952 | 17952 | 예 |
| a2_age_model | 1 | 1 | 예 |
| a2_age_month_input | 2244 | 2244 | 예 |
| a2_age_raw | 6336 | 6336 | 예 |
| a2_age_source | 48 | 48 | 예 |
| a2_detection | 132 | 132 | 예 |
| a2_evidence | 1 | 1 | 예 |
| a2_feature | 1056 | 1056 | 예 |
| a2_month_input | 132 | 132 | 예 |
| a2_observation_window | 6 | 6 | 예 |
| a3_dimension | 30 | 30 | 예 |
| a3_policy | 0 | 0 | 예 |
| a3_run | 22 | 22 | 예 |
| a3a_comparison | 1320 | 1320 | 예 |
| a3a_feature | 10560 | 10560 | 예 |
| a3a_industry | 0 | 0 | 예 |
| a3a_quarter_summary | 352 | 352 | 예 |
| a3b_feature | 180 | 180 | 예 |
| a3b_industry | 0 | 0 | 예 |
| a3b_month_summary | 6 | 6 | 예 |
| a3b_total | 36 | 36 | 예 |
| ctx_consumption_anchor | 22 | 22 | 예 |
| ctx_elder_annual | 88 | 88 | 예 |
| ctx_enrichment_state | 1 | 1 | 예 |
| ctx_evidence_guide | 6 | 6 | 예 |
| ctx_sns_index | 660 | 660 | 예 |
| ctx_survey_annual | 572 | 572 | 예 |
| ctx_weather | 6 | 6 | 예 |
| ctx_youth_reference | 476 | 476 | 예 |
| db1_run | 7 | 7 | 아니요 |
| input_import | 14 | 14 | 예 |
| month_run | 6 | 6 | 아니요 |
| pipeline_state | 1 | 1 | 아니요 |

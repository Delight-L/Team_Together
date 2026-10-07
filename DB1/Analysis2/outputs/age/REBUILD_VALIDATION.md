# 연령별 이력 재구축 검증 결과

- months: 48
- service_rows: 5280
- five_year_rows: 12672
- raw_rows: 50688
- baseline_service_rows: 4620
- update_service_rows: 660
- weighted_reconciliation_checks: 9504
- max_reconciliation_error: 4.547473508864641e-13
- stored_history_checks: 9504
- stored_history_mismatches: 0
- max_stored_history_error: 6.821210263296962e-13
- review_required_rows_both_schemes: 408

48개월 모두 동 22개·성별 2개·연령 코드 12개의 원본 셀을 확인했다. 기존 월별 계산 방식과의 가중 재집계 및 실제 저장된 동별 이력을 대조했다. 이 보고서는 전처리 검증이며, 연령별 변화 탐지 또는 사회적 고립 판정 검증이 아니다.

## 검토 필요 자료

```text
                                           rows  months
행정동  age_scheme interest_structural_issue              
일원2동 five_year  True                        288      24
     service    True                        120      24
```

세 관심집단이 모두 0인 경우는 구조적 문제 표시로 보존한다. 이를 고립이 없다는 관측값으로 해석하지 않는다.

## 실행 검증

- Analysis2 테스트: 21개 통과.
- DB1 공통 테스트: 8개 통과.
- 일반 Analysis2 scan: 현재 이력을 유지하고 2026-01 원본 대기 상태로 정상 종료.
- 2025-12 연령별 전처리 재실행: 중복 추가 없음.
- 운영본 복사본에 배포: 기존 분석 표 전체 내용 보존, 추가 표 행 수 및 DB 무결성·외래키 확인.

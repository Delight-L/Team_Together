# 주요 지표 정의

| 결과 | 필드 | 정의 / 해석 |
|---|---|---|
| 공통 | `adm_cd` | DB1의 7자리 통계 행정동코드. 상권 원본 8자리 코드는 crosswalk로 변환 |
| 공통 | `period` | 3A: YYYYQn, 3B: YYYY-MM. 분기를 월 관측으로 분할하지 않음 |
| 공통 | `age` | 결제 고객 연령. 10·20·30·40·50대와 60대이상 |
| 공통 | `domain` | 버전이 고정된 소비영역. 자료별 포함 업종은 완전히 같지 않음 |
| 3A Feature | `count`, `amount` | 관측된 업종의 해당 연령 매출건수·원본 금액 합계 |
| 3A Feature | `daily_count` | count / 실제 분기 일수. 관측 업종을 그대로 합산한 기술값 |
| 3A Feature | `observed_share` | 실제 관측 업종 수 / 해당 영역에 정의한 업종 수. 결제 고객 포착률 아님 |
| 3A Feature | `age_capture_ratio` | 모든 연령 구간 매출건수 합 / 영역 전체 매출건수. 연령 구간별 건수와 전체 건수의 관측 범위 차이를 보여줌 |
| 3A Comparison | `matched_industries` | 현재와 이전 동일 분기들에서 모두 관측된 업종의 교집합 |
| 3A Comparison | `matched_current_daily_count` | 공통 업종에 한한 현재 건수 / 현재 분기 일수. Feature의 daily_count와 대상 업종이 다를 수 있음 |
| 3A Comparison | `baseline_daily_mean/min/max` | 현재보다 앞선 동일 분기들의 공통 업종 일평균 건수의 평균/최소/최대 |
| 3A Comparison | `baseline_n`, `baseline_periods` | 비교 가능한 과거 동일 분기 수와 명시적 기간 목록 |
| 3A Comparison | `change_pct` | (공통 업종 현재 일평균 / 기준 평균 − 1) × 100. 기준 0 또는 3분기 미만이면 NULL |
| 3A Comparison | `below_prior_min`, `above_prior_max` | 과거 범위보다 낮음/높음이라는 기술적 비교. 통계적 이상 탐지 신호가 아님 |
| 3A Comparison | `gangnam_change_percentile` | 동일 분기·연령·영역에서 변화율이 계산된 동들 간 평균순위 / 비교 동 수. 관측 업종 바구니가 동별로 다를 수 있음 |
| 3A Comparison | `qoq_daily_change_pct`, `yoy_daily_change_pct` | 정확히 이전 분기/전년 동일 분기와 각각의 공통 업종 일평균 비교. 분기 대비는 별도 계절 조정값 아님 |
| 3B Feature | `count`, `daily_count` | 강남구 가맹점 관측 업종의 월별 건수와 달력 일수 기준 일평균. 고객 거주지 기준 값 아님 |
| 3B Feature | `observed_industry_days_min` | 해당 영역·연령에 포함된 원래 연령·업종 월 집계의 관측일수 최솟값. 비관측 날짜가 실제 0인지 자료 누락인지 구분할 수 없음 |
| 3B Feature | `mom_daily_change_pct` | 관측 업종 전체의 영역 일평균 전월비. 업종 구성이 변했을 수 있어 공통업종 전월비와 함께 봄 |
| 3B Feature | `matched_mom_daily_change_pct` | 현재와 정확한 전월에서 모두 관측된 영역 업종의 일평균 전월비 |
| 3B Feature | `matched_control_change_pct` | 핵심 5개 영역에 국한하지 않고 같은 연령 전체 업종에서 현재·전월 공통 업종의 일평균 전월비 |
| 3B Feature | `relative_change_pp` | 공통업종 영역 전월비 − 공통업종 전체 연령 전월비. 단위는 퍼센트포인트. 3A 변화율과 직접 차감하지 않음 |
| 3B Feature | `count_share_of_all_industries` | 해당 영역 건수 / 같은 월·연령의 모든 관측 업종 건수 |
| 3B Feature | `amount_per_transaction` | 원본 금액 합 / 결제건수. 원본 금액 단위를 유지하며 별도 배율/물가 조정 없음 |
| 통합 | `any_signal` | Analysis2의 실제 동·월 변화신호. 상세 30행에 반복돼도 신호 한 건 |
| 통합 | `context_period`, `a1_cluster_type` | Analysis2가 저장할 때 적용한 Analysis1의 기간 및 지역유형 |
| 통합 | `a3a_alignment` | 같은 분기 소비 맥락을 붙인 회고적 연결. 실시간 확보 가능성을 뜻하지 않음 |
| 통합 | `a3b_scope` | 구 단위 가맹점 소비 맥락. 동별로 배분된 관측값이 아님 |
| 공개일 조회 | `available_from` | 확인한 자료 공개/사용 가능일. 없으면 시점별 조회에 연결하지 않음 |

NULL은 계산할 수 없거나 자료가 아직 없는 상태이며 실제 0과 다릅니다. 두 카드 원본의 표본·추정 방식·업종 범위가 다르므로 건수·금액을 더해 하나의 총량으로 만들지 않습니다.

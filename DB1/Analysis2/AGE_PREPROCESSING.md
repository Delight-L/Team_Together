> 2026-10-07 원천 정의 정정: 이 문서의 통신 월은 실제 관측월이 아니라 집계 기준월입니다. 실제 관측은 직전 3개월입니다. 같은 라벨월 소비는 후속 기간 맥락이며 동시 변화 근거가 아닙니다. 기간 정렬은 `v_a123_age_source_context`, 최신 규칙은 `docs/SOURCE_DEFINITIONS_RESULT_20261007.md`를 따르세요.

# Analysis2 동·연령대별 과거 자료 재구축

2026-10-07 추가. 이번 단계는 **전처리와 이력 저장**이다. 연령별 변화 탐지는 후속 구현된 [AGE_DETECTION.md](AGE_DETECTION.md)를 따른다. 실제 고립 판정과 Analysis3 연령별 결합은 아직 수행하지 않는다. 기존 동별 탐지 결과에 나타나는 신호를 각 연령대에 복사하지 않는다.

## 기간·단위

- 기준선 자료: 2022-01~2025-06, 42개월.
- 업데이트 구간: 2025-07~2025-12, 6개월. 이후 새 월은 같은 전처리를 거쳐 추가된다.
- `service`: 20s·30s·40s·50s·60plus, 성별 통합. 동 22개 × 연령 5개 = 월 110행.
- `five_year`: 원본의 20·25·30·35·40·45·50·55·60·65·70·75 코드를 유지, 성별 통합. 월 264행.
- 원본 성별·연령별 모든 컬럼은 `a2_age_raw`에 보존한다. 원본 최상위 연령 코드 75의 상한을 임의로 79로 정의하지 않는다. 10대 통신자료는 없다.

## 지표 계산

기존 monthly_features의 계산을 공유한다. 통화·문자 대상자 평균은 총인구수 가중 평균, 이동 지표는 총인구수에서 해당 미추정 인구수를 뺀 가중 평균, 관심집단 비율은 관심집단 추정 수의 합 / 1인가구 추정 수의 합이다. 단순 평균을 사용하지 않는다. 각 가중 평균에는 수치가 존재하고 가중치가 양수인 셀만 포함한다.

`total_population`, `telecom_one_person_population`, `interest_one_person_population`, `*_valid_population`, `source_cells`를 함께 저장한다. 이 인구는 제공 자료의 추정 집계이며, 통신사 실제 표본 수 또는 주민등록 인구로 단정할 수 없다. 서로 다른 파일의 1인가구 추정 분모를 무조건 동일하게 강제하지 않는다.

이동 추정 비율, 기상·요일, 세 관심집단이 모두 0인 경우의 `interest_structural_issue`도 연령별로 유지한다. 0을 임의로 양수로 바꾸지 않고 계산 불가능한 값은 결측으로 보존한다.

`quality_status=available`은 핵심 값이 양수이고 관심집단 분모가 양수이며 구조적 0 문제가 없다는 전처리 상태다. 탐지 가능성 또는 통계적 신뢰성을 인증하는 값은 아니다. 나머지는 `review_required`. 최소 인구 기준과 추정 비율 임계값은 후속 탐지 보정·검증에서 결정한다.

## DB와 결과 파일

DB1의 `outputs/db1.sqlite`에 다음 표를 추가한다.

- `a2_age_feature`: `(adm_cd,date,age_scheme,age_band)` 기본키, 버전·기준선/업데이트 구간·품질 상태·지표 JSON.
- `a2_age_raw`: `(date,kind,adm_cd,sex,age_code)` 기본키, 원본 집계 셀 JSON.
- `a2_age_source`: 월별 원본 메타데이터, 원본 값과 전처리 버전의 지문.

다른 분석과 기존 A2 표는 계속 동 단위를 사용한다. 새로운 연령별 전처리 표를 기존 통합 뷰의 연령별 탐지 결과로 오해하지 말아야 한다.

`Analysis2/outputs/age/`:

- `analysis2_age_service_history.csv`: 전체 기본 연령별 이력.
- `analysis2_age_service_baseline.csv`: 기준선 42개월.
- `analysis2_age_service_update.csv`: 2025-07 이후.
- `analysis2_age_five_year_history.csv`: 전체 5세 코드별 이력.
- `source_inventory.csv`: 원본 파일 경로.
- `monthly_quality_report.csv`: 월별 행 수·검토 필요 건수·재집계 오차.
- `weighted_reconciliation.csv`: 연령별 결과를 동별로 합쳐 기존 계산 방식과 대조.
- `existing_history_comparison.csv`, `REBUILD_VALIDATION.md`: 실제 저장된 기존 이력과의 대조 결과 및 최종 검증.

## 실행·업데이트

DB1 폴더에서:

```powershell
.\run_db1.ps1 -Command analysis2-age
.\run_db1.ps1 -Command analysis2-age -Month 2026-01
.\run_db1.ps1 -Command scan
.\run_db1.ps1 -Command export
```

기본 재구축 범위는 2022-01~2025-12다. 일반 Analysis2 월 처리/scan은 동별 이력의 마지막 월까지 빠진 연령별 이력을 순차 보완한다. 신규 파일은 설정된 telecom_dir와 interest_dir에 기존 월 이름 규칙으로 배치해야 한다. 기상 파일에도 해당 월이 있어야 한다. 자동 다운로드 기능은 없다.

원본 전체 재검증은 `python Analysis2/age_features.py --start 2022-01 --end 2025-12`로 실행한다. 동일 원본 재실행은 중복 추가하지 않으며 기존 원본 값이 달라지면 자동 덮어쓰기를 차단한다. 월 건너뛰기·중복 원본 파일·빠진 성별/연령 셀·동 코드 변경·잘못된 미추정 인구수도 중단한다. 월별 저장은 하나의 트랜잭션으로 수행한다.

## 다음 분석 단계

동·연령별 변화 탐지와 실제/상대 변화의 보존은 [AGE_DETECTION.md](AGE_DETECTION.md)에 구현했다. 겹치는 3개월 집계 지표의 지속성을 독립 월로 세지 않는다. 다음 단계는 Analysis3 소비와의 연결 및 Analysis1·강남구 관계망 통계를 통한 고립 관련 근거 보강이다.

# DB1 Analysis1 함수화 및 실행 구조

강남구 22개 행정동 지역 맥락 유형화 프로토타입

## 1. Analysis1의 목적

DB1의 Analysis1은 강남구 22개 행정동이 서로 어떤 생활·인구·가구·복지
구조를 가지고 있는지를 비교하여 지역의 유형을 탐색하는 분석이다. 특정
행정동의 사회적 고립 위험도를 직접 산출하는 위험점수가 아니라, 사회적
고립과 관련될 수 있는 여러 지역 특성을 종합해 행정동 간 구조적 차이를
파악하는 지역 맥락 분석(Regional Context Analysis)이다.

최종적으로 각 행정동은 K-Means 군집화를 통해 3개의 지역 유형 중 하나로
분류되며, 이 결과는 이후 Analysis2·3 등 다른 분석 결과를 해석할 때
지역적 배경을 설명하는 자료로 활용한다.

## 2. 전체 처리 구조

Analysis1은 하나의 Python 파일에서 모든 작업을 처리하지 않는다. 데이터
입력, 설정, 검증, 통계 분석, 결과 관리 기능을 여러 파일로 분리하고
run_analysis1.py가 이를 연결하여 실행한다. 핵심 원칙은 분석에 필요한
데이터가 준비되면 동일한 분석 절차를 반복 실행할 수 있도록 통계 로직을
함수화하는 것이다.

1.  1.  원천 데이터: 통신 / 등록인구 / 가구 / 장애인 / 기초생활수급자
2.  2.  전처리: 행정동 단위 통합 및 비율·지표 생성
3.  3.  Analysis1 입력: gangnam_analysis1_pca_input_2025H2.csv
4.  4.  입력 설정·검증: pca_columns.example.json + config.py +
        validation.py
5.  5.  핵심 분석: PCA → 13 Features → 4개 Domain 균형화
6.  6.  군집 분석: K-Means k=2\~6 비교 → 최종 k=3
7.  7.  안정성 검증: Perturbation Stability
8.  8.  결과 표준화 및 파일 저장

## 3. Analysis1 입력 데이터

### 3.1 PCA 직전 통합 데이터

현재 핵심 입력 파일은 gangnam_analysis1_pca_input_2025H2.csv이다.
원천데이터 자체가 아니라 각 원천데이터의 전처리를 완료하고 PCA를
수행하기 직전 단계까지 통합한 분석용 데이터이며, 검증된 파일은 22행 ×
30열이다. 22행은 강남구의 22개 행정동을 의미한다.

  -----------------------------------------------------------------------
  영역                                주요 변수
  ----------------------------------- -----------------------------------
  행정동 식별                         adm_cd, dong_name

  활동 규모                           flow_per_point

  생활인구 성·연령 구조               male_ratio, age_10_ratio \~
                                      age_60_plus_ratio

  시간대 활동 구조                    night_ratio, morning_ratio,
                                      daytime_ratio, evening_ratio

  주중·주말 활동                      weekend_weekday_index

  주민 연령 구조                      resident_ratio_0_19 \~
                                      resident_ratio_65_plus

  외국인 구조                         foreigner_ratio

  가구 구조                           hh_1_ratio \~ hh_4plus_ratio

  복지 배경                           disability_ratio,
                                      livelihood_recipient_ratio
  -----------------------------------------------------------------------

Analysis1은 원천데이터의 공간결합이나 월별 집계를 직접 수행하는 모듈이
아니다. 전처리가 완료되어 행정동 1행 단위로 구성된 데이터를 입력받아
통계 분석을 수행한다.

## 4. 프로젝트 파일 구조와 역할

``` text
Analysis1/
├─ analysis/
│  ├─ __init__.py
│  └─ analysis1.py
├─ common/
│  ├─ __init__.py
│  ├─ config.py
│  └─ result_schema.py
├─ data/
│  ├─ __init__.py
│  ├─ ingestion.py
│  └─ validation.py
├─ run_analysis1.py
├─ pca_columns.example.json
└─ gangnam_analysis1_pca_input_2025H2.csv
```

  ----------------------------------------------------------------------------
  파일                                     역할
  ---------------------------------------- -----------------------------------
  gangnam_analysis1_pca_input_2025H2.csv   전처리가 완료된 강남구 22개
                                           행정동의 PCA 직전 분석 입력 데이터

  pca_columns.example.json                 4개 PCA 영역별로 어떤 원변수를
                                           사용할지 정의

  common/config.py                         행정동 수, k, random seed, 4개
                                           Domain·13 Features 등 분석 방법론과
                                           실행 조건 관리

  data/ingestion.py                        CSV/XLSX/Parquet 등의 데이터를
                                           pandas DataFrame으로 로딩

  data/validation.py                       필수 컬럼, 행정동 수, 중복, 결측,
                                           자료형, 무한값 등 입력 데이터 검증

  analysis/analysis1.py                    PCA, Feature 생성, Domain 균형화,
                                           K-Means, 안정성 검증 등 핵심 통계
                                           분석 수행

  common/result_schema.py                  PASS/WARNING/FAIL, metrics,
                                           warnings, outputs 등 실행 결과 형식
                                           표준화

  run_analysis1.py                         각 구성요소를 연결하여 전체
                                           Analysis1 파이프라인을 실행하는
                                           진입점
  ----------------------------------------------------------------------------

## 5. 주요 설정 파일

### 5.1 pca_columns.example.json

어떤 원변수들을 하나의 PCA 영역으로 묶을지 정의한다. 현재 PCA 영역은
active_pop, time_structure, resident_age, household_structure의 네
가지다. 분석 코드에 컬럼명을 직접 고정하지 않고 데이터 구조에 맞는 PCA
입력 컬럼을 외부 설정으로 관리한다.

### 5.2 common/config.py

Analysis1의 분석 방법론을 중앙에서 관리한다. 현재 강남구 프로토타입은
expected_areas=22, random_state=42, final_k=3, k 후보 2\~6, perturbation
noise 0.05/0.10/0.20, ARI 기준 0.80을 사용한다. 또한 실제 입력의
flow_per_point를 내부 표준 Feature명 activity_intensity로 매핑한다.

  -----------------------------------------------------------------------
  Domain                              Feature
  ----------------------------------- -----------------------------------
  활동규모                            activity_intensity

  생활활동구조                        active_pop_pc1, active_pop_pc2,
                                      time_structure_pc1,
                                      time_structure_pc2,
                                      weekend_weekday_index

  인구·가구구조                       resident_age_pc1, resident_age_pc2,
                                      foreigner_ratio,
                                      household_structure_pc1,
                                      household_structure_pc2

  구조적 복지배경                     disability_ratio,
                                      livelihood_recipient_ratio
  -----------------------------------------------------------------------

## 6. 입력과 검증 계층

### 6.1 data/ingestion.py

외부 데이터 파일을 pandas DataFrame으로 읽어오는 역할을 담당한다. 데이터
로딩과 통계 분석을 분리함으로써 향후 DB1이 구축되더라도 핵심 분석 로직을
크게 변경하지 않고 입력 계층만 교체할 수 있다.

### 6.2 data/validation.py

분석 전에 필수 컬럼 존재 여부, 행정동 수, 행정동 중복, 결측값, 숫자형
Feature 여부, 무한값 등을 검사한다. 검증 실패 시 분석을 중단하도록
구성하여 향후 AI Agent가 자동 실행할 때 잘못된 데이터로 결과를 생성하는
것을 방지한다.

## 7. analysis/analysis1.py의 핵심 처리

fit_pca_block() 각 PCA 블록의 원변수를 StandardScaler로 표준화한 뒤
PCA를 수행하여 PC1·PC2를 생성한다.

build_feature_table() PCA 결과와 직접 사용하는 변수를 결합하여 최종 13개
Feature 테이블을 만든다.

balance_domains() 13개 Feature를 Z-score로 표준화하고 각 Domain 내부
Feature에 1/√n 가중치를 적용하여 4개 Domain의 거리 기여를 균형화한다.

evaluate_kmeans() k=2\~6을 대상으로 Silhouette, Inertia, Cluster 크기,
Singleton 존재 여부를 비교한다.

perturbation_stability() Feature에 작은 noise를 반복 추가한 뒤 원래
군집과의 ARI를 계산하여 군집 구조의 안정성을 확인한다.

fit_final_clusters() 최종 k=3으로 K-Means를 실행하여 22개 행정동에
cluster 값을 부여한다.

build_cluster_profile() 군집 결과를 원래의 해석 가능한 변수와 다시
연결하여 Cluster별 특성을 요약한다.

save_outputs() Feature, 균형화 결과, 군집 평가, 안정성, 최종 Cluster,
모델 객체, 실행 manifest를 저장한다.

## 8. K-Means와 안정성 검증

K-Means 후보 k=2\~6을 비교한 뒤 최종적으로 k=3을 사용한다. Cluster 번호
0·1·2는 순위나 위험 수준을 의미하지 않으며 단순한 군집 식별자다. 또한
silhouette만으로 구조를 판단하지 않고 Perturbation Stability를 함께
계산하여 작은 데이터 변화에도 군집이 유지되는지 보조적으로 검증한다.

## 9. 결과 표준화와 저장

common/result_schema.py는 분석 결과를 status, data_period, data_version,
validation, metrics, warnings, outputs 등의 공통 형식으로 관리한다. 이는
향후 AI Agent가 실행 성공 여부, 경고, 데이터 기간과 결과 위치를
구조적으로 판단하기 위한 기반이다.

  결과 파일                              의미
  -------------------------------------- -----------------------------------
  analysis1_features.csv                 PCA 이후 최종 13 Features
  analysis1_balanced_features.csv        표준화 및 Domain 가중치 적용 결과
  analysis1_k_metrics.csv                k=2\~6 평가 결과
  analysis1_perturbation_stability.csv   Perturbation 안정성 결과
  analysis1_clusters.csv                 행정동별 최종 Cluster
  analysis1_cluster_profile.csv          Cluster별 특성 요약
  analysis1_model_bundle.joblib          PCA·Scaler·K-Means 객체
  analysis1_run_manifest.json            실행 조건·검증·결과 기록

## 10. 실행 진입점: run_analysis1.py

run_analysis1.py는 사용자가 실제 Analysis1을 실행할 때 사용하는
진입점이다. 입력 파일과 PCA mapping을 읽고 run_analysis1()을 호출하며,
사용자는 내부 함수를 일일이 실행할 필요 없이 하나의 명령으로 전체
파이프라인을 수행할 수 있다.

## 11. 현재 재현 검증 결과

실제 2025H2 강남구 22개 행정동 데이터를 사용하여 기존 Colab 분석과
함수화된 Python 모듈의 결과를 비교했다. 22개 행정동, 13개 Feature, 최종
k=3이 정상 재현되었으며 k=3의 Silhouette는 약 0.283512, Inertia는 약
39.461122, Cluster 크기는 7/3/12로 확인되었다.

기존 최종 군집과 신규 코드의 군집을 행정동 단위로 비교한 결과 Adjusted
Rand Index(ARI)=1.0이 확인되었으며, 22개 행정동 모두 기존 분석과 동일한
군집에 배정되었다. 따라서 현재 함수화된 Analysis1의 핵심 분석
파이프라인은 기존 분석을 재현하는 것으로 검증되었다.

## 12. 향후 DB1 및 AI Agent 연결

현재 프로토타입은 CSV를 입력으로 사용하지만 최종 시스템에서는 DB1에서
Analysis1 입력 데이터를 조회하여 DataFrame으로 전달하는 방식으로
전환한다. run_analysis1()은 DataFrame을 입력받도록 구성되어 있으므로
CSV에서 DB로 입력원이 변경되어도 핵심 통계 로직은 유지할 수 있다.

향후 Analysis2·3도 동일하게 '입력 → 검증 → 분석 → 결과 표준화' 구조로
함수화한 뒤, 세 분석에서 실제 사용하는 데이터와 산출물을 기준으로 강남구
프로토타입 DB1을 구축하고 AI Agent가 각 분석 모듈을 호출하도록 연결한다.

## 13. 요약

Analysis1은 여러 원천데이터를 강남구 22개 행정동 단위의 분석 입력
데이터로 표준화한 뒤, PCA와 Domain 균형화를 통해 13개 지역 맥락
Feature를 구성하고, K-Means와 안정성 검증을 통해 행정동의 구조적 유형을
탐색하는 재현 가능한 분석 모듈이다. 현재 기존 분석과 ARI=1.0으로 재현
검증을 완료했으며, 향후 DB1과 AI Agent에 연결 가능한 독립 분석 엔진으로
활용한다.

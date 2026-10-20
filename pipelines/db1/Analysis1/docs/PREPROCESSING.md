# Analysis1 전처리 · 독거노인 비율 기준

현재 공식 모델은 `analysis1_2025H2_elder_v2`입니다. 지역 유형의 구조 지표는
**65세 이상 등록인구 중 독거노인 비율**과 동별 생계급여 수급자 비율입니다.

## 현재 입력과 계산

- SKT AGE/TIME/WKDY 원천자료의 행정동 공간조인·6개월 평균
- 등록인구 Q3/Q4의 하반기 평균: 연령·외국인 비율
- 세대원수 Q3/Q4의 하반기 평균: 가구원 수 구성비
- 독거노인 수: 연간 동별 `합계·계` 관측
- 독거노인 비율의 인구 기준: 독거노인 수와 같은 해 Q4의 65세 이상 등록인구
- 생계급여 수급자: 강남구 구간에서 동별 집계
- 행정동 코드에 따른 22개 동의 일대일 결합·결측·분모 검증

`build_analysis1_pca_input`은 SKT·등록인구·세대·생계급여 자료를 결합하고,
`attach_cluster_feature`가 연간 독거노인 비율을 추가합니다. 최종 원입력은 22행×30열,
PCA와 고정 모델에 적용하는 지표는 13개입니다. 기존 장애인 비율은 현재 모델 입력에서 제외했습니다.

연간 독거노인 수와 Q4 인구의 관측 시점 차이를 함께 기록합니다. 공개 시점 미확인 자료는
사후 지역 배경으로 설명하며, 월별 고립률·고립 사례 수·개인 판정으로 해석하지 않습니다.
H1은 전년도까지, H2는 해당 연도까지의 관측을 선택합니다. 해당 연도의 인구 분모가 없으면 처리를 보류합니다.

## 실행과 갱신

전체 원천자료 경로는 `run_full_preprocessing.py`, 반기 갱신은 `update_worker.py`를 사용합니다.
메인 서비스의 관리자 5종 업로드는 `service_adapter.py`를 통해 동일한 고정 모델을 적용합니다.
실행 방법은 [Analysis1 안내](../../README.md#analysis1)와 [서비스 통합 안내](../../../../docs/data-operations.md)를 참조하세요.
기존 참조·검증 자료는 과거 결과 재현용이며, 현재 지표명을 바꾸기 위해 과거 숫자나 검증 결과를 수정하지 않습니다.

## 이전 전처리 기록 (구 모델)

아래는 장애인 비율을 사용하던 시기의 구현·검증 기록입니다. “현재”, “남은 adapter”,
장애인 입력·오차에 관한 설명은 당시 상태를 뜻합니다. 현재 입력과 실행 기준은 위 안내를 따릅니다.

목표: Colab 노트북의 원본 전처리를 로컬 Python 모듈로 이전하고 기존 `gangnam_analysis1_pca_input_2025H2.csv`를 reference로 검증한다.

### v1 당시 구현
- CSV 인코딩/구분자 자동 로딩
- 등록인구 Q3/Q4 → 하반기 평균 및 연령/외국인 비율
- 세대원수 Q3/Q4 → 1/2/3/4+ 가구비율
- 장애인 동별 → 장애인 비율
- 월별 SKT 33-feature 파일 → Analysis1 사용 13개 원변수 선택
- 22개 행정동 one-to-one 결합 및 검증

### v1 당시 미구현 adapter
1. `국민기초생활 수급자 동별 현황(202405).xlsx`의 생계급여 구조를 노트북 Cell 54~65와 동일하게 함수화
2. SKT `flow_age_pop_YYYYMM`, `flow_time_pop_YYYYMM`, `flow_wkdy_pop_YYYYMM` 원본이 로컬 raw 폴더에 들어올 경우 33-feature 생성까지 자동화

현재 제공된 파일에는 2025-07 SKT 33-feature 가공본만 있고 위 18개 SKT 원본(3종×6개월)은 포함되어 있지 않으므로, v1은 이 파일을 SKT 입력 경계로 사용한다.

### SKT 유동인구 원본 전처리
Colab 노트북과 동일하게 AGE/TIME/WKDY 원본의 EPSG:5179 좌표를 `서울_행정동_경계_2017_EPSG5179.geojson`과 `within` 공간조인합니다. `BLOCK_CD` 접두어만으로 행정동을 지정하면 기존 202507 산출물과 일치하지 않으므로 사용하지 않습니다.

```bash
python run_skt_preprocessing.py \
  --raw-dir data/raw/skt \
  --month 202507 \
  --boundary data/raw/boundary/서울_행정동_경계_2017_EPSG5179.geojson \
  --reference data/processed/gangnam_db1_features_202507.csv
```

8~12월도 같은 폴더에 3종 원본을 넣고 `--month YYYYMM`만 변경하여 실행합니다.

### SKT 202507 regression validation
- Raw inputs: AGE/TIME/WKDY 202507 + Seoul administrative boundary EPSG:5179
- Spatial join: point-in-polygon (`within`), identical to the original Colab method
- Gangnam output: 22 administrative dongs
- Time-period definition fixed to the existing 202507 DB1 artifact: night 00-05, morning 06-10, daytime 11-18, evening 19-23
- 1123074 is normalized from the 2017 boundary label `일원2동` to current project label `개포3동`
- `sat_ratio` and `sun_ratio` are included so the output reproduces all 33 reference columns
- Regression result against `gangnam_db1_features_202507.csv`: PASS (22/22 dongs, numerical differences only floating-point rounding level)


### v4 공공데이터 전처리 검증
- 등록인구 Q3/Q4: reference PCA input과 최대 오차 < 1e-16
- 세대원수별 세대수 Q3/Q4: 최대 오차 < 1e-16
- 장애인 현황: 최대 오차 < 1e-16
- 국민기초생활 수급자: 강남구 블록 제한 후 최대 오차 < 1e-16
- 주의: 서울 전체에는 같은 행정동명이 존재하므로 welfare.py는 반드시 강남구 블록을 먼저 제한합니다.

### v5 당시 구 모델의 전체 로컬 전처리
`run_full_preprocessing.py`는 SKT CSV/ZIP 폴더를 직접 받아 ZIP 내부 파일명을 기준으로 202507~202512 AGE/TIME/WKDY를 자동 탐색합니다. 이후 공간조인, 6개월 평균, 등록인구/세대/장애/복지 결합을 거쳐 `gangnam_analysis1_pca_input_2025H2.csv`를 생성합니다.

시간대 정의는 최종 Analysis1 PCA 입력 기준인 00~06 / 07~11 / 12~18 / 19~23을 사용합니다. 과거 202507 33-column 파일 검증이 필요한 경우 `legacy_202507` 프로필을 별도로 사용할 수 있습니다.

### v6 - fixed baseline and change detection
`run_baseline.py` fixes the approved 2025H2 13-feature / four-domain / KMeans(k=3) baseline. `run_change_detection.py` transforms later 30-column Analysis1 inputs with the saved PCA/scalers/KMeans without refitting, and outputs feature deltas, four domain distances, centroid distance, and cluster/type changes.

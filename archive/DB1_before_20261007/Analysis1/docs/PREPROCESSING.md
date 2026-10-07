# Analysis1 로컬 전처리 v1

목표: Colab 노트북의 원본 전처리를 로컬 Python 모듈로 이전하고 기존 `gangnam_analysis1_pca_input_2025H2.csv`를 reference로 검증한다.

## 현재 구현
- CSV 인코딩/구분자 자동 로딩
- 등록인구 Q3/Q4 → 하반기 평균 및 연령/외국인 비율
- 세대원수 Q3/Q4 → 1/2/3/4+ 가구비율
- 장애인 동별 → 장애인 비율
- 월별 SKT 33-feature 파일 → Analysis1 사용 13개 원변수 선택
- 22개 행정동 one-to-one 결합 및 검증

## 남은 adapter
1. `국민기초생활 수급자 동별 현황(202405).xlsx`의 생계급여 구조를 노트북 Cell 54~65와 동일하게 함수화
2. SKT `flow_age_pop_YYYYMM`, `flow_time_pop_YYYYMM`, `flow_wkdy_pop_YYYYMM` 원본이 로컬 raw 폴더에 들어올 경우 33-feature 생성까지 자동화

현재 제공된 파일에는 2025-07 SKT 33-feature 가공본만 있고 위 18개 SKT 원본(3종×6개월)은 포함되어 있지 않으므로, v1은 이 파일을 SKT 입력 경계로 사용한다.

## SKT 유동인구 원본 전처리
Colab 노트북과 동일하게 AGE/TIME/WKDY 원본의 EPSG:5179 좌표를 `서울_행정동_경계_2017_EPSG5179.geojson`과 `within` 공간조인합니다. `BLOCK_CD` 접두어만으로 행정동을 지정하면 기존 202507 산출물과 일치하지 않으므로 사용하지 않습니다.

```bash
python run_skt_preprocessing.py \
  --raw-dir data/raw/skt \
  --month 202507 \
  --boundary data/raw/boundary/서울_행정동_경계_2017_EPSG5179.geojson \
  --reference data/processed/gangnam_db1_features_202507.csv
```

8~12월도 같은 폴더에 3종 원본을 넣고 `--month YYYYMM`만 변경하여 실행합니다.

## SKT 202507 regression validation
- Raw inputs: AGE/TIME/WKDY 202507 + Seoul administrative boundary EPSG:5179
- Spatial join: point-in-polygon (`within`), identical to the original Colab method
- Gangnam output: 22 administrative dongs
- Time-period definition fixed to the existing 202507 DB1 artifact: night 00-05, morning 06-10, daytime 11-18, evening 19-23
- 1123074 is normalized from the 2017 boundary label `일원2동` to current project label `개포3동`
- `sat_ratio` and `sun_ratio` are included so the output reproduces all 33 reference columns
- Regression result against `gangnam_db1_features_202507.csv`: PASS (22/22 dongs, numerical differences only floating-point rounding level)


## v4 공공데이터 전처리 검증
- 등록인구 Q3/Q4: reference PCA input과 최대 오차 < 1e-16
- 세대원수별 세대수 Q3/Q4: 최대 오차 < 1e-16
- 장애인 현황: 최대 오차 < 1e-16
- 국민기초생활 수급자: 강남구 블록 제한 후 최대 오차 < 1e-16
- 주의: 서울 전체에는 같은 행정동명이 존재하므로 welfare.py는 반드시 강남구 블록을 먼저 제한합니다.

## v5: 2025H2 전체 로컬 자동 전처리
`run_full_preprocessing.py`는 SKT CSV/ZIP 폴더를 직접 받아 ZIP 내부 파일명을 기준으로 202507~202512 AGE/TIME/WKDY를 자동 탐색합니다. 이후 공간조인, 6개월 평균, 등록인구/세대/장애/복지 결합을 거쳐 `gangnam_analysis1_pca_input_2025H2.csv`를 생성합니다.

시간대 정의는 최종 Analysis1 PCA 입력 기준인 00~06 / 07~11 / 12~18 / 19~23을 사용합니다. 과거 202507 33-column 파일 검증이 필요한 경우 `legacy_202507` 프로필을 별도로 사용할 수 있습니다.

## v6 - fixed baseline and change detection
`run_baseline.py` fixes the approved 2025H2 13-feature / four-domain / KMeans(k=3) baseline. `run_change_detection.py` transforms later 30-column Analysis1 inputs with the saved PCA/scalers/KMeans without refitting, and outputs feature deltas, four domain distances, centroid distance, and cluster/type changes.

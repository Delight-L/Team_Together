# Analysis1 원본파일 전처리 에이전트

API 키나 자동 다운로드는 사용하지 않습니다. 사진처럼 `raw_data` 폴더에 원본 파일을 넣고 실행하면, Analysis1 지역 유형 분석에 쓸 CSV를 만듭니다.

## 1. 원본 파일 넣기

`pipelines/preprocessing/regional_types/raw_data` 폴더에 아래 **필수 5개**를 넣습니다. 파일명 뒤의 날짜·괄호는 달라도 됩니다.

|필수 파일|파일명에서 포함돼야 하는 글자|
|---|---|
|2025H2 SKT 유동 특성 자료|`gangnam_db1_features_2025H2.csv` (전달본 반기 집계)|
|등록인구(연령별·동별)|`등록인구`|
|세대원수별 세대수|`세대원수별`|
|독거노인 현황(2025년 포함)|`독거노인별`, `성별`, `항목`, `단위` 열이 있는 CSV|
|국민기초생활 수급자 동별 현황|`국민기초생활 수급자 동별 현황`|

나머지 원본 파일(1인가구·고령자·장애등급·수급자 연령별 등)은 지금 Analysis1의 PCA 입력에 직접 쓰이지 않지만, 같은 `raw_data` 폴더에 함께 보관해도 됩니다.

## 2. 실행

프로젝트 루트에서 실행합니다.

```powershell
python main.py --preprocess-analysis1
```

원본 또는 결과 폴더가 다른 곳에 있다면:

```powershell
python main.py --preprocess-analysis1 --raw-dir "raw_data" --output-dir "outputs\analysis1_preprocessed"
```

## 3. 결과

`outputs/analysis1_preprocessed`에 아래 파일이 생깁니다.

- `analysis1_input.csv`: PCA·군집화 입력 파일
- `analysis1_profile.csv`: 고정 elder v2 모델로 계산한 동별 지역 유형과 원자료 프로필
- `pca_columns.json`: PCA에 사용할 열 목록
- `preprocessing_manifest.json`: 22개 동·결측 검증 결과

이 결과는 동별 **지역 유형·맥락** 자료이며, 개인 또는 동의 고립 위험 점수는 아닙니다. `일원2동` 표기는 행정동 코드 기준으로 `개포3동`으로 통일합니다.

65세 이상 등록인구 중 독거노인 비율은 2025년 독거노인 수를 2025년 4분기 65세 이상 등록인구로 나눕니다.
승인된 `analysis1_2025H2_elder_v2` 모델을 적용하며 업로드 때 재학습하지 않습니다.
연간 자료의 공개일은 미확인입니다. 과거 월 당시 알고 있던 정보로 설명하지 않습니다.
이 업로드 경로는 2025H2 자료용입니다. 신규 반기는 `pipelines/db1/run_db1.py analysis1 --period ...`로 처리합니다.


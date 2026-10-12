# Analysis1 원본파일 전처리 에이전트

API 키나 자동 다운로드는 사용하지 않습니다. 사진처럼 `raw_data` 폴더에 원본 파일을 넣고 실행하면, Analysis1 지역 유형 분석에 쓸 CSV를 만듭니다.

## 1. 원본 파일 넣기

`preprocessing/regional_types/raw_data` 폴더에 아래 **필수 5개**를 넣습니다. 파일명 뒤의 날짜·괄호는 달라도 됩니다.

|필수 파일|파일명에서 포함돼야 하는 글자|
|---|---|
|공모전/SKT 유동 특성 자료|`gangnam_db1_features`|
|등록인구(연령별·동별)|`등록인구`|
|세대원수별 세대수|`세대원수별`|
|장애인 현황(장애유형별·동별)|`장애인 현황(장애유형별`|
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
- `analysis1_profile.csv`: 동별 전처리 프로필
- `pca_columns.json`: PCA에 사용할 열 목록
- `preprocessing_manifest.json`: 22개 동·결측 검증 결과

이 결과는 동별 **지역 유형·맥락** 자료이며, 개인 또는 동의 고립 위험 점수는 아닙니다. `일원2동` 표기는 행정동 코드 기준으로 `개포3동`으로 통일합니다.

이전 중복 전처리 폴더에 있던 JSON 산출물은 `outputs/previous_preprocessing_agent`에 보존했습니다.

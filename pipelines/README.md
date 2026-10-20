# 데이터 파이프라인 안내

분석 결과 생성, 원본 전처리, 복지사업 수집을 관리합니다. 아래 명령은 프로젝트 루트 기준입니다.

| 폴더 | 역할·안내 |
|---|---|
| `db1/` | Analysis1·2·3, 조사 맥락, 모델·검증. [DB1 실행과 분석 기준](db1/README.md) |
| `regional_analysis/` | 통합 분석 진입점(DB1 파이프라인 호출) |
| `preprocessing/regional_types/` | Analysis1 원본 전처리 |
| `preprocessing/regional_features/` | 기존 Analysis2의 월별 원본 전처리 |
| `risk_analysis/` | 별도 위험변화 탐지 도구 |
| `welfare/` | 공공 API의 DB2 복지사업 수집 |

## 복지사업 수집

설정과 수집 옵션을 확인한 뒤 실행합니다. 예약 수집 구성은 [수집 운영 안내](../docs/DB2_지자체복지_정기수집.md)와 저장소의 `scripts/`·`deploy/` 설정을 함께 확인하세요. 폴더 존재만으로 예약 실행이 배포된 것은 아닙니다.

```powershell
python -m pipelines.welfare.collect --help
```

DB1 결과 생성과 서비스 PostgreSQL 반영은 별도 단계입니다. [DB1 서비스 통합](../docs/data-operations.md)의 검사·반영 절차를 따릅니다.

## 문서 목차

- [지역 분석 실행 연결](#regional-analysis)
- [Analysis1 원본 전처리](#regional-types)
- [Analysis2 원본 전처리](#regional-features)
- [별도 위험변화 분석](#risk-analysis)

<a id="regional-analysis"></a>

## 지역 분석 실행 연결

작업 기준 폴더: `pipelines/regional_analysis/`

`python main.py --analysis`의 실행점(`main.py`)과, `python main.py --preprocess`가 쓰는 예전 Analysis2 실행기를 둡니다.
분석 코드 본체는 `pipelines/db1`, 보미의 지역 변화 신호 에이전트는 `backend/agents/regional_analysis`에 있습니다.

```powershell
python main.py --analysis --no-download
python main.py --analysis --publish
```

기본 명령은 전달된 Analysis1 elder v2 / Analysis2 CSV를 검사합니다. `--publish`는
서비스 DB에 새 실행 버전으로 반영합니다. 분석 작업 영역과 과거 실행은 보존합니다.
신규 반기나 월 분석은 `--command analysis1 --period ...`, `--command analysis2 --month ...`를 사용합니다.
원천자료 설정과 PostgreSQL 작업 스키마를 `--config`, `--db`로 지정할 수 있습니다.

### 폴더 구성

| 항목 | 역할 |
|---|---|
| `main.py` | `--analysis` 실행점. `pipelines/db1/run_db1.py`와 `scripts/import_db1.py`를 호출 |
| `Analysis2/` | 예전(전체 기간 일괄) Analysis2 실행기. `--preprocess` 증분 갱신(`pipelines/preprocessing/regional_features/auto_update.py`)이 호출 |

예전 Analysis2의 과거 결과(reference CSV)는 `pipelines/db1/Analysis2/data/reference/`에 같은 파일로 보존되어 있어 이 폴더에서는 지웠습니다.
`Analysis2/outputs/`는 실행할 때 다시 만들어지는 결과라 저장소에 두지 않습니다.
신규 순차 분석은 `pipelines/db1/Analysis2`를 사용합니다. 기존 위험신호를 임의로 재계산하거나
연간 독거노인 배경자료를 개인 고립 확정값으로 해석하지 않습니다.

상세 실행과 검증 범위는 [DB1 서비스 통합](../docs/data-operations.md)을 참고하세요.

<a id="regional-types"></a>

## Analysis1 원본 전처리

작업 기준 폴더: `pipelines/preprocessing/regional_types/`

API 키나 자동 다운로드는 사용하지 않습니다. 사진처럼 `raw_data` 폴더에 원본 파일을 넣고 실행하면, Analysis1 지역 유형 분석에 쓸 CSV를 만듭니다.

### 1. 원본 파일 넣기

`pipelines/preprocessing/regional_types/raw_data` 폴더에 아래 **필수 5개**를 넣습니다. 파일명 뒤의 날짜·괄호는 달라도 됩니다.

|필수 파일|파일명에서 포함돼야 하는 글자|
|---|---|
|2025H2 SKT 유동 특성 자료|`gangnam_db1_features_2025H2.csv` (전달본 반기 집계)|
|등록인구(연령별·동별)|`등록인구`|
|세대원수별 세대수|`세대원수별`|
|독거노인 현황(2025년 포함)|`독거노인별`, `성별`, `항목`, `단위` 열이 있는 CSV|
|국민기초생활 수급자 동별 현황|`국민기초생활 수급자 동별 현황`|

나머지 원본 파일(1인가구·고령자·장애등급·수급자 연령별 등)은 지금 Analysis1의 PCA 입력에 직접 쓰이지 않지만, 같은 `raw_data` 폴더에 함께 보관해도 됩니다.

### 2. 실행

프로젝트 루트에서 실행합니다.

```powershell
python main.py --preprocess-analysis1
```

원본 또는 결과 폴더가 다른 곳에 있다면:

```powershell
python main.py --preprocess-analysis1 --raw-dir "raw_data" --output-dir "outputs\analysis1_preprocessed"
```

### 3. 결과

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

<a id="regional-features"></a>

## Analysis2 원본 전처리

작업 기준 폴더: `pipelines/preprocessing/regional_features/`

기준 feature table을 보존한 채 서울 열린데이터광장의 월별 통신정보·관심집단 파일을 확인하고, 새 월만 증분 전처리한 뒤 Analysis2를 실행하는 프로그램입니다. 공식 페이지에 공개된 파일 링크를 사용하므로 별도 API 키가 없어도 되며, 페이지 구조나 접근 제한이 바뀌면 다운로드 실패로 기록합니다.

### 실행

프로젝트 루트에서 Python 의존성을 설치하고 실행하세요.

```powershell
python -m pip install -r requirements.txt
python main.py --preprocess
```

기본 실행은 `최신 파일 확인/다운로드 → 새 월 전처리 → 기존 feature table에 추가 → Analysis2 실행`입니다. Analysis2는 `pipelines/db1/Analysis2/run_analysis2.py`를 `--input`(갱신된 feature table)과 `--output-dir`(이 폴더의 `outputs`)로 실행합니다. 새 월에 필요한 날씨 행이 `reference/weather_monthly.csv`에 없으면 안전하게 중단하므로 날씨 자료를 먼저 추가해야 합니다. 전체 재생성이 필요할 때만 `python main.py --preprocess --full`을 사용합니다.

`raw_data`에 2022~2025년 통신정보와 관심집단 원본 ZIP을 넣습니다. ZIP 안의 ZIP도 해제합니다. 원본을 복사하지 않고 사용할 수 있습니다.

```powershell
python main.py --preprocess --input "C:\자료\원본.zip" --output "C:\결과\Analysis2"
python main.py --preprocess --input "C:\자료\2022.zip" --input "C:\자료\2023_2025.zip"
python main.py --preprocess --compare "C:\참고\gangnam_analysis2_feature_table_2022_2025.csv"
python -m unittest discover -s pipelines/preprocessing/regional_features/tests -v
```

`--compare`는 기존 결과와 모든 숫자 열을 절대오차 1e-8로 비교합니다. 비교 결과가 DIFFERENT여도 원본 계산이 유효하면 CSV를 생성하며, 열별 차이와 불일치 개수를 보고합니다. 기존 CSV의 행동 지표를 계산 입력으로 쓰지 않습니다.

다운로드된 원본은 `raw_data`에 남고, 처리 상태는 `outputs/auto_update_manifest.json`에 기록됩니다. 새 월의 통신정보와 관심집단 파일이 모두 준비되기 전에는 기존 결과를 바꾸지 않습니다.

### 결과와 실패

- `outputs/gangnam_analysis2_feature_table_2022_2025.csv`: 기본 48개월 × 22동 = 1,056행, 23열. Analysis2 입력 파일로 사용합니다.
- `preprocessing_manifest.json`: 원본·중첩 경로·SHA-256, 중복 및 제외 내역, 처리 월·종류, 이름 변경, 날씨 출처.
- `validation_report.json`: PASS/FAIL, 오류, 선택적 비교 결과.

누락·손상·숫자 오류·유효 인구 음수·분모 0·같은 월의 서로 다른 자료가 있으면 종료코드 1로 실패합니다. 실패한 실행은 새 정상 CSV를 만들지 않습니다. 이전 실행의 CSV가 있으면 남겨두되 보고서에 이전 결과임을 표시합니다. 재실행은 결과와 보고서를 교체합니다. 성공은 종료코드 0 및 보고서 PASS로 확인합니다.

설정 JSON 오류도 FAIL 보고서를 기록합니다. 설정을 읽을 수 없으면 `--output` 지정 위치 또는 기본 `outputs` 폴더에 기록합니다. 임시 폴더 정리까지 성공한 후 새 CSV를 교체하므로 정리 실패 시에도 이전 CSV는 유지됩니다. 비교 허용오차는 0 이상인 유한한 숫자만 허용합니다.

### 계산과 자료 출처

통화·문자는 총인구 가중평균입니다. 이동 4종은 각 지표의 미추정 인구를 뺀 유효 인구로 가중평균을 계산합니다. 추정비율은 유효 인구 합/총인구 합입니다. 관심집단 비율은 집단수 합/1인가구수 합입니다. 월력은 월~금과 토~일을 구분하며 공휴일을 재분류하지 않습니다.

제공한 `서울시 공공데이터.zip`의 통신정보 전처리 코드와 `Analysis2.zip`의 최종 CSV 규격을 참고했습니다. 날씨 48개월 3열만 기존 Analysis2 CSV에서 재사용합니다. 원 관측소 및 수집 정의는 제공 자료에서 확인되지 않았습니다. `reference/provenance.json`에 출처 파일과 해시를 기록했습니다. 날씨 외 행동값은 원본 XLSX에서 계산합니다.

번들 날씨 출처는 기록된 날씨 SHA-256과 실제 입력이 일치할 때만 적용합니다. 다른 날씨 CSV는 사용자 지정 자료로 표시하고 실제 경로·해시를 기록합니다. 그 파일의 상위 출처는 확인되지 않은 것으로 표시합니다.

코드 1123074는 기존 Analysis2와 호환되도록 `일원2동`으로 출력합니다. 원본의 `개포3동` 표기는 변경 이력에 남깁니다. 2024-01 이후 `interest_structural_issue=True`를 유지하며 관측된 0을 임의 보간하지 않습니다.

### 설정과 제한

`config.json`에서 시작·종료월, 입력·출력·날씨 경로, 압축 제한을 바꿀 수 있습니다. 상대 경로는 설정 파일의 폴더 기준입니다. 사용자 설정은 `--config 경로`로 지정합니다. 날짜 범위를 줄이면 부분 전처리가 가능하지만 기존 Analysis2의 48개월 조건은 충족하지 않습니다. 새로운 기간에는 `date,rain_days,rainfall_mm,snow_days` 형식의 월별 날씨 CSV가 필요합니다. 출력 파일 이름은 호환성을 위해 고정되어 있으므로 실제 기간은 보고서와 설정을 확인하세요.

파일명에는 `2022.1월` 또는 `2022-01`처럼 기준월이 있어야 합니다. 지원 스키마의 XLSX만 입력하세요. SHA 중복은 한 번 처리하고, 같은 종류·월의 서로 다른 파일은 강남구 인구 셀의 정규화된 값이 같을 때만 중복으로 인정합니다. 서로 다른 자료를 더해서 합치지 않습니다. 워크북은 읽기 전용으로 순차 처리하고 강남구의 필요한 값만 집계합니다.

성별 1·2 × 연령 20~75세(5세 단위)의 24개 셀을 동별로 검증합니다. 일부 행 누락도 오류로 처리합니다. 새 스키마에서 연령 구간이 달라지면 `demographics`를 명시적으로 수정해야 합니다.

ZIP 경로 탈출·심볼릭 링크·CRC 손상·해제 크기/깊이/개수 초과를 차단합니다. 임시 해제 폴더는 실행 종료 시 제거됩니다. 기본 총 해제 제한은 12GiB이며 충분한 임시 디스크 공간이 필요합니다. 압축 원본은 배포 패키지에 포함하지 않습니다.

<a id="risk-analysis"></a>

## 별도 위험변화 분석

작업 기준 폴더: `pipelines/risk_analysis/`

동별 월간 집계 데이터에서, 다른 동보다 위험 방향으로 크게 변했고 그 동의 과거 변화폭보다 이례적인 지표를 찾습니다. 개인 단위 판정이 아니라 **현장 확인 우선순위 후보**를 만드는 도구입니다.

### 1. 준비

이 폴더의 `main.py`(실행), `analyzer.py`(탐지 로직), `data_provider.py`(CSV 검증), `config.py`(지표 규칙), `region_context.py`(지역 유형)를 함께 씁니다. 필요한 패키지는 프로젝트 루트의 `requirements.txt`로 설치합니다.

### 2. CSV 필수 열

입력 CSV에는 다음 세 열이 꼭 있어야 합니다.

`행정동코드`, `행정동명`, `기준연월`

`기준연월`은 `2025-07` 형태여야 합니다. 같은 동·같은 월은 한 행만 있어야 합니다.

### 3. 포함된 전처리 CSV로 실행

프로젝트 루트에서 **한 줄 전체를 한 번에** 입력합니다.

```bash
python main.py --risk --input "pipelines/risk_analysis/data/gangnam_db1_dong_month_behavior_mart_2025_07_12(1).csv" --min-relative-change 5 --z-threshold 3.5 --output-dir outputs
```

이 명령은 저장소에 포함된 전처리 CSV를 입력으로 사용합니다. 분석 지표는 `config.py`에 이 CSV의 실제 열 이름으로 연결돼 있습니다. 경로는 명령을 입력한 폴더 기준이라, 결과는 프로젝트 루트의 `outputs` 폴더에 저장됩니다.

특정 지표만 분석하려면 열 이름을 쉼표로 넣습니다.

```bash
python main.py --risk --input "pipelines/risk_analysis/data/gangnam_db1_dong_month_behavior_mart_2025_07_12(1).csv" --metrics "flow_per_point,평일 총 이동 횟수,휴일 총 이동 횟수 평균" --min-relative-change 5 --z-threshold 2.5 --output-dir outputs
```

### 4. 결과

- `outputs/risk_metric_assessment.csv`: 전체 동·월·지표 판정
- `outputs/risk_metric_signals.csv`: 두 기준을 모두 통과한 변화 후보
- `outputs/risk_region_alerts.csv`: 동·월별 후보 요약

실행이 끝나면 위 CSV 저장 경로 아래에 `[사용자용 위험 변화 후보]`가 바로 출력됩니다. Analysis 1의 확정 `k=3` 동별 지역 Context를 **행정동코드**로 조회해, 지역 유형과 특징을 함께 보여줍니다. 반복되는 확인 포인트는 실행 화면에서 제외하고 코드 내부에만 보관합니다. 따라서 동 이름의 과거 명칭·띄어쓰기와 무관하게 같은 지역을 연결합니다. `pipelines/risk_analysis/data/gangnam_analysis1_cluster_profile_2025H2(1).csv`는 유형별 대표 지표를 보관한 근거 파일입니다. 군집은 위험도 확정값이 아니라 해석 보조 정보입니다.

### 위험 방향

활동·이동·통화 대상은 **감소**, 집 체류·저외출·카카오톡 비사용 비율은 **증가**를 위험 방향으로 설정했다. 개인 판정이 아니라 동별 현장 확인 후보를 찾는 용도다.
## 원본 CSV부터 실행하기

Analysis1 원본 전처리는 공용 `pipelines/preprocessing/regional_types`를 사용합니다. 프로젝트 루트에서 `python main.py --preprocess-analysis1 --raw-dir "원본폴더"`로 실행하세요. 입력과 산출물은 [전처리 안내](README.md#regional-types)를 확인하세요.

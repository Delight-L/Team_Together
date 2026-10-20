# DB1 실행·분석 통합 안내

Analysis1·2·3, 조사 맥락, 검증과 그래프 설명을 이 문서에 모았습니다. [전체 파이프라인](../README.md) · [서비스 DB 반영](../../docs/data-operations.md)

각 절의 **작업 기준 폴더**를 확인하세요. 코드 표기와 일반 텍스트의 상대 경로는 해당 폴더 기준이며, 클릭 가능한 문서 링크는 이 README 기준입니다. 날짜·건수가 있는 운영 기록은 당시 결과로, 현재 DB 상태를 보증하지 않습니다.

## 문서 목차

- [공통 실행과 운영 기록](#execution)
- [Analysis1 지역 유형](#analysis1)
- [Analysis2 변화 탐지](#analysis2)
- [과거 재현·민감도 검증](#validation)
- [Analysis3 소비 맥락](#analysis3)
- [관계망·외로움 조사자료](#survey-context)
- [보존 그래프](#figures)

<a id="execution"></a>

## 공통 실행과 운영 기록

작업 기준 폴더: `pipelines/db1/`

Analysis1은 반기별 지역유형, Analysis2는 월별 변화 탐지, Analysis3은 분기·월 소비 맥락을 처리합니다. 원본 자료는 프로젝트 바깥의 기존 공모전·서울시 데이터 폴더에서 읽습니다.

### 실행
DB1 폴더의 PowerShell에서 실행합니다.
```powershell
.\run_db1.ps1 -Command status
.\run_db1.ps1 -Command scan
.\run_db1.ps1 -Command export
```
테스트 파일·fixture·`run_tests.ps1`은 프로젝트 마무리(2026-10-20) 때 삭제했습니다.
이 문서의 테스트 명령·건수는 로컬 검증 자료가 있는 환경 또는 당시 실행 기록을 설명합니다.
`scan`은 새 자료를 전처리하고 DB에 통합한 후 CSV를 갱신합니다. `export`는 저장된 DB 결과를 다시 내보냅니다. `watch`는 실행 중 주기적으로 scan을 반복합니다. Analysis1 특정 반기는 `-Command analysis1 -Period 2026H1`, Analysis2 특정 월은 `-Command analysis2 -Month 2026-01`로 실행합니다. 해당 기간 원본과 공공자료가 준비되어야 합니다.

### 파일 위치
- `config/db1_config.json`: 공통 DB, 원본 및 Analysis1·2 설정.
- `db1_pipeline`: DB1 분석 실행기가 공유하는 작업·전달 DB. 웹 서비스는 검사·게시된 PostgreSQL 결과를 조회합니다.
- `outputs/integrated/`: Analysis1·2 통합 CSV와 Analysis1·2·3 연결 CSV.
- `outputs/figures/`: 기존 분석 그래프 PNG·SVG. CSV 갱신과 별도로 보존된 시각화입니다.
- `Analysis1/data/reference/`: 고정 기준 입력; `models/2025H2_elder_v2/`: 기준 모델.
- `Analysis1/data/processed/<반기>/`: 전처리 입력; `outputs/baseline/`, `outputs/periods/<반기>/`: 분석 결과.
- `Analysis2/data/reference/`: 초기 이력·기준 비교 자료; `outputs/history.csv`, `detection.csv`, `evidence.csv`: DB 결과 내보내기; `outputs/monthly/<월>/`: 월별 특징·탐지 결과.
- `Analysis2/tests/fixtures/`: 테스트에 필요한 작은 원본 예제. 운영 원본 폴더와 구분합니다.
- `Analysis3/config/analysis3_config.json`: 소비 자료·내보내기 설정; `db/schema.sql`: 스키마; `outputs/`: 소비 전처리·분석 결과; `outputs/mappings/`: 동·업종 연결표; `logs/`: 마지막 실행 기록.
- `tests/`, 각 분석의 `tests/`: 검증; `tools/`: 초기 설정·원본 검증 보조 도구; `docs/`: 실행 안내·과거 검증·정리 기록.

이전 중복 DB, 중복 CSV, 구식 일괄 실행기, 대시보드와 보고서는 정리 전 전체 백업에 보관합니다. 과거 검증 문서의 경로는 당시 기록이며 현재 실행 안내는 이 문서입니다. 기준 모델과 운영 DB의 내용은 폴더 정리 과정에서 변경하지 않습니다.


Analysis2의 동·연령대별 전처리 이력과 업데이트 경로를 추가했습니다. `run_db1.ps1 -Command analysis2-age`로 재구축할 수 있으며 일반 `scan`에도 연결됩니다. [상세 안내](Analysis2/AGE_PREPROCESSING.md)를 확인하세요. 연령별 변화 탐지를 구현했습니다. `run_db1.ps1 -Command analysis2-age-detect`로 실행하며 일반 Analysis2 scan에도 연결됩니다. [탐지 안내](Analysis2/AGE_DETECTION.md)를 확인하세요.


### 동·연령별 행동과 소비 연결 (2026-10-07)

연결 구현과 실행을 완료했다. 동·연령별 행동과 소비의 같은 관측 기간 연결은 `v_a123_age_source_context`를 우선 사용한다. 기존 `v_a23_age_monthly`와 `v_a23_age_detail`은 같은 라벨월의 후속 기간 소비 맥락이다. 분기 집계는 `v_a23_age_quarter`, 공표일 기준 조회는 `v_a23_age_available_context`다. 상세 해석과 업데이트 규칙은 `Analysis3/docs/AGE_BEHAVIOR_CONSUMPTION.md`를 참조한다. 소비는 보조 근거이며 탐지 신호나 고립 점수에 합산하지 않는다.


### 동별 독거노인 통계 연결 기록 (2026-10-07, 구 모델)

동별 독거노인 관측 통계 연결을 완료했다. `v_a1_elder_annual`은 연간 지표, `v_a1_elder_context`는 반기 지역 유형 연결, `v_a123_age_elder_context`는 동·연령별 행동·소비와의 사후 연결이다. 독거노인은 65세 이상이므로 60plus에만 부분 연령 일치로 연결한다. 다른 연령대에는 직접 적용하지 않는다. 공표일 기준 조회는 `v_a123_age_elder_available_context`다. 독거 여부는 고립 판정이 아니며 기존 모형과 점수는 유지한다. 갱신 명령은 `run_db1.ps1 -Command analysis1-elder`와 일반 `scan`이고, 해석·DB 질의·정정 처리 규칙은 `Analysis1/ELDERLY_CONTEXT.md`에 있다.


### 관계망·외로움 조사자료

강남구와 서울 전체의 연령별 서울서베이(2022~2025) 및 2022년 청년 고립 참고자료를 추가했다. `Context/README.md`에서 지표 정의와 조회 방법을 확인한다. `run_db1.ps1 -Command survey-context`로 갱신하며 `scan`/`watch`/`export`에도 연결된다. 연도별 원본과 코드 연결의 등록이 필요하다. 기존 탐지 신호와 점수는 보존한다. 통합 조회는 `v_a123_age_survey_context`이며 조사값은 동별 통계가 아닌 강남구 연령별 공통 맥락이다.


신호 이후 네 지표 수준·회복 추적은 `analysis2-activity`로 실행하며 월 처리·scan/watch에도 연결됩니다. [AI_AGENT_HANDOFF.md](docs/AI_AGENT_HANDOFF.md)와 [현재 적용 결과](docs/ACTIVITY_LEVEL_RESULT_20261007.md)를 참조하세요.


### AI agent 담당자 인수

먼저 [조회 실행 안내](docs/AI_AGENT_HANDOFF.md), [현재 10건의 근거별 설명](docs/ISOLATION_SIGNAL_EXPLANATIONS.md), [인수 검증 결과](docs/DB1_HANDOFF_ACCEPTANCE_20261007.md)를 읽으세요. `tools/read_agent_context.py --signals-only`로 읽기 전용 통합 근거를 조회합니다. 집계 기준월과 실제 직전 3개월 관측을 구분하고 SNS 시계열 증감률을 계산하지 않습니다. 검증용 모의 DB와 원본 파일은 운영 DB1에 포함하지 않습니다.


### 2026-10-07 근거 보완 반영

청년 조사 세부 통계, 관측 기간 기상, 지연 소비 근거 보충, 공개일 기준 조회를 추가했습니다. [근거 사용 설명](Context/EVIDENCE_CONTEXT.md)과 [검증 결과](docs/DB1_IMPROVEMENTS_RESULT_20261007.md)를 함께 전달하세요. 기존 탐지 건수는 소통 10·이동 0·복합 0으로 유지됩니다.


### GitHub 전달 전 정리

[폴더 구성과 전달 안내](docs/FILE_ORGANIZATION.md)를 참조하세요. 최신 인수인계 본문은 docs/AI_AGENT_HANDOFF.md입니다. 과거 변경 백업은 DB1_backups로 이동했으며 운영 DB·모델·기준 입력은 유지했습니다. 근거별 상태와 청년 세부 근거를 포함한 통합 조회는 tools/read_agent_context.py를 사용하세요.


### 기존 탐지의 근거별 설명

[설명 생성기 사용 방법](docs/ISOLATION_EXPLANATION_USAGE.md)에 따라 DB 업데이트 완료 후 실행합니다. 기존 군집·탐지를 유지하고 자체 과거 기준, 지역 비교, 지속성, 보조 근거를 독립 항목으로 표시합니다.

```powershell
python tools/explain_signals.py --output outputs/handoff/isolation_signal_explanations.json --markdown docs/ISOLATION_SIGNAL_EXPLANATIONS.md
```

현재 자체 과거 기준 10건·지역 비교 2건이며 지속성은 모두 추가 추적입니다. 설명 테스트는 `tests/test_explain_signals.py`에 있어 기본 검증에 포함됩니다.


### 기상 변화 추적

2022-01~2025-06 기상을 고정 기준으로 2025-07부터 실제 월별·행동 관측 3개월별 계절 비교를 저장합니다. 기존 `evidence-context` 및 scan/export 갱신 경로에 포함되며 행동 탐지는 유지합니다. [실제 결과와 사용 방법](docs/WEATHER_TRACKING_RESULT_20261007.md)을 확인하세요.


### Analysis1 모델 갱신 (2026-10-12)

현재 지역 배경 지표는 **65세 이상 등록인구 중 독거노인 비율**입니다. 연간 독거노인 수를 같은 해 4분기 65세 이상 등록인구로 나눕니다. 공식 모델은 `analysis1_2025H2_elder_v2`이며 업데이트 입력·분모·반기 적용 규칙은 [Analysis1 안내](README.md#analysis1)를 참조하세요. 과거의 독거노인 보조 연결 설명은 당시 버전의 기록입니다.

<a id="analysis1"></a>

## Analysis1 지역 유형

작업 기준 폴더: `pipelines/db1/Analysis1/`

### 현재 지역 배경 지표

공식 모델은 `analysis1_2025H2_elder_v2`입니다. 지표명은 **65세 이상 등록인구 중 독거노인 비율**이며,
연간 독거노인 수를 같은 해 4분기 65세 이상 등록인구로 나눕니다. 월별 고립률이나 개인 고립 판정이 아닙니다.
현재 기준과 갱신 규칙은 아래 **Analysis1 공식 모델 변경 (2026-10-12)** 절을 따릅니다.
2026-10-07에 작성한 “기존 모형 유지” 설명은 교체 전 보조 통계 연결 기록입니다.

반기별 지역유형 분석. 기준 모델은 models/2025H2_elder_v2, 고정 입력은 data/reference, 전처리 입력은 data/processed/<반기>, 결과는 outputs/periods/<반기>에 저장합니다.

공통 실행은 [공통 실행 안내](#execution)의 `run_db1.ps1`을 사용합니다. 테스트는 각 분석의 `tests` 폴더를 기준으로 실행합니다.


### 동별 독거노인 통계 연결 (2026-10-07)


### Analysis1 공식 모델 변경 (2026-10-12)

공식 모델은 `analysis1_2025H2_elder_v2`입니다. 장애인 비율을
`elderly_living_alone_rate_65plus`(연간 독거노인 수 / 같은 연도 4분기 65세 이상 등록인구)로 대체했습니다.
기존 연령구조 PCA와 동별 생계급여 수급자 비율을 유지하며 최종 지표는 13개입니다.
독거노인의 수급권자·저소득 구성은 보조 설명에만 사용합니다. 구 단위 연령별 일반수급자 자료는 군집화에 포함하지 않습니다.
22개 동의 군집 배정과 기존 유형 명칭은 유지됐습니다. 실루엣은 0.2835에서 0.2976으로 변했습니다.
이는 군집 구조 비교이며 사회적 고립 탐지 정확도 개선을 뜻하지 않습니다.

연간 독거노인 원본은 설정의 `analysis1.elderly_living_alone.sources`, 연령별 등록인구 원본은
`population_sources`에서 검색합니다. 현재 등록인구 원본 경로와 같은 폴더에 동일한 형식의 신규 파일을 넣으면 됩니다.
원본의 연도·분기 헤더를 판독하므로 다운로드 일시가 다른 파일명도 허용합니다.
새 독거노인 연도와 해당 연도 Q4의 연령별 등록인구가 모두 있어야 새로운 비율을 계산합니다.
분모는 총 등록인구의 65세 이상 합계이며 연간 독거노인 통계와 Q4 인구의 기준 시점 차이를 명시합니다.
원본은 해시 이름으로 보관하고, 원관측은 `a1_elder_observation`, 연간 결과는 `a1_elder_annual`,
분모와 출처는 `a1_elder_population`에 누적 저장합니다. 동일 실행은 중복되지 않습니다.
과거 관측 또는 분모가 달라진 파일은 자동 덮어쓰기를 차단하므로 명시적 정정 절차가 필요합니다.

`run_db1.ps1 -Command analysis1-elder`는 연간 자료·분모·보조 결과를 갱신합니다.
`scan`/`watch`는 이를 갱신하고, SKT 6개월 및 반기 공공자료가 완비되면 새 반기 전처리·기준 모델 적용·DB 저장을 수행합니다.
H1은 전년도까지, H2는 해당 연도까지의 가장 최근 독거노인 관측을 선택합니다.
올해 연간 자료가 아직 없으면 직전 연도를 사용하고 실제 적용 연도·지연 연수를 메타데이터에 기록합니다.
새 독거노인 연도가 있으나 같은 연도 분모가 없으면 반기 처리를 보류하며 임의 분모나 미래 자료를 쓰지 않습니다.
연간 자료가 늦게 추가돼도 이미 저장한 반기 유형을 소급 변경하지 않습니다. 이후 새 반기에 적용합니다.
기준 PCA·표준화·K-Means는 고정 모델을 사용하며 신규 연도마다 재학습하지 않습니다.
연간 경제취약 보조 자료는 기존 관측과 함께 누적되며 고립 확정치나 전 연령의 취약성 점수로 해석하지 않습니다.
실제 공개일 미확인 자료와 2025H2 기준은 사후 지역 설명입니다. 알려진 시점의 실시간 근거로 표현하지 않습니다.
Analysis2·3의 기존 신호·소비 결과는 변경하지 않았습니다.

<a id="analysis2"></a>

## Analysis2 변화 탐지

작업 기준 폴더: `pipelines/db1/Analysis2/`

초기 2022-01~2025-06 이력은 data/reference에 보관합니다. 새로운 월은 기존 이력으로 변화를 탐지한 뒤 운영 DB에 통합합니다. outputs/history.csv·detection.csv·evidence.csv와 monthly/<월>은 DB에서 내보낸 결과입니다.

공통 실행은 [공통 실행 안내](#execution)의 `run_db1.ps1`을 사용합니다. 테스트는 각 분석의 `tests` 폴더를 기준으로 실행합니다.


### 동·연령대별 전처리 이력

2022-01~2025-12 원본에서 연령별 이력을 재구축했습니다. 기준선/업데이트 구간, DB 표, 신규 월 추가 및 해석 범위는 [AGE_PREPROCESSING.md](Analysis2/AGE_PREPROCESSING.md)를 확인하세요. 연령별 탐지를 추가했습니다. [AGE_DETECTION.md](Analysis2/AGE_DETECTION.md)를 확인하세요.

<a id="validation"></a>

## 과거 재현·민감도 검증

작업 기준 폴더: `pipelines/db1/Analysis2/validation/`

운영 모델을 바꾸지 않는 2025년까지의 사후 검증 스냅샷이다. DB1 루트에서 실행한다. 분석 스크립트는 DB의 feature/raw 데이터를 읽고 별도 검증 산출물만 쓴다. 진단 시나리오를 운영 탐지표로 가져오지 않는다.

```powershell
python Analysis2/validation/run_validation.py
python Analysis2/validation/sns_review.py
python Analysis2/validation/build_report.py
```

`python Analysis2/validation/inspect_layout.py`는 원천 컬럼 설명서를 다시 읽는 선택 단계이며 DB1 상위의 서울시 공공데이터 폴더가 필요하다. 설명서는 수정하지 않는다. pandas/numpy는 기존 Analysis2 실행 환경을 사용한다. 설명서 추출에는 openpyxl이 필요하다.

출력은 `outputs/validation/retrospective_20261007/`다. 재실행은 이 검증 스냅샷 파일들을 갱신한다. docs의 배포 보고서·인계 문서는 검토 후 별도로 갱신해야 한다. 자동 scan/watch에는 연결하지 않았으며 현재 운영 모델·점수·신호는 그대로 유지한다.

검증 범위는 모델 계산의 시간 순서·재현성과 기준 민감도이며 고립 정답 정확도·당시 공개일 기준 실시간 이용 가능성을 검증하지 않는다.

<a id="analysis3"></a>

## Analysis3 소비 맥락

작업 기준 폴더: `pipelines/db1/Analysis3/`

작업 폴더: `pipelines/db1/Analysis3/`
공통 DB: 상위 `db1_pipeline`. Analysis3 CSV는 이 폴더의 `outputs`에 있습니다.

### 목적과 의미 연결

Analysis1은 지역의 활동·인구·가구·복지 구조를 설명하고, Analysis2는 동별 월간 통신·이동 변화를 탐지합니다. Analysis3은 그 지역·기간에 관측된 **가맹점 소비 활동**을 연결합니다. 개인 단위 자료를 연결하거나 고립·위험을 판정하는 모델은 아닙니다.

- **3A / 서울 상권분석:** 강남구 22개 동 × 분기 × 고객 연령 6개 × 소비영역 5개. 지역 소비 기반의 장기 변화 맥락.
- **3B / 신한카드:** 강남구 가맹점 × 월 × 고객 연령 6개 × 소비영역 5개. 구 전체 단기 소비 맥락.
- **Analysis1 연결:** 통합 DB에 저장된 해당 월의 지역유형과 적용 기간을 그대로 사용합니다. 소비영역을 특정 지역유형과 동일한 개념으로 치환하지 않습니다.
- **Analysis2 연결:** `a2_detection`에서 실제 동·월·신호종류를 가져옵니다. 노트북의 수기 입력 14건은 재사용하지 않습니다. 초기 연결 당시 신호는 삼성1동 2025-12 Mobility/New 1건이었습니다. 현재 신호는 실제 DB 조회로 확인합니다.

소비영역은 외식·카페, 여가·운동, 대면 생활서비스, 생활필수, 의료·건강입니다. 외식·여가는 이동·외부활동 해석의 보조 맥락, 생활서비스·필수·의료는 생활 활동 구성의 보조 맥락으로 활용할 수 있습니다. 이용건수 감소를 이동·통신 감소의 원인이라고 단정하지 않습니다. 의료 소비 변화도 건강 악화를 직접 의미하지 않습니다.

두 자료는 가맹점 위치 기준입니다. 강남구 결제 고객은 다른 지역에 거주할 수 있습니다. 카드의 `CLN_SGG_CD=서울`은 강남구 거주자를 뜻하지 않습니다. 동별 상권 소비도 해당 동 주민 소비의 대리값으로 확정하지 않습니다. 신한카드 구 단위 수치를 동별로 배분하거나 동별 실적으로 저장하지 않습니다.

### 기존 노트북에서 변경한 점

참고 파일: `C:\Users\user\Downloads\Analysis3A + Analysis3B 완료.ipynb`의 57개 셀을 검토했습니다. 그 코드를 자동 실행하거나 문서 속 지시를 실행하지 않았습니다.

- Colab 업로드·다운로드 및 수기 이벤트 대신 로컬 원본 자동 검색과 공통 DB 조회.
- 상권 8자리 코드와 DB1 7자리 코드의 명시적 crosswalk. `11680740`의 원본 명칭 `일원2동`은 원본에 보존하며 공통 명칭은 개포3동.
- 신한카드 60·70·80·90대는 **건수·금액부터 합산**해 상권의 60대 이상에 맞춤. 원래 연령은 `a3b_industry`에 보존.
- 분기/월 일수는 달력에서 계산. 업종 관측일수 부족도 별도로 보존.
- 3A 비교는 현재 분기를 포함하지 않는 과거 동일 분기 자료와 **공통 관측 업종**을 사용. 일평균 건수로 비교하며 최소 3개 과거 동일 분기가 필요.
- 3B는 정확히 직전 달과 비교. 월이 빠지면 마지막 관측월을 전월처럼 사용하지 않음. 영역과 전체 연령 소비 기준선 모두 각자의 공통 관측 업종으로 비교.
- 관측이 없는 소비영역은 NULL로 보존. 부분 관측 업종 수·정의된 업종 수·연령별 합/전체 건수 비율을 함께 저장.
- 과거 최소 이하 여부와 강남구 변화 백분위는 기술 통계로 보존. 노트북의 하위20% 이중 신호나 다영역 위험점수를 그대로 적용하지 않음.

소비영역 명칭은 같아도 두 원본의 업종 정의는 동일하지 않습니다. 예를 들어 상권에는 호프·간이주점/의료기기, 카드에는 목욕탕/종합병원이 포함됩니다. `mappings.py`와 `outputs/mappings/industry_mapping.csv`가 전체 포함·제외 업종을 공개합니다. 두 자료의 건수·금액을 합쳐 총량을 만들거나 서로의 증감률을 직접 빼지 않습니다. 카드 금액은 원본 단위를 그대로 보존하며 레이아웃에 확인되지 않은 배율을 적용하지 않았습니다.

### 기간과 과거 정보 사용

3A 초기 관측 History는 2022Q1–2025Q2이며 첫 비교는 2025Q3입니다. 2025Q3·Q4는 2022–2024년 동일 분기와 비교합니다. 이후 2026년 자료가 들어오면 그 시점 이전 동일 분기 관측을 추가한 확장 기준선을 사용합니다. 원본 History는 누적하고, 과거 비교에는 미래 분기를 포함하지 않습니다. 과거 결과는 미래 자료를 추가해도 변하지 않도록 테스트했습니다.

3B 현재 자료는 2025-07–12의 6개월뿐입니다. 7월은 전월 비교가 NULL이며, 장기 계절성 변화탐지 모델을 학습할 History가 부족합니다. 8–12월의 전월·전체 연령 대비 변화는 기술적 맥락 지표이며 Analysis2와 같은 통계적 이상 신호가 아닙니다.

**같은 분기 상권 자료를 해당 분기의 월에 연결한 결과는 회고적 결과입니다.** Q4 전체 소비를 10월에 이미 알았다고 가정하지 않습니다. `v_a123_monthly`·`v_a123_detail`은 `retrospective_same_quarter`를 명시합니다. 월별 금액으로 나누거나 보간하지 않습니다.

`v_a123_available_context`는 실제 공개일이 확인된 자료만 월말 시점까지 연결합니다. 현재 원본에서 공개일을 확인할 수 없어 기본값은 NULL이며, 이 view의 소비 맥락은 미연결입니다. 미래 운영에서 확인한 공개일을 **최초 적재 전에** 설정합니다:

```json
"available_from": {
  "market:2026Q1":"2026-05-20",
  "card:2026-01":"2026-02-15"
}
```

위 날짜는 설정 형식 예시이며 실제 공개일이 아닙니다. 공개일은 관측 기간 종료일보다 빠를 수 없습니다. 이미 저장된 공개일/기준선 정책 변경은 자동 덮어쓰기하지 않습니다. 별도 승인된 버전 변경이 필요합니다.

### 실행과 업데이트

현재 PC의 `analysis1` 환경을 사용합니다. Analysis3 폴더에서:

```powershell
.\run_analysis3.ps1 -Command scan
.\run_analysis3.ps1 -Command status
.\run_analysis3.ps1 -Command export
```

DB1 폴더에서 전체 1·2·3 업데이트:

```powershell
.\run_db1.ps1 -Command scan
.\run_db1.ps1 -Command analysis3
```

전체 `scan`은 Analysis1 → Analysis2 → Analysis3 순서입니다. 기존 `analysis1`, `analysis2` 명령도 성공 후 Analysis3을 실행해 통합 CSV를 갱신합니다. 세 분석 전체를 한 transaction으로 묶지는 않으며, 한 분석이 실패해도 이전에 성공한 다른 분석의 저장은 유지됩니다. 다음 scan으로 재시도할 수 있습니다.

신규 월 카드 CSV·신규 분기/연도 상권 CSV를 `config/analysis3_config.json`의 원본 폴더에 넣고 scan을 실행하면 됩니다. 연도·파일명 고정 없이 내용의 기간을 읽습니다. 최상위 폴더의 `.csv`를 검색하므로 파일은 설정된 폴더에 직접 두세요.

각 원본 파일은 해당 월/분기의 **완전 스냅샷**이어야 합니다. 여러 파일로 나눈 추가분을 자동 합산하지 않습니다. 겹친 동일 스냅샷 파일은 한 번만 저장하며 서로 다른 완전 스냅샷이면 충돌로 처리합니다.

- 카드: 전체 날짜와 공통 연령 6개가 있어야 월을 처리. 개별 업종의 관측일수 부족은 지표에 남김. 달력 완전성이 업종 누락까지 보증하는 것은 아닙니다.
- 상권: 공통 22개 동이 있어야 분기를 처리. 개별 업종 누락은 0으로 보충하지 않음.
- 미완료 기간은 대기 목록, 스키마·숫자·중복키·새 지역코드 오류는 실패로 보고.
- 처리된 기간은 원본 정규화 fingerprint/방법 버전/공개일 확인 후 동일하면 건너뜀. 수정된 기존 기간은 덮어쓰기 차단.
- 마지막 저장 기간 이전의 누락 자료를 뒤늦게 적재해 과거 기준선을 바꾸는 backfill은 자동 실행하지 않음. 명시적 이력/버전 변경이 필요.
- 선택된 새 기간의 원본 집계, 처리 기록, 파생 지표는 하나의 PostgreSQL 트랜잭션. 충돌/저장 실패면 신규 전체 배치 rollback.
- CSV는 DB commit 후 내보냄. 내보내기 실패 시 `export`로 재생성 가능.

자동 감시는 실행 중인 프로세스에 한해 작동합니다. 이번 작업에서 상시 프로세스나 예약작업을 등록하지 않았습니다.

```powershell
# DB1 전체 감시
.\run_db1.ps1 -Command watch -Interval 60
# Analysis3만 감시
.\run_analysis3.ps1 -Command watch -Interval 60
```

### 결과 파일과 DB

- `outputs/a3a_feature.csv`: 동·분기·연령·영역 관측값과 업종/연령 포착 범위.
- `outputs/a3a_comparison.csv`: 과거 동일 분기 공통업종 비교·백분위·분기/전년 대비.
- `outputs/a3b_feature.csv`: 구·월·연령·영역 일평균과 전월/전체 기준선 대비 변화.
- `outputs/a3b_total.csv`: 핵심영역에 국한하지 않는 모든 업종의 연령별 기준선.
- `../outputs/integrated/analysis2_quarter.csv`: DB의 실제 월별 행동신호를 분기로 집계. 관측월 수와 기대 3개월을 함께 표시.
- `../outputs/integrated/analysis123_monthly.csv`: 22개 동 × 6개월 132행. 지역유형·행동신호·소비 맥락을 요약.
- `../outputs/integrated/analysis123_detail.csv`: 연령 6개 × 영역 5개까지 확장한 상세. 반복된 행동신호를 새로운 독립 신호로 세지 않음.
- 신규 행동 월에 아직 소비 자료가 없어도 동·월·연령·영역 행을 유지하며 소비 지표만 NULL로 표시.
- `../outputs/integrated/signal_context_detail.csv`: 실제 행동신호가 있는 동·월의 소비 맥락 상세.
- `../outputs/integrated/analysis123_available_context.csv`: 공개일 검증을 거친 월말 시점 조회.

DB 원본 집계는 `a3a_industry`, `a3b_industry`, 파생 결과는 위 파일과 같은 테이블, 처리 provenance는 `a3_run`, 고정 전처리 정책은 `a3_policy`입니다. 기존 `db1_run`/Analysis1·2 테이블은 변경하지 않습니다. 카드 수기 행정동 배분은 하지 않습니다.

당시 수치/건수 검증 결과는 `docs/validation/analysis12_20261006.md`를 참조하세요.

### 정리 후 경로
소비 분석 CSV는 outputs, 동·업종 연결표는 outputs/mappings, 통합 CSV와 신호 연결 CSV는 상위 outputs/integrated에 저장합니다. 마지막 scan 기록은 logs/last_scan.json, 검증 기록은 docs에 있습니다. 공통 실행·설정은 상위 README.md를 참조하세요.


### 동·연령별 행동과 소비 연결 (2026-10-07)

연결 구현과 실행을 완료했다. 동·연령·월별 행동 근거에는 `v_a23_age_monthly`와 `v_a23_age_detail`을 사용한다. 분기 집계는 `v_a23_age_quarter`, 공표일 기준 조회는 `v_a23_age_available_context`다. 상세 해석과 업데이트 규칙은 `Analysis3/docs/AGE_BEHAVIOR_CONSUMPTION.md`를 참조한다. 소비는 보조 근거이며 탐지 신호나 고립 점수에 합산하지 않는다.

<a id="survey-context"></a>

## 관계망·외로움 조사자료

작업 기준 폴더: `pipelines/db1/Context/`

### 역할

서울서베이 2022~2025년 가구원 원자료를 강남구 및 서울 전체의 연령별로 집계한다. 기존 Analysis1 지역 유형, Analysis2 행동 변화, Analysis3 소비 변화에 사회적 지원망과 외로움의 관측 맥락을 추가한다. 새로운 Analysis4/5나 종합 위험점수를 만들지 않는다.

서울 청년 고립·은둔 조사는 2022년 정적 참고자료다. 조사연도와 공개일(2024-05-22)을 구분하고, 청년조사와 가구조사의 표본을 합치지 않는다. TABLE 파일은 DATA의 파생 집계이므로 추가 표본으로 저장하지 않는다.

### 저장·조회

| 이름 | 내용 |
|---|---|
| `ctx_survey_source` | 원본 해시, 연도, 공개일, 코드북, 변수 연결, 가중치·품질 설명 |
| `ctx_survey_metric` | 자치구/서울·연령·문항별 가중 통계와 분모·표본 수 |
| `ctx_evidence_guide` | 청년 조사 문항과 행동·소비·지원 해석 연결 |
| `v_survey_annual` | 조사연도별 지표 조회 |
| `v_survey_age_trend` | 정확히 직전 연도와의 기술적 차이 |
| `v_a123_age_survey_context` | 기존 행동·소비·독거노인 결과 + 같은 연도 또는 가장 가까운 이전 연도의 강남구 연령별 조사 맥락 |
| `v_a123_age_survey_available_context` | 알려진 공개일이 행동 월말 이전인 서울서베이만 연결 |

마지막 두 뷰는 기존 동·연령·월별 행 수를 유지한다. `survey_context_json` 안에 지표별 `value`, `unit`, `n_valid`, `n_event`, `effective_n`, `quality_status`, 해석 설명이 있다. 강남구 통계가 같은 연령의 22개 동에 공통 참고값으로 연결되며, `survey_geography_alignment=district_not_dong`를 반드시 함께 읽는다. 이를 동별 외로움 또는 고립률로 설명하지 않는다. 여러 동을 합산할 때 이 값을 반복 합산하지 않는다.

공개일이 확인되지 않은 서울서베이는 설정에서 NULL로 보존했다. 회고 뷰에서 2025년 값을 2025년 행동에 연결하는 것은 당시 이용 가능했음을 뜻하지 않는다. 공표일 기준 뷰에 근거가 없으면 NULL이다. 이 뷰도 행동·소비·독거노인 자체의 공표일을 모두 검증하는 완전한 실시간 판단 뷰는 아니다.

청년 조사는 별도 조회한다. 19~39세 및 5년 구간(19~24, 25~29, 30~34, 35~39)으로 보존하며, 19세가 들어간 구간을 DB1의 20s로 연결하지 않는다. 40대 이상에는 직접 적용하지 않는다.

### 전처리 정의

- 서울서베이는 가구원 `wtb1` 원가중치를 사용한다. 연령은 공개된 `DEW2` 20대·30대·40대·50대·60세 이상을 보존한다. 응답자의 출생연도로 만 나이를 임의 재계산하지 않는다.
- 서울 전체와 강남구를 원자료에서 각각 직접 집계한다. 서울 전체 연령통계와 강남구 전체통계를 곱해서 만들지 않는다.
- 일반 지원망 질문에 '없다'(2)고 답하면 세부 질문을 건너뛴다. 몸이 아플 때·금전 도움·정서적 대화 상대의 빈칸은 분기상 부재로 처리하고, 그 개수를 기록한다. 그 외 빈칸은 비응답으로 유지하고 문항별 분모에서 제외한다. 자녀·가족 돌봄 문항의 비해당은 고립 부재/존재로 해석하지 않으며 이번 공통 지표에서 제외한다.
- `no_support_parent`, `no_support_sick`, `no_support_money`, `no_support_emotion`은 상황별 도움받을 사람이 없는 비율이다. `no_support_all3`은 세 상황 모두 없는 비율이다.
- `loneliness_family_mean10`, `loneliness_outside_mean10`은 1~5점 응답을 `(응답-1)/4*10`으로 변환한 가중 평균이다. `_agree`는 응답 4 또는 5의 비율이다.
- `no_support3_and_lonely_outside`는 세 지원망 부재와 가족 외 관계 외로움 응답 4/5의 교집합이다. 본 프로젝트의 기술적 정의이며 서울시 공식 고립 진단 또는 고립률이 아니다.
- 2025년에 추가된 동반자 부족·혼자 남겨짐·사람들 사이 고립 문항은 별도 지표다. 기존 2개 외로움 문항과 합쳐 장기 추세를 만들지 않는다.
- 2024년에는 응답 표현이 변경돼 외로움 전년 차이에 `response_wording_changed`를 표시한다. 숫자 차이를 고립 악화/개선으로 확정하지 않는다.
- 비율은 0~1, 점수는 0~10이다. 비율 차이 0.01은 1%p이며 1% 증가율과 다르다.

### 표본과 불확실성

각 지표의 전체 표본, 유효 응답 수, 사건 응답 수, 고유 가구 수, 가중치 편차에 따른 유효 표본 수를 제공한다. 유효 응답 또는 가중 유효 표본이 30 미만이면 `small_sample`, 사건 또는 비사건 응답이 5 미만이면 `sparse_response_count`를 기록한다. 이는 서비스용 검토 표시이며 공식 통계의 공표 기준이나 정확도 보증이 아니다.

유효 표본 수는 `(가중치 합)^2/가중치 제곱합`이다. 가구 내 군집·층화 설계를 반영한 표준오차나 신뢰구간은 계산하지 않았다. 연도별 응답자가 같은 사람인 패널이라고 가정하지 않으며, 전년 차이를 통계적으로 유의한 개인 변화로 설명하지 않는다.

청년 가구조사는 `WT_ALL3` 가중치를 이용해 분류 비율을 계산한다. 가구원들이 동일 가구에 속할 수 있으므로 군집 문제를 표시한다. `WT_ALL2` 합과 코드북에 적힌 모집단 수가 달라 이를 인구수로 확대해 제시하지 않는다. 청년조사에는 확인된 가중치가 없어 응답자 구성비를 제공하며, 강남구 청년 인구의 고립 유병률로 설명하지 않는다.

### AI agent 활용

예시: '특정 동 40대의 소통 감소가 관측됐다. 같은 시기 강남구 40대 조사에서 정서적 지원망 부족 및 외로움은 어떤 수준이었는가?'를 조회한다. 조사 근거가 있어도 동일 주민의 고립이 확인됐다고 말하지 않는다. 이동·통신·소비는 서로 다른 모집단일 수 있다.

전 연령 공통 행동 탐지는 유지한다. 독거노인 자료는 65세 이상 맥락, 청년 조사는 19~39세 참고, 서울서베이는 전 연령 공통 조사 맥락이다. 자료가 더 많은 연령대의 위험점수를 올리거나 자료가 없는 연령의 위험을 0으로 만들지 않는다.

```sql
SELECT year,age_band,metric,value,n_valid,effective_n,quality_status
FROM v_survey_annual
WHERE survey='seoul_survey' AND district='gangnam'
AND age_band IN ('40s','50s')
ORDER BY year,age_band,metric;

SELECT adm_cd,date,age_band,survey_year,survey_geography_alignment,survey_context_json
FROM v_a123_age_survey_context
WHERE date='2025-12-01' AND age_band='40s';

SELECT * FROM ctx_evidence_guide WHERE topic='consumption';
```

### 업데이트·정정

DB1 루트에서 `run_db1.ps1 -Command survey-context` 또는 `python run_db1.py survey-context`를 실행한다. `scan`/`watch`도 등록된 조사 원본을 확인하고, `export`는 저장된 결과를 다시 내보낸다. 같은 해시의 원본은 재집계하지 않는다.

새 연도 파일을 확보하면 `config/db1_config.json`의 `survey_context.seoul_years`에 연도·경로·변수 연결·확인된 공개일을 등록한다. 문항 번호를 전년도에서 자동 복사하지 않는다. 코드북의 지표 의미·응답 값·연령구간·가중치를 확인한 후 실행한다. 파일만 폴더에 넣는 방식의 자동 감지는 이번 조사자료에 제공하지 않는다. 원본 수집과 설정 등록은 운영자가 연결해야 한다.

원본은 `Context/data/raw/<sha256>/`에 바이트 그대로 보관한다. 공개일 미확인(NULL)을 확인된 날짜로 채우는 것은 설정 수정 후 실행하면 반영된다. 이미 확인된 공개일의 변경·삭제, 원본·연도·변수 연결의 역사적 변경은 자동 덮어쓰기를 차단하므로 명시적 버전 정정이 필요하다. 입력 검증 실패 시 새로운 조사 지표를 저장하지 않는다. `scan` 전체는 하나의 transaction이 아니므로 다른 분석 단계 실패 시 이미 성공한 단계는 남을 수 있다.

내보내기는 `outputs/integrated/v_survey_annual.csv`, `v_survey_age_trend.csv`, `ctx_evidence_guide.csv`, `v_a123_age_survey_context.csv`, `v_a123_age_survey_available_context.csv`다. 검증 요약은 `survey_context_validation.json`이다.

전처리 핵심 회귀 검사는 `python Context/tests/check_survey.py`로 실행한다.


### 2026-10-07 근거 보완 반영

<a id="figures"></a>

## 보존 그래프

작업 기준 폴더: `pipelines/db1/outputs/figures/`

기존 2025H2 분석 결과의 PNG·SVG 그래프 6개를 보존했습니다. 대시보드 관련 파일은 정리 전 백업에 있습니다. 이 이미지들은 DB 갱신 시 자동으로 다시 그려지는 파일이 아닙니다.

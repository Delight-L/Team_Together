# DB1 실행 및 폴더 안내

Analysis1은 반기별 지역유형, Analysis2는 월별 변화 탐지, Analysis3은 분기·월 소비 맥락을 처리합니다. 원본 자료는 프로젝트 바깥의 기존 공모전·서울시 데이터 폴더에서 읽습니다.

## 실행
DB1 폴더의 PowerShell에서 실행합니다.
```powershell
.\run_db1.ps1 -Command status
.\run_db1.ps1 -Command scan
.\run_db1.ps1 -Command export
.\run_tests.ps1
```
`scan`은 새 자료를 전처리하고 DB에 통합한 후 CSV를 갱신합니다. `export`는 저장된 DB 결과를 다시 내보냅니다. `watch`는 실행 중 주기적으로 scan을 반복합니다. Analysis1 특정 반기는 `-Command analysis1 -Period 2026H1`, Analysis2 특정 월은 `-Command analysis2 -Month 2026-01`로 실행합니다. 해당 기간 원본과 공공자료가 준비되어야 합니다.

## 파일 위치
- `config/db1_config.json`: 공통 DB, 원본 및 Analysis1·2 설정.
- `outputs/db1.sqlite`: 세 분석이 공유하는 운영 DB. 유일한 운영 기준입니다.
- `outputs/integrated/`: Analysis1·2 통합 CSV와 Analysis1·2·3 연결 CSV.
- `outputs/figures/`: 기존 분석 그래프 PNG·SVG. CSV 갱신과 별도로 보존된 시각화입니다.
- `Analysis1/data/reference/`: 고정 기준 입력; `models/2025H2/`: 기준 모델.
- `Analysis1/data/processed/<반기>/`: 전처리 입력; `outputs/baseline/`, `outputs/periods/<반기>/`: 분석 결과.
- `Analysis2/data/reference/`: 초기 이력·기준 비교 자료; `outputs/history.csv`, `detection.csv`, `evidence.csv`: DB 결과 내보내기; `outputs/monthly/<월>/`: 월별 특징·탐지 결과.
- `Analysis2/tests/fixtures/`: 테스트에 필요한 작은 원본 예제. 운영 원본 폴더와 구분합니다.
- `Analysis3/config/analysis3_config.json`: 소비 자료·내보내기 설정; `db/schema.sql`: 스키마; `outputs/`: 소비 전처리·분석 결과; `outputs/mappings/`: 동·업종 연결표; `logs/`: 마지막 실행 기록.
- `tests/`, 각 분석의 `tests/`: 검증; `tools/`: 초기 설정·원본 검증 보조 도구; `docs/`: 실행 안내·과거 검증·정리 기록.

이전 중복 DB, 중복 CSV, 구식 일괄 실행기, 대시보드와 보고서는 정리 전 전체 백업에 보관합니다. 과거 검증 문서의 경로는 당시 기록이며 현재 실행 안내는 이 문서입니다. 기준 모델과 운영 DB의 내용은 폴더 정리 과정에서 변경하지 않습니다.


Analysis2의 동·연령대별 전처리 이력과 업데이트 경로를 추가했습니다. `run_db1.ps1 -Command analysis2-age`로 재구축할 수 있으며 일반 `scan`에도 연결됩니다. [상세 안내](Analysis2/AGE_PREPROCESSING.md)를 확인하세요. 연령별 변화 탐지를 구현했습니다. `run_db1.ps1 -Command analysis2-age-detect`로 실행하며 일반 Analysis2 scan에도 연결됩니다. [탐지 안내](Analysis2/AGE_DETECTION.md)를 확인하세요.


## 동·연령별 행동과 소비 연결 (2026-10-07)

연결 구현과 실행을 완료했다. 동·연령별 행동과 소비의 같은 관측 기간 연결은 `v_a123_age_source_context`를 우선 사용한다. 기존 `v_a23_age_monthly`와 `v_a23_age_detail`은 같은 라벨월의 후속 기간 소비 맥락이다. 분기 집계는 `v_a23_age_quarter`, 공표일 기준 조회는 `v_a23_age_available_context`다. 상세 해석과 업데이트 규칙은 `Analysis3/docs/AGE_BEHAVIOR_CONSUMPTION.md`를 참조한다. 소비는 보조 근거이며 탐지 신호나 고립 점수에 합산하지 않는다.


## 동별 독거노인 통계 연결 (2026-10-07)

동별 독거노인 관측 통계 연결을 완료했다. `v_a1_elder_annual`은 연간 지표, `v_a1_elder_context`는 반기 지역 유형 연결, `v_a123_age_elder_context`는 동·연령별 행동·소비와의 사후 연결이다. 독거노인은 65세 이상이므로 60plus에만 부분 연령 일치로 연결한다. 다른 연령대에는 직접 적용하지 않는다. 공표일 기준 조회는 `v_a123_age_elder_available_context`다. 독거 여부는 고립 판정이 아니며 기존 모형과 점수는 유지한다. 갱신 명령은 `run_db1.ps1 -Command analysis1-elder`와 일반 `scan`이고, 해석·DB 질의·정정 처리 규칙은 `Analysis1/ELDERLY_CONTEXT.md`에 있다.


## 관계망·외로움 조사자료

강남구와 서울 전체의 연령별 서울서베이(2022~2025) 및 2022년 청년 고립 참고자료를 추가했다. `Context/README.md`에서 지표 정의와 조회 방법을 확인한다. `run_db1.ps1 -Command survey-context`로 갱신하며 `scan`/`watch`/`export`에도 연결된다. 연도별 원본과 코드 연결의 등록이 필요하다. 기존 탐지 신호와 점수는 보존한다. 통합 조회는 `v_a123_age_survey_context`이며 조사값은 동별 통계가 아닌 강남구 연령별 공통 맥락이다.


소통 신호 이후 수준·회복 추적은 `analysis2-activity`로 실행하며 월 처리·scan/watch에도 연결됩니다. [Analysis2/ACTIVITY_LEVEL.md](Analysis2/ACTIVITY_LEVEL.md)와 [현재 적용 결과](docs/ACTIVITY_LEVEL_RESULT_20261007.md)를 참조하세요.


## AI agent 담당자 인수

먼저 [조회 실행 안내](docs/AI_AGENT_QUICKSTART.md), [실제 3건 설명 예시](docs/AI_AGENT_EXPLANATION_EXAMPLES.md), [인수 검증 결과](docs/DB1_HANDOFF_ACCEPTANCE_20261007.md)를 읽으세요. `tools/read_agent_context.py --signals-only`로 읽기 전용 통합 근거를 조회합니다. 집계 기준월과 실제 직전 3개월 관측을 구분하고 SNS 시계열 증감률을 계산하지 않습니다. 검증용 모의 DB와 원본 파일은 운영 DB1에 포함하지 않습니다.


## 2026-10-07 근거 보완 반영

청년 조사 세부 통계, 관측 기간 기상, 지연 소비 근거 보충, 공개일 기준 조회를 추가했습니다. [근거 사용 설명](Context/EVIDENCE_CONTEXT.md)과 [검증 결과](docs/DB1_IMPROVEMENTS_RESULT_20261007.md)를 함께 전달하세요. 기존 탐지 건수는 소통 10·이동 0·복합 0으로 유지됩니다.


## GitHub 전달 전 정리

[폴더 구성과 전달 안내](docs/FILE_ORGANIZATION.md)를 참조하세요. 최신 인수인계 본문은 docs/AI_AGENT_HANDOFF.md입니다. 과거 변경 백업은 DB1_backups로 이동했으며 운영 DB·모델·기준 입력은 유지했습니다. 근거별 상태와 청년 세부 근거를 포함한 통합 조회는 tools/read_agent_context.py를 사용하세요.

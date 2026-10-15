# DB1 서비스 통합

`delightL`의 `671e86f` 전달본을 메인 서비스에 연결합니다. 두 브랜치에 공통 조상이 없어
메인 기반 `codex/db1-integration`에 `pipelines/db1/`만 가져왔습니다. 기존 챗봇·업무 기록 변경은 별도 체크아웃에 보존합니다.

## 동작

- Analysis1 공식 모델은 `analysis1_2025H2_elder_v2`입니다. 장애인 비율 대신 연간 독거노인 수 / 같은 해 Q4의 65세 이상 등록인구를 사용합니다.
- 관리자 구조자료 5종 검사와 기존 전처리 실행기는 동일한 신규 전처리·고정 모델을 사용합니다. 지역 유형, 원자료 비율, 기준기간, 모델 버전이 서비스 DB에 함께 저장됩니다.
- 신규 Analysis2의 `*_residual`, `*_rz`와 기존 v11의 긴 열 이름을 모두 받습니다. 월 키 중복과 묶음 신호 불일치를 거절합니다.
- 월별 업로드를 반영하면 `db1.analysis2_detections`에 새 버전을 추가합니다. 이전 월과 이전 실행을 보존합니다. 구조자료는 `db1.analysis1_region_typology`에 저장합니다.
- 자료 반영, 원본 행 보관(`service_ingestion_rows`), 관리자 업로드 이력은 한 트랜잭션입니다. 실패하면 함께 롤백합니다. 동일 기간에 정정 업로드하면 새 실행 버전으로 보관합니다.
- CSV 조회도 신규 전달본을 사용합니다. 기존 참조 결과 770개 동·월을 유지하면서 2025-07~12의 순차 분석 132행을 우선 적용합니다. 결과 범위는 2023-02~2025-12입니다. 2022년 등 탐지 이력이 없는 관측을 새 탐지 결과로 만들지 않습니다.
- Analysis2 과거 판정은 재계산하지 않습니다. 신규 Analysis1 구조자료와 과거 판정의 모델 출처를 구분합니다. Analysis2의 구 장애인 참조 CSV는 과거 재현용으로 보존합니다.
- 독거노인 지표는 사후 연간 배경자료입니다. 60세 이상 집단과 65세 이상 통계의 범위가 다르며, 개인 고립 또는 당시 공개된 실시간 근거로 표현하지 않습니다.

## 실행

기존 앱 의존성을 설치합니다. 모델 파일의 scikit-learn 버전은 1.7.2로 고정했습니다.
전체 원천자료 갱신은 `pipelines/db1/requirements.txt`의 공간·Parquet 의존성도 필요합니다.

```powershell
python -m pip install -r requirements.txt
python main.py --analysis --no-download
python scripts/import_db1.py
```

위 명령은 읽기·검사만 수행합니다. 서비스 DB 연결 정보는 저장소 루트 `.env`에서 읽습니다.
쓰기 가능한 서비스 DB 계정으로 전달본을 반영할 때:

```powershell
python scripts/import_db1.py --publish
```

Analysis1·2 결과를 같은 트랜잭션으로 추가하고 `service_imports`에 이력을 기록합니다.
`WELFIND_DATA_SOURCE=auto` 또는 `db`인 서버에서 새 결과를 읽습니다.
외부 실행기로 반영한 경우 기존 서버의 최신 실행 캐시 갱신은 최대 60초 걸립니다.
`WELFIND_DATA_SOURCE=csv`는 로컬 전달본을 읽는 개발 설정입니다.

운영 SQLite에 업데이트된 결과를 읽어 반영할 때:

```powershell
python scripts/import_db1.py --sqlite "pipelines/db1/outputs/db1.sqlite"
python scripts/import_db1.py --sqlite "pipelines/db1/outputs/db1.sqlite" --publish
```

`pipelines/db1/outputs/db1.sqlite`는 약 380MB의 Git LFS 자산입니다. 실파일이 없는 체크아웃에서는
`git lfs pull`로 받아야 합니다. 포인터를 SQLite로 열거나 덮어쓰는 실행은 거절합니다.
CSV 전달본 검사·반영은 대용량 SQLite 다운로드 없이도 가능합니다.

신규 반기·월 원천자료 갱신은 독립된 기존 DB1 실행기를 사용합니다.

```powershell
$env:TEAM_TOGETHER_DATA_ROOT = "D:/Team_Together-data"
python pipelines/db1/tools/configure_db1.py --source-root $env:TEAM_TOGETHER_DATA_ROOT --output pipelines/db1/config/db1_config.local.json
python main.py --analysis --command analysis1 --period 2026H1 --config pipelines/db1/config/db1_config.local.json --db pipelines/db1/outputs/runtime/db1.sqlite
```

별도 새 운영 파일은 필요한 원천자료를 갖춘 상태에서 `initialize`로 먼저 구성해야 합니다.
`--publish`를 추가하면 실행 성공 후 해당 SQLite 결과를 서비스 DB로 연결합니다.
원천자료가 없는 새 연도는 합성 데이터나 임의 분모로 대체하지 않습니다.

## 검증 범위

서비스 DB의 기존 두 테이블 열·타입·기본키는 읽기 전용으로 확인했습니다.
새 결과 변환, 22개 동의 기존 군집 배정 유지, Q4 분모, 이전 월 보존, 트랜잭션 롤백,
관리자 반영 후 조회는 로컬 테스트로 확인합니다. 운영 DB에 실제 반영하지 않았습니다.
원본 SQLite와 외부 원천자료가 필요한 DB1 배포 회귀검사는 실파일을 받은 환경에서 별도로 실행합니다.

2026-10-13 검증 결과:

- 웹 API·DB1 통합 회귀: 24개 통과
- Analysis1 독거노인·반기·공공 전처리: 23개 통과
- Analysis2 활동 수준·연령 탐지·순차 분석·업데이트 검사: 42개 통과
- Context 근거·관측 시점·날씨 검사: 41개 통과
- 프런트엔드 회귀: 5개 통과, Vite 빌드 성공
- 전달본 dry run: 22개 동, 770개 동·월, `published=false`
- 공용 PostgreSQL 스키마 읽기 검증 완료; 운영 DB 쓰기는 수행하지 않음

## 서비스 반영 확인 (2026-10-13)

실제 서비스 PostgreSQL에 전달본을 추가 반영했습니다. 실행 ID는 `9162408e-c58e-4823-8e18-76969eb18838`입니다. 22개 동의 elder v2 지역 배경과 770개 동·월 분석을 같은 트랜잭션에 저장했고 이전 실행은 보존했습니다. 서비스 재조회에서 새 실행과 22개 동의 모델 버전을 확인했습니다. 연간 기준은 2025년, 분모는 2025Q4의 65세 이상 등록인구입니다.

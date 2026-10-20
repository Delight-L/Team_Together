# 데이터 운영 안내

분석·전처리·서비스의 DB 저장소는 PostgreSQL입니다. `.env`의 `DB_HOST`, `DB_PORT`, `DB_NAME`,
`DB_USER`, `DB_PASSWORD`를 공유하며, 작업 영역은 `DB1_PIPELINE_SCHEMA` 또는 `--db`의 스키마 이름으로 구분합니다.
`--db`는 파일 경로가 아닙니다. 원천 CSV·XLSX와 모델 파일은 기존 위치에서 계속 읽습니다.

## 스키마 경계

| 스키마 | 역할 |
|---|---|
| `db1_pipeline` | 분석·전처리 작업 영역 |
| `db1_regional_archive` | 기존 지역 분석 작업 자료와 원문 보존 |
| `db1_regional_archive.source_archive` | 제거한 과거 실행기·평가 기록·스키마 정의 원문과 SHA-256 보존 |
| `db1` | 기존 서비스 분석 자료 및 버전별 게시 결과 |
| `db1_v16` | 게시된 지역 분석 run을 읽는 뷰 |
| `db2`, `work` | 복지자료와 업무·보고서·관리자 설정 |

작업 스키마 이름은 영문 소문자·숫자·밑줄만 허용하며 기존 서비스 스키마를 작업 대상으로 지정할 수 없습니다.
분석을 실행한다고 서비스의 활성 분석 버전이 자동으로 바뀌지는 않습니다.

## 상태 조회와 전달본 검사

프로젝트 루트에서 실행합니다.

```powershell
python pipelines/db1/run_db1.py status --db db1_pipeline
python pipelines/db1/Analysis3/run_analysis3.py status --db db1_pipeline
python main.py --analysis --no-download
python scripts/import_db1.py --workspace db1_pipeline
```

`scripts/import_db1.py`는 기존 모델·강남구 22개 동·독거노인 비율 등 전달본 검증을 계속 적용합니다.
잘못된 모델 버전이나 자료가 누락된 작업 스키마를 승인된 서비스 자료로 간주하지 않습니다.

새 작업 영역을 초기화하려면 `run_db1.py initialize --db <전용스키마>`를 사용합니다.
원천자료 준비·모델 검증·월별 순차 실행·중복 입력 차단 기준은 유지됩니다.

## 트랜잭션·조회

- 연결은 `pipelines/db1/database.py`에서 관리합니다. 정상 종료 시 commit, 예외 시 rollback 후 연결을 닫습니다.
- 읽기 전용 연결은 repeatable-read 트랜잭션을 사용합니다.
- 작업 조정기는 PostgreSQL advisory lock을 사용해 동일 스키마의 동시 실행을 막습니다.
- 컬럼·테이블 확인은 `information_schema`, JSON·날짜·집계는 PostgreSQL 함수를 사용합니다.
- 부동소수 계산 보존을 위해 분석 실수 컬럼은 `DOUBLE PRECISION`입니다.
- DataFrame은 PostgreSQL 커서와 컬럼으로 구성하며, 파일 DB용 pandas 경로를 사용하지 않습니다.

## 지역 분석 엔진 게시

지역 분석 서비스 버전은 `backend/agents/regional_analysis/data_pipeline/publish_postgres.py`의
`publish(workspace_schema, engine)`로 게시합니다. 작업 스키마를 읽기 전용으로 고정하고 내용 해시를 계산한 뒤
버전별 자료와 활성 포인터를 하나의 트랜잭션으로 저장합니다. 이전 버전 활성화는 `activate(engine, run_id)`입니다.
계산 작업기의 게시 연결은 `data_pipeline/publication.py`에 있습니다.

게시 테이블이 없는 환경의 대시보드 호환 조회(DB1 서비스 테이블 + 전달 CSV)는 유지합니다.
게시·활성화는 서비스의 활성 run을 바꾸는 별도 쓰기 작업입니다. 아래 DB1 서비스 전달본 반영과 구분합니다.

## 원천자료 갱신

`python main.py --analysis --no-download`는 기본 `service-preview` 전달본 검사입니다.
새 원자료를 재계산하는 명령이 아닙니다. 분석을 갱신하려면 원천 CSV·XLSX와 모델,
필요한 `pipelines/db1/requirements.txt` 의존성을 준비하고 전용 작업 스키마를 지정합니다.
아래 `initialize`와 `analysis1`은 작업 스키마·산출물을 변경합니다.

```powershell
$env:TEAM_TOGETHER_DATA_ROOT = "D:/Team_Together-data"
python pipelines/db1/tools/configure_db1.py --source-root $env:TEAM_TOGETHER_DATA_ROOT --output pipelines/db1/config/db1_config.local.json
python pipelines/db1/run_db1.py initialize --config pipelines/db1/config/db1_config.local.json --db db1_pipeline
python main.py --analysis --command analysis1 --period 2026H1 --config pipelines/db1/config/db1_config.local.json --db db1_pipeline
```

기존 작업 영역을 사용하면 해당 스키마·원자료 상태를 먼저 확인합니다.
새 연도의 원천자료를 합성 데이터나 임의 분모로 대체하지 않습니다.
Analysis1은 반기 지역 유형, Analysis2는 월 변화 탐지, Analysis3은 소비 맥락을 계산합니다.
분석별 명령·모델·입력 조건은 [DB1 상세 안내](../pipelines/db1/README.md)를 따릅니다.

## DB1 서비스 전달본 반영

먼저 `python scripts/import_db1.py --workspace db1_pipeline`으로 검사합니다.
`--workspace`를 생략하면 저장소의 전달 CSV를 읽습니다. `--publish`를 붙이지 않으면 서비스 DB에 쓰지 않습니다.
검사 후 아래 명령으로 Analysis1·2 결과를 같은 트랜잭션에 추가하고 `service_imports`에 실행 이력을 기록합니다.

```powershell
python scripts/import_db1.py --workspace db1_pipeline --publish
```

- Analysis1 공식 모델은 `analysis1_2025H2_elder_v2`이며 강남구 22개 동과 독거노인 비율을 검증합니다.
- 독거노인 지표는 연간 독거노인 수 / 같은 해 Q4의 65세 이상 등록인구입니다. 사후 연간 배경자료이며 개인 고립 판정에 쓰지 않습니다.
- 전달본 변환은 신규 Analysis2 열과 기존 v11 열을 받으며, 월 키 중복과 묶음 신호 불일치를 거절합니다.
- 월 결과는 `db1.analysis2_detections`, 지역 유형은 `db1.analysis1_region_typology`에 저장합니다.
- 새 실행과 원본 행·업로드 이력을 함께 저장하고 실패하면 롤백합니다. 이전 월·실행은 보존합니다.
- `WELFIND_DATA_SOURCE=auto`는 DB 우선·실패 시 CSV, `db`는 DB만, `csv`는 로컬 전달본을 사용합니다.
- 외부 도구로 반영한 실행은 서버의 최신 실행 확인 주기(60초) 이후 조회될 수 있습니다.

이 반영은 동·월 서비스 테이블을 갱신하는 경로입니다. 지역 분석 엔진의 버전별 게시·활성화는 위 절을 따릅니다.
분석 실행기에 `--publish`를 붙이면 성공 후 서비스 전달본 반영까지 수행하므로 검사 실행과 구분합니다.

## 보존 기록 복원

```powershell
python scripts/read_source_archive.py --list
python scripts/read_source_archive.py --path "<목록의 경로>" --output "<새 출력 파일>"
```

원문 해시를 확인한 뒤 새 파일로만 복원하며 기존 파일을 덮어쓰지 않습니다.
과거 평가 결과는 현재 PostgreSQL 서비스의 정확도·성능 수치가 아닙니다.

이관 당시 테이블·행 수와 검증 수치는 [PostgreSQL 이관 기록](history/postgresql-migration-2026-10-19.md)에 보존합니다.
DB2 수집은 [수집 운영 안내](DB2_지자체복지_정기수집.md), DB 서버 구성은 [클라우드 DB 안내](오라클_클라우드_DB_구축.md)를 따릅니다.

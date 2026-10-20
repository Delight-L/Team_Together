# PostgreSQL 분석·서비스 저장소

분석·전처리·서비스의 DB 저장소는 PostgreSQL입니다. `.env`의 `DB_HOST`, `DB_PORT`, `DB_NAME`,
`DB_USER`, `DB_PASSWORD`를 공유하며, 작업 영역은 `DB1_PIPELINE_SCHEMA` 또는 `--db`의 스키마 이름으로 구분합니다.
`--db`는 파일 경로가 아닙니다. 원천 CSV·XLSX와 모델 파일은 기존 위치에서 계속 읽습니다.

## 스키마 경계

| 스키마 | 역할 |
|---|---|
| `db1_pipeline` | 분석·전처리 작업 영역. 원본 61개 테이블·120,414행·27개 뷰를 이관 |
| `db1_regional_archive` | 기존 지역 분석 작업 자료 보존. 원본 46개 테이블·44,665행·11개 뷰를 별도로 이관 |
| `db1_regional_archive.source_archive` | 제거한 과거 실행기·평가 기록·스키마 정의 원문과 SHA-256 보존 |
| `db1` | 기존 서비스 분석 자료 및 버전별 게시 결과 |
| `db1_v16` | 게시된 지역 분석 run을 읽는 뷰 |
| `db2`, `work` | 복지자료와 업무·보고서·설정. 이번 이관에서 기존 자료를 변경하지 않음 |

작업 스키마 이름은 영문 소문자·숫자·밑줄만 허용하며 기존 서비스 스키마를 작업 대상으로 지정할 수 없습니다.
분석을 실행한다고 서비스의 활성 분석 버전이 자동으로 바뀌지는 않습니다.

## 실행

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

## 게시

지역 분석 서비스 버전은 `backend/agents/regional_analysis/data_pipeline/publish_postgres.py`의
`publish(workspace_schema, engine)`로 게시합니다. 작업 스키마를 읽기 전용으로 고정하고 내용 해시를 계산한 뒤
버전별 자료와 활성 포인터를 하나의 트랜잭션으로 저장합니다. 이전 버전 활성화는 `activate(engine, run_id)`입니다.
계산 작업기의 게시 연결은 `data_pipeline/publication.py`에 있습니다.

게시 테이블이 없는 환경의 대시보드 호환 조회(DB1 서비스 테이블 + 전달 CSV)는 유지합니다.
게시·활성화는 별도 작업이며 이번 이관으로 기존 서비스의 활성 버전을 교체하지 않았습니다.

## 보존 기록 복원

```powershell
python scripts/read_source_archive.py --list
python scripts/read_source_archive.py --path "<목록의 경로>" --output "<새 출력 파일>"
```

원문 해시를 확인한 뒤 새 파일로만 복원하며 기존 파일을 덮어쓰지 않습니다.
과거 평가 결과는 현재 PostgreSQL 서비스의 정확도·성능 수치가 아닙니다.

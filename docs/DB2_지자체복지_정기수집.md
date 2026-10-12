# DB2 지자체복지서비스 정기 수집

2026-10-07 구현. 기존 PostgreSQL 연결(`db/connection.py`)을 사용합니다.
과거 DB2 문서의 `db2_storage.py`와 기존 수집 스키마 파일은 현재 체크아웃에 없어,
기존 테이블을 바꾸지 않는 전용 테이블을 추가했습니다. 현재 실행 방법은 이 문서를 기준으로 합니다.

## API와 저장

- [공식 서비스](https://www.data.go.kr/data/15108347/openapi.do): 목록 `LcgvWelfarelist`, 상세 `LcgvWelfaredetailed`.
- 엔드포인트: `https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations`.
- 공식 Swagger 사본: `docs/db2_api_spec.json` (2026-10-07 확인).
- `db2.local_welfare_services`: 서비스 ID별 목록·상세 최신 정보, 대상·기준·지원내용·신청방법·사업 시행일.
- `db2.welfare_api_snapshots`: 성공적으로 저장한 목록/상세의 XML 원문과 수집 시점. 문의처·홈페이지·근거법령·서식 등 반복 필드도 상세 JSON에 보존합니다.
- `db2.welfare_collection_runs`: 실행 범위, 결과, 목록·상세·오류·요청 건수.
- `db2.welfare_api_daily_usage`: 한국 날짜별 누적 요청 건수. 실패 요청과 재시도도 포함합니다.

사업 시행일은 프로그램 모집일과 다릅니다. 최종 수정일을 시행일로 쓰지 않습니다.
응답의 제공 지역을 거주 자격으로 판단하지 않습니다. 목록에서 사라진 서비스는 자동 삭제하거나 종료 처리하지 않습니다.
기존 `db2.welfare_services` 또는 화면에 자동 병합하지 않습니다. 아래 신규 테이블에서 조회합니다.

## 기본 수집 정책

매일 전국 목록을 100건씩 페이지 조회한 다음 상세를 수집합니다.
변경·미수집 항목을 우선하고, 상세 확인이 7일 이상 지난 항목을 다시 확인합니다.
각 그룹에서는 마지막 상세 시도 시각이 오래된 순서로 처리하여 실패 항목 하나가 뒤의 항목을 막지 않게 합니다.
조회수만 바뀐 경우 상세 갱신 대상으로 만들지 않습니다.

기본 하루 예산은 900회입니다. 수동 실행·예약 실행이 같은 DB의 사용량을 공유합니다.
인증키를 다른 프로그램에서 사용한 횟수는 알 수 없으므로 공공데이터포털의 전체 사용량과 별도로 관리해야 합니다.
예산에 도달하면 `budget_exhausted`로 정상 종료하고 저장분을 유지합니다.
상세는 다음 날 대기 항목부터 이어집니다. 목록은 실행마다 1페이지부터 다시 확인합니다.
전국 약 4,819건 기준 초기 상세 수집은 여러 날이 필요하며, 변동/실패/다른 키 사용량에 따라 더 걸릴 수 있습니다.

XML 결과 코드와 HTTP 상태를 모두 확인합니다. 일시적인 연결/서버/초당한도 오류는 최대 두 번 재시도합니다.
인증·일일한도 오류는 즉시 중단합니다. 개별 상세 오류는 기존 상세 값을 유지하고 다음 항목을 처리합니다.
DB 세션 잠금으로 동일 DB에 대한 중복 수집을 막습니다.
`completed`는 이번 실행이 처리한 범위의 완료입니다. 상세 대기 항목이 0개라는 뜻은 아닙니다.
`--max-pages`로 제한한 검증 실행도 제한 범위의 결과로 기록됩니다.

## 설정과 수동 실행

`.env`에 기존 DB 접속 설정과 `DB2_WELFARE_API_KEY`를 넣습니다.
전용 키가 없으면 기존 `DATA_API_KEY`를 사용합니다. 15108347 활용신청 승인이 필요합니다.
기존 시설 API의 `DATA_API_ENDPOINT` 설정과 독립적으로 동작합니다.

```powershell
.\.venv\Scripts\python.exe -m db.collect_welfare init
.\.venv\Scripts\python.exe -m db.collect_welfare collect

# 소량 검증: 목록 한 페이지, 상세 최대 2건
.\.venv\Scripts\python.exe -m db.collect_welfare collect --max-pages 1 --rows 2 --max-details 2

# 특정 지역
.\.venv\Scripts\python.exe -m db.collect_welfare collect --province 서울특별시 --district 강남구
```

예약 수집에도 지역을 적용하려면 `.env`의 `DB2_WELFARE_PROVINCE`, `DB2_WELFARE_DISTRICT`를 설정합니다.
둘 다 비우면 전국입니다. 호출 예산은 `DB2_WELFARE_DAILY_BUDGET`로 조정합니다.
예산을 올리기 전에 계정의 실제 승인 한도를 확인하세요.

## Windows 예약 작업

`TeamTogether-DB2-Welfare`: 한국 시간 매일 03:00, 현재 사용자 로그인 상태에서 실행합니다.
PC가 켜져 있고 PostgreSQL/API에 연결할 수 있어야 합니다.
놓친 실행은 실행 가능한 시점에 시작하며, 동시 실행은 무시하고 최대 2시간 실행합니다.
절전 해제나 로그아웃 중 실행은 설정하지 않았습니다.
프로젝트 폴더와 `.venv` 위치를 옮기면 작업을 다시 등록해야 합니다.
실행 로그: `runtime/db2_logs/<날짜_시간_실행ID>.log` (인증키는 출력하지 않습니다).

```powershell
# 새 환경에 등록 (이미 같은 이름의 작업이 있으면 덮어쓰지 않고 중단)
.\scripts\install_db2_welfare_task.ps1

Get-ScheduledTask -TaskName TeamTogether-DB2-Welfare
Get-ScheduledTaskInfo -TaskName TeamTogether-DB2-Welfare
Start-ScheduledTask -TaskName TeamTogether-DB2-Welfare

# 시간 변경
Set-ScheduledTask -TaskName TeamTogether-DB2-Welfare -Trigger (New-ScheduledTaskTrigger -Daily -At '04:00')
# 중지 또는 제거
Disable-ScheduledTask -TaskName TeamTogether-DB2-Welfare
Unregister-ScheduledTask -TaskName TeamTogether-DB2-Welfare -Confirm:$false
```

## 조회와 검증

웹의 관련 사업 조회와 챗봇의 사업 매칭은 `db2.local_welfare_services`를 직접 조회합니다.
선택 시·군·구 및 같은 시·도의 시·군·구 미지정 자료(NULL, 빈 문자열, `-`)를 검토 후보로 표시합니다.
강남구는 서울특별시, 춘천시는 강원특별자치도/강원도 자료를 조회합니다.
지역 미지정 자료를 전국 사업이나 시·도 전체 주민 대상 사업으로 확정하지 않습니다.
알려진 시행기간이 종료되었거나 시작 전인 사업은 한국 날짜 기준으로 제외하며,
기간이 없으면 확인 필요로 표시합니다. 신청·모집 기간은 별도로 원문에서 확인해야 합니다.
상세 수집·갱신 대기 자료도 목록 요약으로 표시하고 대기 상태를 안내합니다.
`benefit_text`는 매칭과 화면의 지원 내용에 사용합니다.
검토 저장 시 당시 사업 정보·출처·수집 상태를 함께 저장해 이후 API 갱신과 구분합니다.
보고서에는 저장된 검토 의견과 원문 링크, 상세 확인 대기 여부가 반영됩니다.
조회는 DB 읽기만 수행하며, 수집 API를 즉석에서 호출하지 않습니다.

```sql
SELECT service_id, name, province, district, target_text, eligibility_text,
       benefit_text, application_text, effective_start, effective_end,
       source_url, detail_checked_at, detail_pending
FROM db2.local_welfare_services ORDER BY province, district, name;

SELECT status, started_at, finished_at, request_count, list_count,
       detail_count, error_count, error_message
FROM db2.welfare_collection_runs ORDER BY started_at DESC LIMIT 20;

SELECT count(*) AS services, count(detail_payload) AS detailed,
       count(*) FILTER (WHERE detail_pending) AS pending
FROM db2.local_welfare_services;
```

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s db\tests -v
# 실제 DB 테스트: 테스트 데이터/호출 카운터 변경은 트랜잭션 끝에 모두 롤백
$env:RUN_DB2_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s db\tests -v
```

실제 API 목록 2건·상세 2건을 총 3회 호출하여 저장 확인했습니다.
전국 전체 상세 적재는 예약 작업이 호출 예산 안에서 순차적으로 진행합니다.
원문 스냅샷과 실행 로그는 자동 삭제하지 않으므로 운영 시 저장량을 확인해야 합니다.

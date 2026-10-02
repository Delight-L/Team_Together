# 강남구와 춘천시의 복지자원 수집

DB2는 현재 `.env`의 PostgreSQL 데이터베이스 안에 `db2` 스키마로 생성했습니다.
별도의 서버나 데이터베이스를 만든 것은 아닙니다. 기존 테이블을 삭제하거나 변경하지 않습니다.
`get_api.py`가 비어 있고 이전 범용 수집 파일이 없는 현재 작업 상태를 유지하면서
새 수집기는 `collect_db2.py`, 저장 함수는 `db2_storage.py`에 작성했습니다.

## 공식 수집처와 확인 결과

확인일: 2026-09-30. API 기능명과 필드는 해당 공공데이터포털의 공식 Swagger로 확인했습니다.

| 출처 | 지역과 제공 내용 | 현재 구현 및 제한 |
| --- | --- | --- |
| [지자체복지서비스](https://www.data.go.kr/data/15108347/openapi.do) | 강남구·춘천시 목록 및 서비스별 대상·선정기준·지원내용·신청방법·문의처·시행 시작/종료일 | 현재 키로 실호출 성공. 강남구 14건, 춘천시 24건 적재 |
| [강남구 스마트복지관 복지정보](https://www.data.go.kr/data/15155517/fileData.do) | 서비스명, 기관명, 요약, 대상, 내용 | 수집 코드 작성. 현재 키는 401. 2025-11-30 기준 파일로 현재 모집 정보가 아님 |
| [춘천시 노인일자리 현황](https://www.data.go.kr/data/15129863/fileData.do) | 수행기관, 유형, 사업명, 사업내용, 배정인원, 연락처, 데이터 기준일자 | 수집 코드 작성. 현재 키는 401. 진행·모집 기간 필드 없음 |
| [강남구 스마트복지관 공고](https://bokji.gangnam.go.kr/main.do) | 프로그램 모집·진행 일정 | 공개 수집 API 미확인. 원문 검토 후 회차별 JSON 등록 |
| [춘천시 배워봄](https://bwb.chuncheon.go.kr/community/institution-news/) | 기관별 강좌·교육 모집 공고 | 공개 수집 API 미확인. 원문 검토 후 회차별 JSON 등록 |

현재 지자체 API 수집은 `ctpvNm`과 `sggNm`를 모두 지정하고 응답 지역도 대조합니다.
서울시/강원도 전체 사업, 중앙부처 사업까지 전수 수집한 것은 아닙니다.
API의 `enfcBgngYmd`, `enfcEndYmd`는 **사업 시행일**이며 개별 프로그램의 운영 회차와 다릅니다.
데이터 기준일이나 최종 수정일을 사업/프로그램 종료일로 사용하지 않습니다.
강남구 게시 파일에 포함되었다는 사실만으로 이용 대상을 강남구민으로 한정하지 않습니다.

파일 API의 인증 오류는 해당 데이터셋 활용신청 및 odcloud에서 사용하는 키를 확인해야 합니다.
두 API의 실데이터 적재 검증은 인증이 해결된 뒤 필요합니다. 공식 명세 기반 필드 매핑은 테스트했습니다.

## 실행

```powershell
# 가상환경 활성화 후
python collect_db2.py init

# 기본은 1페이지 10건입니다. 아래는 각 지역 전체 목록과 상세를 수집합니다.
python collect_db2.py collect --source local --region both --all-pages --rows 100

# 지역별 실행
python collect_db2.py collect --source local --region gangnam --all-pages
python collect_db2.py collect --source local --region chuncheon --all-pages

# 별도 활용신청/인증 확인 후 실행
python collect_db2.py collect --source gangnam_smart --all-pages
python collect_db2.py collect --source chuncheon_jobs --all-pages

# 검토한 공고를 등록 또는 갱신합니다.
python collect_db2.py import-programs data/db2_reviewed_notices.json
```

현재 지자체 수집은 목록 2회와 상세 38회, 총 40회가 필요합니다(재시도 제외).
목록과 상세를 항목 단위로 저장하며 실패 전에 완료한 항목은 남습니다.
재실행하면 최신 서비스는 갱신되고 원천 스냅샷은 새로 추가됩니다.
매번 모든 데이터를 삭제하는 방식은 사용하지 않습니다. 새 응답에서 사라진 사업의 종료 여부도 추정하지 않습니다.

## 테이블 구조

| 테이블 | 역할 | 고유키 |
| --- | --- | --- |
| `regions` | 두 지역과 API 검색 명칭 | 지역 ID |
| `sources` | 출처, 요청주소, 데이터 기준일, 수집 제약 | 출처 ID |
| `raw_snapshots` | 각 수집 시점의 원천 응답, 수정 전 값 보존 | 수집 UUID |
| `organizations` | 기관명·연락처·주소 | 출처 + 지역 + 기관 ID |
| `welfare_services` | 복지사업과 지원조건, 사업 시행기간 | 출처 + 지역 + 서비스 ID |
| `programs` | 회차를 묶는 프로그램 정보 | 출처 + 지역 + 프로그램 ID |
| `program_sessions` | 연도·기수별 모집/진행 일정과 검토 상태 | 출처 + 지역 + 프로그램 ID + 회차 ID |

모든 테이블은 `db2` 스키마에 있습니다. SQL 전체는 `db2_schema.sql`에서 확인합니다.
공식 서비스 ID가 없는 파일데이터는 기관명·사업명(춘천 일자리는 유형 포함)을 조합한 해시를 사용합니다.
명칭이 바뀌면 새 항목이 되므로 사람이 동일 사업 여부를 검토해야 합니다. 동일 조합의 다른 행이 나오면 수집을 중단합니다.
출처가 다른 비슷한 기관/서비스를 이름만으로 자동 병합하지 않습니다.

프로그램 공고 등록 함수는 `save_program_session(engine, record)`입니다.
`session_id`를 `2025-1기`, `2026-1기`처럼 분리하면 다른 회차를 덮어쓰지 않습니다.
같은 회차를 수정해도 이전 값은 `raw_snapshots`에 남습니다.
기관이나 서비스 API의 행을 자동으로 프로그램 회차로 생성하지 않습니다.

## 과거 사례와 현재 모집 구분

- 모집: `application_start`, `application_end`
- 진행: `starts_on`, `ends_on`
- 공고 원문: `period_text`, `source_url`, `published_on`
- 확인 이력: `snapshot_id`, `last_verified_at`
- 검토: `pending`, `reviewed`
- 근거 상태: `unknown`, `announced`(공고 확인), `completed`(완료 확인), `cancelled`

모르는 날짜는 NULL입니다. 공고 게시일을 모집 시작일로 대신 쓰지 않습니다.
`completed`는 실제 완료 근거를 확인한 경우에만 지정합니다.

`current_program_candidates` 뷰는 검토 완료·모집 기간 내·종료되지 않은 공고만 반환합니다.
모집일이 불명확하거나 상시 모집인 자료는 자동 포함하지 않습니다. 실제 접수 가능 여부,
대상자 적격 여부와 잔여 정원은 원문/운영기관에서 추가 확인해야 합니다.

`past_program_cases` 뷰는 검토한 공고 중 진행 종료일이 지난 자료를 반환합니다.
`completion_confirmed=false`는 **과거 모집·운영계획 공고**이며 실제 운영 실적이 확인된 자료가 아닙니다.
취소·검토 대기 자료는 이 뷰에서 제외합니다. 날짜 비교는 한국 시간 기준입니다.

이번에 원문을 확인하여 등록한 두 공고는 모두 `announced`입니다.

- [강남구 집·주·인 1기](https://bokji.gangnam.go.kr/board/BBS_NEWS/546/view.do?mid=ID01_02): 공고상 2025-02-13~04-10. 모집 마감 02-10, 시작일 미기재.
- [춘천시 찾아가는 방문강좌](https://bwb.chuncheon.go.kr/community/institution-news/?bbsId=BBSMSTR_000000000002&flag=view&nttId=1641): 모집 2025-03-24~04-07, 교육 04-21~06-30.

## 조회 예시

```sql
-- 지역별 복지서비스 및 지원조건
SELECT region_id, name, target_text, benefit_text, application_text,
       effective_start, effective_end, source_url
FROM db2.welfare_services
ORDER BY region_id, name;

-- 현재 모집 후보 (현재 등록한 과거 공고는 나오지 않아야 합니다.)
SELECT p.name, s.*
FROM db2.current_program_candidates s
JOIN db2.programs p ON (p.source_id, p.region_id, p.external_id)
                    = (s.source_id, s.region_id, s.program_id);

-- 과거 공고 참고, 실제 완료 여부를 구분해서 표시
SELECT p.name, s.region_id, s.session_name, s.starts_on, s.ends_on,
       s.completion_confirmed, s.source_url
FROM db2.past_program_cases s
JOIN db2.programs p ON (p.source_id, p.region_id, p.external_id)
                    = (s.source_id, s.region_id, s.program_id);

-- 같은 서비스의 과거 응답을 재검토
SELECT collected_at, payload
FROM db2.raw_snapshots
WHERE source_id = 'local' AND region_id = 'gangnam'
ORDER BY collected_at DESC;
```

## 검증

```powershell
python -m unittest discover -s tests -v
$env:RUN_DB_TESTS='1'
python -m unittest discover -s tests -v
```

DB 테스트는 테스트 행을 트랜잭션 안에서만 만들고 롤백합니다.
실제 두 지역 수집, SQL 날짜 제약, 회차 보존, 스냅샷 보존, 과거/현재 뷰 구분을 검증했습니다.

# 전국 복지자원과 프로그램 사례를 위한 DB2

기존 `db2` 스키마를 확장했습니다. 기존 강남구·춘천시 서비스 및 과거 공고는 유지합니다.
에이전트와 자동 실행 스케줄은 아직 구현/등록하지 않았습니다.

## 지역 구분

- 기존 `region_id`: 자료에 표시된 **제공·게시 지역**. 주민의 이용 자격을 뜻하지 않습니다.
- `organizations.location_region_id`: 실제 기관 소재지. 확인되지 않으면 NULL입니다.
- `coverage_scope`: 이용 범위. `unknown`, `national`, `specified_regions`.
- `service_coverage`, `session_coverage`: 원문 확인으로 특정한 이용 가능 지역.
- `residency_text`: 거주 조건 원문. 연령·소득 조건 등 기존 target/eligibility도 함께 확인해야 합니다.

기관이 강남구에 있어도 전국에서 이용할 수 있고, 다른 지역의 사업도 강남구에서 도입할
참고 사례로 검색할 수 있습니다. 온라인 제공이 곧 전국 이용 가능을 의미하지 않습니다.
지자체 API의 지역명을 이용 범위로 자동 복사하지 않습니다.

전국 수집은 응답의 시도명·시군구명을 `register_region()`으로 등록합니다.
지역 ID는 이 프로젝트 내부 식별자이며 법정동/행정구역 표준코드가 아닙니다.
행정구역 개편으로 이름이 달라지는 경우 추후 별칭/표준코드 정리가 필요합니다.

## 추가 구조

| 구분 | 테이블/필드 | 용도 |
| --- | --- | --- |
| 기관 성격 | sources / organizations의 provider_sector | 공공·비영리·민간·미확인 |
| 서비스 범위 | welfare_services + service_coverage | 이용 지역, 거주 조건, 전달 방식, 비용, 검토 근거 |
| 회차 범위 | session_access + session_coverage | 개별 프로그램 회차의 이용 조건 |
| 사례 증빙 | program_evidence | 공고, 운영 완료 보고, 평가, 기관 자체 주장 구분 |
| 수집 관리 | collection_runs | 요청 지역, 시작/마지막 페이지, 전체 건수, 처리 행 수, 성공·실패 |

`raw_snapshots`는 매 수집 시점의 원천을 보존합니다. 서비스 최신 값은 UPSERT하지만
변경 전 원천은 없어지지 않습니다. 내용이 바뀐 서비스는 review_status를 pending으로
돌립니다. 이용 범위의 이전 검토값은 남지만 재검토 전 후보 뷰에서 제외됩니다.

## 조회 구분

- `reviewed_service_candidates`: 검토된 범위가 있고 알려진 시행기간을 벗어나지 않은 서비스.
  기간이 NULL이면 상시라고 단정하지 않습니다. 최종 참여 자격을 보장하는 뷰가 아닙니다.
- `current_program_candidates`: 검토·모집 일정·이용 범위가 확인된 현재 모집 후보.
- `past_program_cases`: 기간이 지난 검토된 공고. 운영 완료 확인과는 구분합니다.
- `confirmed_program_cases`: 완료 상태와 검토된 completion_report 근거가 모두 있는 과거 사례.
  완료 보고가 있다는 사실이 효과 검증을 의미하지는 않습니다. 성과 평가는 evaluation 근거를 확인합니다.

## 실행

```powershell
python collect_db2.py init

# 전국에서 1페이지 10건만 조회 (새 기본값)
python collect_db2.py collect --source local

# 중단 페이지부터 일부 수집
python collect_db2.py collect --source local --region nationwide --start-page 2 --rows 10

# 전체 요청: API 호출 한도에 맞춰 실행해야 합니다.
python collect_db2.py collect --source local --region nationwide --all-pages --rows 100
```

실제 전국 목록에서 4,819건을 확인했습니다. 확인 시점의 수치이며 전체 적재를 완료한 것은 아닙니다.
서비스마다 상세 API를 추가 호출하므로 전체 수집에는 약 4,900회가 필요합니다.
한도에 도달하면 실패로 기록하고 이전 저장분을 유지합니다. `last_page`는 마지막으로 요청한
페이지이므로 실패 시 그 페이지부터 다시 실행하세요. 목록이 수집 사이 변경되면 페이지 위치가
바뀔 수 있어 재조회가 필요합니다. 체크포인트가 변경된 원천의 누락까지 보장하지 않습니다.
`completed`는 요청한 범위의 처리 완료이며 전국 전체 수집 완료를 뜻하지 않습니다.
현재 collection_runs는 지자체 수집에 적용합니다. 파일 API의 실행 추적은 후속 확장 대상입니다.

## 이용 범위 검토 입력

```python
from db.connection import engine
from db2_storage import set_service_access

# 실제로 확인한 원문과 서비스 ID를 넣습니다. 아래는 호출 형식입니다.
set_service_access(
    engine, source_id="local", region_id="gangnam", service_id="실제 서비스 ID",
    coverage_scope="specified_regions", eligible_regions=["gangnam"],
    evidence_url="확인한 원문 URL", residency_text="원문에 명시된 거주 조건",
    delivery_mode="onsite", cost_text="원문에 명시된 비용",
)
engine.dispose()
```

회차는 `set_session_access(engine, identity, access)`로 같은 종류의 범위를 입력합니다.
identity는 source_id·region_id·program_id·session_id 네 개의 키입니다.
`add_program_evidence(engine, record)`는 이 네 키와 evidence_type, evidence_url,
summary, review_status를 받아 증빙을 추가합니다. 증빙만 넣어 완료 상태를 자동 변경하지 않습니다.

민간 자료는 아래 구조의 JSON을 `import-source`로 등록한 후 기존 `import-programs`를 사용합니다.
실제 확인하지 않은 업체나 서비스 예시를 DB에 입력하지 않았습니다.

```json
{
  "source_id": "고유 출처 ID",
  "name": "실제 기관명",
  "catalog_url": "공식 프로그램 목록 URL",
  "source_type": "provider_notice",
  "provider_sector": "private"
}
```

```powershell
python collect_db2.py import-source source.json
python collect_db2.py import-programs notices.json
```

기관 성격과 제공 지역은 별개입니다. source의 기관 성격을 기관 테이블 전체로 자동 전파하지 않습니다.
전국 민간 사이트를 자동 수집하는 크롤러, 중앙부처 API 수집기, 서비스 자동 분류는 아직 포함하지 않습니다.

## SQL 예시

```sql
-- 제공 지역에 상관없이 강남구에서 이용할 수 있다고 검토된 서비스 후보
SELECT s.name, s.region_id AS provider_region, s.target_text, s.residency_text, s.source_url
FROM db2.reviewed_service_candidates s
WHERE s.coverage_scope = 'national'
   OR EXISTS (
       SELECT 1 FROM db2.service_coverage c
       WHERE (c.source_id,c.provider_region_id,c.service_id)
           = (s.source_id,s.region_id,s.external_id)
         AND c.eligible_region_id = 'gangnam'
   );
-- 이 예시는 명시한 지역과 전국 범위를 조회합니다. 광역 지역의 하위 시군구 확장은 별도 처리해야 합니다.

-- 전국 사례: 제공 지역으로 제한하지 않고 조회
SELECT p.name, s.region_id, s.session_name, s.source_url
FROM db2.past_program_cases s JOIN db2.programs p
ON (p.source_id,p.region_id,p.external_id)=(s.source_id,s.region_id,s.program_id);

SELECT requested_region, started_at, status, processed_count, reported_total,
       start_page, last_page, requested_all_pages
FROM db2.collection_runs ORDER BY started_at DESC;
```


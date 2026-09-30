# 두 함수로 API 원천 데이터와 업무 데이터를 저장하기

구현 파일은 `api_pipeline.py`입니다. 기존 시설 전용 `get_api.py`와 별도로 사용할 수 있습니다.

| 함수              | 입력과 결과                                       |
| ---               | ---                                               |
| `save_api_data()` | API 주소와 응답 구조 → `api_raw_data` 원천 테이블 |
| `load_api_data()` | 원천 데이터와 컬럼 매핑 → 기존 업무용 테이블      |

## JSON 예제

아래 예제 API가 `{"items": [{"id": "001", "name": "시설 A", "address": "서울"}]}`를
반환한다고 가정합니다. URL과 경로는 실제 API에 맞게 변경합니다.
업무용 테이블의 타입과 제약은 프로젝트에서 직접 정의합니다.

```sql
CREATE TABLE facility_example (
    facility_id TEXT PRIMARY KEY,
    facility_name TEXT,
    address TEXT
);
```

```python
from db_init import engine
from api_pipeline import save_api_data, load_api_data

try:
    # 1. API 응답의 각 항목을 원천 테이블에 저장합니다.
    raw_count = save_api_data(
        engine,
        url="https://example.com/api/facilities",  # 실제 API 주소로 변경
        source="facilities_example",
        params={"pageNo": 1, "numOfRows": 10},
        items_path="items",
        id_field="id",
    )

    # 2. 왼쪽은 대상 DB 컬럼, 오른쪽은 원천 데이터 필드입니다.
    saved_count = load_api_data(
        engine,
        source="facilities_example",
        table_name="facility_example",
        field_map={
            "facility_id": "id",
            "facility_name": "name",
            "address": "address",
        },
        key_columns=["facility_id"],
    )
    print(f"원천 {raw_count}건, 업무용 테이블 {saved_count}건 처리")
finally:
    engine.dispose()
```

## XML API 예제

시설종류코드 API는 아래처럼 호출합니다. 함수 자체에 특정 기관의 명세를 고정하지 않고
호출하는 쪽에서 성공 코드를 검사합니다. HTTP 200이라도 업무 오류가 들어올 수 있습니다.

```python
import os
from db_init import engine  # .env 설정을 읽습니다.
from api_pipeline import save_api_data

def validate_welfare_response(data):
    response = data.get("response", {})
    header = response.get("header", {})
    if header.get("resultCode") != "00":
        raise ValueError("사회복지시설 API 조회 실패. 인증키·신청 상태를 확인하세요.")

try:
    count = save_api_data(
        engine,
        url=("https://apis.data.go.kr/B554287/sclWlfrFcltInfoInqirService2/"
             "getFcltKindCodeInfoInqire2"),
        source="welfare_facility_kinds",
        params={
            "serviceKey": os.environ["DATA_API_KEY"],
            "pageNo": 1,
            "numOfRows": 10,
            "fcltKindCd": "090110",
        },
        response_format="xml",
        items_path="response.body.items.item",
        id_field="fcltKindCd",
        validate_response=validate_welfare_response,
    )
    print(count)
finally:
    engine.dispose()
```

## 저장 규칙

- 원천 테이블은 첫 수집 때 자동 생성하며 `(source, external_id)`로 삽입/갱신합니다.
  `source`는 같은 데이터셋에 항상 같은 이름을 사용합니다. 서로 다른 데이터셋은 구분합니다.
- `payload`는 항목 단위 JSONB입니다. 페이지 헤더와 XML 원문은 보관하지 않습니다.
  XML 값은 문자열, 반복 태그는 목록, 속성은 `@속성명`으로 변환합니다.
  네임스페이스는 제거하며 혼합 텍스트 문서용 XML의 완전한 보존은 지원하지 않습니다.
- 목록 경로가 없으면 오류로 처리합니다. JSON의 빈 목록 `[]`은 0건으로 처리합니다.
  XML에서 데이터가 없을 때 `item` 태그 자체가 사라지는 경우에는 경로 오류가 발생하므로
  해당 API의 빈 응답 형태를 별도로 처리해야 합니다.
- 한 호출은 한 응답만 수집합니다. 페이지 순회, POST 요청, 자동 재시도는 포함하지 않습니다.
  추가 HTTP 인증은 `headers`로 전달할 수 있습니다.
- 원천 응답의 ID는 문자열 또는 정수여야 합니다. ID가 없다면 먼저 식별 기준을 정해야 합니다.
- 업무용 테이블은 미리 존재해야 하며 `key_columns`와 일치하는 PK/UNIQUE 제약이 필요합니다.
  두 개 이상의 컬럼을 지정해 복합키로 사용할 수도 있습니다.
- `load_api_data()`는 해당 source에 저장된 모든 원천 행을 읽습니다. 이번 호출 건만 처리하지 않습니다.
  서로 다른 source를 같은 대상 테이블에 넣는다면 대상 키 충돌이 없도록 키 설계를 해야 합니다.
- 지정한 컬럼만 갱신합니다. 누락된 필드는 오류, 명시적인 JSON null은 SQL NULL입니다.
  변환이 필요하면 `converters={"인원수_컬럼": int}`처럼 지정합니다.
- 각 함수는 별도 트랜잭션입니다. 업무용 적재가 실패해도 원천 데이터는 남아 있어 재처리할 수 있습니다.
  원천 응답이나 업무용 데이터에서 사라진 항목을 자동 삭제하지 않습니다.
- 반환값은 삽입과 갱신을 합친 처리 행 수이며 신규 삽입 건수만을 의미하지 않습니다.

## 검증

```powershell
python -m unittest discover -s tests -v

# 기존 .env의 PostgreSQL에 연결해 삽입/갱신을 검증합니다.
# 테스트 테이블은 고유한 임시 이름을 사용하며 종료 시 모두 롤백합니다.
$env:RUN_DB_TESTS='1'
python -m unittest discover -s tests -v
```

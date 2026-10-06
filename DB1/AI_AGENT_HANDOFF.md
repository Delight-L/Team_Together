# DB1 인계 안내 — AI agent 담당자용

## 1. 담당 범위와 전달 목적

DB1 담당자는 원본 전처리, Analysis1·2·3 분석, 업데이트 처리, 공통 DB 저장 및 검증을 제공한다. AI agent 담당자는 DB1 조회 연결, 도구/API 또는 MCP 설계, 질문 처리, 근거 선택, 설명 생성 및 서비스 연동을 구현한다. 이 문서는 연결 방법과 해석 기준을 전달하며 agent 구현 자체를 포함하지 않는다.

DB1은 지역별 관측·분석 근거를 제공하는 저장소다. 최종 종합 위험점수나 개인별 위험 판정을 제공하지 않는다. 그런 기능은 현재 결과를 바탕으로 이미 검증된 기능이라고 소개할 수 없다.

## 2. 전달할 파일

프로젝트 전체를 전달할 때 상대 경로 구조를 그대로 유지한다.

| 파일/폴더 | 용도 |
|---|---|
| `outputs/db1.sqlite` | 세 분석의 운영 기준 데이터. agent가 우선 조회할 SQLite 파일 |
| `outputs/integrated/` | 같은 DB 결과를 CSV로 내보낸 자료. 탐색·확인·CSV 기반 구현에 활용 |
| `README.md` | 현재 폴더 구조와 실행 방법 |
| `Analysis3/docs/DATA_DICTIONARY.md` | 소비 지표 정의 및 해석 |
| `config/db1_config.json`, `Analysis3/config/analysis3_config.json` | 원본 위치 및 실행 설정 |
| 분석 코드·모델·기준 자료·tests | 업데이트 실행 및 검증에 필요 |
| `docs/validation/reorganization_20261006.md` | 실제 폴더의 58개 테스트 통과 기록 |

조회만 구현하는 팀원은 DB와 이 안내, 지표 사전부터 확인하면 된다. 다른 PC에서 업데이트까지 실행하려면 설정의 원본 절대 경로와 Python 실행 경로, 의존성을 해당 환경에 맞춰 설정하고 원본 자료를 별도로 준비해야 한다. 현재 PowerShell 실행기는 로컬 Anaconda 경로를 기본값으로 사용한다. 폴더 복사만으로 다른 PC의 업데이트 환경까지 구성되는 것은 아니다.

## 3. 세 분석의 의미

| 분석 | 무엇을 제공하는가 | 시간·공간 단위 |
|---|---|---|
| Analysis1 | 활동·인구·가구·복지 구조를 반영한 지역유형과 기준 대비 변화 | 강남구 22개 동·반기. 기준 2025H2 |
| Analysis2 | 통신·이동 활동의 과거 이력 대비 변화신호와 근거 | 동·월. 초기 이력 2022-01~2025-06, 이후 월별 탐지 |
| Analysis3A | 상권 소비의 연령·영역별 구성 및 과거 동일 분기 비교 | 동별 가맹점·분기 |
| Analysis3B | 신한카드 소비의 연령·영역별 전월 변화 | 강남구 가맹점 전체·월 |

통합 결과는 “어떤 특성의 지역에서 어떤 변화가 발생했고, 같은 시기 소비는 어떠했는가”를 설명한다. 행정동코드 `adm_cd`는 7자리 문자열로 취급한다. 월 `date`는 `YYYY-MM-01`, 반기는 `YYYYH1/H2`, 분기는 `YYYYQ1~Q4`다.

## 4. agent가 조회할 데이터

SQLite의 view는 기존 테이블을 연결한 조회용 구조다. agent는 다음 view부터 사용하면 된다.

| 조회 대상 | 행 단위 / 키 | 용도 |
|---|---|---|
| `v_a123_monthly` | 동·월 / `adm_cd`, `date` | 지역유형·행동신호·소비 요약 |
| `v_a123_detail` | 동·월·고객 연령·소비영역 / 위 키 + `age`, `domain` | 세부 근거 확인 |
| `v_db1_integrated` | 동·월 | Analysis1·2와 탐지 근거 연결 |
| `v_a2_quarter` | 동·분기 | 월별 신호를 분기로 요약. 관측월 수 함께 확인 |
| `v_a123_available_context` | 동·월 | 해당 월말 이전 공개일이 확인된 소비 자료 연결 |
| `db1_run`, `a3_run` | 분석/자료·기간 | 처리 완료 기간·방법 버전·원본 처리 기록 |

SQL view의 `a1_features`, `a2_result`, `a2_evidence`, `a3a_summary`, `a3b_summary`, `a3a_feature`, `a3a_comparison`, `a3b_month_context` 등은 JSON 문자열이다. Python에서는 NULL 여부를 확인한 후 `json.loads`로 읽는다. CSV 내보내기는 일부 JSON을 여러 열로 펼치므로 SQL view와 CSV의 열 구성이 완전히 같지 않다.

`any_signal`, `communication_signal`, `mobility_signal`, `combined_signal`은 0/1이다. `signal_status`는 New/Continuing 등의 탐지 상태이며 무신호일 때 NULL일 수 있다. `context_period`는 해당 Analysis2 결과에 실제 적용된 Analysis1 반기다. agent가 이를 임의로 최신 반기로 바꿔 연결하면 과거 결과의 의미가 달라진다.

## 5. 읽기 전용 조회 예시

아래 코드는 DB1 루트를 전달받는 함수 예시이며, agent 구현이나 서버는 아니다.

```python
from pathlib import Path
import sqlite3
import json

def read_month(db1_root, month):
    # 호출자는 month를 YYYY-MM 형식으로 검증한다.
    db = (Path(db1_root) / 'outputs' / 'db1.sqlite').resolve()
    with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute('''
            SELECT date, adm_cd, adm_nm, context_period, a1_cluster_type,
                   any_signal, communication_signal, mobility_signal,
                   combined_signal, signal_status,
                   a3a_period, a3a_summary, a3b_summary
            FROM v_a123_monthly
            WHERE date = ?
            ORDER BY adm_cd
        ''', (month + '-01',)).fetchall()
        result = [dict(row) for row in rows]
        for row in result:
            for key in ('a3a_summary', 'a3b_summary'):
                row[key] = json.loads(row[key]) if row[key] is not None else None
        return result
```

월별 신호 확인:

```sql
SELECT date, adm_cd, adm_nm, a1_cluster_type,
       communication_signal, mobility_signal, combined_signal, signal_status
FROM v_a123_monthly
WHERE date = ? AND any_signal = 1
ORDER BY adm_cd;
```

선택한 동·월의 상세 근거:

```sql
SELECT age, domain, a3a_period,
       a3a_feature, a3a_comparison, a3b_month_context
FROM v_a123_detail
WHERE adm_cd = ? AND date = ?
ORDER BY age, domain;
```

행동 신호 수는 월별 요약에서 센다. 상세 view의 6개 연령 × 5개 영역에 같은 신호가 반복되므로 `SUM(any_signal)`을 상세 view에 바로 적용하면 과대 집계된다.

처리 기간 확인:

```sql
SELECT analysis, MAX(period) AS latest_processed_period
FROM db1_run GROUP BY analysis;
SELECT source, MAX(period) AS latest_processed_period
FROM a3_run GROUP BY source;
```

이는 처리 완료 기간이며 자료 공개일이나 향후 업데이트 일정을 뜻하지 않는다. 월별 통합 view는 Analysis2 탐지 결과를 기준으로 연결하므로 Analysis3 자료가 있어도 그 월에 Analysis2가 없으면 통합 행이 없을 수 있다. 실제 연속성과 결측은 해당 테이블의 기간 목록으로 확인한다.

## 6. 현재 결과로 이해하기

인계 시점에는 2025-07~12의 22개 동, 월별 통합 132행과 상세 3,960행이 있다. 최신 상권 분기는 2025Q4, 카드 월은 2025-12다. Analysis2 이력은 초기 924행에 132행이 추가된 1,056행이다.

2025-12 삼성1동(`1123058`)은 Analysis1의 고활동·청년유동·1인가구 중심형에 해당하고 Analysis2의 새로운 이동 감소 신호가 있다. 같은 2025Q4 상권의 비교 가능한 30개 연령·영역 중 15개가 과거 동일 분기 최솟값보다 낮다. 20대 외식·카페 공통업종 일평균 결제건수는 과거 동일 분기 평균 대비 약 25.8% 낮다.

응답 예시: “삼성1동은 활동성이 높은 지역유형이며, 2025년 12월 이동 감소 신호가 새로 관측됐습니다. 2025년 4분기 일부 상권 소비도 과거 동일 분기보다 낮아 지역 활동 변화를 추가 확인할 근거가 있습니다.”

이는 감소 원인이나 주민 개인의 상태를 확정하는 결론이 아니다. 현재 수치는 인계 시점의 예시이므로 실제 서비스에서는 매번 DB 조회 결과로 생성한다.

## 7. 해석할 때 반드시 유지할 기준

- 신호 없음은 해당 모델의 조건을 충족하지 않았다는 뜻이다. 정상·안전 판정과 동일하지 않다.
- NULL은 미관측·미확보·비교 불가일 수 있다. 0으로 치환하지 않는다. 비교 가능 여부, 기준 이력 수, 관측 업종 범위를 함께 확인한다.
- Analysis3 고객 연령은 결제 고객 연령이다. 주민 연령으로 설명하지 않는다.
- 상권 소비는 동의 가맹점 기준이며, 카드 소비는 강남구 전체 가맹점 기준이다. 강남구 카드 수치는 동별 관측값으로 배분하거나 합산하지 않는다.
- 두 소비 자료는 업종·관측 범위가 달라 금액/건수를 더해 총량을 만들지 않는다. 상세에 반복된 구 단위 값도 중복 합산하지 않는다.
- 같은 분기 소비가 여러 월에 반복 연결돼도 그 소비가 월마다 새로 관측된 것은 아니다.
- 과거 동일 분기 비교, 전월 비교, 전년 비교는 서로 다른 기준이다. 기준 기간과 공통업종 범위를 밝혀 설명한다.
- 상관된 변화가 관측돼도 원인·개인 고립·건강 악화·복지 대상 여부를 확정하지 않는다.
- 개인 단위 연결이나 종합 위험점수는 현재 DB1의 제공 결과가 아니다.

## 8. 회고적 설명과 실시간 판단

`v_a123_monthly`와 `v_a123_detail`은 같은 시기의 분기·월 소비를 회고적으로 연결한다. 7월 행에 연결된 3분기 전체 소비는 7월말 당시 사용할 수 있던 정보라고 가정할 수 없다. 2025H2 Analysis1 기준도 하반기 전체를 사용했으므로 당시 실시간 유형이었다고 소개하면 안 된다.

`v_a123_available_context`는 소비의 `available_from`이 확인된 자료만 해당 월말 이전 조건으로 연결한다. 공개일이 미확인되면 소비 연결값이 NULL일 수 있다. 이 view만으로 Analysis1·2까지 포함한 전체 실시간 이용 가능성이 보장되지는 않는다. 당시 판단 재현 기능을 만들려면 모든 자료와 모델의 이용 가능 시점·버전 관리가 추가로 필요하다.

## 9. 업데이트와 조회의 역할 분리

현재 지원 명령은 DB1 루트에서 실행한다.

```powershell
.\run_db1.ps1 -Command status
.\run_db1.ps1 -Command scan
.\run_db1.ps1 -Command export
.\run_tests.ps1
```

`scan`은 Analysis1→2→3 순서로 신규 자료를 처리한다. Analysis1은 반기, Analysis2는 월, Analysis3A는 분기, 3B는 월별 자료를 처리하며 필요한 기간의 원본이 충족되어야 한다. CSV 내보내기는 DB 저장 후 실행한다. 세 분석 전체가 하나의 transaction은 아니므로 한 단계가 실패하면 이미 성공한 단계의 결과는 남을 수 있다. 소비 누락 시에도 행동 월의 상세 행은 유지되고 소비값은 NULL일 수 있다.

업데이트 실행자는 운영 환경에서 정한다. agent의 일상 질의는 읽기 전용으로 두고, 기존 전처리·분석 코드가 DB를 갱신하도록 연결한다. DB 파일을 다른 PC로 전달할 때는 업데이트 작업을 멈춘 시점의 일관된 복사본을 전달하거나 SQLite backup 기능을 사용한다.

## 10. AI agent 담당자에게 전달할 요청

“DB1의 분석 및 업데이트 파이프라인은 구축돼 있습니다. `outputs/db1.sqlite`의 통합 view를 읽기 전용으로 조회하는 연결을 구현해 주세요. 질문에서 동·기간을 선택하고, 월별 요약과 필요한 상세 근거를 조회해 지역 특성·변화신호·소비 맥락을 설명하면 됩니다. 기간·공간 단위와 결측을 유지하고, 결과를 개인 위험 판정으로 확대하지 않아야 합니다. 조회 API/도구 구성과 서비스 응답 형식은 AI agent 담당 범위입니다. 원본 전처리와 변화 탐지 기능을 agent 쪽에서 다시 구현할 필요는 없습니다.”

연결 검증은 삼성1동 2025-12 예시 조회, 무신호 동 조회, 없는 기간의 빈 결과, 소비 NULL 처리, 상세 신호 중복 집계 방지, JSON 파싱, 읽기 전용 연결부터 확인하면 된다.

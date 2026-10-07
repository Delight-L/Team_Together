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
| Analysis2 | 통신·이동 활동의 과거 이력 대비 변화신호와 근거 | 기존 동·월 및 추가 동·연령·월. 초기 이력 2022-01~2025-06, 이후 월별 탐지 |
| Analysis3A | 상권 소비의 연령·영역별 구성 및 과거 동일 분기 비교 | 동별 가맹점·분기 |
| Analysis3B | 신한카드 소비의 연령·영역별 전월 변화 | 강남구 가맹점 전체·월 |

통합 결과는 “어떤 특성의 지역에서 어떤 변화가 발생했고, 같은 시기 소비는 어떠했는가”를 설명한다. 행정동코드 `adm_cd`는 7자리 문자열로 취급한다. 월 `date`는 `YYYY-MM-01`, 반기는 `YYYYH1/H2`, 분기는 `YYYYQ1~Q4`다.

## 4. agent가 조회할 데이터

SQLite의 view는 기존 테이블을 연결한 조회용 구조다. agent는 다음 view부터 사용하면 된다.

| 조회 대상 | 행 단위 / 키 | 용도 |
|---|---|---|
| `v_a2_age_detection` | 동·월·연령·모델 버전 / `adm_cd`, `date`, `age_band`, `model_version` | 새 연령별 행동 변화 판정. 소비 연결은 다음 단계 |
| `v_a123_monthly` | 동·월 / `adm_cd`, `date` | 지역유형·행동신호·소비 요약 |
| `v_a123_detail` | 동·월·고객 연령·소비영역 / 위 키 + `age`, `domain` | 세부 근거 확인 |
| `v_db1_integrated` | 동·월 | Analysis1·2와 탐지 근거 연결 |
| `v_a2_quarter` | 동·분기 | 월별 신호를 분기로 요약. 관측월 수 함께 확인 |
| `v_a123_available_context` | 동·월 | 해당 월말 이전 공개일이 확인된 소비 자료 연결 |
| `db1_run`, `a3_run` | 분석/자료·기간 | 처리 완료 기간·방법 버전·원본 처리 기록 |

SQL view의 `a1_features`, `a2_result`, `a2_evidence`, `a3a_summary`, `a3b_summary`, `a3a_feature`, `a3a_comparison`, `a3b_month_context` 등은 JSON 문자열이다. Python에서는 NULL 여부를 확인한 후 `json.loads`로 읽는다. CSV 내보내기는 일부 JSON을 여러 열로 펼치므로 SQL view와 CSV의 열 구성이 완전히 같지 않다.

기존 동별 view의 `any_signal`, `communication_signal`, `mobility_signal`, `combined_signal`은 0/1이다. 새 `v_a2_age_detection`에서는 도메인 신호가 NULL이면 판정 불가능이며 0으로 바꾸지 않는다. 기존 `signal_status`는 New/Continuing 등의 탐지 상태이며 무신호일 때 NULL일 수 있다. 연령별 상태는 New/Continuing/New_after_gap/No_signal/Deferred를 구분한다. `context_period`는 해당 Analysis2 결과에 실제 적용된 Analysis1 반기다. agent가 이를 임의로 최신 반기로 바꿔 연결하면 과거 결과의 의미가 달라진다.

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

## 11. 2026년 1월 이후 신규 자료 업데이트와 자동 운영

DB1에는 2026년 이후 자료의 전처리·분석·기존 이력 통합·DB 저장 기능이 준비돼 있다. 현재 방식은 **지정된 원본 폴더에 새 자료를 넣고 기존 업데이트 명령을 실행하는 방식**이다. 원본 다운로드, AI agent의 업데이트 도구 연결, 예약 실행까지 구현되거나 등록된 상태는 아니다.

### 분석별 업데이트 시점

| 분석 | 다음 처리 기간 | 처리 조건 및 동작 |
|---|---|---|
| Analysis1 | 2026H1 | 1~6월의 SKT 자료와 필요한 공공자료가 갖춰지면 반기 분석·기준 대비 변화 탐지·DB 저장. 새 유형은 기본적으로 2026-07부터 적용 |
| Analysis2 | 2026-01 | 마지막 저장 월 다음 월부터 통신·관심집단·기상 자료를 전처리하고, 기존 이력으로 변화를 탐지한 뒤 신규 특징·결과·근거를 DB에 저장 |
| Analysis3A | 2026Q1 | 완성된 1분기 상권 자료를 전처리하고 소비 지표·과거 동일 분기 비교를 갱신해 DB에 저장 |
| Analysis3B | 2026-01 | 완성된 1월 카드 자료를 전처리하고 월별 소비 및 정확한 직전 달 대비 변화를 계산해 DB에 저장 |

Analysis1은 반기 단위이므로 2026년 1월 자료만으로 2026H1 유형을 생성하지 않는다. 새로운 유형이 적용되기 전 Analysis2는 DB에 저장된 기존 적용 가능 유형을 사용한다. Analysis3 소비 자료가 아직 없으면 통합 결과의 소비 항목은 NULL일 수 있다. 세 분석이 매달 동시에 완성되는 구조로 해석하지 않는다.

### agent가 호출할 기존 명령

DB1 루트에서 한 번 신규 자료를 확인하고 처리한다.

```powershell
.\run_db1.ps1 -Command scan
```

실행 중인 프로세스에서 60초 간격으로 신규 자료를 확인하려면 다음 명령을 사용한다.

```powershell
.\run_db1.ps1 -Command watch -Interval 60
```

`watch`는 컴퓨터 재시작 뒤 자동 복구되는 서비스나 예약 작업이 아니다. 처리되지 않은 오류가 발생하면 실행이 종료될 수 있다. 주기적 실행의 유지·재시작·오류 알림은 서비스 운영 계층에서 연결한다.

Analysis2는 중간 월을 건너뛰지 않고 순서대로 처리한다. 예를 들어 1월의 통신·관심집단 파일이 없으면 2월 파일이 있어도 1월을 기다린다. `scan`은 Analysis1→2→3 순서이므로 앞 단계 오류가 뒤 단계 실행을 막을 수 있다. 실행 전후 `status`, 명령 종료 코드, 처리 기간과 로그를 확인한다.

### 신규 원본과 설정 준비

- `config/db1_config.json`의 Analysis1·2 원본 폴더 및 파일 경로, `Analysis3/config/analysis3_config.json`의 카드·상권 폴더를 운영 환경에 맞춰 설정한다.
- Analysis2에는 신규 월의 통신·관심집단 원본과 **해당 월의 기상 자료**가 필요하다. 현재 설정의 기상 파일에 2026년 자료를 반영하거나 새 파일 경로를 지정해야 한다. 새 이름의 기상 파일을 아무 위치에 두는 것만으로 경로가 자동 변경되지는 않는다.
- Analysis1의 자동 반기 검색은 설정에 등록된 반기 또는 원본 폴더의 `flow_age_pop_YYYYMM.csv`를 기준으로 한다. ZIP만 들어오는 경우에는 처리할 반기를 설정하거나 명시적으로 실행해야 하며, 반기 전체 자료와 공공자료 조건을 충족해야 한다.
- 자료 형식, 동 코드, 필수 열, 기간 완전성이 검증 조건을 충족해야 한다. 신규 형식·새 지역코드·불완전 자료는 정상 입력으로 간주하지 않는다.
- 이미 처리한 기간의 수정 자료를 자동으로 덮어쓴다고 가정하지 않는다. 충돌·수정 이력 처리는 별도 절차가 필요하다.

### DB1 담당자와 AI agent 담당자의 범위

| DB1에서 제공하는 기능 | AI agent/서비스 담당자가 연결할 기능 |
|---|---|
| 신규 자료 전처리·분석·DB 통합 | 신규 원본 수집·다운로드·정해진 위치에 저장 |
| `scan`, `watch`, `status`, `export` 실행 명령 | 명령 호출 도구·예약 실행·프로세스 유지 |
| 입력 검증, 처리 기록, 기존 결과 조회 | 오류 감지·알림·재시도 및 최신 처리 기간 확인 |
| 통합 view와 근거 자료 | 읽기 전용 질의 도구 및 사용자 설명 생성 |

일상 조회 연결과 업데이트 실행 연결은 역할을 구분한다. agent가 직접 SQL로 분석 결과를 생성·수정하는 대신, 기존 업데이트 파이프라인을 실행해 DB를 갱신하고 결과를 다시 읽도록 설계한다. 재시도 시 종료 코드뿐 아니라 분석별 저장 기간도 확인한다. 앞 단계에서 이미 저장한 결과가 남을 수 있으므로 매번 전체 실패로 간주하거나 DB를 초기화하지 않는다.

### 검증 상태와 팀원 전달 문구

현재 로컬 자료와 업데이트 처리 로직에 대한 58개 테스트는 통과했다. **실제 2026년 원본으로 전체 업데이트를 끝까지 수행한 검증은 아직 하지 않았다.** 최초 신규 자료가 확보되면 처리 월/반기/분기, 입력 행 수와 중복 여부, DB 저장, 통합 view, 결측 처리와 CSV 갱신을 확인해야 한다.

“DB1의 신규 자료 전처리·분석·DB 통합 기능은 구현돼 있습니다. AI agent 담당자는 원본 수집, 업데이트 명령 호출, 실행 스케줄, 오류 감지·재시도를 연결해 주세요. 2026년 1월부터 Analysis2와 카드 자료는 월별로, Analysis1은 반기별로, 상권 자료는 분기별로 갱신됩니다. 첫 실제 신규 자료로 실행 결과를 함께 확인하면 됩니다.”


## Analysis2 연령별 전처리 이력 (2026-10-07)

`a2_age_feature`는 동·연령·월별 전처리 지표이며 탐지 결과가 아닙니다. `service`는 20s·30s·40s·50s·60plus, `five_year`는 원본 연령 코드를 보존합니다. 2022-01~2025-06은 기준선, 이후는 업데이트 구간입니다. `a2_age_raw`는 성별·5세 단위 원본 셀을 보존합니다. `quality_status=available`은 전처리 값의 기본 완전성만 뜻합니다. 기존 통합 뷰의 동별 탐지 신호를 이 연령대에 복사하거나 연령별 고립 신호로 설명하지 마세요. `scan`은 새로운 동별 이력에 맞춰 연령별 이력도 추가합니다. 상세한 분모·품질·업데이트 규칙과 결과 위치는 [Analysis2/AGE_PREPROCESSING.md](Analysis2/AGE_PREPROCESSING.md)에 있습니다.


## Analysis2 동·연령별 변화 탐지 (2026-10-07)

`v_a2_age_detection`에서 동·연령·월별 결과를 조회하세요. `a2_age_model`에 고정 기준·보정 임계값·버전, `a2_age_common_change`에 강남구 연령별 공통 변화를 저장합니다. `communication_signal`/`mobility_signal`은 해당 도메인의 감소 신호, `combined_signal`/`isolation_related_candidate`는 두 도메인이 겹친 집단 수준 후보입니다. NULL은 판정 불가능이며 0으로 바꾸지 마세요. `assessment_status`, `review_reasons`, 보조 근거 가용성을 함께 읽으세요. 2025-07~12 결과는 소통 신호 10건, 이동 신호 0건, 동시 후보 0건, 부분 판정 4건입니다. 이는 고립이 없다는 뜻이 아닙니다. 보정 임계값은 탐색용으로 고립 정답 자료를 통한 정확도 검증은 아직 없습니다. 기존 통합 뷰의 동별 탐지와 연령별 탐지를 구분하며, Analysis3 소비의 교차 확인 근거는 새 `v_a23_age_*` 조회에 있으며 고립 확정 근거로 설명하지 마세요. 상세 규칙과 결과 위치는 [Analysis2/AGE_DETECTION.md](Analysis2/AGE_DETECTION.md)를 참조하세요.


## 동·연령별 행동과 소비 연결 (2026-10-07)

연결 구현과 실행을 완료했다. 동·연령·월별 행동 근거에는 `v_a23_age_monthly`와 `v_a23_age_detail`을 사용한다. 분기 집계는 `v_a23_age_quarter`, 공표일 기준 조회는 `v_a23_age_available_context`다. 상세 해석과 업데이트 규칙은 `Analysis3/docs/AGE_BEHAVIOR_CONSUMPTION.md`를 참조한다. 소비는 보조 근거이며 탐지 신호나 고립 점수에 합산하지 않는다.


## 동별 독거노인 통계 연결 (2026-10-07)

동별 독거노인 관측 통계 연결을 완료했다. `v_a1_elder_annual`은 연간 지표, `v_a1_elder_context`는 반기 지역 유형 연결, `v_a123_age_elder_context`는 동·연령별 행동·소비와의 사후 연결이다. 독거노인은 65세 이상이므로 60plus에만 부분 연령 일치로 연결한다. 다른 연령대에는 직접 적용하지 않는다. 공표일 기준 조회는 `v_a123_age_elder_available_context`다. 독거 여부는 고립 판정이 아니며 기존 모형과 점수는 유지한다. 갱신 명령은 `run_db1.ps1 -Command analysis1-elder`와 일반 `scan`이고, 해석·DB 질의·정정 처리 규칙은 `Analysis1/ELDERLY_CONTEXT.md`에 있다.


## 관계망·외로움 및 청년 고립 조사 연결 (2026-10-07)

서울서베이 2022~2025년 가구원 원자료로 강남구와 서울 전체의 연령별 지원망·외로움 통계를 구축했다. `v_survey_annual`과 `v_survey_age_trend`에서 조사연도별 통계와 직전 연도의 기술적 차이를 조회한다. 2025년의 새 외로움 문항은 과거 문항과 별도로 보존한다.

`v_a123_age_survey_context`는 기존 동·연령·월별 행동·소비·독거노인 결과에 **강남구 연령별** 조사 맥락을 추가한다. `survey_geography_alignment=district_not_dong`를 반드시 읽고, 같은 값이 22개 동에 연결돼도 동별 관측값으로 설명하거나 합산하지 않는다. `survey_context_json`의 표본 수·유효 표본·품질과 NULL을 유지한다. 조사 통계는 탐지 임계값이나 위험점수를 올리는 입력이 아니다.

`v_a123_age_survey_available_context`는 확인된 공개일이 행동 월말 이전인 조사만 연결한다. 현재 서울서베이 공개일은 NULL이므로 이 뷰의 조사값도 NULL이다. 회고 뷰의 2025년 조사 연결을 당시 실시간 정보로 설명하지 않는다. 공개일 확인 후 설정을 채우면 갱신 가능하다.

2022년 서울 청년 가구조사·청년조사는 `v_survey_annual`의 별도 survey로 저장한다. 가구조사는 가중 통계, 청년조사는 비가중 응답자 구성비다. 19~39세 및 5년 구간을 보존하며 19세 포함 구간을 DB1 20s로 복사하지 않는다. `ctx_evidence_guide`는 외출·대면교류·온라인 소통·소비 해석과 지원 필요의 참고 문항을 제공한다. 2025년 행동 탐지의 정답 또는 강남구 동별 고립률이 아니다.

새 조사 원본은 연도별 문항·가중치를 확인하고 `config/db1_config.json`의 `survey_context`에 등록한다. 갱신은 `run_db1.ps1 -Command survey-context`이며 일반 `scan`/`watch`에 연결했다. 상세 정의·질의·정정 절차는 [Context/README.md](../Context/README.md), 실행 결과는 [docs/SURVEY_CONTEXT_RESULT.md](SURVEY_CONTEXT_RESULT.md)에 있다.


## 신호 이후 소통 활동 수준·회복 추적 (2026-10-07)

`v_a2_activity_followup_latest`에서 각 동·연령의 최초 신호 이후 최신 소통 수준을 조회합니다. `raw_state`(원자료), `seasonal_state`(고정 과거 같은 달 정규화), `local_state`(구 같은 연령 공통 변화 분리)를 함께 설명하세요. `both_below_reference`, `recovered_to_reference`, `mixed_recovery`, `unavailable`은 신호 발생 직전 비교 수준과의 관계이며 위험 등급·유의성·고립 확정이 아닙니다. NULL을 0으로 바꾸지 마세요. 작은 부호 차이만으로 악화나 회복을 단정하지 마세요.

추가 변화 신호가 없더라도 활동 수준이 발생 전보다 낮을 수 있습니다. 상대 상태가 회복됐다고 원자료 수준이 회복된 것으로 설명하지 마세요. 동일 개인의 지속 고립을 확인한 결과도 아닙니다. `consecutive_both_below_months`는 중첩 집계 창이 있을 수 있는 인접 집계월 수입니다. 소통/이동 변화 신호 및 결합 고립 후보는 기존 `v_a2_age_detection`에서 별도로 읽습니다.

`analysis2-activity`로 직접 계산할 수 있고 `scan`/`watch`의 분석 연결 및 `analysis2-age-detect`, 일반 월 처리·내보내기에도 연결돼 있습니다. 신규 월의 기존 전처리·DB 적재가 선행돼야 합니다. 자세한 기준·업데이트·해석 제한은 [Analysis2/ACTIVITY_LEVEL.md](Analysis2/ACTIVITY_LEVEL.md), 현재 결과는 [docs/ACTIVITY_LEVEL_RESULT_20261007.md](ACTIVITY_LEVEL_RESULT_20261007.md)를 참조하세요. 현재 기준은 사후 해석용이며 공휴일·장기 추세를 완전히 보정한 시계열 모형이나 고립 성능 검증 결과가 아닙니다.


## 과거 재현·설정 민감도와 설명 보류 기준 (2026-10-07)

현재 10건의 탐지는 저장 결과와 동일하게 재현됐고 과거 점수에 미래 월이 영향을 주지 않는지 확인했습니다. 다만 임계값·기준 기간에 따라 신호 수가 달라졌고, 같은 달 수준 비교 방식을 바꾸면 상대 회복 상태도 달라졌습니다. 유지된 설정 수를 신뢰도·발생 확률·정확도로 설명하지 마세요. 운영 탐지 및 수준 추적 기준은 이번 검증으로 바꾸지 않았습니다.

SNS 음수 제외 및 증감률 계산에 따른 기존 8건 보류 해석은 철회했습니다. SNS는 시점별 표준화 상대 지수여서 시간 비교에 사용할 수 없습니다. 같은 기준월·연령 내 지역 비교만 제공하고, 0값은 비사용으로 단정하지 않습니다.

필수 설명·보류 기준은 [docs/AI_AGENT_EXPLANATION_RULES.md](AI_AGENT_EXPLANATION_RULES.md), 시나리오별 결과는 [docs/RETROSPECTIVE_VALIDATION_20261007.md](RETROSPECTIVE_VALIDATION_20261007.md)를 참조하세요. `outputs/validation/retrospective_20261007/agent_case_review.json`은 2025년까지 10건의 검증 스냅샷입니다. 새 월에 자동 적용되는 위험 결과나 정답 자료가 아닙니다. 재실행 방법은 `Analysis2/validation/README.md`에 있습니다. 원천 공개일·휴일 정의·SNS 품질 및 분모는 추가 확인이 필요합니다.


## 원천 정의 정정 및 AI agent 인수 안내

`v_a123_age_source_context`를 우선 조회하세요. 집계 기준월과 실제 관측 기간을 구분합니다. 2025-10 기준은 7~9월이므로 2025Q3 소비와 연결합니다. 2025-11 기준은 8~10월이어서 분기 상권 비교는 NULL입니다. 기존 같은 라벨월 소비 연결은 후속 기간 맥락입니다. SNS 음수는 유효하며 시계열 증감률은 계산하지 않습니다. 공휴일 포함 정의·실제 공개일은 미확인입니다.

담당자 실행 안내: [docs/AI_AGENT_QUICKSTART.md](AI_AGENT_QUICKSTART.md). 정정된 10건: [docs/SOURCE_DEFINITIONS_RESULT_20261007.md](SOURCE_DEFINITIONS_RESULT_20261007.md). 자동 갱신 명령 `source-semantics`는 기존 분석 연결 뒤 실행되며 파일 확보·공개일 확인은 별도입니다.


## 최종 인수 검증 및 실제 설명 예시

[실제 3건 설명 예시](AI_AGENT_EXPLANATION_EXAMPLES.md), [검증 범위와 전달 구성](DB1_HANDOFF_ACCEPTANCE_20261007.md)를 추가했습니다. `tools/read_agent_context.py`는 읽기 전용이며 같은 기준월의 활동 추적·조사 배경을 함께 반환합니다. 신규 2026-01·02 기준 자료와 카드 업데이트는 운영 DB와 분리한 모의 검증에서 통과했습니다. 운영 자료는 2025-12 기준까지 유지했습니다. Analysis1 신규 반기와 새 연도 조사는 이번 모의 검증 범위에 포함되지 않습니다. 모의 결합 신호를 실제 사례로 발표하지 마세요.


## 2026-10-07 근거 보완 반영

청년 조사 세부 통계, 관측 기간 기상, 지연 소비 근거 보충, 공개일 기준 조회를 추가했습니다. [근거 사용 설명](../Context/EVIDENCE_CONTEXT.md)과 [검증 결과](DB1_IMPROVEMENTS_RESULT_20261007.md)를 함께 전달하세요. 기존 탐지 건수는 소통 10·이동 0·복합 0으로 유지됩니다.


공식 홈페이지·공모전 정의서의 공개일 조사 결과는 [공개일 증빙 조사](DATA_PUBLICATION_AUDIT_20261007.md)를 참조하세요. 파일 수정일과 최초 공개일을 구분하며 미확인 날짜는 기준일 조회에 사용하지 않습니다. 청년 조사 2024-05-22는 공식 페이지로 재확인했습니다.


## 기존 탐지의 자동 설명 생성

`tools/explain_signals.py`는 기존 모델과 군집을 유지하면서 실제 탐지를 설명합니다. 실행 방법은 `docs/ISOLATION_EXPLANATION_USAGE.md`, 현재 전체 사례는 `docs/ISOLATION_SIGNAL_EXPLANATIONS.md`, 구조화 결과는 `outputs/handoff/isolation_signal_explanations.json`에 있습니다. DB 업데이트 완료 뒤 생성기를 다시 실행해 최신 설명을 만듭니다.

JSON `isolation_explanation_v2`의 `evidence_checks`는 자체 과거 기준·지역 비교·지속성·보조 근거를 독립 항목으로 제공합니다. 순차 통과 조건이나 위험 등급이 아닙니다. 현재 자체 기준 10건, 지역 비교 2건, 지속성은 10건 모두 추가 추적입니다. 소비는 기간 정렬·비교 가능 여부 및 공간 적용 범위를 함께 전달하며 기존 신호를 승격하지 않습니다. 평가 자료 부족과 추가 탐지 없음을 구분합니다. 각 사례의 `evidence`는 원본 근거를 보존하며 `isolation_related_candidate`는 기존 판정입니다. 확률은 산출하지 않습니다.

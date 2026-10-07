# AI agent 담당자 인수 안내

## 최신 근거와 설명 조회

아래 SQL은 핵심 저장 결과 조회 예시입니다. 기상 계절 비교·조사·추적을 모두 포함하려면 `python tools/read_agent_context.py --signals-only --limit 1000`을 우선 사용하세요. `weather_tracking`은 실제 관측 창의 비교이고 `observation_weather`는 그 창의 원값입니다. 읽을 결과는 [현재 10건 설명](ISOLATION_SIGNAL_EXPLANATIONS.md), 구조화 결과는 `outputs/handoff/isolation_signal_explanations.json`입니다. DB 업데이트 후 `tools/explain_signals.py`로 설명을 갱신합니다. [기상 결과와 갱신 방법](WEATHER_TRACKING_RESULT_20261007.md)을 함께 확인하세요.


## 우선 조회

`outputs/db1.sqlite`를 읽기 전용으로 열고 `v_a123_age_source_context`를 조회한다. 원천 기준월과 실제 관측 창을 함께 표시한다. 기존 공식 결과는 그대로 보존돼 있다.

```python
from pathlib import Path
import sqlite3, json
root = Path(r"C:\Users\user\Desktop\Team_Together\DB1")
con = sqlite3.connect((root / "outputs/db1.sqlite").as_uri() + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
rows = con.execute("""SELECT * FROM v_a123_age_source_context
 WHERE communication_signal=1 OR mobility_signal=1
 ORDER BY source_label_date, adm_cd, age_band""").fetchall()
for row in rows:
    item = dict(row)
    for key in ("observation_window_json", "same_period_sns_json", "observation_consumption_json"):
        item[key] = json.loads(item[key]) if item[key] else None
    print(item)
con.close()
```

자료 계약은 `docs/AI_AGENT_EXPLANATION_RULES.md`를 따른다. `assessment_status`, 모델 버전, 관측 창, 소비 비교 가능 여부를 보존한다. 소비 NULL을 0%로 바꾸지 않는다. SNS 증감률은 계산하지 않는다. 조사 맥락은 `v_a123_age_survey_context`, 수준 추적은 `v_a2_activity_followup_latest`에서 같은 동·연령·기준월로 별도 조회한다. 조사 공개일이 없으면 당시 이용 가능한 근거로 표시하지 않는다.

## 업데이트

원본 파일 확보 → 기존 설정의 입력 위치에 저장 → 기존 `scan`/월 처리 실행 → Analysis1 반기 갱신, Analysis2 전처리·탐지, Analysis3 적재 → 기간 정렬 맥락 갱신 순서다. 파일 다운로드와 원천 공개일 확인은 외부 담당자의 작업이다. DB1의 파일 처리 기능이 다운로드까지 자동 수행하지는 않는다.

기간 정렬만 재실행: `./run_db1.ps1 -Command source-semantics`. 일반 분석 연결과 내보내기에도 연결돼 있다. 2026-01 기준 통신은 2025-10~12월을 관측하므로 2025Q4 소비에 연결한다. 실제 2026년 1월 행동 관측이 포함되는 기준월은 2026-02부터다. 원천 스키마·기간 정의가 유지되는 업데이트에 적용한다. 과거 적재값 변경은 자동 덮어쓰기하지 않고 명시적인 정정 절차로 처리한다.

최종 설명에서 실제 사회적 고립 확정, 동일 주민 소비 감소, SNS 대체 소통 증가, 공휴일 보정 완료를 주장하지 않는다. 이 자료는 동·연령 집단의 고립 관련 행동 변화와 보조 근거를 전달한다.


## 검증된 조회 도구와 담당자 실행 순서

DB1 폴더에서 다음을 실행한다. 조회 도구는 Python 표준 라이브러리와 읽기 전용 SQLite만 사용한다.

```powershell
python .\tools\read_agent_context.py --signals-only --limit 10
python .\tools\read_agent_context.py --label 2025-11-01 --dong 1123065 --age 30s
.\run_db1.ps1 -Command status
```

설명 예시는 `docs/AI_AGENT_EXPLANATION_EXAMPLES.md`, 인수 검증 범위는 `docs/DB1_HANDOFF_ACCEPTANCE_20261007.md`를 확인한다. 도구의 `activity_followup_same_label`은 같은 기준월의 후속 상태만 반환하며 신호 발생 전에 후속 추적이 없으면 NULL이다. 예시 문서의 최신 후속 상태는 별도의 명시적 사후 조회다. 모든 응답은 사후 설명용이고 실제 공개일 미확인을 유지한다.

업데이트 담당자는 두 설정 JSON의 원본 경로와 파일 명명·스키마를 확인하고 파일을 확보한다. 상태 확인 → 전체 DB 백업 → 원본 저장 → scan → 다시 상태와 기간 정렬 결과 조회 → 로그·NULL·품질 검토 순서다. 오류가 났을 때 완료 로그를 확인하기 전 성공으로 간주하지 않는다. 여러 분석을 순서대로 실행하므로 전체 명령이 단일 트랜잭션은 아니다. 앞 단계만 적재된 경우 원인을 수정하고 동일 파일로 다시 실행하면 이미 적재된 기간은 중복 삽입하지 않는다. 원본 수정은 자동 덮어쓰지 않고 별도 정정 절차로 처리한다.

2026-01·02 기준 자료의 모의 검증은 통과했지만 Analysis1 2026H1 새 반기 산출과 실제 2026년 자료로 실행한 것은 아니다. 모의 자료는 운영 원본 디렉터리와 운영 DB에 전달하지 않는다. 파일 처리 기능과 외부 다운로드·실제 공개일 확인을 구분한다.


## 2026-10-07 근거 보완 반영

청년 조사 세부 통계, 관측 기간 기상, 지연 소비 근거 보충, 공개일 기준 조회를 추가했습니다. [근거 사용 설명](../Context/EVIDENCE_CONTEXT.md)과 [검증 결과](../docs/DB1_IMPROVEMENTS_RESULT_20261007.md)를 함께 전달하세요. 기존 탐지 건수는 소통 10·이동 0·복합 0으로 유지됩니다.

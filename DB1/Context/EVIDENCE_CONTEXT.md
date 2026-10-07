# 근거 조회 및 업데이트

권장 조회 도구는 tools/read_agent_context.py이다. 기존 소통·이동·소비 근거에 youth_reference, observation_weather_json, evidence_status, source_availability를 포함한다. 상세 통합 뷰는 v_a123_age_evidence_context이며 JSON 필드는 해석 후 사용한다.

```powershell
.\run_db1.ps1 -Command source-semantics
.\run_db1.ps1 -Command evidence-context
python .\tools\read_agent_context.py --signals-only --limit 10
python .\tools\read_agent_context.py --signals-only --as-of 2025-12-31
```

source-semantics는 소비 근거 보충 후 evidence-context를 실행한다. 정상 업데이트 흐름에도 포함된다. 과거 소비 원본의 수정·삭제는 자동 덮어쓰기를 허용하지 않으며 별도 버전 이관이 필요하다. 최초 이관은 기존 소비 스냅샷을 앵커로 등록하고 기존 근거를 변경하지 않는다. 이후 관련 신규 기간의 누락 근거만 보충하고 a23_context_revision에 기록한다.

config/db1_config.json의 evidence_publication.records에 kind, period, available_from, proof를 등록한다. kind는 telecom/interest/card/weather/market/survey이고 월은 YYYY-MM, 분기는 YYYYQn, survey는 source_id다. available_from은 증빙에 따른 실제 공개일 YYYY-MM-DD다. NULL은 미확인이며 건너뛴다. DB registered_at은 처리 시각이고 공개일이 아니다. 이미 알려진 공개일을 변경하려면 별도 정정 절차가 필요하다.

--as-of는 모든 사용 핵심 입력의 공개일을 확인하고 부가 근거도 공개일로 제한한다. 모델 배포 시점과 Analysis1 산출 시점을 재구축한 실시간 백테스트는 아니므로 retrospective_only와 live_availability_verified=false를 유지한다.

청년 조사의 2022년 관측·등록 공개일을 구분한다. household는 WT_ALL3 가중 가구 응답, youth는 비가중 청년 응답이다. 20대 가구 배경은 19~29세 부분 일치로 표시하며 다른 연령대에 억지 적용하지 않는다. 수치는 자치구 또는 서울 배경으로만 설명하고 행정동 추정치로 변환하지 않는다. 표본 수·유효 표본·응답 제외·희소 표본 경고를 함께 전달한다.

기상은 통신 라벨 직전 3개월의 서울 관측치이며 결측 월이 있으면 합계를 계산하지 않는다. SNS는 표준화 지수로 시계열 증감·변화율을 계산하지 않는다. 소비는 상점 소재지 기준이므로 해당 동 주민의 소비라고 설명하지 않는다. 개인의 고립 확정, 근거 수에 따른 임의 위험 점수화는 허용되지 않는다.

테이블: ctx_youth_source/metric, ctx_weather_month/window 및 provenance/revision, ctx_publication_registry, ctx_consumption_anchor/enrichment_state, a23_context_revision. CSV는 Context/outputs/evidence에 내보낸다. 실제 10건의 상세 조회 파일은 outputs/handoff/agent_signal_evidence.json이다.


## 계절을 맞춘 기상 변화 추적

`weather_tracking.py`는 고정 기준(2022-01~2025-06)과 실제 기상 월별·행동 관측 3개월별 비교를 생성합니다. `evidence-context`와 기존 scan/export의 근거 갱신 경로에 포함됩니다. 월별 원본에 신규 월을 추가하면 기준은 유지하면서 신규 월·관측 창만 추가합니다. 기준 또는 기존 기상값의 정정은 별도 버전 이관이 필요합니다. 최소 동일 계절 비교 3개가 있어야 차이를 제공합니다. 누락 월은 부분 합계로 대체하지 않습니다. 공개일 조회는 현재·기준 월 모두 검증합니다. 테이블과 평탄 CSV는 각각 `ctx_weather_month_tracking/window_tracking`, `weather_month_tracking.csv`, `weather_window_tracking.csv`이며 Context/outputs/evidence에 저장합니다. 상세 결과는 [기상 변화 추적](../docs/WEATHER_TRACKING_RESULT_20261007.md)을 참조하세요.

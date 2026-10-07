# DB1 탐지 설명 생성기

## 근거별 확인 상태

JSON 형식은 `isolation_explanation_v2`이며 각 사례의 `evidence_checks`에 다음 독립 항목을 제공합니다. 위험 등급이나 순차 통과 조건이 아닙니다.

- `self_history`: 자체 과거 기준을 충족한 지표, 평가 가능한 지표 및 자료 부족 지표.
- `regional_comparison`: 동일 연령의 지역 공통 변화를 제외한 기준을 충족한 지표. 자체 과거 기준이 미충족이어도 별도로 확인할 수 있습니다.
- `persistence`: 연속 탐지·후속 추적 값을 보존하되 현재는 `requires_followup`으로 표시합니다. 겹치는 3개월 관측 창이나 같은 라벨의 상태만으로 지속성 확인 완료를 판정하지 않습니다. 독립된 기간의 지속성 판정은 이 생성기에 구현되어 있지 않습니다.
- `auxiliary`: 기간이 정확히 일치하고 비교 가능한 상권 소비의 감소·증가 방향, 비교 영역 수와 전체 영역 수, 신한카드 비교 가능 여부, 조사 자료의 공간·연령 적용 범위.

`confirmed`는 해당 탐지 기준 충족, `not_detected`는 평가했지만 추가 탐지 없음, `not_assessable`은 평가 자료 부족입니다. 이를 서로 바꾸거나 모든 항목이 확인될 때까지 기존 신호를 숨기면 안 됩니다. 보조 근거는 기존 신호·복합 후보 판정을 변경하지 않습니다.

현재 10건은 자체 과거 기준 확인 10건, 지역 비교 확인 2건, 지속성 추가 추적 10건입니다. 비교 가능한 상권 소비 5개 영역 모두 감소한 사례는 2건이며 이것만으로 고립 위험을 높이지 않습니다. 상권 비교 변화율은 저장된 과거 동일 분기 비교 기준에 따른 값이며 직전 분기 대비 변화율과 구분합니다.

기존 Analysis1 군집과 Analysis2 탐지를 그대로 읽어 Analysis3 소비 및 Context의 조사·기상 근거를 붙입니다. SQLite는 읽기 전용으로 열며 재학습·점수 변경·DB 수정은 하지 않습니다.

DB1 폴더에서 실행:

```powershell
python tools/explain_signals.py --output outputs/handoff/isolation_signal_explanations.json --markdown docs/ISOLATION_SIGNAL_EXPLANATIONS.md
```

`--dong 1123065 --age 30s --label 2025-11-01`로 개별 사례를 선택합니다. `--include-no-signals`는 신호 없는 결과도 설명합니다. `--as-of YYYY-MM-DD`는 기존 공개일 필터를 적용하므로 입력 공개일이 확인되지 않은 사례는 제외됩니다. 기본 출력은 사후 관측 설명입니다.

매번 DB1 업데이트 파이프라인이 완료된 뒤 위 명령을 실행해야 최신 설명 파일을 생성합니다. 결과 JSON의 category는 탐지 유형이고 isolation_related_candidate는 기존 DB1 판정을 그대로 유지합니다. probability는 null입니다. evidence에는 기간, 품질, 표본·분모, 보조자료 적용 여부와 실제 근거를 보존합니다. AI agent는 explanation을 사용자 설명 초안으로, metrics와 evidence를 검증 가능한 근거로 사용합니다.

직전 라벨과 비교한 통신 변화율은 exp(log_change)-1로 계산합니다. 실제 관측 창은 3개월이며 직전 창과 2개월 겹칩니다. rZ 경계는 각 지표·기준에 저장된 실제 값을 사용합니다. 소비 비교기간이 맞지 않거나 이전 자료가 없으면 판단을 유보합니다. SNS는 동일 라벨의 상대 비교만 허용합니다. 구 단위 연간 조사와 독거노인·청년 조사에는 공간·연령 적용 범위가 유지됩니다.

---
title: '이상신호 전체 조회 오인 및 보정 변화 설명 수정'
type: 'bugfix'
created: '2026-10-19'
status: 'draft'
context:
  - 'docs/bomi-architecture.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 화면 요약용 정규식이 `이상신호가 탐지된 모든 동을 자세히 설명해줘`의 첫 글자 `이`와 뒤의 `설명`을 결합해 화면 설명 요청으로 오인한다. 또한 원자료 이동량은 증가했지만 강남구 공통 흐름 제거 후 하방 이상신호가 탐지된 사례를 장황하고 혼동되게 설명한다.

**Approach:** 화면 요약 판정은 `이 화면`, `이 자료`, `현재 화면`, `대시보드`처럼 화면 문맥을 명시한 표현에만 적용한다. 이동 원자료가 증가한 하방 신호는 원자료 증감과 보정 후 판정을 분리해, 실제 감소가 아니라 공통 흐름 대비 이례적으로 낮은 변화임을 수치와 함께 설명한다.

## Boundaries & Constraints

**Always:** 기존 대시보드 요약 요청은 계속 현재 선택 동·월·연령 문맥을 사용한다. 이상신호 전체 조회는 `signals` 의도와 전체 범위를 유지한다. 원자료 증감률은 저장된 로그 변화량에서 산출한 값만 사용하며, 보정값의 방향을 원자료 감소로 표현하지 않는다.

**Ask First:** 의도 분류 체계나 신호 판정 공식 자체를 변경해야 하는 경우.

**Never:** 특정 질문 문장 하나만 예외 처리하지 않는다. 신호 기준, DB 데이터, 대시보드 조회 로직 또는 LLM 프롬프트를 이번 수정의 우회책으로 변경하지 않는다.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 전체 신호 상세 조회 | `이상신호가 탐지된 모든 동을 자세히 설명해줘`, 대시보드에 특정 동 선택 | `signals` 전체 조회를 유지하고 선택 동의 `reason`으로 축소하지 않음 | 화면 문맥을 상속하지 않음 |
| 명시적 화면 요약 | `이 화면 설명해줘`, `현재 화면 요약해줘`, `대시보드 자료 정리해줘` | 현재 선택 동·월·연령의 화면 설명으로 처리 | 유효한 화면 문맥만 적용 |
| 원자료 증가·보정 후 하방 신호 | 세곡동 평일 `+9.1%`, 휴일 `+3.1%`인 이동 신호 | 실제 증가 수치와 보정 후 신호를 분리하고 “공통 흐름 대비 이례적으로 낮은 변화”로 설명 | 보정 점수가 증거에 없으면 구체 점수를 만들어내지 않음 |

</frozen-after-approval>

## Code Map

- `backend/bomi/adapters/v16.py` -- 화면 요약 정규식과 대시보드 문맥 강제 적용 분기.
- `backend/agents/regional_v16/chatbot_agent/answer_generator.py` -- 원자료 증감 및 보정 후 신호의 자연어 설명 생성.
- `backend/agents/regional_v16/chatbot_agent/test_answer_generator.py` -- 신호 설명 회귀 테스트.
- `backend/bomi/tests/test_v16_adapter.py` -- 새로 추가할 화면 요약 의도 회귀 테스트.

## Tasks & Acceptance

**Execution:**
- [ ] `backend/bomi/adapters/v16.py` -- 화면 요약 정규식을 명시적 화면 지칭으로 제한한다.
- [ ] `backend/bomi/tests/test_v16_adapter.py` -- 전체 신호 질의와 실제 화면 요약 질의를 함께 고정하는 회귀 테스트를 추가한다.
- [ ] `backend/agents/regional_v16/chatbot_agent/answer_generator.py` -- 증가한 이동 지표의 설명을 원자료와 보정 판정이 바로 구분되도록 다듬는다.
- [ ] `backend/agents/regional_v16/chatbot_agent/test_answer_generator.py` -- 세곡동 형태의 증가 원자료·하방 신호 문구를 검증한다.

**Acceptance Criteria:**
- Given 특정 동이 선택된 대시보드, when 전체 이상신호 상세 질의를 입력하면, then `rule_dashboard_summary`가 아니라 전체 `signals` 의도로 처리된다.
- Given 명시적 화면 요약 표현, when 질의를 입력하면, then 기존처럼 선택된 대시보드 문맥의 `reason` 의도로 처리된다.
- Given 평일과 휴일 이동량이 모두 증가한 이동 신호, when 답변을 생성하면, then 실제 증가율을 표시하고 실제 감소가 아닌 공통 흐름 대비 이례적으로 낮은 변화라고 설명한다.

## Spec Change Log

## Design Notes

정규식은 단독 조사 `이`를 허용하지 않고 `이 화면`, `이 자료`, `이 정보`, `이 내용`만 허용한다. `현재`, `지금`, `선택한`도 뒤에 화면·자료·정보·내용 중 하나가 붙어야 화면 요약으로 판정한다.

## Verification

**Commands:**
- `.\.venv\Scripts\python.exe -m unittest backend.bomi.tests.test_v16_adapter` -- 전체 조회와 화면 요약 의도 테스트 통과.
- `.\.venv\Scripts\python.exe -m unittest backend.agents.regional_v16.chatbot_agent.test_answer_generator` -- 신호 설명 테스트 통과.

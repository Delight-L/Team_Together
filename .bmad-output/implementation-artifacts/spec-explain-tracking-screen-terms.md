---
title: 'Explain tracking-screen terms in Bomi'
type: 'feature'
created: '2026-10-20'
status: 'done'
baseline_commit: '5c57dd1e063aa9ade4a2d2b2d3c037737680aee8'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The follow-up tracking screen uses labels such as `탐지월: 통신 탐지` and `탐지 직전 기준월 = 100`. Although a user can ask about `탐지월`, questions phrased with the other visible labels are not consistently recognised as screen-term questions and can receive a generic analysis reply. The labels are concise for the dashboard, but their meaning is not self-evident to a person reviewing a case.

**Approach:** Route Korean variants of the three visible tracking terms to Bomi's existing dashboard-workspace explanation path and give each term a short, fixed, plain-language answer. Keep the explanation tied to the screen: communication means phone-call and text-message contact indicators; a detection is a change needing review, not a diagnosis; the reference month is the chart's 100 baseline for comparing subsequent movement.

## Boundaries & Constraints

**Always:** Support spacing variants that a user is likely to type (`통신 탐지`/`통신탐지`, `탐지 직전 기준월`/`탐지직전 기준월`); preserve the existing general tab explanation and existing `탐지월` handling; use deterministic, non-AI wording in both AI-on and AI-off modes; state that a detected change does not establish an individual's isolation status.

**Ask First:** Expanding the response to describe additional dashboard labels or changing the labels rendered in the UI.

**Never:** Infer the cause of a detected communication change, identify an individual, or represent a detection as a welfare-eligibility or isolation diagnosis.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Communication detection label | `통신 탐지가 뭐예요?` or `통신탐지 뜻` | The reply says it concerns phone-call and text-message contact indicators and is a change requiring review, not a diagnosis. | Use the fixed dashboard answer without requiring analysis rows. |
| Detection month label | `탐지월이 뭐야?` | The reply identifies it as the 기준월 in which the screen marked the relevant change. | Use the fixed dashboard answer. |
| Reference baseline label | `탐지 직전 기준월은 무엇인가요?` or no-space variant | The reply says it is the month immediately before detection, set to 100 as the chart comparison starting point. | Use the fixed dashboard answer. |
| Existing tab request | `이 탭 설명해줘` | The established multi-item tab explanation remains available. | Do not replace it with a term-only answer. |

</frozen-after-approval>

## Code Map

- `backend/bomi/questions.py` -- shared early router vocabulary for questions that must reach the regional-analysis workspace.
- `backend/db/region_workspace.py` -- workspace-local tab classifier and deterministic user-facing answer generator.
- `backend/db/group_workspace_regression.py` -- executable regression coverage for dashboard-chat answers and workspace selection.

## Tasks & Acceptance

**Execution:**

- [x] `backend/bomi/questions.py` -- add the visible tracking-label variants to the tab-question vocabulary so fixed routing selects `region_analysis`.
- [x] `backend/db/region_workspace.py` -- keep its duplicate tab vocabulary in sync and return a compact, term-specific explanation before the broad tab explanation.
- [x] `backend/db/group_workspace_regression.py` -- test routing and deterministic replies for each label and spacing variant, while retaining coverage for the existing general tab answer.

**Acceptance Criteria:**

- Given a user asks `통신 탐지가 뭐예요?`, when Bomi selects an answer handler, then it uses the dashboard workspace and explains phone-call/text-message contact indicators, the review-only nature of the signal, and the non-diagnostic limitation.
- Given a user asks about `탐지월`, when the question is answered with AI enabled or disabled, then the response identifies the displayed detection 기준월 without inventing a cause.
- Given a user asks about `탐지 직전 기준월` with or without spaces, when the response is generated, then it explains the 100 baseline and its role as the comparison starting point.
- Given an existing generic tab question, when Bomi answers it, then the current broad explanation remains intact.

## Spec Change Log

## Design Notes

Term-specific text should be selected only when that label is in the question. For example: `통신 탐지는 전화·문자 연락 지표에서 평소와 다른 변화가 보여 추가 확인이 필요한 신호입니다. 개인의 고립을 확정하는 판단은 아닙니다.` This avoids returning a long tab manual to someone who just points at a chip or chart caption.

## Verification

**Commands:**

- `py -m unittest backend.db.group_workspace_regression` -- expected: all workspace explanation and router regression cases pass.
- `npm run build` from `frontend/` -- expected: the existing UI screen that supplies these labels still builds successfully.

## Suggested Review Order

**Question routing**

- Classify the visible Korean labels before generic analysis can handle them.
  [questions.py:22](../../backend/bomi/questions.py#L22)

**Deterministic explanations**

- Return brief screen-specific meaning, limitations, and the chart baseline without AI generation.
  [region_workspace.py:174](../../backend/db/region_workspace.py#L174)

- Apply the term response before the established broad tab explanations.
  [region_workspace.py:188](../../backend/db/region_workspace.py#L188)

**Regression coverage**

- Verify routing, spacing variants, AI parity, and preservation of general tab guidance.
  [group_workspace_regression.py:99](../../backend/db/group_workspace_regression.py#L99)

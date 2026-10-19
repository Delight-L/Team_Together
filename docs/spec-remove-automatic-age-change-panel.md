---
title: 'Give accurate raw-data source explanations in analysis chat'
type: 'feature'
created: '2026-10-19'
status: 'done'
baseline_commit: '5b24a1420130ebc815eae2c87e8b6cbc4f9c8998'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The analysis assistant answers a question about the displayed data's raw source with a generic service introduction. It does not tell the user where the source was obtained, which original fields were used, or how they became the displayed values. Separately, overall signal responses automatically expand into a per-age change section even when comparison values are missing.

**Approach:** Add a grounded source-provenance response for explicit raw-data/source questions, using only verified project metadata for each dashboard data family. Stop fetching and rendering the automatic age-group change section for overall signal and reason answers, while keeping explicitly requested age lookups.

## Boundaries & Constraints

**Always:** Preserve the current overall-signal narrative, region/month scope, and safety caveat; distinguish each screen area’s source family; name a download source or original field only when verified in project metadata; explain unknown provenance as unverified; remove the now-unused age-change data fetch along with its rendering path; retain explicit `age_activity` and age-scoped signal behavior.

**Ask First:** Broader removal of age-related query capability, data tables, or evaluation fixtures.

**Never:** Invent a source URL, original file, column, or download date; replace unavailable age comparisons with invented values; change signal classification rules; alter the response behavior for an explicitly requested age band.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Overall signal explanation | A `signals` or `reason` request without an explicit age scope | Shows only the trustworthy overall signal narrative; it contains no automatic age-change heading or per-age missing-comparison clauses. | Existing no-signal response remains unchanged. |
| Explicit age request | An `age_activity` or age-scoped signal request | Continues to show the requested age group's existing result/status response. | Existing unavailable-data wording remains available for that explicit request. |
| Raw-data source question | A user asks where screen data was downloaded, what raw data was used, or which fields were extracted | Identifies the applicable source family, verified download/source location when known, verified extraction/aggregation steps, and any provenance gap. | Does not fabricate missing provenance. |

</frozen-after-approval>

## Code Map

- `backend/agents/regional_v16/chatbot_agent/answer_generator.py` -- builds chat narratives, including the automatic age-change addendum currently appended to overall signal/reason answers.
- `backend/agents/regional_v16/chatbot_agent/query_service.py` -- prepares evidence and currently performs supplementary per-age change lookups solely for that addendum.
- `backend/db/group_workspace.py` -- routes group-dashboard chat questions and constructs grounded non-AI answers.
- `backend/db/group_repository.py` -- exposes the processed group-flow source files and mapping actually used by the dashboard.
- `pipelines/db1/docs/DATA_PUBLICATION_AUDIT_20261007.md` -- verified official source locations and provenance limitations for Analysis2 inputs.
- `backend/**/tests/` (new or existing suitable test module) -- focused regression coverage for source answers and automatic-vs-explicit age behavior.

## Tasks & Acceptance

**Execution:**
- [x] `backend/agents/regional_v16/chatbot_agent/answer_generator.py` -- remove the automatic age-change story helper and all calls that append it from overall `reason`/`signals` narrative paths -- prevents sparse age comparisons from being displayed unsolicited.
- [x] `backend/agents/regional_v16/chatbot_agent/query_service.py` -- remove the age-change-only fetch, temporary state, and supplementary-evidence insertion -- ensures the backend does not perform data work for a panel no longer rendered.
- [x] `backend/db/group_workspace.py` and source metadata helpers -- recognize source/raw-data questions ahead of broad keyword routes and generate a concise, verified provenance answer for displayed data families -- answers the user’s actual question without generic feature copy.
- [x] `backend/**/tests/` -- add or extend focused regression tests for source answers and automatic versus explicitly requested age output -- protects both scope boundaries.

**Acceptance Criteria:**
- Given an overall signal or reason request without an age filter, when its response is generated, then it contains neither `같은 기준월의 연령별 변화도 함께 볼게요.` nor automatically generated `비교 자료가 부족해` age-change clauses.
- Given the same request, when evidence is gathered, then no per-age supplementary change list is requested or attached solely to support automatic rendering.
- Given a user explicitly requests an age group, when the existing age activity or age-scoped signal path executes, then the answer still identifies and reports that requested age scope under the existing rules.
- Given a user asks where the displayed data was downloaded or which raw fields were extracted, when a group-dashboard answer is generated, then it identifies the relevant verified source family and transformation without exposing unverified provenance as fact.
- Given a displayed source has no verified public download location in the project, when the user asks for its origin, then the answer says that it is a project-provided source and identifies the missing verification rather than inventing a link.

## Verification

**Commands:**
- `npm run build` (from `frontend`) -- expected: successful frontend production build; confirms the repository's available UI build remains healthy.
- `python -m compileall backend/agents/regional_v16/chatbot_agent` -- expected: no Python syntax errors.
- Focused Python test command for the added/located chatbot test module -- expected: the two automatic-vs-explicit age assertions pass.

## Suggested Review Order

**Dashboard source-answer boundary**

- Routes explicit data-source questions before generic dashboard explanations.
  [group_workspace.py:22](../backend/db/group_workspace.py#L22)

- Uses current snapshot file families and only verified public-source links.
  [group_workspace.py:29](../backend/db/group_workspace.py#L29)

- Prevents a generic service-source question from being treated as data provenance.
  [group_workspace.py:112](../backend/db/group_workspace.py#L112)

**Regional chatbot source-answer boundary**

- Recognizes direct raw-data questions while avoiding a bare `출처` false positive.
  [intent_parser.py:122](../backend/agents/regional_v16/chatbot_agent/intent_parser.py#L122)

- Returns a deterministic, source-scoped explanation rather than generated text.
  [answer_generator.py:34](../backend/agents/regional_v16/chatbot_agent/answer_generator.py#L34)

- Avoids query work when the source explanation needs no regional data rows.
  [query_service.py:56](../backend/agents/regional_v16/chatbot_agent/query_service.py#L56)

**Removed sparse age-change addendum**

- Overall signal narratives no longer append an unsolicited age-by-age comparison.
  [answer_generator.py:266](../backend/agents/regional_v16/chatbot_agent/answer_generator.py#L266)

**Regression checks**

- Covers source boundaries plus automatic-versus-explicit age behavior.
  [group_workspace_regression.py:12](../backend/db/group_workspace_regression.py#L12)

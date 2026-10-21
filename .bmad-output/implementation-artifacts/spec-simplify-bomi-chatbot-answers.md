---
title: 'Make every Bomi answer easy for first-time users'
type: 'feature'
created: '2026-10-20'
status: 'done'
baseline_commit: 'b718afa7f36d3d728c70af1b9cf858b9743bc750'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Bomi answers are produced through several routes: fixed regional-analysis templates, AI-written analysis answers, welfare-service answers, and fallback or clarification messages. Some already use friendly Korean, but several expose technical terms, long sentences, internal-style labels, or multiple concepts at once. A first-time user can receive a correct answer without understanding what it means or what to do next.

**Approach:** Audit every user-facing Bomi response route and make plain Korean a shared, enforceable response standard. Each answer must begin with the direct answer, explain unfamiliar terms immediately in everyday words, keep necessary limitations without jargon, and offer one clear next step when more information is needed. This applies equally to AI output, deterministic templates, safety/error guidance, regional and group workspaces, and the plain-language introduction to report drafts.

## Boundaries & Constraints

**Always:** Keep all factual values, safety notices, source/eligibility caveats, and the distinction between regional signals and individual diagnoses intact. Use Korean sentences that can be understood without knowledge of data analysis or welfare administration. Define unavoidable terms in the same sentence or replace them with ordinary words. Make AI-enabled and deterministic fallback paths meet the same standard. Retain compact answers for direct yes/no or status questions.

**Ask First:** Changing the data model, search ranking, eligibility decision, or user-visible dashboard labels; removing a safety, source, or uncertainty notice.

**Never:** Invent information to make an explanation easier; describe a regional signal as an individual's diagnosis, cause, risk score, or welfare eligibility; weaken existing privacy or factual-answer checks.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Regional analysis question | User asks why a region was marked or how data changed | Answer starts with the result, uses common words, explains any unavoidable signal or comparison term beside it, and states the limitation plainly. | Preserve a deterministic template when AI is unavailable or fails. |
| Welfare-service question | A matching service record is found | Explain what help it offers first, then who may use it and what the user should check; source status remains visible in plain words. | If no record matches, ask for the minimum missing detail using an example. |
| Clarification or unavailable data | Region, period, or comparable data is missing | State what is missing and give one short example of the requested input. | Do not expose internal field names, raw codes, or stack errors. |
| AI response | Optional AI response is used | The system instruction requires short sentences, everyday wording, in-place definitions, and a direct first sentence. | Existing factual validator and template fallback continue to protect correctness. |

</frozen-after-approval>

## Code Map

- `backend/agents/regional_analysis/chatbot_agent/answer_generator.py` -- deterministic regional-analysis answers and optional Gemini answer instruction.
- `backend/agents/regional_analysis/chatbot_agent/orchestrator.py` -- direct replies, clarification questions, fallback routing, and validation fallback.
- `backend/agents/regional_analysis/chatbot_agent/analysis2_knowledge.py` and `guardrails.py` -- fixed methodology, scope, and personal-request answers.
- `backend/bomi/phrases.py` -- shared fixed guides, blocked-output notices, and router-facing answer phrases.
- `backend/bomi/agents/welfare_prompt.py` and `backend/bomi/agents/welfare.py` -- system prompt and caller for AI-generated welfare answers.
- `backend/db/region_workspace.py` and `backend/db/group_workspace.py` -- workspace-specific AI prompts and deterministic regional/group explanations.
- `backend/chatbot/welfare/app/dialogue/resources.py` -- deterministic welfare-search answer text.
- `backend/chatbot/welfare/app/dialogue/presentation.py` -- labels and record material exposed to welfare-answer generation.
- `backend/agents/report_writer.py` and its Bomi report-agent caller -- report-draft answer framing while preserving the required formal report body.
- `backend/chatbot/explain_ai.py` -- shared AI-answer request boundary for Bomi features.
- Existing regression modules near the above response routes -- add focused coverage for wording requirements and preserve route-specific behavior.

## Tasks & Acceptance

**Execution:**

- [x] `backend/bomi/phrases.py`, `backend/bomi/agents/welfare_prompt.py`, and every user-facing AI system prompt -- establish the same answer contract: conclusion first; one idea per short sentence; unfamiliar terms explained immediately; administrative/internal language avoided; one next action where action is needed.
- [x] `backend/db/region_workspace.py`, `backend/db/group_workspace.py`, and `backend/agents/regional_analysis/chatbot_agent/{answer_generator.py,analysis2_knowledge.py,guardrails.py,orchestrator.py}` -- rewrite deterministic analysis, methodology, scope, no-data, and clarification answers to meet the contract while retaining exact numbers and non-diagnosis limits.
- [x] `backend/chatbot/welfare/app/dialogue/{resources.py,presentation.py}` and `backend/bomi/agents/welfare.py` -- make service summaries, warning labels, no-result messages, and requested-detail labels understandable without welfare-system knowledge; keep source and verification status explicit.
- [x] `backend/agents/report_writer.py` and its Bomi caller -- add a plain-language preface to report-draft replies, without replacing the formal report content that staff must review and edit.
- [x] Relevant existing or new Python regression tests -- cover representative fixed, AI-on, AI-off/failure, blocked, regional, group, welfare, report, and missing-information replies; assert required safety limitations remain while unexplained jargon is not reintroduced.

**Acceptance Criteria:**

- Given a first-time user asks an analysis question, when Bomi answers, then the first sentence states the result in ordinary Korean and any technical term needed to understand it is immediately explained.
- Given data is missing or a question needs more detail, when Bomi asks a follow-up, then it says exactly what to provide and includes a short usable example.
- Given an AI answer is configured or unavailable, when the same supported question is answered, then both paths use understandable Korean and preserve factual, privacy, and non-diagnosis safeguards.
- Given a welfare-service result has a source, date, region restriction, or unverified application detail, when Bomi presents it, then that limitation remains visible in plain language and is not mistaken for confirmed eligibility.
- Given Bomi returns a safety, scope, error, or report-draft message, when a first-time user reads it, then the user can understand what happened, what the limitation means, and what to do next without internal-system terminology.

## Spec Change Log

## Design Notes

Use a consistent explanation pattern: answer first; state one necessary number or fact; explain its practical meaning; state the next action or important limit. For example, replace an unexplained phrase such as “탐지 기준” with “평소와 다른 변화인지 가르는 기준(탐지 기준)” on first use, then use the shorter phrase later in that answer. Keep technical detail available when asked, but do not make it the default wording.

## Verification

**Commands:**

- `py -m unittest discover -s backend -p '*test*.py'` -- expected: available backend tests pass without external service credentials.
- `npm run build` from `frontend/` -- expected: the client still builds after any user-facing label adjustment.

## Suggested Review Order

**Shared answer rules**

- Require plain Korean before the welfare model generates any user-facing reply.
  [welfare_prompt.py:4](../../backend/bomi/agents/welfare_prompt.py#L4)

- Apply the same rules to optional regional-analysis AI output.
  [answer_generator.py:653](../../backend/agents/regional_analysis/chatbot_agent/answer_generator.py#L653)

- Apply the shared structure to group-analysis AI output.
  [group_workspace.py:160](../../backend/db/group_workspace.py#L160)

**Deterministic and fallback replies**

- Make missing welfare-search results actionable with a concrete example.
  [resources.py:297](../../backend/chatbot/welfare/app/dialogue/resources.py#L297)

- Explain regional-analysis terms and boundaries without weakening safety limits.
  [analysis2_knowledge.py:4](../../backend/agents/regional_analysis/chatbot_agent/analysis2_knowledge.py#L4)

- Keep blocked requests understandable and redirect users to supported questions.
  [guardrails.py:7](../../backend/agents/regional_analysis/chatbot_agent/guardrails.py#L7)

- Add a clear review instruction before formal report-draft content.
  [report_writer.py:512](../../backend/agents/report_writer.py#L512)

**Screen wording and regression protection**

- Route common tracking-label variations to their fixed plain-language explanation.
  [questions.py:22](../../backend/bomi/questions.py#L22)

- Preserve the new wording requirements with focused no-service regression coverage.
  [plain_language_regression.py:16](../../backend/bomi/plain_language_regression.py#L16)

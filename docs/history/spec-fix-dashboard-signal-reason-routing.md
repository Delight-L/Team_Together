---
title: '대시보드 탐지 이유 질문의 근거 경로 수정'
type: 'bugfix'
created: '2026-10-19'
status: 'done'
route: 'one-shot'
---

# 대시보드 탐지 이유 질문의 근거 경로 수정

## Intent

**Problem:** `왜 신호로 잡혔나요?` 같은 질문이 현재 대시보드 탐지자료가 아니라 별도 v16 조회로 전달되어, 화면에는 탐지 1건인데 보미는 0건이라고 답했습니다.

**Approach:** 탐지 이유를 묻는 자연어 표현을 별도로 판별하고, 선택된 동과 대시보드 평가자료가 일치할 때만 현재 화면 근거로 설명합니다. 다른 동을 명시하거나 화면 근거가 없으면 기존 v16 범위 해석을 유지합니다.

## Suggested Review Order

**질문 분류와 답변 선택**

- 이유·근거 표현을 넓게 인식하되 일반 선정 질문은 제외합니다.
  [`region_workspace.py:59`](../../backend/db/region_workspace.py#L59)

- 탐지 1건은 상세 근거로, 0건은 공식 미탐지로 답합니다.
  [`region_workspace.py:357`](../../backend/db/region_workspace.py#L357)

**화면 범위 보호**

- 선택 동·평가자료가 일치할 때만 대시보드 근거를 사용합니다.
  [`region_analysis.py:62`](../../backend/bomi/agents/region_analysis.py#L62)

**회귀 검증**

- 자연어 변형과 역삼2동 30대 신호 근거를 검증합니다.
  [`group_workspace_regression.py:116`](../../backend/db/group_workspace_regression.py#L116)

- 다른 동·미선택·자료 없음·오탐 경계를 검증합니다.
  [`group_workspace_regression.py:143`](../../backend/db/group_workspace_regression.py#L143)

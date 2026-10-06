"""챗봇 단계 사이에서만 공유하는 데이터 형식."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    message: str = ""
    needs_clarification: bool = False

@dataclass(frozen=True)
class QueryIntent:
    purpose: str
    question_type: str
    dong: str | None = None
    start_month: str | None = None
    end_month: str | None = None
    signal: str = "any"
    metric: str | None = None
    needs: tuple[str, ...] = ()
    limit: int | None = None
    dongs: tuple[str, ...] = ()
    # LLM이 현재 질문을 직전 확정 조회의 후속 질문으로 해석했는지 여부.
    use_previous_scope: bool = False
    # "전체 기간"처럼 사용 가능한 모든 월을 명시한 경우의 표시.
    all_available_period: bool = False
    # 범위가 부족할 때, LLM이 사용자에게 되물을 짧은 문장.
    clarifying_question: str | None = None

@dataclass
class Evidence:
    title: str
    summary: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class AnswerResult:
    text: str
    evidence: Evidence
    follow_ups: tuple[str, ...] = ()

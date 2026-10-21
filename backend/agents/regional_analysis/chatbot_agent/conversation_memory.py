"""목적체크 LLM에 전달할 짧은 대화 문맥."""

from __future__ import annotations
from dataclasses import dataclass
from .schemas import Evidence, QueryIntent


@dataclass(frozen=True)
class ConversationTurn:
    user: str
    purpose: str
    question_type: str
    districts: tuple[str, ...]
    start_month: str | None
    end_month: str | None
    signal: str
    result_summary: str
    age_band: str | None = None
    age_bands: tuple[str, ...] = ()
    metric: str | None = None


class ConversationMemory:
    def __init__(self, max_turns: int = 6):
        self.max_turns = max_turns
        self.turns: list[ConversationTurn] = []
        self.pending_intent: QueryIntent | None = None
        self.pending_question: str | None = None

    def set_pending(self, question: str, intent: QueryIntent) -> None:
        self.pending_question = question
        self.pending_intent = intent

    def _pending_scope(self) -> ConversationTurn | None:
        intent = self.pending_intent
        if intent is None:
            return None
        names = intent.dongs or ((intent.dong,) if intent.dong else ())
        return ConversationTurn(
            self.pending_question or '',
            intent.purpose,
            intent.question_type,
            names,
            intent.start_month,
            intent.end_month,
            intent.signal,
            '추가 조건 답변 대기',
            intent.age_band,
            intent.age_bands,
            intent.metric,
        )

    def add(self, user: str, intent: QueryIntent, evidence: Evidence) -> None:
        self.pending_intent = None
        self.pending_question = None
        districts = []
        for row in evidence.rows:
            name = row.get("행정동") or row.get("dong_name")
            if name and name not in districts:
                districts.append(str(name))
        # 결과 행이 없는 질문도 다음 질문의 기준이 될 수 있으므로, 의도에 있던
        # 대상 동을 함께 보존한다.
        for name in intent.dongs:
            if name not in districts:
                districts.append(name)
        if intent.dong and intent.dong not in districts:
            districts.append(intent.dong)
        start_month, end_month = intent.start_month, intent.end_month
        # A regional list can span months, but a subsequent "왜 이 동인가요?"
        # answer is about one displayed signal record.  Preserve that record's
        # label month so a following age/metric question does not expand back
        # into every month from the original regional search.
        if intent.question_type in {"reason", "support"}:
            dates = {str(row.get("date"))[:7] for row in evidence.rows if row.get("date")}
            if len(dates) == 1:
                start_month = end_month = dates.pop()
        self.turns.append(
            ConversationTurn(
                user,
                intent.purpose,
                intent.question_type,
                tuple(districts),
                start_month,
                end_month,
                intent.signal,
                evidence.summary,
                intent.age_band,
                intent.age_bands,
                intent.metric,
            )
        )
        self.turns = self.turns[-self.max_turns :]

    def as_prompt_data(self) -> list[dict]:
        scope = self._pending_scope()
        turns = self.turns + ([scope] if scope else [])
        data = [
            {
                "user": t.user,
                "purpose": t.purpose,
                "question_type": t.question_type,
                "districts": list(t.districts),
                "start_month": t.start_month,
                "end_month": t.end_month,
                "signal": t.signal,
                "result_summary": t.result_summary,
                "age_band": t.age_band,
                "age_bands": list(t.age_bands),
                "metric": t.metric,
            }
            for t in turns
        ]
        if scope:
            data[-1].update(awaiting_clarification=True, needs=list(self.pending_intent.needs))
        return data

    def last_scope(self) -> ConversationTurn | None:
        """조건 응답을 기다리는 조회, 또는 직전 조회의 확정 범위."""
        return self._pending_scope() or (self.turns[-1] if self.turns else None)

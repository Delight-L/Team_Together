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

class ConversationMemory:
    def __init__(self, max_turns: int = 6):
        self.max_turns=max_turns
        self.turns: list[ConversationTurn]=[]

    def add(self, user: str, intent: QueryIntent, evidence: Evidence) -> None:
        districts=[]
        for row in evidence.rows:
            name=row.get("행정동") or row.get("dong_name")
            if name and name not in districts:
                districts.append(str(name))
        # 결과 행이 없는 질문도 다음 질문의 기준이 될 수 있으므로, 의도에 있던
        # 대상 동을 함께 보존한다.
        for name in intent.dongs:
            if name not in districts:
                districts.append(name)
        if intent.dong and intent.dong not in districts:
            districts.append(intent.dong)
        self.turns.append(ConversationTurn(
            user, intent.purpose, intent.question_type, tuple(districts),
            intent.start_month, intent.end_month, intent.signal, evidence.summary
        ))
        self.turns=self.turns[-self.max_turns:]

    def as_prompt_data(self) -> list[dict]:
        return [
            {"user":t.user,"purpose":t.purpose,"question_type":t.question_type,
             "districts":list(t.districts),"start_month":t.start_month,
             "end_month":t.end_month,"signal":t.signal,
             "result_summary":t.result_summary}
            for t in self.turns
        ]

    def last_scope(self) -> ConversationTurn | None:
        """직전 조회의 확정 범위. 대명사 해석의 보조 안전망으로만 쓴다."""
        return self.turns[-1] if self.turns else None

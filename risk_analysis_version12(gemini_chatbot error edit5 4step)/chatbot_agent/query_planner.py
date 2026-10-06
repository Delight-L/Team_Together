"""LLM의 자연어 해석을 실제 데이터 조회 계획으로 완성·검증한다."""
from __future__ import annotations

import re
from dataclasses import replace

from .conversation_memory import ConversationMemory
from .schemas import QueryIntent

_MONTH = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")
_CONTEXTUAL_TYPES = {"reason", "previous", "activity", "context", "support"}
_REQUIRED_SLOTS = {
    "signals": ("기간",),
    "rank_regions": ("기간",),
    "anomaly": ("기간", "지표"),
    "activity": ("기간",),
    "reason": ("행정동", "기간"),
    "previous": ("행정동", "기간"),
    "context": ("행정동",),
    "support": ("행정동",),
}


def complete_and_validate(intent: QueryIntent, memory: ConversationMemory,
                          available_start: str, available_end: str) -> QueryIntent:
    """생략된 후속 질문은 직전 확정 범위로 보완하고, 날짜만 엄격히 검증한다.

    기간의 의미(예: 하반기)는 여기서 규칙으로 번역하지 않는다. LLM이 해석한
    YYYY-MM 결과가 실제 데이터의 범위 안에 있는지만 확인한다.
    """
    needs = list(intent.needs)
    names = intent.dongs or ((intent.dong,) if intent.dong else ())
    previous = memory.last_scope()

    # LLM이 후속 질문이라고 판단한 경우에만 직전 확정 범위를 이어받는다.
    # 새 지역·새 질문의 누락 조건을 과거 결과로 임의 보완하지 않는다.
    if intent.use_previous_scope and not names and previous and previous.districts:
        names = previous.districts
        needs = [item for item in needs if item != "행정동"]

    start, end, signal = intent.start_month, intent.end_month, intent.signal
    if intent.all_available_period:
        start, end = available_start, available_end
        needs = [item for item in needs if item != "기간"]
    elif intent.use_previous_scope and previous:
        start = start or previous.start_month
        end = end or previous.end_month
        signal = signal if intent.signal != "any" else previous.signal

    if (start and not end) or (end and not start):
        if "기간" not in needs:
            needs.append("기간")
    elif start and end:
        if not (_MONTH.fullmatch(start) and _MONTH.fullmatch(end)) or start > end:
            if "기간" not in needs:
                needs.append("기간")
        elif start < available_start or end > available_end:
            if "기간" not in needs:
                needs.append("기간")

    dong = names[0] if len(names) == 1 else None
    required = _REQUIRED_SLOTS.get(intent.question_type, ())
    for slot in required:
        if slot == "행정동" and not names:
            needs.append(slot)
        elif slot == "기간" and not (start and end):
            needs.append(slot)
        elif slot == "지표" and not intent.metric:
            needs.append(slot)
    return replace(intent, dong=dong, dongs=tuple(names), start_month=start,
                   end_month=end, signal=signal, needs=tuple(dict.fromkeys(needs)))

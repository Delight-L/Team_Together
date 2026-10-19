"""LLM의 자연어 해석을 실제 데이터 조회 계획으로 완성·검증한다."""
from __future__ import annotations

import re
from dataclasses import replace

from .conversation_memory import ConversationMemory
from .schemas import QueryIntent

_MONTH = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")
_CONTEXTUAL_TYPES = {"reason", "previous", "activity", "age_activity", "age_data_coverage", "context", "support", "consumption"}
_REQUIRED_SLOTS = {
    "signals": ("기간",),
    "rank_regions": ("기간",),
    "anomaly": ("기간", "지표"),
    "activity": ("기간",),
    "age_activity": ("행정동", "기간"),
    "age_data_coverage": ("기간",),
    "capabilities": (),
    "reason": ("행정동", "기간"),
    "previous": ("행정동", "기간"),
    "context": ("행정동",),
    "support": ("행정동",),
    "consumption": ("행정동", "기간"),
    "consumption_criteria": (),
    "data_status": (),
    "methodology": (),
    "provenance": (),
}


def complete_and_validate(intent: QueryIntent, memory: ConversationMemory,
                          available_start: str, available_end: str) -> QueryIntent:
    """생략된 후속 질문은 직전 확정 범위로 보완하고, 날짜만 엄격히 검증한다.

    기간의 의미(예: 하반기)는 여기서 규칙으로 번역하지 않는다. LLM이 해석한
    YYYY-MM 결과가 실제 데이터의 범위 안에 있는지만 확인한다.
    """
    needs = list(intent.needs)
    # Only an anomaly ranking needs one activity metric. Other query types
    # already define their metric set (all CORE values or transaction counts).
    if intent.question_type!='anomaly':needs=[item for item in needs if item!='지표']
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
    elif (intent.question_type in _CONTEXTUAL_TYPES and previous and names
          and set(names).issubset(set(previous.districts)) and not (start or end)):
        # A button such as "왜 삼성1동이 확인 대상인가요?" carries the
        # selected district but not the visible list's period. Preserve that
        # period instead of asking the user to repeat it.
        start, end = previous.start_month, previous.end_month
        needs = [item for item in needs if item != "기간"]

    # LLM needs are provisional.  A scope restored from conversation memory is
    # now a resolved slot, so stale requests for that slot must not survive.
    if names:needs=[item for item in needs if item!='행정동']
    if intent.metric:needs=[item for item in needs if item!='지표']

    if (start and not end) or (end and not start):
        if "기간" not in needs:
            needs.append("기간")
    elif start and end:
        if not (_MONTH.fullmatch(start) and _MONTH.fullmatch(end)) or start > end:
            if "기간" not in needs:
                needs.append("기간")
        elif end < available_start or start > available_end:
            if "기간" not in needs:
                needs.append("기간")
        else:
            start=max(start,available_start);end=min(end,available_end)
            needs=[item for item in needs if item!='기간']

    dong = names[0] if len(names) == 1 else None
    required = _REQUIRED_SLOTS.get(intent.question_type, ())
    for slot in required:
        if slot == "행정동" and not names:
            needs.append(slot)
        elif slot == "기간" and not (start and end):
            needs.append(slot)
        elif slot == "지표" and not intent.metric:
            needs.append(slot)
    age=intent.age_band
    if age is None and intent.question_type!='age_activity' and not intent.age_scope_explicit and intent.use_previous_scope and previous:age=previous.age_band
    if age not in {None,'20s','30s','40s','50s','60plus'}:needs.append('연령')
    remaining=tuple(dict.fromkeys(needs))
    clarification=intent.clarifying_question if set(remaining)==set(intent.needs) else None
    return replace(intent, dong=dong, dongs=tuple(names), start_month=start, age_band=age,
                   end_month=end, signal=signal, needs=remaining,clarifying_question=clarification)

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    kind: str
    supported: bool


OUT_OF_SCOPE = "현재 챗봇의 목적에 맞지 않는 질문입니다. 고립 문제 데이터와 관련된 질문을 해주세요."


def route_question(question: str) -> Route:
    q = question.lower().strip()
    data_terms = ("신호", "에비던스", "evidence", "detection", "행정동", "동별", "몇 건", "몇건", "근거", "전처리", "데이터", "파일")
    method_terms = ("통신 신호", "이동 신호", "communication signal", "mobility signal", "robust", "mad", "임계값", "threshold", "기준", "combined", "new", "continuing", "공통변화", "로그 변화")
    all_signal_terms = ("35건", "35 건", "35개", "35 개", "35 signals", "all signals", "전체 신호", "전체 동", "신호별", "모든 신호", "전부 알려", "모두 알려")
    if any(term in q for term in ("어떤 동", "어느 동", "발견된 동", "발생한 동", "행정동 목록")):
        return Route("dong_summary", True)
    if "동" in q and any(term in q for term in ("왜", "떴", "발생", "이유", "근거")):
        return Route("dong_detail", True)
    if any(term in q for term in all_signal_terms) and any(term in q for term in ("신호", "동", "행정동", "건", "목록", "알려")):
        return Route("all_signals", True)
    if any(term in q for term in method_terms):
        return Route("methodology", True)
    if any(term in q for term in data_terms):
        return Route("data_question", True)
    # 자연스러운 질문도 분석 의도가 드러나면 허용한다.
    # 특정 컬럼명이나 고정 키워드를 요구하지 않아 "왜 잡혔어?" 같은 질문을 놓치지 않는다.
    intent_terms = ("왜", "이유", "변화", "평소", "감소", "늘었", "잡혔", "떴", "발견", "판정", "결과", "분석", "설명", "문제")
    subject_terms = ("동", "지역", "행정", "신호", "통신", "이동", "고립", "이상", "여기", "해당", "이번", "기간")
    if any(term in q for term in intent_terms) and any(term in q for term in subject_terms):
        return Route("data_question", True)
    return Route("out_of_scope", False)

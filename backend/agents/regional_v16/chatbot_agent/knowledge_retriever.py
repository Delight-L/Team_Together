"""3단계 RAG의 최소 구현. 계산 원리와 해석 한계를 질문에 맞춰 제공한다."""
from __future__ import annotations
from .analysis2_knowledge import CALCULATION_GUIDE, answer_methodology

def retrieve(question: str, question_type: str) -> str:
    method = answer_methodology(question)
    if method: return method
    if question_type == "reason":
        return "판정은 전월 로그 변화량, 강남구 공통변화 제거, 과거만 사용하는 Expanding Robust Z 순서입니다. 통신은 통화·문자, 이동은 평일·휴일 이동 횟수가 모두 Z ≤ -2여야 신호가 됩니다."
    process_terms = ("분석 과정", "계산 과정", "계산 방법", "탐지 과정", "판정 과정", "1단계", "6단계")
    if any(term in question.lower() for term in process_terms):
        return CALCULATION_GUIDE
    return ""

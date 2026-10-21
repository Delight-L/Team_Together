"""1단계 입력필터링. 권한과 지원 범위는 LLM 전에 코드로 제한한다."""

from __future__ import annotations
import re
from .schemas import GuardResult

MAX_CHARS = 1000
OUT_OF_SCOPE = (
    "지역에서 나타난 변화에 대해 물어봐 주세요. 예: ‘2025년에 더 살펴볼 동은 어디인가요?’"
)
PERSONAL_REQUEST = (
    "이 자료는 동 전체를 모아 본 자료예요. 특정 사람의 고립 여부나 명단은 알 수 없어요."
)


def validate_input(question: str) -> GuardResult:
    q = question.strip()
    if not q:
        return GuardResult(False, "질문을 입력하거나 메뉴를 선택해 주세요.")
    if len(q) > MAX_CHARS:
        return GuardResult(False, f"질문은 {MAX_CHARS}자 이내로 입력해 주세요.")
    if re.search(r"(명단|개인.*고립|누가.*고립|주민.*이름|전화번호)", q):
        return GuardResult(False, PERSONAL_REQUEST)
    if re.search(r"(지시.*무시|프롬프트.*공개|api.?key|비밀번호)", q, re.I):
        return GuardResult(
            False, "이 요청은 처리할 수 없어요. 지역 변화나 복지 지원에 대해 물어봐 주세요."
        )
    return GuardResult(True)

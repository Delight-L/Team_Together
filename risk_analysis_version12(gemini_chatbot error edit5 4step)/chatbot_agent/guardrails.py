"""1단계 입력필터링. 권한과 지원 범위는 LLM 전에 코드로 제한한다."""
from __future__ import annotations
import re
from .schemas import GuardResult

MAX_CHARS = 1000
OUT_OF_SCOPE = "지역 변화 신호와 관련된 질문을 해주세요. 예: ‘2025년 신호가 나온 동은?’"
PERSONAL_REQUEST = "이 자료는 동 단위 집계입니다. 개인의 고립 여부나 대상자 명단은 확인할 수 없습니다."

def validate_input(question: str) -> GuardResult:
    q = question.strip()
    if not q: return GuardResult(False, "질문을 입력하거나 메뉴를 선택해 주세요.")
    if len(q) > MAX_CHARS: return GuardResult(False, f"질문은 {MAX_CHARS}자 이내로 입력해 주세요.")
    if re.search(r"(명단|개인.*고립|누가.*고립|주민.*이름|전화번호)", q):
        return GuardResult(False, PERSONAL_REQUEST)
    if re.search(r"(지시.*무시|프롬프트.*공개|api.?key|비밀번호)", q, re.I):
        return GuardResult(False, "자료 조회와 관계없는 요청은 처리할 수 없습니다.")
    years = [int(y) for y in re.findall(r"20\d{2}", q)]
    if any(y < 2022 or y > 2025 for y in years):
        return GuardResult(False, "현재 자료는 2022년 1월부터 2025년 12월까지입니다.")
    return GuardResult(True)

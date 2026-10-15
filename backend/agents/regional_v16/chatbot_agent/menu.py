"""2단계 목적체크 화면에 표시할 고정 메뉴와 예시 질문."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class MenuPurpose:
    key: str
    title: str
    examples: tuple[str, ...]

PURPOSES = (
    MenuPurpose("find_region", "[확인할 지역 찾기]", (
        "선택 기간에 신호가 나온 동은? ex) 2025년도에 이상신호가 나온 동은?",
        "통신 혹은 이동 지표의 감소가 이례적인 동은?",
    )),
    MenuPurpose("track_change", "[우리 동 변화 확인]", (
        "어떤 활동이 변했나요? ex) 개포동의 어떤 활동이 변했나요?",
        "왜 신호로 잡혔나요?",
        "전월에도 신호가 있었나요?",
    )),
    MenuPurpose("plan_review", "[예방사업 방향 검토]", (
        "이 동의 지역 특성은?",
        "함께 살펴볼 다른 설명은?",
        
    )),
)


def render_menu() -> str:
    lines = ["\n무엇을 확인할까요? 번호를 고르거나 자유롭게 질문하세요."]
    for i, purpose in enumerate(PURPOSES, 1):
        lines.append(f"{i}. {purpose.title}")
        lines.extend(f"   {i}-{j}. {example}" for j, example in enumerate(purpose.examples, 1))
    lines.append("0. 자유 질문 입력")
    return "\n".join(lines)

def menu_question(choice: str) -> str | None:
    try:
        major, *minor = [int(v) for v in choice.strip().split("-")]
    except ValueError:
        return None
    if not 1 <= major <= len(PURPOSES): return None
    purpose = PURPOSES[major - 1]
    if not minor: return purpose.examples[0]
    if len(minor) == 1 and 1 <= minor[0] <= len(purpose.examples):
        return purpose.examples[minor[0] - 1]
    return None

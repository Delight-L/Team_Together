"""행정동 표기 변경과 자주 발생하는 오타를 조회 전 표준 이름으로 바꾼다."""

from __future__ import annotations

import re
from difflib import get_close_matches

ALIASES = {
    "일원2동": "개포3동",
    "논형1동": "논현1동",
    "논형돈1동": "논현1동",
    "논형동1동": "논현1동",
}


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def normalize_question(question: str) -> str:
    value = compact(question)
    for old, new in ALIASES.items():
        value = value.replace(old, new)
    return value


def explicit_districts(question: str, districts: set[str]) -> tuple[str, ...]:
    normalized = normalize_question(question)
    exact = tuple(sorted((name for name in districts if name in normalized), key=len, reverse=True))
    if exact:
        return exact

    roots = {re.sub(r"[0-9]+동$", "", name) for name in districts}
    root_matches: list[str] = []
    for root in roots:
        if root and f"{root}동" in normalized:
            root_matches.extend(sorted(name for name in districts if name.startswith(root)))
    if root_matches:
        return tuple(dict.fromkeys(root_matches))

    # 오타 자동 보정은 질문 안에 '동'으로 끝나는 후보가 있고 한 글자 정도만 다를 때로 제한한다.
    candidates = re.findall(r"[가-힣0-9]{2,8}동", normalized)
    for candidate in candidates:
        match = get_close_matches(candidate, sorted(districts), n=1, cutoff=0.8)
        if match:
            return (match[0],)
    return ()

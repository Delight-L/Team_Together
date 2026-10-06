"""2단계 목적체크. 메뉴와 자유 질문을 같은 QueryIntent로 변환한다."""
from __future__ import annotations
import re
from .schemas import QueryIntent

METRICS = {
    "통화": "call_contacts", "문자": "text_contacts", "평일 이동": "weekday_move_count",
    "휴일 이동": "weekend_move_count", "주말 이동": "weekend_move_count",
}

def looks_like_reason_followup(question: str) -> bool:
    """직전 지역 목록의 탐지 이유를 묻는 자연어 후속 질문인지 판별한다."""
    q = question.replace(" ", "")
    return (
        any(token in q for token in ("왜", "무엇이", "무엇때문", "뭐때문", "어떤이유", "무슨이유"))
        and any(token in q for token in ("이상", "탐지", "신호", "선정", "잡힌", "변했"))
    ) or any(token in q for token in ("이상으로탐지", "탐지된이유", "신호가나온이유"))

def _month(text: str) -> tuple[str | None, str | None]:
    hits = re.findall(r"(202[2-5])\s*년\s*(\d{1,2})\s*월", text)
    if hits:
        months = [f"{y}-{int(m):02d}" for y,m in hits]
        return months[0], months[-1]
    years = re.findall(r"(202[2-5])\s*년", text)
    if years: return f"{years[0]}-01", f"{years[-1]}-12"
    return None, None

def _all_period(text: str) -> bool:
    return bool(re.search(r"(전체|모든|전)\s*(기간|연도|월)|처음부터|전부", text))

def _limit(text: str) -> int | None:
    match = re.search(r"(\d{1,2})\s*(?:개\s*)?동", text)
    if match:
        return max(1, min(int(match.group(1)), 22))
    korean = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5}
    match = re.search(r"(한|두|세|네|다섯)\s*(?:개\s*)?동", text)
    return korean.get(match.group(1)) if match else None

def parse_intent(question: str, districts: set[str]) -> QueryIntent:
    q = question.lower()
    dong = next((d for d in districts if d in question), None)
    start, end = _month(question)
    all_period = _all_period(question)
    signal = "combined" if ("동시" in q or "함께" in q and "통신" in q and "이동" in q) else "communication" if "통신" in q else "mobility" if "이동" in q else "any"
    metric = next((code for word,code in METRICS.items() if word in question), None)
    limit = _limit(question)
    if any(word in q for word in ("지역 특성", "지역적 특성", "지역의 특성", "유형", "예방사업", "현장", "추가 확인", "날씨", "다른 설명")):
        purpose, kind = "plan_review", "context" if "특성" in q or "유형" in q else "support"
    elif any(word in q for word in ("왜", "이유", "근거", "잡혔", "선정")):
        purpose, kind = "track_change", "reason"
    elif any(word in q for word in ("전월", "이전", "이어", "연속", "계속")):
        purpose, kind = "track_change", "previous"
    elif any(word in q for word in ("어떤 활동", "얼마나 변", "변화 보여", "추이")):
        purpose, kind = "track_change", "activity"
    elif any(word in q for word in ("이례", "robust", "z", "가장 크게")):
        purpose, kind = "find_region", "anomaly"
    elif limit and "동" in q:
        purpose, kind = "find_region", "rank_regions"
    else:
        purpose, kind = "find_region", "signals"
    needs=[]
    if kind in {"reason", "previous", "activity", "context", "support"} and not dong: needs.append("행정동")
    # 지역을 새로 말하지 않은 "왜?", "전월에도?"는 직전 조회를 이어받을 수 있다.
    follow_up = not dong and kind in {"reason", "previous", "activity", "context", "support"}
    return QueryIntent(purpose, kind, dong, start, end, signal, metric, tuple(needs), limit,
                       (), follow_up, all_period)

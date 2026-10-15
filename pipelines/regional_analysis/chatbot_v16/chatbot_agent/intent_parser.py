"""2단계 목적체크. 메뉴와 자유 질문을 같은 QueryIntent로 변환한다."""
from __future__ import annotations
import re
from .schemas import QueryIntent
from .analysis2_knowledge import is_methodology_question

METRICS = {
    "통화": "call_contacts", "문자": "text_contacts", "평일 이동": "weekday_move_count",
    "휴일 이동": "weekend_move_count", "주말 이동": "weekend_move_count",
}


def normalize_year_shorthand(text: str) -> str:
    """Interpret Korean two-digit years such as '24년' as 2024."""
    return re.sub(r'(?<!\d)(2\d)\s*년', lambda m: f"20{m.group(1)}년", text)

def looks_like_reason_followup(question: str) -> bool:
    """직전 지역 목록의 탐지 이유를 묻는 자연어 후속 질문인지 판별한다."""
    q = question.replace(" ", "")
    return (
        any(token in q for token in ("왜", "무엇이", "무엇때문", "뭐때문", "어떤이유", "무슨이유"))
        and any(token in q for token in ("이상", "탐지", "신호", "선정", "잡힌", "변했"))
    ) or (
        any(token in q for token in ("자세히", "상세", "설명"))
        and any(token in q for token in ("이상", "탐지", "신호"))
    ) or any(token in q for token in ("이상으로탐지", "탐지된이유", "신호가나온이유")) or (
        any(token in q for token in ("줄었", "감소", "늘었", "증가", "급격히"))
        and any(token in q for token in ("이동", "통화", "문자", "소통"))
    )

def _month(text: str) -> tuple[str | None, str | None]:
    text = normalize_year_shorthand(text)
    interval=re.search(r'(20\d{2})\s*년\s*(\d{1,2})\s*월?\s*(?:[~～∼–-]|부터)\s*(?:(20\d{2})\s*년\s*)?(\d{1,2})\s*월',text)
    if interval:
        y,a,y2,b=interval.groups();return f'{y}-{int(a):02d}',f'{y2 or y}-{int(b):02d}'
    iso=re.findall(r'(20\d{2}-(?:0[1-9]|1[0-2]))',text)
    if iso:return iso[0],iso[-1]
    half=re.search(r'(20\d{2})\s*년?\s*(상반기|하반기)',text)
    if half:return (f'{half[1]}-01',f'{half[1]}-06') if half[2]=='상반기' else (f'{half[1]}-07',f'{half[1]}-12')
    quarter=re.search(r'(20\d{2})\s*년?\s*([1-4])\s*분기',text)
    if quarter:
        y,q=quarter.groups();return f'{y}-{(int(q)-1)*3+1:02d}',f'{y}-{int(q)*3:02d}'
    named_years=re.findall(r'(20\d{2})\s*년',text)
    named_months=re.findall(r'(?<!\d)(1[0-2]|0?[1-9])\s*월',text)
    if len(set(named_years))==1 and named_months:
        return f'{named_years[0]}-{int(named_months[0]):02d}',f'{named_years[0]}-{int(named_months[-1]):02d}'
    hits = re.findall(r"(20\d{2})\s*년\s*(\d{1,2})\s*월", text)
    if hits:
        months = [f"{y}-{int(m):02d}" for y,m in hits]
        return months[0], months[-1]
    years = re.findall(r"(20\d{2})\s*년", text)
    if years: return f"{years[0]}-01", f"{years[-1]}-12"
    return None, None

def unsupported_numeric_age(text):
    """Reject narrower bounds rather than silently widening them to a service bin."""
    if re.search(r'(?<!\d)60\s*대(?!\s*이상)',text):return True
    cleaned=re.sub(r'(?<!\d)60\s*(?:세|살)\s*이상','',text)
    return bool(re.search(r'(?<!\d)\d{1,3}\s*(?:세|살)',cleaned))

def age_condition(text):
    if unsupported_numeric_age(text):return None,True
    if re.search(r'전\s*연령|전체\s*연령|연령\s*전체',text):return None,False
    ages=set(re.findall(r'(?<!\d)([1-9]0)\s*대',text))
    if re.search(r'60\s*(?:세|살)\s*이상|노년층|고령층',text):ages.add('60')
    if not ages:return None,False
    if len(ages)!=1 or not ages.issubset({'20','30','40','50','60'}):return None,True
    age=next(iter(ages));return '60plus' if age=='60' else age+'s',False

def comparison_ages(text):
    """Extract explicitly written age groups for separate comparison rows."""
    ages=set(re.findall(r'(?<!\d)([1-9]0)\s*대',text))
    if re.search(r'60\s*(?:세|살)\s*이상|노년층|고령층',text):ages.add('60')
    unsupported=bool(ages-{'20','30','40','50','60'}) or unsupported_numeric_age(text)
    return tuple('60plus' if age=='60' else age+'s' for age in ('20','30','40','50','60') if age in ages),unsupported

def _all_period(text: str) -> bool:
    return bool(re.search(r"(전체|모든)\s*(기간|연도|월)|전\s+(기간|연도|월)|처음부터|전부", text))

def _limit(text: str) -> int | None:
    # People often ask for "3곳" rather than "3개 동".
    match = re.search(r"(\d{1,2})\s*(?:개\s*)?(?:동|곳)", text)
    if match:
        return max(1, min(int(match.group(1)), 22))
    korean = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5}
    match = re.search(r"(한|두|세|네|다섯)\s*(?:개\s*)?(?:동|곳)", text)
    return korean.get(match.group(1)) if match else None

def parse_intent(question: str, districts: set[str]) -> QueryIntent:
    q = question.lower()
    dong = next((d for d in districts if d in question), None)
    start, end = _month(question)
    all_period = _all_period(question)
    signal = "combined" if ("동시" in q or "함께" in q and "통신" in q and "이동" in q) else "communication" if "통신" in q else "mobility" if "이동" in q else "any"
    metric = next((code for word,code in METRICS.items() if word in question), None)
    limit = _limit(question)
    age_words=bool(re.search(r'연령|나이|세대|[2-6]0\s*대|60\s*세',q))
    if any(word in q for word in ('소비','상권','거래')) and any(word in q for word in ('기준','급증 판단','급증 판정')):
        purpose, kind = 'plan_review', 'consumption_criteria'
    elif is_methodology_question(question):
        purpose, kind = "track_change", "methodology"
    elif age_words and re.search(r'볼\s*수|가능|지원|제공',q):
        purpose, kind = 'track_change', 'capabilities'
    elif age_words and any(word in q for word in ('변화','달라','차이','추이','비교','지표','활동','어떻게')) and not any(word in q for word in ('신호','탐지','기준','이유')):
        purpose, kind = 'track_change', 'age_activity'
    elif any(word in q for word in ('데이터 상태','처리 상태','업데이트 상태','초기 이력','초기이력')):
        purpose,kind='track_change','data_status'
    elif any(word in q for word in ('소비','상권','카드')):
        purpose,kind='plan_review','consumption'
    elif any(word in q for word in ("지역 특성", "지역적 특성", "지역의 특성", "지역 배경", "보조자료", "함께 볼", "유형", "예방사업", "현장", "추가 확인", "날씨", "다른 설명")):
        purpose, kind = "plan_review", "context" if "특성" in q or "유형" in q else "support"
    elif any(word in q for word in ("왜", "이유", "근거", "잡혔", "선정")) or looks_like_reason_followup(question):
        purpose, kind = "track_change", "reason"
    elif any(word in q for word in ("전월", "이전", "이어", "연속", "계속")):
        purpose, kind = "track_change", "previous"
    elif any(word in q for word in ("어떤 활동", "얼마나 변", "변화 보여", "추이","회복","신호 이후","지속성")):
        purpose, kind = "track_change", "activity"
    elif any(word in q for word in ("이례", "robust", "z", "가장 크게")):
        purpose, kind = "find_region", "anomaly"
    elif limit and "동" in q:
        purpose, kind = "find_region", "rank_regions"
    else:
        purpose, kind = "find_region", "signals"
    needs=[]
    age,ambiguous=age_condition(question)
    bands=()
    if kind in {'age_activity','capabilities'}:
        bands,ambiguous=comparison_ages(question)
        age=bands[0] if len(bands)==1 else None
    if ambiguous:needs.append('연령')
    if kind in {"reason", "previous", "activity", "age_activity", "context", "support"} and not dong: needs.append("행정동")
    # 지역을 새로 말하지 않은 "왜?", "전월에도?"는 직전 조회를 이어받을 수 있다.
    signal_period_follow_up = (
        kind == "signals" and signal != "any"
        and any(word in q for word in ("구간", "언제", "시기", "기간"))
    )
    follow_up = not dong and (kind in {"reason", "previous", "activity", "age_activity", "context", "support", "consumption"} or signal_period_follow_up)
    return QueryIntent(purpose, kind, dong, start, end, signal, metric, tuple(needs), limit,
                       (), follow_up, all_period,age_band=age,
                       age_scope_explicit=bool(age or bands or ambiguous or re.search(r'전\s*연령|전체\s*연령',question)),age_bands=bands,
                       include_values=bool(re.search(r'원값|실제\s*값|월별\s*값|원수치',question)))

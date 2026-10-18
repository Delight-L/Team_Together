"""복지 검색 조건과 검색 결과. 담당 선택과 답변에서 같은 검색을 재사용합니다."""
import re
from backend.common import SEOUL
from datetime import datetime
from backend.chatbot.welfare.app.dialogue import resources, semantic
from backend.chatbot.welfare.app.dialogue.query_rules import excludes_past

FOLLOWUP = re.compile(
    r'^(?:(?:그|이)(?:사업|지원|프로그램)(?:의|은|는)?|그러면|그럼)?'
    r'(?:대상|자격|조건|신청|서류|문의|연락처|담당기관|운영|기간|비용|지원금|어디로)')


def is_followup(question):
    text = resources.compact(question)
    return len(text) <= 80 and bool(FOLLOWUP.match(text))


def filters(query, planning=False):
    reference = planning or bool(re.search(r'다른\s*지역|타\s*지역|참고\s*사례|비교\s*사례', query))
    past_year = any(int(year) < datetime.now(SEOUL).year for year in re.findall(r'(20\d{2})\s*년', query))
    historical = (planning or past_year or bool(re.search(r'과거|지난|종료된|이전\s*공고', query))) and not excludes_past(query)
    return {'include_reference': reference, 'include_past': historical}


async def retrieve(query, *, city='', district='', use_ai=False, planning=False):
    constraints = filters(query, planning)
    records = resources.search(query, limit=20 if use_ai else 5, city=city, district=district, **constraints)
    mode = 'keyword'
    if use_ai:
        records, mode = await semantic.hybrid_search(query, records, city=city, **constraints)
    return {'query': query, 'records': records, 'mode': mode}

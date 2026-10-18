"""검색 방식이 공유하는 질문 의도 규칙. 지원 항목과 고유 사업명을 구분합니다."""
import re

GENERIC_NAMES = frozenset((
    '주거비', '주거지원', '생활비', '생활지원', '교통비', '의료비', '교육비',
    '학비', '식비', '생계비', '지원금', '장려금', '응시료', '상담', '돌봄',
))
PAST_EXCLUSION = re.compile(
    r'(?:과거|예전|옛날|지난|종료된?|이전|20\d{2}년)'
    r'(?:(?:의)?(?:사업|자료|계획|공고|사례|정보|모집|접수|내용))*'
    r'(?:은|는|을|를|도|만|가|이)?(?P<action>제외|빼|말고|아니라|아닌|없이|보여주지|추천하지)'
    r'(?P<tail>.{0,10})')


def excludes_past(query):
    """과거 자료 제외가 명시된 경우. '제외하지 말고'는 제외 요청이 아닙니다."""
    text = re.sub(r'\s+', '', query)
    for match in PAST_EXCLUSION.finditer(text):
        if match['action'] in ('제외', '빼') and re.match(
                r'(?:하지|지)(?:말|마|않)', match['tail']):
            continue
        return True
    return False


def named_program(query, name):
    """고유 사업명은 우선 검색하되 '주거비' 같은 일반 항목은 후보를 독점하지 않습니다."""
    def compact(text):
        return re.sub(r'[^가-힣a-zA-Z0-9]', '', text).lower()
    label, question = compact(name), compact(query)
    if len(label) < 3 or label not in question:
        return False
    if label not in GENERIC_NAMES:
        return True
    # 일반 항목도 이름을 따옴표로 지정하거나 해당 항목만 명시하면 조회할 수 있습니다.
    quoted = re.findall(r'["\'“‘「『]([^"\'”’」』]+)["\'”’」』]', query)
    return any(compact(part) == label for part in quoted) or bool(re.search(
        re.escape(label) + r'(?:(?:이?라는|인)이름|(?:이라는|라는)?항목만)', question))

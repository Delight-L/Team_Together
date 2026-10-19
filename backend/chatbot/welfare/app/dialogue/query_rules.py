"""검색 방식이 공유하는 질문 의도 규칙. 지원 항목과 고유 사업명을 구분합니다."""
import re


def compact(text):
    """띄어쓰기·문장부호를 제거한 복지 검색용 비교 문자열."""
    return re.sub(r'[^가-힣a-zA-Z0-9]', '', text).lower()


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
    label, question = compact(name), compact(query)
    if len(label) < 3 or label not in question:
        return False
    if label not in GENERIC_NAMES:
        return True
    # 일반 항목도 이름을 따옴표로 지정하거나 해당 항목만 명시하면 조회할 수 있습니다.
    quoted = re.findall(r'["\'“‘「『]([^"\'”’」』]+)["\'”’」』]', query)
    return any(compact(part) == label for part in quoted) or bool(re.search(
        re.escape(label) + r'(?:(?:이?라는|인)이름|(?:이라는|라는)?항목만)', question))


ELDERLY_TERMS = ('어르신', '노인', '고령', '노년', '독거노인')
OTHER_TARGETS = ('아동', '영아', '유아', '어린이', '청소년', '청년', '아이돌봄')


def elderly_request(query):
    """복수 대상 비교나 이름 지정과 구분할 명시적인 어르신 지원 요청."""
    text = compact(query)
    return (any(term in text for term in ELDERLY_TERMS)
            or bool(re.search(r'(?:60|65|70|75|80)세이상', text))) and not any(
                term in text for term in OTHER_TARGETS)


def care_only_request(query):
    return bool(re.search(r'돌봄(?:관련)?(?:사업|서비스|지원)?만|(?:보완|생활비)지원(?:은|을)?(?:제외|빼)', compact(query)))


def select_recommendations(records, limit):
    """전체 개수 안에서 직접 지원을 먼저, 보완 지원은 최대 한 개 제공합니다."""
    direct = [r for r in records if r.get('support_role') != 'living']
    living = [r for r in records if r.get('support_role') == 'living']
    if direct and living and limit > 1:
        return direct[:limit - 1] + living[:1]
    return direct[:limit] if direct else living[:1]


def filter_target_records(query, records):
    """어르신 추천은 사업명·대상에 근거가 있는 후보만 남깁니다(자격 확정은 아님)."""
    if not elderly_request(query):
        return records
    wants_care = any(term in compact(query) for term in ('돌봄', '돌보'))
    wants_reference = any(term in query for term in ('과거', '실적', '사례', '기획', '구상'))
    care_terms = ('돌봄', '안부', '병원동행', '외출동행', '방문간호', '방문건강',
                  '방문목욕', '응급', '복약', '식사', '급식', '오찬', '도시락',
                  '반찬', '말벗', '가사', '간병', '요양')
    selected = []
    for record in records:
        if named_program(query, record['name']):
            selected.append(record)
            continue
        target = compact(str(record.get('target') or ''))
        # 아이돌봄 소득 산정의 보험료 설명을 노인 대상 근거로 오인하지 않습니다.
        target = target.replace('노인장기요양보험료', '')
        evidence = compact(record['name']) + ' ' + target
        if any(term in evidence for term in ELDERLY_TERMS) or re.search(
                r'(?:만)?(?:6\d|[7-9]\d)세(?:이상|부터)', target):
            benefit = compact(record['name'] + ' ' + str(record.get('description') or ''))
            # 개최 실적은 현재 이용할 돌봄서비스 후보를 채우는 데 쓰지 않습니다.
            if wants_care and not wants_reference and any(
                    term in benefit for term in ('행사실적', '개최실적', '행사실시결과')):
                continue
            if not wants_care or any(term in benefit for term in care_terms):
                selected.append(record)
            elif not care_only_request(query) and any(term in benefit for term in
                    ('건강보험료', '생계비', '생활비', '의료비', '주거비', '난방비')):
                selected.append(dict(record, support_role='living'))
    return selected

"""Browse resident services by area/age; DB1 changes do not imply an individual need.

Only unambiguous incompatibilities are excluded. Unstructured or conflicting source
conditions remain visible for review. No individual sex, income or household is inferred.
"""

import re
from datetime import date
from backend.db.mission_store import service_candidates, service_key, seoul_now

AGE_BANDS = {
    '20대': (20, 29),
    '30대': (30, 39),
    '40대': (40, 49),
    '50대': (50, 59),
    '60대 이상': (60, 130),
}
SECTORS = ('건강', '일자리·경력', '관계·여가', '생활·경제', '가족·돌봄')


def text(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def age_ranges(value):
    """Read explicit age expressions only, not amounts, article numbers or dates."""
    value = text(value)
    value = re.sub(r'(\d+)\s*세\s*이상\s*(?:만\s*)?(\d+)\s*세\s*이하', r'\1~\2세', value)
    pattern = re.compile(
        r'(?:만\s*)?(\d{1,3})\s*세?\s*[~∼〜\-–－]\s*(?:만\s*)?(\d{1,3})\s*세\s*(미만|이하|이상|초과)?|(?:만\s*)?(\d{1,3})\s*세\s*(이상|이하|미만|초과)'
    )
    ranges = []
    for match in pattern.finditer(value):
        a, b, upper, c, bound = match.groups()
        if a:
            lo, hi = int(a), int(b) - (upper == '미만')
        else:
            n = int(c)
            lo, hi = {'이상': (n, 130), '초과': (n + 1, 130), '이하': (0, n), '미만': (0, n - 1)}[
                bound
            ]
        if 0 <= lo <= hi <= 130:
            ranges.append((lo, hi))
    if re.search(r'3050\s*여성', value):
        ranges.append((30, 59))
    # An upper extension for veterans is not an independent all-age program.
    for match in re.finditer(r'최대\s*(\d{1,3})\s*세', value):
        if ranges and int(match[1]) <= 130:
            ranges.append((min(a for a, b in ranges), int(match[1])))
    return sorted(set(ranges))


def overlap(ranges, band):
    return any(lo <= band[1] and hi >= band[0] for lo, hi in ranges)


def fully_covered(ranges, band):
    return all(any(a <= n <= b for a, b in ranges) for n in range(band[0], band[1] + 1))


def excerpts(service, fields):
    return [
        {'field': field, 'term': '대상·이용 조건', 'excerpt': text(service.get(field))}
        for field in fields
        if text(service.get(field)) not in ('', '.', '-')
    ]


def sector(service):
    rules = (
        ('일자리·경력', r'취업|재취업|구직|인턴|일자리|경력|자격증'),
        ('가족·돌봄', r'출산|산후|산모|육아|보육|입양|양육|돌봄'),
        ('건강', r'건강|치매|뇌병변|장애|의료|병원|휠체어|보장구|보조기|생리용품'),
        ('관계·여가', r'관계|교류|여가|외로움|고립|마음편의점|사회참여'),
        ('생활·경제', r'영테크|금융|통장|대출|보증금|주택|주거|요금|수당|소득|경제'),
    )
    # A title's explicit topic outranks an incidental phrase such as 재무 건강.
    for value in (text(service.get('name')), text(service.get('summary'))):
        for name, pattern in rules:
            if re.search(pattern, value):
                return name
    return '생활·경제'


def evaluate(service, context, today=None):
    band = AGE_BANDS.get(context.get('age'))
    if not context.get('city') or (context.get('age') and not band):
        return None
    today = today or seoul_now().date()
    for key, excluded in [
        ('effective_start', lambda d: d > today),
        ('effective_end', lambda d: d < today),
    ]:
        raw = str(service.get(key) or '')[:10]
        if raw and raw != '9999-12-31':
            try:
                if excluded(date.fromisoformat(raw)):
                    return None
            except ValueError:
                pass
    target = text(service.get('target_text'))
    eligible = text(service.get('eligibility_text'))
    name = text(service.get('name'))
    conditions = target + ' ' + eligible
    checks = []
    notes = []
    conflicts = []
    # Provider names in a resident's eligibility do not make it an institution grant.
    institution = bool(re.search(r'상점|사업체|민간\s*상업\s*시설|기관|단체', target))
    residents = bool(
        re.search(r'시민|주민|가구|가정|여성|남성|청년|장애인|산모|이용자|어르신', target)
    )
    if institution and (re.search(r'사업자등록|소상공인\s*상점', eligible) or not residents):
        return None
    # Published district is not sufficient evidence of a residence requirement.
    places = set(
        re.findall(r'([가-힣]{2,5}구)\s*(?:에\s*)?(?:거주|주민등록|등록장애|주소)', conditions)
    )
    if places and context['city'] not in places:
        return None
    area_known = bool(places and context['city'] in places)
    if context['city'] == '강남구' and re.search(
        r'서울(?:특별)?시\s*(?:에\s*)?(?:거주|주민등록|내\s*전\s*지역)|서울시민', conditions
    ):
        area_known = True
    if context['city'] == '춘천시' and re.search(
        r'강원(?:특별자치)?도\s*(?:거주|주민등록)|춘천시민', conditions
    ):
        area_known = True
    if not area_known:
        checks.append('선택 지역 주민의 이용 가능 여부·거주 요건 확인')
    if len(places) > 1:
        checks.append('지원 유형별 이용 지역 확인')
    # Child age is not the parent's age. Leave family eligibility for confirmation.
    family = bool(re.search(r'출산|산후|산모|육아|양육|입양|신혼|다자녀', name))
    primary = re.split(r'제외\s*대상|지원\s*내용|지원\s*금액|신청\s*방법', target, maxsplit=1)[0]
    ranges = age_ranges(primary)
    secondary = age_ranges(eligible)
    benefits = age_ranges(service.get('benefit_text') or service.get('support_text'))
    unrestricted = bool(
        re.search(r'나이.{0,4}무관|연령.{0,4}(?:무관|제한\s*없)|누구나|모든\s*연령', primary)
    )
    if family:
        checks.append('부모·자녀의 연령과 가족 관련 자격을 구분해 확인')
        ranges = []
        secondary = []
    if band:
        if ranges and not overlap(ranges, band):
            if (secondary and overlap(secondary, band)) or unrestricted:
                conflicts.append('지원 대상과 이용 조건의 연령 범위가 달라 원문 확인 필요')
            else:
                return None
        elif not ranges and secondary and not overlap(secondary, band):
            return None
        effective = ranges or secondary
        if ranges and secondary and overlap(ranges, band) != overlap(secondary, band):
            conflicts.append('지원 대상과 이용 조건의 연령 범위가 달라 원문 확인 필요')
        if secondary and benefits and overlap(secondary, band) != overlap(benefits, band):
            conflicts.append('세부 조건과 지원 내용의 연령 범위가 달라 원문 확인 필요')
        if benefits and not fully_covered(benefits, band):
            notes.append('일부 혜택은 별도 연령 조건이 있습니다. 기본 서비스와 구분해 확인하세요.')
        if band and effective and overlap(effective, band) and not fully_covered(effective, band):
            checks.append('연령대 중 일부만 해당하므로 실제 나이·예외 요건 확인')
        if not effective and not unrestricted:
            checks.append('명시된 연령 조건이 없어 세부 대상 연령 확인')
    else:
        effective = []
        checks.append('검토할 실제 나이·사업별 연령 조건 확인')
    for pattern, question in (
        (r'장애|보장구|보조기', '장애 등록·상태·이용 기기 조건 확인'),
        (r'중위\s*소득|수급|차상위|저소득|재산|연소득', '소득·재산·수급 자격 확인'),
        (r'취업|미취업|경력단절|구직|자영업|사업자', '취업·경력·사업자 등 경제활동 조건 확인'),
        (r'여성|남성|산모', '개인의 성별 및 해당 지원 유형의 대상 조건 확인'),
        (r'출산|임신|산후|육아|양육|입양', '출산·양육 등 가족 관련 자격과 신청 기한 확인'),
        (r'무주택|임차|주택|주거|전월세', '주거·주택 소유·계약 조건 확인'),
        (r'학자금|신용유의|연체|채무|대출', '대출·채무·신용 등 금융 관련 자격 확인'),
        (r'1인\s*가구|독거|한부모|다자녀', '가구 형태·가족 조건 확인'),
        (r'유공|보훈|유족', '국가유공·보훈 등 별도 자격 확인'),
        (r'외로움|고립감|고립위험', '본인의 이용 의향과 사업별 등록·상담 절차 확인'),
        (r'도움이 필요한|돌봄이 필요한|어려운', '실제 지원 필요와 이용 의향 확인'),
        (r'거주.{0,10}(?:개월|년)|(?:개월|년).{0,15}거주', '거주 기간 및 주민등록 요건 확인'),
    ):
        if re.search(pattern, conditions):
            checks.append(question)
    checks = list(dict.fromkeys(conflicts + checks))
    bare_age_area = bool(
        re.fullmatch(r'(?:만\s*)?\d+\s*세\s*(?:이상|이하)\s*서울(?:특별)?시민', target)
    ) and eligible in ('', '.', '-')
    if not checks and not bare_age_area:
        checks.append('사업별 세부 대상 자격과 제외 조건 확인')
    # Explicit age+area agreement is not a finding of individual entitlement.
    level = 'data_check' if conflicts else 'needs_confirmation' if checks else 'age_area'
    label = {
        'data_check': '자료 확인 필요',
        'needs_confirmation': '추가 조건 확인',
        'age_area': '연령·지역 조건 부합',
    }[level]
    age_note = (
        f"{context['age']} 연령 범위와 사업 대상 연령이 겹칩니다."
        if band and effective and overlap(effective, band)
        else '개인 나이·세부 연령 조건은 별도 확인이 필요합니다.'
        if not unrestricted
        else '대상 설명에 연령 제한 없이 누구나 이용할 수 있다고 명시되어 있습니다.'
    )
    area_note = (
        f"{context['city']} 주민을 포함하는 거주 조건이 확인됩니다."
        if area_known
        else '사업 게시 지역만으로 이용 가능 여부를 확정하지 않습니다.'
    )
    criterion = area_note + ' ' + age_note
    return {
        'service': service,
        'key': service_key(service),
        'sector': sector(service),
        'match_level': level,
        'match_label': label,
        'criteria_summary': criterion,
        'additional_checks': checks or ['이용 절차·운영 장소·현재 접수 여부 확인'],
        'benefit_notes': notes,
        'score': 0,
        'browse_priority': 0
        if band and area_known and effective and fully_covered(effective, band)
        else 1
        if area_known and (effective or unrestricted)
        else 2
        if area_known
        else 3,
        'reasons': [
            {
                'category': '지역·연령 조회',
                'metrics': [],
                'service_terms': [],
                'check_question': criterion,
                'purpose_evidence': excerpts(service, ['target_text', 'eligibility_text']),
            }
        ],
        'qualification': '지역·연령별 검토 후보이며 개인의 지원 필요·이용 자격을 확정하지 않습니다.',
    }


def browse_services(context, services=None, today=None):
    if (
        (context.get('age') and context.get('age') not in AGE_BANDS)
        or not context.get('district')
        or not context.get('city')
    ):
        return []
    catalog = services if services is not None else service_candidates(context['city'])
    matches = [m for s in catalog if (m := evaluate(s, context, today)) is not None]
    rank = {'age_area': 0, 'needs_confirmation': 1, 'data_check': 2}
    return sorted(
        matches,
        key=lambda m: (
            rank[m['match_level']],
            m['browse_priority'],
            SECTORS.index(m['sector']),
            m['service']['name'],
        ),
    )

"""관측된 통신·이동 변화에서 확인할 지원 목적을 DB2 사업 내용과 연결합니다.

대상·신청 문구는 관련성 근거로 쓰지 않으며 개인의 고립 상태·감소 원인·자격을
추정하지 않습니다. 사업 목적 관련 후보와 추가 조건 확인 후보를 구분합니다.
"""
import re
from backend.db.mission_store import reference_services, service_candidates, service_key

SERVICE_FIELDS = ['name','summary','benefit_text','support_text','description','content']
DOMAIN_METRICS = {'communication':('call_contacts','text_contacts'),
                  'mobility':('weekday_move_count','weekend_move_count')}
METRIC_LABELS = {'call_contacts':'전화 연락','text_contacts':'문자 연락',
                 'weekday_move_count':'평일 이동','weekend_move_count':'휴일 이동'}
# Bare 방문/문화/지원/상담 are deliberately not relevance criteria.
PURPOSES = (
    {'category':'관계·교류 활동','domains':('communication','mobility'),
     'patterns':(r'사회적\s*(?:관계|고립)',r'관계\s*(?:형성|회복|망)',r'사회\s*참여',
                 r'사회\s*활동',r'교류',r'소통',r'모임',r'여가',r'문화\s*활동'),
     'question':'연락·외출 변화의 배경과 교류 활동 참여 의향을 확인하세요.'},
    {'category':'안부·정서 지원','domains':('communication',),
     'patterns':(r'안부\s*(?:확인|서비스|전화|지원)',r'말벗',r'외로움',r'정서\s*지원',r'심리\s*상담',r'마음\s*건강'),
     'question':'안부 확인이나 상담을 원하는지 확인하세요. 연락 감소만으로 필요를 확정하지 않습니다.'},
    {'category':'외출·이동 지원','domains':('mobility',),
     'patterns':(r'병원\s*(?:방문|이용)?.{0,12}동행',r'건강\s*동행',r'이동\s*(?:지원|권)',
                 r'외출\s*(?:지원|동행)',r'교통비',r'버스\s*요금',r'휠체어',r'보장구'),
     'question':'외출·이동에 실제 어려움이 있는지와 원하는 지원을 먼저 확인하세요.'},
)
REFERENCE_TERMS = ['사회참여','교류','모임','고립','안부','말벗','외로움','정서지원',
                   '심리상담','병원','동행','이동지원','교통비','휠체어']


def joined_text(item, fields):
    return ' '.join(str(item.get(field) or '') for field in fields)


def detected_domains(evidence):
    """같은 사례의 두 지표가 함께 탐지된 영역만 사용합니다."""
    grouped = {}
    for row in evidence:
        if row.get('is_risk_signal') is not True:
            continue
        metric = row.get('metric')
        if metric not in METRIC_LABELS:
            metric = next((k for k,v in METRIC_LABELS.items() if v in row.get('metric_label','')),None)
        if not metric:
            continue
        case = row.get('case_id') or (row.get('행정동명'),row.get('기준연월'),row.get('age_label'))
        grouped.setdefault(case,{})[metric] = row
    result = {}
    for domain, metrics in DOMAIN_METRICS.items():
        labels = list(dict.fromkeys(rows[m].get('metric_label',METRIC_LABELS[m])
            for rows in grouped.values() if all(m in rows for m in metrics) for m in metrics))
        if labels:
            result[domain] = labels
    return result


def purpose_text(value):
    """지원 내용 열에 섞인 신청·구비서류 문단을 잘라냅니다."""
    value = re.sub(r'https?://\S+', '', str(value or ''))
    return re.split(r'(?:신청\s*(?:방법|절차|서류)|구비\s*서류|접수\s*(?:방법|절차))\s*[:：]?',value,maxsplit=1)[0]


def additional_checks(service, categories):
    text = joined_text(service,['target_text','eligibility_text'])
    checks = []
    if '외출·이동 지원' in categories:
        checks.append('외출·이동 지원의 실제 필요와 본인의 이용 의향 확인')
        if re.search(r'병원|건강\s*동행', joined_text(service,SERVICE_FIELDS)):
            checks.append('병원 이용 시 동행 도움이 필요한지 확인')
    for pattern, question in (
        (r'등록\s*장애인|장애\s*등록|장애인|장애의 정도','사업에서 요구하는 장애·이용 기기 조건 확인'),
        (r'1인\s*가구|독거','사업에서 요구하는 가구 형태 확인'),
        (r'중위\s*소득|수급|차상위|저소득','소득·수급 등 추가 자격과 비용 조건 확인'),
        (r'만?\s*\d+\s*세|청년|청소년|어르신|고령|아동','사업 대상 연령과 선택 연령대의 포함 여부 확인'),
        (r'임산부|산모|임신|출산|산후','임신·출산·산후 등 사업에서 요구하는 대상 요건 확인'),
        (r'시설|업체|기관|상점','주민이 직접 이용하는 사업인지, 기관·시설 대상 사업인지 확인'),
    ):
        if re.search(pattern,text):
            checks.append(question)
    checks.append('이용 가능 지역·현재 접수 여부·세부 자격은 원문 및 운영기관 확인')
    return list(dict.fromkeys(checks))


def match_services(city, evidence, services=None):
    """관련 후보만 반환합니다. score는 목적 분류 수이며 적합 확률이 아닙니다."""
    domains = detected_domains(evidence)
    if not domains:
        return []
    if services is None:
        services = service_candidates(city)
    matched = []
    for service in services:
        sources = {field:purpose_text(service.get(field)) for field in SERVICE_FIELDS}
        # Social participation may be an indirect outcome of transport/equipment.
        # It does not turn the actual service into a contact/relationship activity.
        mobility_offer = re.search(r'교통비|버스\s*요금|휠체어|보장구|보조기[구기]|건강\s*동행|병원.{0,12}동행',str(service.get('name') or ''))
        reasons = []
        for purpose in PURPOSES:
            if mobility_offer and purpose['category'] != '외출·이동 지원':
                continue
            related = [d for d in purpose['domains'] if d in domains]
            if not related:
                continue
            hits = []
            for field,value in sources.items():
                for pattern in purpose['patterns']:
                    hit = re.search(pattern,value)
                    if hit:
                        hits.append({'field':field,'term':hit.group(),
                                     'excerpt':value[max(0,hit.start()-35):hit.end()+90].strip()})
            if hits:
                reasons.append({'category':purpose['category'],
                    'metrics':list(dict.fromkeys(label for d in related for label in domains[d])),
                    'service_terms':list(dict.fromkeys(h['term'] for h in hits)),
                    'purpose_evidence':hits,'check_question':purpose['question']})
        if not reasons:
            continue
        categories = [r['category'] for r in reasons]
        checks = additional_checks(service,categories)
        # No restriction found in text does NOT mean eligibility is confirmed.
        conditional = len(checks)>1
        matched.append({'service':service,'key':service_key(service),'reasons':reasons,
            'score':len(reasons),'match_level':'needs_confirmation' if conditional else 'purpose',
            'match_label':'추가 조건 확인 후보' if conditional else '지원 목적 관련 후보',
            'additional_checks':checks,'qualification':'지원 필요나 이용 자격을 판정한 결과가 아닙니다.'})
    matched.sort(key=lambda item:(item['match_level']=='needs_confirmation',item['service']['name']))
    return matched


def reference_matches(city, evidence, services=None):
    """다른 지역의 사업은 이용 후보와 분리한 기획 참고 사례입니다."""
    if not detected_domains(evidence):
        return []
    if services is None:
        services = reference_services(city,REFERENCE_TERMS)
    return match_services(city,evidence,services)

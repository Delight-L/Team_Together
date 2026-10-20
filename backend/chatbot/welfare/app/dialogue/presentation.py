"""답변용 근거 표현. 검색·서명 원본은 유지하고 AI에는 읽기 쉬운 자료만 전달합니다."""
import re


def requested_fields(question):
    """명시적으로 물은 항목만 고릅니다. 사업 추천은 기본 요약을 사용합니다."""
    fields = []
    for words, key, label in (
        (('대상', '자격', '조건'), 'target', '자료에 적힌 이용 대상'),
        (('신청', '절차', '서류'), 'procedure', '자료에 적힌 신청 방법'),
        (('기관', '문의', '연락처'), 'agency', '담당 기관'),
        (('기간', '언제', '운영', '모집', '접수'), 'period', '기간 안내'),
    ):
        if any(word in question for word in words):
            fields.append((key, label))
    return fields


def brief_description(text):
    """첫 문장이 대상·담당 안내여도 원문에 있는 지원 활동을 먼저 발췌합니다."""
    text = re.sub(r'\s+', ' ', str(text)).strip()
    sentences = re.split(r'(?<=[.!?。])\s+', text)
    activity = re.compile(r'제공|지원|방문|동행|상담|교육|돌봄|안부|응급|정서|복약|활동|지급|급식|배달|대여|감면|연계|보조|기능')
    # 대상·담당 기관을 소개하는 문장보다 실제 지원 내용이 있는 문장을 우선합니다.
    candidates = [s for s in sentences if activity.search(s) and not (
        re.search(r'대상\s*조건|담당\s*기관|과\s*담당', s)
        and not re.search(r'제공|방문|동행|상담|교육|지급|응급|복약|기능', s))]
    first = candidates[0] if candidates else sentences[0]
    return first if len(first) <= 160 else first[:160].rstrip() + '…'


def record_cautions(record):
    return [label for key, label in (('expired', '종료된 사업'),
            ('reference_only', '다른 지역 참고 사례'), ('application_closed', '접수 종료'),
            ('application_future', '접수 시작 전')) if record.get(key)]

FIELDS = {
    'name': '사업명', 'description': '지원 내용', 'target': '자료에 적힌 이용 대상', 'agency': '담당 기관',
    'source': '출처', 'pages': '문서 페이지', 'url': '원문 주소', 'application_url': '자료상 신청 주소',
    'region': '자료에 적힌 지역', 'procedure': '자료에 적힌 신청 방법', 'plan_period': '당시 계획 기간',
    'period': '기간 안내', 'effective_start': '적용 시작일', 'effective_end': '적용 종료일',
    'application_start': '접수 시작일', 'application_end': '접수 종료일',
    'record_kind': '자료 구분', 'status': '자료 상태', 'notes': '주의사항',
}
INTERNAL_FIELDS = re.compile(
    r'\b(?:source_type|record_kind|current_operation_verified|application_details_verified|'
    r'eligibility_reviewed|reference_only|snapshot_hash|captured_at|collected_at|'
    r'application_closed|application_future|true|false)\b', re.I)


def answer_material(context, records):
    readable = []
    for number, record in enumerate(records, 1):
        item = {'자료 번호': number, **{label: record[key] for key, label in FIELDS.items() if record.get(key)}}
        if record.get('support_role') == 'living':
            item['안내 구분'] = '함께 확인할 생활비 지원 · 직접 돌봄 사업은 아님'
        item['자료 유형'] = {'document': '정책 문서·검토 자료', 'api': '공공 API 안내',
            'service': '등록 복지서비스', 'session': '사업 회차 공고'}.get(record.get('source_type'), '복지 자료')
        item['확인 상태'] = {
            label: '확인됨' if record.get(key) else '미확인'
            for key, label in (('current_operation_verified', '현재 운영'),
                              ('eligibility_reviewed', '이용 자격 검토'),
                              ('application_details_verified', '신청 절차'))}
        if record.get('reference_only'):
            item['지역 주의'] = '다른 지역의 참고 사례예요. 현재 선택한 지역에서 신청할 수 있는지는 확인되지 않았어요.'
        if record.get('collected_at'):
            item['수집 시점'] = str(record['collected_at'])[:10] + ' (이 날짜가 지금 운영 중이라는 뜻은 아니에요)'
        if str(record.get('effective_end') or '').startswith('9999'):
            item['적용 종료일'] = '종료일 미정 (상시 모집의 근거가 아님)'
        if record.get('contacts'):
            item['연락처 안내'] = [', '.join(str(v) for v in c.values()) if isinstance(c, dict) else str(c)
                                for c in record['contacts']]
        readable.append(item)
    screen = {label: context[key] for key, label in (
        ('city', '지역'), ('district', '행정동'), ('month', '분석 기준월'),
        ('age', '선택 연령'), ('analysis', '지역분석근거')) if key in context}
    return {'화면맥락': screen, '자료목록': readable}


def contains_internal_metadata(answer, records):
    if INTERNAL_FIELDS.search(answer):
        return True
    return any(re.match(r'(?:plan-\d+|db:\[|[a-z][a-z0-9_]*-\d+)', str(r.get('id', '')))
               and str(r['id']) in answer for r in records)

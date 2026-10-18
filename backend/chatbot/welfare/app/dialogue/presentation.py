"""답변용 근거 표현. 검색·서명 원본은 유지하고 AI에는 읽기 쉬운 자료만 전달합니다."""
import re

FIELDS = {
    'name': '사업명', 'description': '지원 내용', 'target': '자료상 대상', 'agency': '담당 기관',
    'source': '출처', 'pages': '문서 페이지', 'url': '원문 주소', 'application_url': '자료상 신청 주소',
    'region': '자료상 지역', 'procedure': '자료상 절차', 'plan_period': '당시 계획기간',
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
        item['자료 유형'] = {'document': '정책 문서·검토 자료', 'api': '공공 API 안내',
            'service': '등록 복지서비스', 'session': '사업 회차 공고'}.get(record.get('source_type'), '복지 자료')
        item['확인 상태'] = {
            label: '확인됨' if record.get(key) else '미확인'
            for key, label in (('current_operation_verified', '현재 운영'),
                              ('eligibility_reviewed', '이용 자격 검토'),
                              ('application_details_verified', '신청 절차'))}
        if record.get('reference_only'):
            item['지역 주의'] = '다른 지역 참고 사례이며 선택 지역의 신청 가능 사업으로 확인된 것이 아님'
        if record.get('collected_at'):
            item['수집 시점'] = str(record['collected_at'])[:10] + ' (운영 확인일 아님)'
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

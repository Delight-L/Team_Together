"""보고서 탭과 챗봇이 공유하는 근거 기반 약식보고서 에이전트."""

SECTIONS = (('summary', '검토 요지'), ('situation', '지역 현황'),
            ('proposal', '복지서비스 연계·추진 제안'), ('next_steps', '향후 조치'))
LIMITS = {'title': 80, 'summary': 350, 'situation': 900, 'proposal': 1200, 'next_steps': 600}


def _fit_blocks(blocks, limit):
    """문장 중간을 잘라 의미를 바꾸지 않고, 긴 근거는 원본 확인으로 안내합니다."""
    result, omitted = [], False
    for block in blocks:
        if len('\n'.join(result + [block])) <= limit - 65:
            result.append(block)
        else:
            omitted = True
    if omitted:
        result.append('긴 근거 일부는 분량상 생략함. 지역 분석·사업 검토 기록에서 원문 확인 필요')
    return '\n'.join(result)


def generate_draft(context, workflow):
    """외부 AI 없이 저장된 기록을 구성합니다. 첨부 예시는 업무 사실로 쓰지 않습니다."""
    if not context.get('district'):
        raise ValueError('보고서를 작성할 행정동을 먼저 선택하세요.')
    if 2 not in workflow.get('done', []) or not workflow.get('analysis_evidence'):
        raise ValueError('분석 근거 확인과 사업 매칭 검토 기록 저장을 먼저 완료하세요.')
    region = f"{context['city']} {context['district']}"
    signals = [r for r in workflow['analysis_evidence'] if r.get('is_risk_signal')]
    situation = [f"대상 지역: {region} / 기준월: {context['month']}"]
    for row in signals[:3]:
        situation.append(str(row.get('explanation') or
                             f"{row.get('metric_label', '지표')}: 변화 후보로 표시됨. 상세 근거 확인 필요"))
    if len(signals) > 3:
        situation.append(f'변화 후보 {len(signals)}건 중 3건 요약. 전체 근거는 지역 분석 화면에서 확인')
    if not signals:
        situation.append('저장된 분석에서 변화 후보가 확인되지 않음. 자료 충분 여부와 현장 상황은 별도 확인 필요')
    situation.append('지역 집계자료의 변화로 개인의 고립 여부나 변화 원인을 확정할 수 없음')
    saved_reviews = workflow.get('reviews', [])
    # 같은 사업을 재검토했다면 마지막 판단을 사용합니다.
    latest = {}
    for index, review in enumerate(saved_reviews):
        latest[review.get('service_key') or ('record', index)] = review
    reviews = list(latest.values())
    proposals = []
    for review in reviews[:4]:
        status = {'적합': '연계 가능성 검토 제안', '보류': '운영 조건 확인 후 재검토',
                  '부적합': '현재 연계 제안에서 제외'}.get(review.get('decision'), '담당자 판단 확인 필요')
        proposal = f"{review.get('name', '사업명 확인 필요')}: {status}\n- 검토 근거: {review.get('note', '확인 필요')}"
        snapshot = review.get('service_snapshot', {})
        if snapshot.get('detail_pending'):
            proposal += '\n- 상세정보 수집·재확인 대기. 이용 조건은 원문 및 운영기관 확인 필요'
        if review.get('source_url'):
            proposal += '\n- 안내 원문: ' + str(review['source_url'])
        proposals.append(proposal)
    if len(reviews) > 4:
        proposals.append(f'전체 {len(reviews)}건 중 4건 요약. 나머지는 사업 검토 기록에서 확인')
    if not proposals:
        proposals.append('저장된 사업 검토 내용 확인 필요')
    viable = any(r.get('decision') == '적합' for r in reviews)
    summary = (f'{region}의 지역 분석 및 사업 검토 결과를 바탕으로 '
               + ('관련 복지서비스 연계 가능성을 검토하고자 함' if viable else
                  '서비스 이용 조건과 현장 수요를 추가 확인한 후 연계 여부를 검토하고자 함'))
    from db.mission_store import review_revision
    return {'title': f"{context['district']} 복지서비스 연계 검토보고",
            'summary': summary, 'situation': _fit_blocks(situation, LIMITS['situation']),
            'proposal': _fit_blocks(proposals, LIMITS['proposal']),
            'next_steps': '운영기관에 지원 대상·거주·연령·소득·신청 기간 및 모집 여부 확인\n현장 수요와 담당 기관 의견을 확인한 후 연계·추진 여부 검토',
            'context': {k: context[k] for k in ('city', 'district', 'month')},
            'review_id': review_revision(workflow),
            'review_snapshot': saved_reviews,
            'mode': '저장된 근거로 구성 · 외부 AI 호출 없음'}


def validate_content(content):
    if not isinstance(content, dict):
        raise ValueError('보고서 초안 내용이 필요합니다.')
    result = {}
    for key, limit in LIMITS.items():
        value = content.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f'보고서 {key} 항목은 1~{limit}자로 입력하세요.')
        if any(ord(c) < 32 and c not in '\n\r\t' for c in value):
            raise ValueError('보고서에 사용할 수 없는 문자가 있습니다.')
        result[key] = value.strip()
    return result


def report_reply(context, workflow):
    try:
        draft = generate_draft(context, workflow or {})
    except ValueError as exc:
        return {'answer': str(exc), 'mode': '보고서 작성 에이전트 · 준비 필요',
                'actions': [{'label': '보고서 작성 열기', 'view': 'report'}]}
    answer = draft['title'] + '\n\n' + '\n\n'.join(
        f'□ {label}\n{draft[key]}' for key, label in SECTIONS)
    return {'answer': answer, 'mode': '보고서 작성 에이전트 · ' + draft['mode'],
            'actions': [{'label': '초안을 보고서 탭에서 수정', 'view': 'report', 'reportDraft': draft}]}


def is_draft_request(question):
    text = question.replace(' ', '')
    return '보고서' in text and any(word in text for word in ('작성해', '만들어', '생성해', '초안작성', '초안생성'))

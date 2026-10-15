"""저장된 업무 근거 중 보고서에 포함할 항목을 선택합니다."""

def latest_reviews(reviews):
    latest = {}
    for index, review in enumerate(reviews):
        latest[review.get('service_key') or f'record:{index}'] = review
    return latest


def select_material(workflow, selection):
    rows = workflow.get('analysis_evidence', [])
    reviews = latest_reviews(workflow.get('reviews', []))
    if selection is None:
        return rows, list(reviews.values()), {}
    if not isinstance(selection, dict) or set(selection) - {'metrics', 'services', 'include_note', 'include_followup'}:
        raise ValueError('보고서 포함 항목이 올바르지 않습니다.')
    for key, allowed in [('metrics', {row['metric_label'] for row in rows}), ('services', set(reviews))]:
        values = selection.get(key, [])
        if not isinstance(values, list) or any(not isinstance(value, str) or value not in allowed for value in values):
            raise ValueError('저장된 근거에서 보고서 포함 항목을 선택하세요.')
    for key in ('include_note', 'include_followup'):
        if type(selection.get(key, False)) is not bool:
            raise ValueError('업무 기록 포함 여부가 올바르지 않습니다.')
    return ([row for row in rows if row['metric_label'] in selection.get('metrics', [])],
            [review for key, review in reviews.items() if key in selection.get('services', [])], selection)


def record_sections(record, selection):
    note = record.get('note', '') if selection.get('include_note') else ''
    followup = ''
    if selection.get('include_followup'):
        lines = [record.get('followup', '')]
        if record.get('assignee'):
            lines.append('담당자·인계 대상: ' + record['assignee'])
        if record.get('due'):
            lines.append('확인 기한: ' + record['due'])
        if record.get('status'):
            lines.append('후속 조치 상태: ' + record['status'])
        followup = '\n'.join(line for line in lines if line)
    return note, followup

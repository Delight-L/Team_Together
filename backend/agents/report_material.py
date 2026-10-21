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
    if not isinstance(selection, dict) or set(selection) - {'metrics', 'services'}:
        raise ValueError('보고서 포함 항목이 올바르지 않습니다.')
    for key, allowed in [
        ('metrics', {row['metric_label'] for row in rows}),
        ('services', set(reviews)),
    ]:
        values = selection.get(key, [])
        if not isinstance(values, list) or any(
            not isinstance(value, str) or value not in allowed for value in values
        ):
            raise ValueError('저장된 근거에서 보고서 포함 항목을 선택하세요.')
    return (
        [row for row in rows if row['metric_label'] in selection.get('metrics', [])],
        [review for key, review in reviews.items() if key in selection.get('services', [])],
        selection,
    )

"""업무 API: 분석 확인 → 근거 검토 → 사업 검토 → 보고서 저장, 그리고 업무 기록(검토·후속 조치).

업무 단계 번호(mission_store에 저장되는 done 값)
  0 분석 확인 저장 / 1 근거 검토 완료 / 2 사업 검토 저장 / 3 보고서 최종 저장
단계 순서는 mission_store.save_event가 서버에서 다시 검사합니다.
"""
import hashlib
import json
import logging
from datetime import date, datetime

from backend.agents import report_writer, service_matching, service_eligibility
from backend.db import experience_store, mission_store
from backend.services import report
from backend.api import limits, sessions
from backend.api.common import ApiError, Response, dashboard_data, evidence_for, region_context

# 사업 검토를 저장할 때 함께 남기는 사업 정보 항목
SERVICE_FIELDS = (
    'source_id', 'service_id', 'name', 'province', 'district', 'summary',
    'target_text', 'eligibility_text', 'benefit_text', 'application_text',
    'effective_start', 'effective_end', 'source_url', 'detail_pending',
    'detail_checked_at', 'source_modified', 'residency_text',
)


def report_filename(context, revision=None):
    suffix = f"_{revision}차" if revision else ''
    age = '_' + context['age'] if context.get('age') else ''
    return f"사업검토보고_{context['district']}{age}_{context['month']}{suffix}.docx"


def load_workflow(context):
    """이 지역·동·기준월의 업무 진행 상황입니다. 아직 없으면 빈 dict입니다."""
    return mission_store.load(context)


def work_context(request):
    """업무 저장 API가 공통으로 쓰는 (context, 분석 자료, 이 동의 분석 결과)를 만듭니다."""
    data = dashboard_data()
    context = region_context(request, data)
    evidence = evidence_for(data, context)
    if not evidence:
        raise ValueError('선택 지역·월의 실제 분석 결과가 없습니다.')
    return context, data, evidence


# ── 조회(GET) ─────────────────────────────────────────────

def missions(request):
    """GET /api/missions: 로그인한 담당자의 지역 업무 목록(업무 기록 화면).

    사업 검토를 저장한 업무에 더해, 사업 검토 전에 검토·후속 조치만 저장한 지역도 빈 업무로 보여 줍니다.
    """
    items = []
    for key, workflow in mission_store.load_all().items():
        parts = json.loads(key)
        owner, city, district, month = parts[:4]
        age = parts[4] if len(parts) > 4 else None
        if owner == request.user['id']:
            items.append({'city': city, 'district': district, 'month': month, **({'age':age} if age else {}), 'workflow': workflow})
    seen = {(item['city'], item['district'], item['month'], item.get('age', '')) for item in items}
    for scope in experience_store.saved_scopes():
        if (scope['city'], scope['district'], scope['month'], scope.get('age', '')) not in seen:
            items.append(scope | {'workflow': {}, 'record_only': True})
    return {'items': items}


def with_analysis_note(current, data):
    """저장된 근거가 지금 화면의 분석 버전과 다르면 analysis_changed로 알려 줍니다."""
    saved = current.get('analysis_run_id')
    return dict(current, analysis_changed=bool(saved) and saved != str(data.get('runId', '')))


def workflow(request):
    """GET /api/workflow: 선택한 동의 업무 진행 상황."""
    data = dashboard_data()
    context = region_context(request, data)
    return with_analysis_note(load_workflow(context), data)


def experience(request):
    """GET /api/experience: 선택한 동의 검토·후속 조치 기록."""
    context = region_context(request, dashboard_data())
    return experience_store.load(context)


def experience_history(request):
    """GET /api/experience/history: 같은 동의 다른 기준월 기록."""
    context = region_context(request, dashboard_data())
    return {'items': experience_store.regional_history(context)}


def services(request):
    """GET /api/services: 선택한 동의 복지사업 후보(DB2). 조회는 업무 완료 상태를 바꾸지 않습니다."""
    context, data, evidence = work_context(request)
    current = load_workflow(context)
    evidence = current.get('analysis_evidence') or evidence
    try:
        matches = service_eligibility.browse_services(context)
        references = service_matching.reference_matches(context['city'], evidence)
    except Exception:
        logging.exception('DB2 service lookup failed')
        raise ApiError(503, 'DB2 사업 조회에 실패했습니다. .env 연결 및 DB 권한을 확인하세요.')
    # references: 다른 지역 참고 사례(기획 참고용). 검토 저장 대상이 아닙니다.
    return {'matches': matches, 'references': references}


def saved_report(request):
    """GET /api/report: 최종 저장한 Word 보고서를 내려받습니다. revision을 주면 그 차수 저장본입니다."""
    context = region_context(request, dashboard_data())
    revision = request.params.get('revision')
    if revision is not None:
        if not str(revision).isdigit():
            raise ValueError('보고서 차수가 올바르지 않습니다.')
        revision = int(revision)
    document = mission_store.load_report(context, revision)
    if not document:
        raise ValueError('저장된 보고서가 없습니다.')
    return Response(document, filename=report_filename(context, revision))


def saved_report_versions(request):
    """GET /api/report/versions: 이 업무에서 저장한 보고서 목록(최신순)."""
    context = region_context(request, dashboard_data())
    return {'items': mission_store.report_versions(context)}


def report_draft_file(request):
    """GET /api/report/draft: 저장 전에 확인할 Word 초안을 내려받습니다."""
    context = region_context(request, dashboard_data())
    draft = sessions.get_preview(request.params.get('token'), request.user, 'report')
    if draft['identity'] != mission_store.identity(context):
        raise ValueError('초안 지역·월과 다릅니다.')
    return Response(draft['document'], filename=draft['record']['filename'])


# ── 저장(POST) ────────────────────────────────────────────

def experience_save(request):
    """POST /api/experience: 검토·후속 조치 기록을 저장합니다."""
    context = region_context(request, dashboard_data())
    return experience_store.save(context, request.params)


def analysis_start(data, evidence):
    """업무를 처음 저장할 때 근거로 기록할 지금 분석 결과(mission_store.save_event의 start)."""
    return {'run_id': data['runId'], 'evidence': evidence, 'source_note': data['source']}


def report_workflow(context, data, evidence):
    """보고서에 쓸 업무 상태입니다. 아직 업무가 없으면 지금 분석 결과를 근거로 둡니다(저장하지 않음).

    사업 검토 없이도 대화·구상·업무 기록으로 보고서를 만들 수 있게 합니다.
    두 번째 값은 최종 저장 때 업무 근거로 기록할 start이며, 이미 근거가 있으면 None입니다.
    """
    current = load_workflow(context)
    if 0 in current.get('done', []):
        return current, None
    start = analysis_start(data, evidence)
    return dict(current, analysis_run_id=start['run_id'], analysis_evidence=evidence,
                analysis_source=start['source_note']), start


def report_content(request):
    """POST /api/report/content: 분석 근거·사업 검토·업무 기록으로 보고서 문장 초안을 만듭니다.

    ai=true이면 AI가 문장을 다듬고, 저장된 근거와 대조를 통과한 경우에만 그 문장을 씁니다.
    """
    context, data, evidence = work_context(request)
    use_ai = request.params.get('ai') is True
    if use_ai:
        limits.check_chat(request.user)  # AI 문장 다듬기도 보미 사용량에 포함합니다.
    selection = request.params.get('selection')
    current, _ = report_workflow(context, data, evidence)
    if request.params.get('include_record') is True and selection is None:
        # 보고서 탭의 '업무 기록 포함': 저장된 지표·사업 검토는 모두 넣고 업무 기록의 의견·후속 조치를 더합니다.
        from backend.agents.report_material import latest_reviews
        selection = {'metrics': [row['metric_label'] for row in current.get('analysis_evidence', [])],
                     'services': list(latest_reviews(current.get('reviews', []))),
                     'include_note': True, 'include_followup': True}
    experience = experience_store.load(context) if isinstance(selection, dict) and (selection.get('include_note') or selection.get('include_followup')) else None
    draft = report_writer.write_draft(context, current, use_ai=use_ai, selection=selection, experience=experience)
    # 업무를 아직 저장하지 않았어도 보고서 탭의 검토 도움말이 수치를 대조할 수 있게 쓴 근거를 함께 돌려줍니다.
    return dict(draft, analysis_evidence=current['analysis_evidence'], analysis_source=current['analysis_source'])


def report_proposal(request):
    """POST /api/report/proposal: 편집 중인 초안의 제안 칸만 최신 사업 검토로 다시 만듭니다.

    초안을 만든 뒤 사업 검토가 바뀌었을 때, 나머지 항목의 편집 내용을 지키며 근거 버전만 맞추는 용도입니다.
    업무 기록 포함 여부 등 초안의 선택은 유지하고, 사업은 지금 저장된 검토를 모두 넣습니다.
    """
    context, data, evidence = work_context(request)
    current, _ = report_workflow(context, data, evidence)
    selection = request.params.get('selection')
    if isinstance(selection, dict):
        from backend.agents.report_material import latest_reviews
        selection = dict(selection, services=list(latest_reviews(current.get('reviews', []))))
    elif selection is not None:
        raise ValueError('보고서 포함 항목이 올바르지 않습니다.')
    uses_record = isinstance(selection, dict) and (selection.get('include_note') or selection.get('include_followup'))
    draft = report_writer.generate_draft(context, current, selection, experience_store.load(context) if uses_record else None)
    return {key: draft.get(key) for key in ('proposal', 'review_id', 'review_snapshot', 'kind', 'selection', 'experience_version')}


def report_preview(request):
    """POST /api/report/preview: 작성 내용으로 Word 파일을 만들고, 확인용 토큰을 돌려줍니다.

    사업 검토가 없어도 됩니다. 업무가 아직 없으면 지금 분석 결과로 만들고, 그 근거를 토큰에 담아 두었다가
    최종 저장 때 업무 근거로 기록합니다. 확인한 파일과 저장되는 근거가 같게 하기 위해서입니다.
    """
    context, data, evidence = work_context(request)
    current, start = report_workflow(context, data, evidence)

    fields = {
        'author': request.text('author'),
        'department': request.text('department'),
        'opinion': request.text('opinion'),
    }
    # 이전 화면이나 임시 초안이 계정 ID를 보내도 보고서에는 담당자 이름을 씁니다.
    if fields['author'] == request.user['id']:
        from backend.services.accounts import DEMO_ACCOUNTS
        fields['author'] = DEMO_ACCOUNTS[request.user['id']]['name']
    content = None
    if 'content' in request.params:
        content = report_writer.validate_content(request.params['content'])
        if report_writer.PLANNING_PROPOSAL in content['proposal']:
            raise ValueError('제안 칸의 안내 문구를 지우고 구상·제안 내용을 직접 작성하세요.')
    if content:
        evidence_token = request.params['content'].get('evidence_token')
        if evidence_token:
            from backend.bomi.conversation import unpack
            saved_evidence = unpack(evidence_token, request.session_token, context)
            content['conversation_sources'] = saved_evidence.get('records', [])[:4]
        fields['opinion'] = content['next_steps']
        selection = request.params['content'].get('selection')
        from backend.agents.report_material import select_material
        select_material(current, selection)
        if selection and (selection.get('include_note') or selection.get('include_followup')):
            version = experience_store.load(context).get('version', 0)
            if request.params['content'].get('experience_version') != version:
                raise ValueError('업무 기록이 변경되었습니다. 저장한 최신 기록으로 초안을 갱신하세요.')
            content['experience_version'] = version
        if selection is not None:
            content['selection'] = selection
    contact = request.text('contact')

    for value in fields.values():
        if not value:
            raise ValueError('부서·작성자·최종 의견을 입력하세요.')
    if len(fields['author']) > 60 or len(fields['department']) > 100 or len(contact) > 80:
        raise ValueError('작성자 60자·부서 100자·연락처 80자 이내로 입력하세요.')
    # 초안을 만든 뒤 사업 검토가 바뀌었다면 예전 내용이므로 다시 만들게 합니다.
    if content and request.params.get('review_id') != mission_store.review_revision(current):
        raise ValueError('사업 검토 내역이 변경되었습니다. 보고서 초안을 다시 생성하세요.')

    document = report.build_report(
        context, current['analysis_evidence'], fields['author'], fields['department'], fields['opinion'],
        current['analysis_source'], workflow=current, content=content, contact=contact,
    )
    record = dict(fields)
    record['content'] = content
    record['contact'] = contact
    record['template'] = 'brief_report_v1'
    record['sha256'] = hashlib.sha256(document).hexdigest()
    record['filename'] = report_filename(context)
    record['review_id'] = mission_store.review_revision(current)
    record['_document'] = document

    preview = {'identity': mission_store.identity(context), 'document': document, 'record': record, 'start': start}
    token = sessions.store_preview(request.user, 'report', preview)
    return {'token': token}


def service_snapshot(service):
    """사업 정보를 저장할 수 있는 값으로 복사합니다. 날짜는 '2025-01-31' 같은 글자로 바꿉니다."""
    snapshot = {}
    for key in SERVICE_FIELDS:
        value = service.get(key)
        if isinstance(value, (date, datetime)):
            value = value.isoformat()
        snapshot[key] = value
    return snapshot


def workflow_start(request):
    """POST /api/workflow/start: ① 분석 확인 저장 — 이 동을 내 업무로 등록합니다."""
    context, data, evidence = work_context(request)
    with sessions.write_lock:
        mission_store.save_event(context, 0, {'run_id': data['runId'], 'evidence': evidence, 'source_note': data['source']})
        return with_analysis_note(load_workflow(context), data)


def workflow_restart(request):
    """POST /api/workflow/restart: 분석이 새로 적재된 업무를 최신 분석으로 다시 시작합니다.

    이전 진행 기록은 previous_rounds에 남고, 저장한 보고서는 차수 목록에 그대로 남습니다.
    """
    context, data, evidence = work_context(request)
    if request.params.get('confirmed') is not True:
        raise ValueError('다시 시작을 확인하세요.')
    with sessions.write_lock:
        mission_store.restart(context, {'run_id': data['runId'], 'evidence': evidence, 'source_note': data['source']})
        return with_analysis_note(load_workflow(context), data)


def workflow_confirm(request):
    """POST /api/workflow/confirm: ② 근거 검토 완료."""
    context, data, evidence = work_context(request)
    with sessions.write_lock:
        mission_store.save_event(context, 1, {'confirmed': True})
        return with_analysis_note(load_workflow(context), data)


def workflow_review(request):
    """POST /api/workflow/review: 조회한 복지사업 하나에 대한 검토 결과를 저장합니다.

    첫 검토라면 지금 분석 결과를 업무 근거로 함께 저장합니다(지역 분석 화면을 거치지 않아도 됩니다).
    """
    context, data, evidence = work_context(request)
    checks = request.params.get('checks', {})
    if not isinstance(checks, dict) or any(key not in {'residency', 'eligibility', 'application'} or type(value) is not bool for key, value in checks.items()):
        raise ValueError('사업 이용 조건 확인 항목이 올바르지 않습니다.')
    need = request.params.get('need', '')
    if need not in ['', '관계·사회참여', '안부·돌봄', '생활·경제']:
        raise ValueError('지원 목적을 목록에서 선택하세요.')
    with sessions.write_lock:
        current = load_workflow(context)
        chosen = None
        # 사업 조회와 저장에 같은 지역·연령 조건을 적용합니다.
        for match in service_eligibility.browse_services(context):
            if match['key'] == request.params.get('serviceKey'):
                chosen = match
                break
        if chosen is None:
            raise ValueError('조회한 실제 사업을 선택하세요.')
        mission_store.save_event(context, 2, {
            'service_key': chosen['key'],
            'name': chosen['service']['name'],
            'decision': request.params.get('decision'),
            'note': request.text('note'),
            'checks': checks,
            'need': need,
            'reasons': chosen['reasons'],
            'source_url': chosen['service'].get('source_url'),
            'service_snapshot': service_snapshot(chosen['service']),
        }, start=analysis_start(data, evidence))
        return with_analysis_note(load_workflow(context), data)


def report_save(request):
    """POST /api/report: 확인한 Word 초안을 최종 보고서로 저장합니다."""
    context, data, evidence = work_context(request)
    if request.params.get('confirmed') is not True:
        raise ValueError('보고서 최종 확인이 필요합니다.')
    token = request.params.get('token')
    with sessions.write_lock:
        draft = sessions.get_preview(token, request.user, 'report')
        if draft['identity'] != mission_store.identity(context):
            raise ValueError('초안 지역·월과 다릅니다.')
        record = dict(draft['record'])
        record['confirmed'] = True
        mission_store.save_event(context, 3, record, start=draft.get('start'))
        sessions.remove_preview(token)
        return with_analysis_note(load_workflow(context), data)

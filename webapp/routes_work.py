"""업무 API: 분석 확인 → 근거 검토 → 사업 검토 → 보고서 저장, 그리고 업무 기록(검토·후속 조치).

업무 단계 번호(mission_store에 저장되는 done 값)
  0 분석 확인 저장 / 1 근거 검토 완료 / 2 사업 검토 저장 / 3 보고서 최종 저장
단계 순서는 mission_store.save_event가 서버에서 다시 검사합니다.
"""
import hashlib
import json
import logging
from datetime import date, datetime

from agents import report_writer, service_matching
from db import experience_store, mission_store
from shared import report
from webapp import limits, sessions
from webapp.common import ApiError, Response, dashboard_data, evidence_for, region_context

# 사업 검토를 저장할 때 함께 남기는 사업 정보 항목
SERVICE_FIELDS = (
    'source_id', 'service_id', 'name', 'province', 'district', 'summary',
    'target_text', 'eligibility_text', 'benefit_text', 'application_text',
    'effective_start', 'effective_end', 'source_url', 'detail_pending',
    'detail_checked_at', 'source_modified', 'residency_text',
)


def report_filename(context):
    return f"사업검토보고_{context['district']}_{context['month']}.docx"


def load_workflow(context):
    """이 지역·동·기준월의 업무 진행 상황입니다. 아직 없으면 빈 dict입니다."""
    return mission_store.load_all().get(mission_store.identity(context), {})


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
    """GET /api/missions: 로그인한 담당자가 저장한 지역 업무 목록(업무 기록 화면)."""
    items = []
    for key, workflow in mission_store.load_all().items():
        owner, city, district, month = json.loads(key)
        if owner == request.user['id']:
            items.append({'city': city, 'district': district, 'month': month, 'workflow': workflow})
    return {'items': items}


def workflow(request):
    """GET /api/workflow: 선택한 동의 업무 진행 상황."""
    context = region_context(request, dashboard_data())
    return load_workflow(context)


def experience(request):
    """GET /api/experience: 선택한 동의 검토·후속 조치 기록."""
    context = region_context(request, dashboard_data())
    return experience_store.load(context)


def experience_history(request):
    """GET /api/experience/history: 같은 동의 다른 기준월 기록."""
    context = region_context(request, dashboard_data())
    return {'items': experience_store.regional_history(context)}


def services(request):
    """GET /api/services: 근거 검토를 마친 동에 맞는 복지사업 후보(DB2)."""
    context = region_context(request, dashboard_data())
    current = load_workflow(context)
    if 1 not in current.get('done', []):
        raise ValueError('먼저 분석 근거를 확인하세요.')
    try:
        matches = service_matching.match_services(context['city'], current['analysis_evidence'])
    except Exception:
        logging.exception('DB2 service lookup failed')
        raise ApiError(503, 'DB2 사업 조회에 실패했습니다. .env 연결 및 DB 권한을 확인하세요.')
    return {'matches': matches}


def saved_report(request):
    """GET /api/report: 최종 저장한 Word 보고서를 내려받습니다."""
    context = region_context(request, dashboard_data())
    document = mission_store.load_report(context)
    if not document:
        raise ValueError('저장된 보고서가 없습니다.')
    return Response(document, filename=report_filename(context))


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


def report_content(request):
    """POST /api/report/content: 저장된 분석·사업 검토로 보고서 문장 초안을 만듭니다.

    ai=true이면 AI가 문장을 다듬고, 저장된 근거와 대조를 통과한 경우에만 그 문장을 씁니다.
    """
    context, data, evidence = work_context(request)
    use_ai = request.params.get('ai') is True
    if use_ai:
        limits.check_chat(request.user)  # AI 문장 다듬기도 보미 사용량에 포함합니다.
    return report_writer.write_draft(context, load_workflow(context), use_ai=use_ai)


def report_preview(request):
    """POST /api/report/preview: 작성 내용으로 Word 파일을 만들고, 확인용 토큰을 돌려줍니다."""
    context, data, evidence = work_context(request)
    current = load_workflow(context)
    if 2 not in current.get('done', []):
        raise ValueError('사업 검토 기록을 먼저 저장하세요.')

    fields = {
        'author': request.text('author'),
        'department': request.text('department'),
        'opinion': request.text('opinion'),
    }
    # 이전 화면이나 임시 초안이 계정 ID를 보내도 보고서에는 담당자 이름을 씁니다.
    if fields['author'] == request.user['id']:
        from shared.accounts import DEMO_ACCOUNTS
        fields['author'] = DEMO_ACCOUNTS[request.user['id']]['name']
    content = None
    if 'content' in request.params:
        content = report_writer.validate_content(request.params['content'])
    if content:
        fields['opinion'] = content['next_steps']
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

    preview = {'identity': mission_store.identity(context), 'document': document, 'record': record}
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
        return load_workflow(context)


def workflow_confirm(request):
    """POST /api/workflow/confirm: ② 근거 검토 완료."""
    context, data, evidence = work_context(request)
    with sessions.write_lock:
        mission_store.save_event(context, 1, {'confirmed': True})
        return load_workflow(context)


def workflow_review(request):
    """POST /api/workflow/review: 조회한 복지사업 하나에 대한 검토 결과를 저장합니다."""
    context, data, evidence = work_context(request)
    with sessions.write_lock:
        current = load_workflow(context)
        chosen = None
        for match in service_matching.match_services(context['city'], current.get('analysis_evidence', [])):
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
            'reasons': chosen['reasons'],
            'source_url': chosen['service'].get('source_url'),
            'service_snapshot': service_snapshot(chosen['service']),
        })
        return load_workflow(context)


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
        mission_store.save_event(context, 3, record)
        sessions.remove_preview(token)
        return load_workflow(context)

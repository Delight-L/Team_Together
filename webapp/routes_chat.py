"""보미 챗봇 API.

- «이 화면 분석»: /api/region/chat (동·구 단위)  ※ 그룹 단위는 routes_groups.chat
- «복지사업 찾기»: /api/chat (stream=True이면 글자 단위로 이어서 보냄)
"""
from agents import report_writer
from chatbot import orchestrator
from chatbot.welfare import service as welfare_service
from chatbot.welfare.app.agent.resources import RESOURCES
from chatbot.welfare.app.config import settings
from db import mission_store, region_workspace
from webapp.common import StreamResponse, dashboard_data, evidence_for, region_context, rows_for_month


def config(request):
    """GET /api/chat/config: 답변 방식과 검색할 복지사업 자료 수입니다."""
    if settings.openai_api_key:
        mode = 'AI 대화'
    else:
        mode = '자료 검색'
    return {'mode': mode, 'resourceCount': len(RESOURCES)}


def region_chat(request):
    """POST /api/region/chat: 동을 골랐으면 그 동의 근거를, 안 골랐으면 구 전체 후보를 설명합니다."""
    data = dashboard_data()
    context = region_context(request, data, district_required=False)
    question = request.params.get('question', '')
    if request.params.get('mode') == 'ai':
        history = request.params.get('history', [])
        return region_workspace.ai_explain_region(context, question, data, history)
    return region_workspace.explain_region(context, question, data)


def welfare_chat(request):
    """POST /api/chat: 보미 «복지사업 찾기». 동을 고르지 않아도 질문할 수 있습니다."""
    data = dashboard_data()
    context = region_context(request, data, district_required=False)
    public_context = {'city': context['city'], 'district': context['district'], 'month': context['month']}

    # 화면에서 쓰는 방식: 대화 전체를 보내고 답변을 글자 단위로 받습니다.
    if request.params.get('stream') is True:
        messages = welfare_service.validate_messages(request.params.get('messages'))
        return StreamResponse(welfare_service.stream_reply(messages, public_context))

    # 아래는 한 번에 답변을 받는 예전 방식입니다(정해진 주제 버튼, 보고서 초안 요청).
    if context['district']:
        evidence = evidence_for(data, context)
    else:
        evidence = rows_for_month(data, context)
    question = request.text('question')
    if not question or len(question) > 2000:
        raise ValueError('질문은 1~2,000자로 입력하세요.')
    history = request.params.get('history', [])
    if not isinstance(history, list):
        raise ValueError('대화 이력이 유효하지 않습니다.')

    topic = request.params.get('topic')
    if topic:
        needs_report = topic == 'report_draft'
    else:
        needs_report = report_writer.is_draft_request(question)
    workflow = {}
    if context['district'] and needs_report:
        workflow = mission_store.load_all().get(mission_store.identity(context), {})

    if topic:
        result = orchestrator.topic_reply(topic, evidence, public_context, workflow)
    else:
        result = orchestrator.free_reply(question, evidence, public_context, history[-4:], workflow=workflow)
    result = dict(result)
    result['context'] = public_context
    return result

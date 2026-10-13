"""보미 챗봇 API.

- 채팅 화면: /api/chat (stream=True) → 총괄 에이전트(agents/supervisor.py)가 담당 에이전트를 골라 답합니다.
- 예전 호출 경로(화면에서는 더 이상 쓰지 않음): /api/chat JSON 방식, /api/region/chat, /api/groups/chat
"""
from agents import report_writer, supervisor
from chatbot import orchestrator
from chatbot.guardrails import mask_question
from webapp import limits
from chatbot.welfare import service as welfare_service
from chatbot.welfare.app.agent.resources import RESOURCES
from chatbot.welfare.app.config import settings
from db import mission_store, region_workspace
from webapp.common import (Request, StreamResponse, dashboard_data, evidence_for, group_context,
                           region_context, rows_for_month)


def config(request):
    """GET /api/chat/config: 답변 방식, AI 사용 가능 여부, 검색할 복지사업 자료 수입니다."""
    if settings.openai_api_key:
        mode = 'AI 대화'
    else:
        mode = '자료 검색'
    return {'mode': mode, 'aiAvailable': bool(settings.openai_api_key), 'resourceCount': len(RESOURCES)}


def region_chat(request):
    """POST /api/region/chat: 동을 골랐으면 그 동의 근거를, 안 골랐으면 구 전체 후보를 설명합니다."""
    data = dashboard_data()
    context = region_context(request, data, district_required=False)
    question, history = mask_question(request.params.get('question', ''), request.params.get('history', []))
    if request.params.get('mode') == 'ai':
        limits.check_chat(request.user)
        return region_workspace.ai_explain_region(context, question, data, history)
    return region_workspace.explain_region(context, question, data)


def chat(request):
    """POST /api/chat: 보미 채팅. 동을 고르지 않아도 질문할 수 있습니다."""
    data = dashboard_data()
    context = region_context(request, data, district_required=False)
    public_context = {'city': context['city'], 'district': context['district'], 'month': context['month']}
    # 가드레일: 사용자별 질문 수 제한(1분·하루). 한도를 넘으면 429입니다.
    limits.check_chat(request.user)

    # 화면에서 쓰는 방식: 대화 전체를 보내면 총괄 에이전트가 담당을 골라 답변을 이어서 보냅니다.
    if request.params.get('stream') is True:
        messages = welfare_service.validate_messages(request.params.get('messages'))
        group = None
        if request.params.get('group') is not None:
            if not isinstance(request.params['group'], dict):
                raise ValueError('그룹 정보가 유효하지 않습니다.')
            group = group_context(Request(request.params['group'], request.user, request.session_token))
        # mode='data'이면 담당 선택·답변 모두 외부 AI를 쓰지 않습니다.
        use_ai = request.params.get('mode') != 'data'
        return StreamResponse(supervisor.stream(messages, context, data, group, use_ai))

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
    question, history = mask_question(question, history)

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

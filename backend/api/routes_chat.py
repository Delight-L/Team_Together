"""보미 챗봇 API.

화면의 채팅은 모두 /api/chat으로 보냅니다.
총괄 에이전트(agents/supervisor.py)가 질문마다 담당 에이전트를 골라 답변을 글자 단위로 이어서 보냅니다.
"""
from backend.agents import supervisor, v16_service
from backend.chatbot.welfare import service as welfare_service
from backend.chatbot.welfare.app.dialogue.resources import RESOURCES
from backend.chatbot import ai_settings
from backend.api import limits
from backend.api.common import Request, StreamResponse, dashboard_data, group_context, region_context


def config(request):
    """GET /api/chat/config: 관리자가 외부 AI를 허용했는지, 어느 제공사인지, 검색할 복지사업 자료 수, v16 자료가 있는지입니다."""
    ai = ai_settings.current()
    provider = ai_settings.PROVIDERS[ai.provider]['label'] if ai.ready else ''
    return {'aiAvailable': ai.ready, 'aiProvider': provider, 'resourceCount': len(RESOURCES),
            'v16Available': v16_service.data_ready()}


def chat(request):
    """POST /api/chat: 대화 전체(messages)를 받아 답변을 이어서 보냅니다. 동을 고르지 않아도 질문할 수 있습니다."""
    data = dashboard_data()
    context = region_context(request, data, district_required=False)
    # 가드레일: 사용자별 질문 수 제한(1분·하루). 한도를 넘으면 429입니다.
    limits.check_chat(request.user)
    messages = welfare_service.validate_messages(request.params.get('messages'))

    # 종합 현황에서 연령·성별 그룹을 열어 둔 상태라면 그 그룹 기준으로 답합니다.
    group = None
    group_params = request.params.get('group')
    if group_params is not None:
        if not isinstance(group_params, dict):
            raise ValueError('그룹 정보가 유효하지 않습니다.')
        group = group_context(Request(group_params, request.user, request.session_token))

    # 화면의 «AI 사용» 스위치가 켜져 있을 때(mode='ai')만 외부 AI를 씁니다. 기본은 자료 기반 답변입니다.
    use_ai = request.params.get('mode') == 'ai'
    # 이전 답변에서 찾은 복지사업 id(보고서 초안 근거). 서버 자료에 있는 id만 쓰입니다.
    source_ids = request.params.get('sources') or []
    if not isinstance(source_ids, list) or len(source_ids) > 10 or not all(isinstance(i, str) for i in source_ids):
        raise ValueError('참고한 사업 목록이 올바르지 않습니다.')
    return StreamResponse(supervisor.stream(messages, context, data, group, use_ai, source_ids))

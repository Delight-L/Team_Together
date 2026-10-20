"""보미 챗봇 API.

화면의 채팅은 모두 /api/chat으로 보냅니다. 이 파일은 요청을 검사해 ChatRequest로 바꾸고,
답변 이벤트 스트림은 bomi 파이프라인이 만듭니다(담당 선택·안전 검사·에이전트 호출은 bomi/ 안에 있습니다).
"""
from backend.api import limits
from backend.api.common import Request, StreamResponse, dashboard_data, group_context, region_context
from backend.bomi.adapters import regional_analysis
from backend.bomi.pipeline import default_pipeline
from backend.bomi.request import ChatRequest, GroupSelection, validate_messages, validate_source_ids
from backend.bomi.conversation import unpack
from backend.chatbot import ai_settings
from backend.chatbot.welfare.app.dialogue.resources import resource_counts, resource_source


def config(request):
    """GET /api/chat/config: 관리자가 외부 AI를 허용했는지, 어느 제공사인지, 검색할 복지사업 자료 수, 지역 분석 자료가 있는지입니다."""
    ai = ai_settings.current()
    provider = ai_settings.PROVIDERS[ai.provider]['label'] if ai.ready else ''
    counts = resource_counts()
    return {'aiAvailable': ai.ready, 'aiProvider': provider, 'resourceCount': sum(counts.values()),
            'resourceCounts': counts,
            'resourceSource': resource_source(),
            'v16Available': regional_analysis.data_ready()}


def _group_selection(request):
    """종합 현황에서 연령·성별 그룹을 열어 둔 상태라면 그 그룹 기준으로 답합니다."""
    params = request.params.get('group')
    if params is None:
        return None
    if not isinstance(params, dict):
        raise ValueError('그룹 정보가 유효하지 않습니다.')
    context, detail = group_context(Request(params, request.user, request.session_token))
    return GroupSelection(context, detail)


def chat(request):
    """POST /api/chat: 대화 전체(messages)를 받아 답변을 이어서 보냅니다. 동을 고르지 않아도 질문할 수 있습니다."""
    data = dashboard_data()
    context = region_context(request, data, district_required=False)
    # 가드레일: 사용자별 질문 수 제한(1분·하루). 한도를 넘으면 429입니다.
    limits.check_chat(request.user)
    messages = validate_messages(request.params.get('messages'))
    state = unpack(request.params.get('conversation'), request.session_token, context)
    source_ids = validate_source_ids(request.params.get('sources'))
    chat_request = ChatRequest(
        messages=tuple(messages), context=context, data=data,
        group=_group_selection(request),
        # 화면의 «AI 사용» 스위치가 켜져 있을 때(mode='ai')만 외부 AI를 씁니다. 기본은 자료 기반 답변입니다.
        use_ai=request.params.get('mode') == 'ai',
        source_ids=tuple(state.get('selected_ids', source_ids)), welfare_state=state)
    return StreamResponse(default_pipeline().stream(chat_request, session_token=request.session_token))

"""보미 챗봇 API.

화면의 채팅은 모두 /api/chat으로 보냅니다.
총괄 에이전트(agents/supervisor.py)가 질문마다 담당 에이전트를 골라 답변을 글자 단위로 이어서 보냅니다.
"""
from agents import supervisor
from chatbot.welfare import service as welfare_service
from chatbot.welfare.app.agent.resources import RESOURCES
from chatbot.welfare.app.config import settings
from webapp import limits
from webapp.common import Request, StreamResponse, dashboard_data, group_context, region_context


def config(request):
    """GET /api/chat/config: 외부 AI를 쓸 수 있는지와 검색할 복지사업 자료 수입니다."""
    return {'aiAvailable': bool(settings.openai_api_key), 'resourceCount': len(RESOURCES)}


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

    # mode='data'이면 담당 선택·답변 모두 외부 AI를 쓰지 않습니다.
    use_ai = request.params.get('mode') != 'data'
    return StreamResponse(supervisor.stream(messages, context, data, group, use_ai))

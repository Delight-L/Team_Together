"""보미 챗봇 API.

화면의 채팅은 모두 /api/chat으로 보냅니다.
총괄 에이전트(agents/supervisor.py)가 질문마다 담당 에이전트를 골라 답변을 글자 단위로 이어서 보냅니다.
"""
from agents import supervisor
from agents.regional_analysis import v16_service
from chatbot.welfare import service as welfare_service
from chatbot.welfare.app.agent.resources import RESOURCES
from chatbot.welfare.app.config import settings
from webapp import limits
from webapp.common import Request, StreamResponse, dashboard_data, group_context, region_context


def config(request):
    """GET /api/chat/config: 외부 AI를 쓸 수 있는지와 검색할 복지사업 자료 수입니다."""
    router_available = bool(settings.openai_api_key)
    v16_available = v16_service.ai_available()
    return {'aiAvailable': router_available or v16_available,
            'routerAiAvailable': router_available, 'v16AiAvailable': v16_available,
            'resourceCount': len(RESOURCES)}


def chat(request):
    """POST /api/chat: 대화 전체(messages)를 받아 답변을 이어서 보냅니다. 동을 고르지 않아도 질문할 수 있습니다."""
    data = dashboard_data()
    context = region_context(request, data, district_required=False)
    # 비교 화면의 지표·기간·동 목록은 자연어에 생략되므로, 검증된 화면
    # 범위만 지역 분석 담당에게 전달한다. 임의 요청 값은 화면 맥락으로 쓰지 않는다.
    screen = request.params.get('screen')
    if isinstance(screen, dict):
        metric = str(screen.get('metric') or '').strip()
        months = set(data.get('months', ()))
        districts = {unit['n'] for unit in data['geometry'].get(context['city'], {}).get('units', ())}
        chosen = tuple(name for name in screen.get('districts', ()) if isinstance(name, str) and name in districts)
        start, end = str(screen.get('from') or ''), str(screen.get('to') or '')
        known_metrics = {row.get('metric_label') for row in data.get('assessment', ())}
        metrics = tuple(item for item in screen.get('metrics', ()) if isinstance(item, str) and item in known_metrics)
        if start in months and end in months and start <= end and chosen and (metric in known_metrics or metrics):
            context['screen'] = {'kind': 'evidence' if screen.get('kind') == 'evidence' else 'comparison',
                                 'metric': metric, 'metrics': metrics, 'from': start, 'to': end,
                                 'districts': chosen}
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

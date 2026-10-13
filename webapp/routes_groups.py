"""종합 현황의 연령·성별 그룹 API."""
from chatbot.guardrails import mask_question
from chatbot.welfare.app.config import settings
from webapp import limits
from db import group_repository, group_workspace
from webapp.common import check_city_access, group_context


def ai_config(request):
    """GET /api/groups/config: 보미의 «AI 해석»을 쓸 수 있는지(API 키가 있는지) 알려 줍니다."""
    return {'aiAvailable': bool(settings.openai_api_key)}


def catalogue(request):
    """GET /api/groups: 조사 파일에 보여 줄 그룹 목록입니다."""
    city = request.text('city')
    check_city_access(request.user, city)
    return group_repository.catalogue(city, request.text('month'))


def detail(request):
    """GET /api/groups/detail: 한 그룹의 브리핑 자료와 그 동의 지역 배경입니다."""
    context, group_detail = group_context(request)
    group_detail['regional'] = group_repository.regional_context(context)
    return group_detail


def review_load(request):
    """GET /api/groups/review: 이 그룹에 저장한 검토 메모입니다."""
    context, group_detail = group_context(request)
    return group_workspace.review(request.user, context)


def services(request):
    """GET /api/groups/services: 지원 목적에 맞는 복지사업 후보입니다."""
    context, group_detail = group_context(request)
    return group_workspace.services(context, request.params.get('need'))


def chat(request):
    """POST /api/groups/chat: 보미 «이 화면 분석»(그룹을 열었을 때)."""
    context, group_detail = group_context(request)
    question, history = mask_question(request.params.get('question', ''), request.params.get('history', []))
    if request.params.get('mode') == 'ai':
        limits.check_chat(request.user)
        return group_workspace.ai_explain(context, question, group_detail, history)
    return group_workspace.explain(context, question, group_detail)


def review_save(request):
    """POST /api/groups/review: 그룹 검토 메모를 저장합니다."""
    context, group_detail = group_context(request)
    # 화면을 연 뒤 원자료가 바뀌었다면 예전 숫자를 보고 쓴 메모이므로 저장하지 않습니다.
    if request.params.get('sourceRun') != group_detail['runId']:
        raise ValueError('집단별 원자료가 갱신되었습니다. 근거를 다시 확인한 뒤 저장하세요.')
    return group_workspace.review(request.user, context, request.params)

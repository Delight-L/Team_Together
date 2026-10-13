"""종합 현황의 연령·성별 그룹 API. 그룹에 대한 보미 질문은 /api/chat(group 포함)으로 처리합니다."""
from backend.db import group_repository, group_workspace
from backend.api.common import check_city_access, group_context


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


def review_save(request):
    """POST /api/groups/review: 그룹 검토 메모를 저장합니다."""
    context, group_detail = group_context(request)
    # 화면을 연 뒤 원자료가 바뀌었다면 예전 숫자를 보고 쓴 메모이므로 저장하지 않습니다.
    if request.params.get('sourceRun') != group_detail['runId']:
        raise ValueError('집단별 원자료가 갱신되었습니다. 근거를 다시 확인한 뒤 저장하세요.')
    return group_workspace.review(request.user, context, request.params)

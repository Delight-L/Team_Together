"""bomi 테스트 공용 도구: 요청 만들기, 이벤트 모으기, 가짜 AI 응답."""
from backend.bomi.pipeline import ChatPipeline
from backend.bomi.request import ChatRequest, GroupSelection

CONTEXT = {'city': '강남구', 'district': '삼성1동', 'month': '2025-12',
           'user': {'id': 'tester', 'admin': False, 'org': '강남구'}, 'workflow_mode': 'live'}
DATA = {'months': ['2025-11', '2025-12'], 'runId': 'test-run', 'assessment': [
    {'기준연월': '2025-12', '행정동명': '삼성1동', 'metric_label': '전화 연락', 'change_pct': -12.3,
     'relative_change_pp': -3.0, 'is_risk_signal': True, 'has_enough_history': True},
    {'기준연월': '2025-11', '행정동명': '삼성1동', 'metric_label': '전화 연락', 'change_pct': 1.0,
     'relative_change_pp': 0.0, 'is_risk_signal': False, 'has_enough_history': True}]}
WORKFLOW = {'done': [0, 1, 2], 'analysis_evidence': [
    {'is_risk_signal': True, 'metric_label': '전화 연락', 'change_pct': -12.3}],
    'reviews': [{'service_key': 'a', 'name': '교류 지원', 'decision': '적합', 'note': '교류 지원 검토'},
                {'service_key': 'b', 'name': '상담 지원', 'decision': '보류', 'note': '자격 확인 필요'}]}
GROUP = ({'age': '30대', 'sex': '남성', 'district': '삼성1동', 'month': '2025-12'}, {})


def make_request(question, history=(), group=None, use_ai=False, source_ids=(), context=None, data=None):
    """group은 예전 테스트와 같은 (context, detail) 튜플로 받습니다."""
    selection = GroupSelection(*group) if group else None
    return ChatRequest(messages=(*history, {'role': 'user', 'content': question}),
                       context=context or CONTEXT, data=data or DATA, group=selection,
                       use_ai=use_ai, source_ids=tuple(source_ids))


def events(question, history=(), group=None, ai=False, source_ids=(), **kwargs):
    """질문 하나의 이벤트를 [(이름, 내용)…]으로 모읍니다."""
    request = make_request(question, history, group, ai, source_ids, **kwargs)
    return list(ChatPipeline().stream(request))


def fake_complete(answer):
    async def complete(messages, json_mode=False, max_tokens=None):
        if isinstance(answer, Exception):
            raise answer
        return answer
    return complete

"""v16 단독 확인 API. 일반 화면 질문은 /api/chat의 보미 파이프라인(bomi/)을 거칩니다."""
import logging

from backend.api import limits
from backend.api.common import StreamResponse, dashboard_data, region_context
from backend.bomi.adapters import v16 as v16_service
from backend.bomi.request import validate_messages
from backend.chatbot.guardrails import mask_messages
from backend.chatbot.welfare.app.llm.client import ai_ready


def chat(request):
    """POST /api/chat/v16: 인증·지역 검사를 거쳐 v16만 호출하는 확인용 API."""
    context = region_context(request, dashboard_data(), district_required=False)
    limits.check_chat(request.user)
    messages = validate_messages(request.params.get('messages'))
    if len(messages[-1]['content']) > 2000:
        raise ValueError('질문은 1~2,000자로 입력하세요.')
    messages, pii = mask_messages(messages)
    question, history = messages[-1]['content'], messages[:-1]
    # /api/chat과 같이 «AI 사용»을 켰고(mode='ai') 관리자가 AI를 허용했을 때만 외부 AI를 씁니다.
    use_ai = request.params.get('mode') == 'ai' and ai_ready()

    def events():
        if pii:
            yield 'notice', {'message': '개인정보로 보이는 내용을 가리고 처리했어요.', 'question': question}
        yield 'route', {'agent': 'regional_v16', 'label': '지역 변화 신호 에이전트 (v16)', 'by': '직접 호출'}
        if not v16_service.data_ready():
            yield 'error', {'message': '지역 분석 근거 자료를 조회하지 못했습니다. 관리자에게 DB 연결과 게시 상태 확인을 요청하세요.'}
            yield 'done', {}
            return
        try:
            result = v16_service.reply(question, history, context, use_ai=use_ai)
            yield 'replace', {'text': result['answer'], 'mode': result.get('mode', ''), 'source': 'v16 · DB1'}
            if result.get('followUps'):
                yield 'follow_ups', {'questions': result['followUps']}
            if result.get('notice'):
                yield 'notice', {'message': result['notice']}
        except Exception:
            logging.exception('v16 단독 조회 실패')
            yield 'error', {'message': '지역 분석 답변을 만드는 중 문제가 생겼습니다. 서버 로그를 확인해 주세요.'}
        yield 'done', {}

    return StreamResponse(events())

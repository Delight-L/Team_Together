"""관리자 «AI 설정» API: 기관 전체의 외부 AI 사용 여부·제공사·모델·키(chatbot/ai_settings.py).

키 원문은 저장만 하고 화면으로 돌려보내지 않습니다(끝 4자리만 표시).
"""
import asyncio
import logging

from backend.chatbot import ai_settings
from backend.chatbot.welfare.app.llm.client import LLM_ERRORS, llm

LOGGER = logging.getLogger(__name__)


def _require_admin(request):
    if not request.user['admin']:
        raise PermissionError('관리자만 AI 설정을 바꿀 수 있습니다.')


def ai_view(request):
    """GET /api/admin/ai: 지금 AI 설정(키 원문 제외)."""
    _require_admin(request)
    return ai_settings.public_view()


def ai_save(request):
    """POST /api/admin/ai: {enabled, provider, model, apiKey?, clearKey?}를 저장합니다."""
    _require_admin(request)
    if not isinstance(request.params, dict):
        raise ValueError('AI 설정 형식이 올바르지 않습니다.')
    view = ai_settings.save(request.params)
    LOGGER.info('관리자 %s가 AI 설정 변경: 사용=%s 제공사=%s', request.user.get('id'), view['enabled'], view['provider'])
    return view


def ai_test(request):
    """POST /api/admin/ai/test: 저장된 설정으로 짧은 질문을 보내 연결을 확인합니다."""
    _require_admin(request)
    if not ai_settings.current().ready:
        return {'ok': False, 'message': 'AI 사용을 켜고 API 키를 저장한 뒤 확인하세요.'}
    try:
        answer = asyncio.run(llm.complete([{'role': 'user', 'content': '연결 확인입니다. "확인"이라고만 답하세요.'}],
                                          max_tokens=20))
    except LLM_ERRORS as exc:
        LOGGER.warning('AI 연결 확인 실패: %s', type(exc).__name__)
        return {'ok': False, 'message': f'연결하지 못했습니다({type(exc).__name__}). 키·모델 이름을 확인하세요.'}
    return {'ok': True, 'message': '연결되었습니다. 응답: ' + answer.strip()[:40]}

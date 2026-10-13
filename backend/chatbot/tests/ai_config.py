"""테스트용: 관리자 AI 설정을 파일 대신 정해진 값으로 바꿉니다."""
from unittest.mock import patch

from backend.chatbot import ai_settings


def ai_key(key, provider='openai', model='test-model'):
    """key가 있으면 AI 사용 켜짐, 빈 문자열이면 꺼짐 상태로 patch합니다."""
    config = ai_settings.AIConfig(bool(key), provider, model, key, '.env' if key else '')
    return patch.object(ai_settings, 'current', return_value=config)

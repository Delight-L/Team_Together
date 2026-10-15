"""보미의 외부 AI 호출 창구. 관리자 «AI 설정»(chatbot/ai_settings.py)에 따라 제공사를 고릅니다.

모든 AI 호출은 이 파일의 llm을 거칩니다.
- llm.stream(messages)      답변을 조각조각 이어 받기
- llm.complete(messages)    답을 한 번에 받기(담당 선택·보고서 문장 다듬기, JSON 응답)
- llm.moderate(text)        유해 콘텐츠 검사(OpenAI 키가 있을 때만, 없으면 검사 생략)
호출이 실패하면 LLM_ERRORS 중 하나가 나므로, 호출한 쪽은 이것을 잡아 AI 없는 안내로 대체합니다.
"""
from collections.abc import AsyncIterator
import re

import anthropic
from google.genai import errors as gemini_errors
from openai import OpenAIError

from backend.chatbot import ai_settings
from backend.chatbot.welfare.app.config import settings
from backend.chatbot.welfare.app.llm import anthropic_client, gemini_client, openai_client


class AIUnavailable(Exception):
    """관리자가 AI를 꺼 두었거나 키가 없어 외부 AI를 부를 수 없습니다."""


class EmptyAnswer(Exception):
    """AI가 빈 답을 돌려줬습니다."""


# 제공사마다 오류 종류가 달라 한데 모아 둡니다. except LLM_ERRORS: 로 잡으세요.
LLM_ERRORS = (OpenAIError, anthropic.AnthropicError, gemini_errors.APIError, AIUnavailable, EmptyAnswer)


def ai_ready():
    """관리자 설정상 외부 AI를 쓸 수 있는지(사용 켜짐 + 키 있음)."""
    return ai_settings.current().ready
PROVIDER_MODULES = {'openai': openai_client, 'anthropic': anthropic_client, 'gemini': gemini_client}


def _ready_config():
    config = ai_settings.current()
    if not config.ready:
        raise AIUnavailable('관리자 AI 설정이 꺼져 있거나 API 키가 없습니다.')
    return config


def _strip_code_fence(text):
    """```json ... ``` 처럼 감싸서 온 JSON 답에서 감싼 부분을 벗겨 냅니다."""
    match = re.fullmatch(r'\s*```(?:json)?\s*(.*?)\s*```\s*', text, re.S)
    return match.group(1) if match else text


class LLMClient:
    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        config = _ready_config()
        module = PROVIDER_MODULES[config.provider]
        async for text in module.stream(config, messages, settings.openai_max_tokens):
            yield text

    async def complete(self, messages: list[dict], json_mode: bool = False, max_tokens: int | None = None) -> str:
        config = _ready_config()
        module = PROVIDER_MODULES[config.provider]
        answer = await module.complete(config, messages, json_mode, max_tokens or settings.openai_max_tokens)
        return _strip_code_fence(answer) if json_mode else answer

    async def moderate(self, text: str) -> list[str]:
        key = ai_settings.openai_key()
        if not key:
            return []  # OpenAI 키가 없으면 유해 콘텐츠 검사를 하지 않습니다(관리자 화면에 표시).
        return await openai_client.moderate(key, settings.openai_moderation_model, text)


llm = LLMClient()
TRUNCATED = openai_client.TRUNCATED

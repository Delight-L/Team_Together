"""Anthropic(Claude) 호출(client.py가 관리자 설정에 따라 고릅니다).

- 지시문(system)은 messages에서 꺼내 system 인자로 따로 보냅니다.
- 최신 모델은 답하기 전에 생각(thinking)하는 데도 출력 토큰을 쓰므로, 상한을 너무 낮게 두지 않고
  대신 effort를 'low'로 두어 짧은 업무 답변에 맞춥니다.
- 안전 분류기가 답을 거절하면(stop_reason='refusal') 서버가 다른 모델로 이어 답하는 fallback을 켭니다
  (지원 모델만). 그래도 거절되면 오류로 알려 호출한 쪽이 AI 없는 안내로 대체합니다.
"""
from collections.abc import AsyncIterator

import anthropic

from chatbot.welfare.app.llm.openai_client import TRUNCATED

MIN_MAX_TOKENS = 8000
FALLBACK_MODELS = {'claude-fable-5-1', 'claude-opus-5-5', 'claude-opus-5', 'claude-sonnet-5-5'}


class Refused(anthropic.AnthropicError):
    """Claude가 안전 분류기로 답을 거절했습니다."""


def _request(config, messages, max_tokens):
    system = '\n\n'.join(m['content'] for m in messages if m['role'] == 'system')
    chat = [{'role': m['role'], 'content': m['content']} for m in messages if m['role'] != 'system']
    request = {'model': config.model, 'max_tokens': max(max_tokens, MIN_MAX_TOKENS), 'messages': chat,
               'output_config': {'effort': 'low'}}
    if system:
        request['system'] = system
    if config.model in FALLBACK_MODELS:
        request['betas'] = ['server-side-fallback-2026-07-01']
        request['fallbacks'] = 'default'
    return request


async def stream(config, messages: list[dict], max_tokens: int) -> AsyncIterator[str]:
    async with anthropic.AsyncAnthropic(api_key=config.api_key, timeout=60, max_retries=0) as client:
        async with client.beta.messages.stream(**_request(config, messages, max_tokens)) as response:
            async for text in response.text_stream:
                yield text
            final = await response.get_final_message()
    if final.stop_reason == 'refusal':
        raise Refused('Claude가 답변을 거절했습니다.')
    if final.stop_reason == 'max_tokens':
        yield TRUNCATED


async def complete(config, messages: list[dict], json_mode: bool, max_tokens: int) -> str:
    async with anthropic.AsyncAnthropic(api_key=config.api_key, timeout=60, max_retries=0) as client:
        async with client.beta.messages.stream(**_request(config, messages, max_tokens)) as response:
            final = await response.get_final_message()
    if final.stop_reason == 'refusal':
        raise Refused('Claude가 답변을 거절했습니다.')
    return ''.join(block.text for block in final.content if block.type == 'text')

"""Google Gemini 호출(client.py가 관리자 설정에 따라 고릅니다).

Gemini는 대화 역할 이름이 user/model이고, 지시문(system)은 설정의 system_instruction으로 보냅니다.
"""
from collections.abc import AsyncIterator

from google import genai
from google.genai import types

from backend.chatbot.welfare.app.llm.openai_client import TRUNCATED


def _request(config, messages, max_tokens, json_mode=False):
    system = '\n\n'.join(m['content'] for m in messages if m['role'] == 'system')
    contents = []
    for message in messages:
        if message['role'] == 'system':
            continue
        role = 'user' if message['role'] == 'user' else 'model'
        contents.append(types.Content(role=role, parts=[types.Part(text=message['content'])]))
    options = {'max_output_tokens': max_tokens}
    if system:
        options['system_instruction'] = system
    if json_mode:
        options['response_mime_type'] = 'application/json'
    return {'model': config.model, 'contents': contents, 'config': types.GenerateContentConfig(**options)}


async def stream(config, messages: list[dict], max_tokens: int) -> AsyncIterator[str]:
    async with genai.Client(api_key=config.api_key).aio as client:
        response = await client.models.generate_content_stream(**_request(config, messages, max_tokens))
        try:
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
                candidates = chunk.candidates or []
                if candidates and candidates[0].finish_reason == types.FinishReason.MAX_TOKENS:
                    yield TRUNCATED
        finally:
            await response.aclose()


async def complete(config, messages: list[dict], json_mode: bool, max_tokens: int) -> str:
    async with genai.Client(api_key=config.api_key).aio as client:
        response = await client.models.generate_content(**_request(config, messages, max_tokens, json_mode))
        return response.text or ''

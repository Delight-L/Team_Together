"""OpenAI 호출(client.py가 관리자 설정에 따라 고릅니다)."""
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

TRUNCATED = '\n\n(답변이 길어 여기까지만 표시했어요. 범위를 좁혀 다시 물어봐 주세요.)'


async def stream(config, messages: list[dict], max_tokens: int) -> AsyncIterator[str]:
    # 팀 HTTP 서버는 요청마다 스레드/이벤트 루프가 다르므로 클라이언트를 공유하지 않습니다.
    async with AsyncOpenAI(api_key=config.api_key, timeout=30, max_retries=0) as client:
        response = await client.chat.completions.create(
            model=config.model, messages=messages, stream=True, max_completion_tokens=max_tokens)
        try:
            async for chunk in response:
                if not chunk.choices:
                    continue
                if text := chunk.choices[0].delta.content:
                    yield text
                if getattr(chunk.choices[0], 'finish_reason', None) == 'length':
                    yield TRUNCATED
        finally:
            await response.close()


async def complete(config, messages: list[dict], json_mode: bool, max_tokens: int) -> str:
    options = {'response_format': {'type': 'json_object'}} if json_mode else {}
    async with AsyncOpenAI(api_key=config.api_key, timeout=30, max_retries=0) as client:
        response = await client.chat.completions.create(
            model=config.model, messages=messages, max_completion_tokens=max_tokens, **options)
    return response.choices[0].message.content or ''


async def moderate(api_key: str, model: str, text: str) -> list[str]:
    """OpenAI 유해 콘텐츠 검사(무료). 걸린 분류 이름 목록, 빈 목록이면 통과입니다."""
    async with AsyncOpenAI(api_key=api_key, timeout=10, max_retries=0) as client:
        response = await client.moderations.create(model=model, input=text)
    result = response.results[0]
    if not result.flagged:
        return []
    categories = result.categories.model_dump() if hasattr(result.categories, 'model_dump') else dict(result.categories)
    return [name for name, hit in categories.items() if hit]

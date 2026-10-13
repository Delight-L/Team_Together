from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from chatbot.welfare.app.config import settings

TRUNCATED = '\n\n(답변이 길어 여기까지만 표시했어요. 범위를 좁혀 다시 물어봐 주세요.)'


class OpenAIClient:
    """보미의 AI 답변 생성, 유해 콘텐츠 검사를 맡습니다. 답변 길이는 .env의 OPENAI_MAX_TOKENS로 제한합니다."""

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        # 팀 HTTP 서버는 요청마다 스레드/이벤트 루프가 다르므로 클라이언트를 공유하지 않습니다.
        # 키가 없는 요청에서는 handle_chat이 이 함수에 진입하지 않습니다.
        async with AsyncOpenAI(api_key=settings.openai_api_key, timeout=30, max_retries=0) as client:
            stream = await client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                stream=True,
                max_completion_tokens=settings.openai_max_tokens,
            )
            try:
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    if text := chunk.choices[0].delta.content:
                        yield text
                    if getattr(chunk.choices[0], 'finish_reason', None) == 'length':
                        yield TRUNCATED
            finally:
                await stream.close()

    async def complete(self, messages: list[dict], json_mode: bool = False, max_tokens: int | None = None) -> str:
        """총괄 에이전트의 담당 선택·보고서 문장 다듬기처럼 답을 한 번에 받을 때 씁니다."""
        options = {'response_format': {'type': 'json_object'}} if json_mode else {}
        async with AsyncOpenAI(api_key=settings.openai_api_key, timeout=30, max_retries=0) as client:
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_completion_tokens=max_tokens or settings.openai_max_tokens,
                **options,
            )
        return response.choices[0].message.content or ''

    async def moderate(self, text: str) -> list[str]:
        """OpenAI 유해 콘텐츠 검사(무료)를 실행해 걸린 분류 이름 목록을 돌려줍니다. 빈 목록이면 통과입니다."""
        async with AsyncOpenAI(api_key=settings.openai_api_key, timeout=10, max_retries=0) as client:
            response = await client.moderations.create(model=settings.openai_moderation_model, input=text)
        result = response.results[0]
        if not result.flagged:
            return []
        categories = result.categories.model_dump() if hasattr(result.categories, 'model_dump') else dict(result.categories)
        return [name for name, hit in categories.items() if hit]


llm = OpenAIClient()

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from chatbot.welfare.app.config import settings


class OpenAIClient:
    """보미의 복지사업 답변을 생성하고 응답을 한 조각씩 전달합니다."""

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        # 팀 HTTP 서버는 요청마다 스레드/이벤트 루프가 다르므로 클라이언트를 공유하지 않습니다.
        # 키가 없는 요청에서는 handle_chat이 이 함수에 진입하지 않습니다.
        async with AsyncOpenAI(api_key=settings.openai_api_key, timeout=30, max_retries=0) as client:
            stream = await client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                stream=True,
            )
            try:
                async for chunk in stream:
                    if chunk.choices and (text := chunk.choices[0].delta.content):
                        yield text
            finally:
                await stream.close()

    async def complete(self, messages: list[dict], json_mode: bool = False) -> str:
        """총괄 에이전트의 담당 선택·보고서 문장 다듬기처럼 답을 한 번에 받을 때 씁니다."""
        options = {'response_format': {'type': 'json_object'}} if json_mode else {}
        async with AsyncOpenAI(api_key=settings.openai_api_key, timeout=30, max_retries=0) as client:
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                **options,
            )
        return response.choices[0].message.content or ''


llm = OpenAIClient()

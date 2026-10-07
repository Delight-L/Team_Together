from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from chatbot.welfare.app.config import settings


class OpenAIClient:
    """LLM 호출 추상화. 이후 Router/Persona 클라이언트로 분리할 때 같은 인터페이스를 유지한다."""

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


llm = OpenAIClient()

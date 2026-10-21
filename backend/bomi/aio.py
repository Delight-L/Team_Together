"""동기 코드에서 비동기 AI 호출(llm 창구)을 쓰는 유일한 접점.

서버는 요청마다 동기 스레드에서 돌고 외부 AI 창구(chatbot/welfare/app/llm/client.py)만 비동기입니다.
`asyncio.run`을 여기 말고는 어디서도 직접 부르지 않습니다. 호출 위치를 한곳으로 모으면
이벤트 루프 생성·종료와 스트림 닫기 규칙을 한 번만 지키면 됩니다.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Iterator
from typing import TypeVar

T = TypeVar('T')


def run(awaitable: Awaitable[T]) -> T:
    """코루틴 하나를 끝까지 실행해 결과를 돌려줍니다."""

    async def _await():
        return await awaitable

    return asyncio.run(_await())


def iterate(stream: AsyncIterator[T]) -> Iterator[T]:
    """비동기 스트림을 동기 이터레이터로 바꿉니다.

    받는 쪽이 중간에 멈추면(연결 취소 등) 진행 중인 비동기 스트림도 함께 닫습니다.
    """

    async def _next():
        return await anext(stream)

    with asyncio.Runner() as runner:
        try:
            while True:
                try:
                    yield runner.run(_next())
                except StopAsyncIteration:
                    break
        finally:
            runner.run(stream.aclose())

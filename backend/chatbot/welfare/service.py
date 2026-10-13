"""복지탐정 HTTP 서버와 보미의 비동기 복지사업 대화를 연결합니다.

복지 검색/답변/AI 호출은 app/dialogue/orchestrator.py의 handle_chat이 담당합니다.
이 파일에는 별도의 프롬프트나 OpenAI 호출 구현을 두지 않습니다.
"""
import asyncio
from pydantic import ValidationError
from backend.chatbot.welfare.app.dialogue.orchestrator import handle_chat
from backend.chatbot.welfare.app.schemas import ChatRequest


def validate_messages(messages):
    try:
        request = ChatRequest.model_validate({'messages': messages})
    except ValidationError as exc:
        raise ValueError('대화는 1~40개, 각 메시지는 1~6,000자이며 마지막 메시지는 사용자 질문이어야 합니다.') from exc
    return [message.model_dump() for message in request.messages]


def stream_reply(messages, context, use_ai=True):
    history = ChatRequest.model_validate({'messages': validate_messages(messages)}).messages
    events = handle_chat(history, context, use_ai)
    # 요청마다 루프를 분리하고 연결 중지 시 진행 중인 비동기 스트림도 종료합니다.
    with asyncio.Runner() as runner:
        try:
            while True:
                try:
                    event = runner.run(anext(events))
                except StopAsyncIteration:
                    break
                yield event
        finally:
            runner.run(events.aclose())

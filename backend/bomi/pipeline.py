"""보미 채팅 파이프라인: 요청 한 번을 이벤트 스트림으로 바꿉니다.

    regularization.prepare(길이·대화 길이·개인정보 가림)
      → [notice: 개인정보 가림]
      → 담당 선택(고정 규칙 → AI → 키워드 규칙)
      → route 이벤트
      → 담당 에이전트 respond  ← 입력 규제(단어 규칙 + moderate API)와 출력 규제는 에이전트가 합니다
      → done (events.seal이 보장)
"""
import logging
from typing import Iterator

from backend.bomi import aio, events, regularization
from backend.bomi.agents import default_agents
from backend.bomi.events import Event
from backend.bomi.phrases import PII_NOTICE
from backend.bomi.request import ChatRequest
from backend.bomi.routing import Route, Router

LOGGER = logging.getLogger(__name__)
SAFETY_ROUTE = Route('guide', '안전 검사')


class ChatPipeline:
    def __init__(self, router: Router | None = None, agents: dict | None = None):
        self.router = router or Router()
        self.agents = agents or default_agents()

    def stream(self, request: ChatRequest, *, session_token: str | None = None) -> Iterator[Event]:
        """검사를 먼저 끝낸 뒤 이벤트 생성기를 돌려줍니다. 검사 실패(ValueError)는 스트림 시작 전에 납니다."""
        prepared = regularization.prepare(request)
        stream = self._run(prepared)
        if session_token:
            from backend.bomi.conversation import events_with_state
            stream = events_with_state(stream, prepared.request.welfare_state,
                                       prepared.request.context, session_token)
        return events.seal(stream)

    # ── 내부 단계 ────────────────────────────────────────────────
    def _run(self, prepared: regularization.Prepared) -> Iterator[Event]:
        request = prepared.request
        if prepared.pii_kinds:
            yield events.notice(PII_NOTICE.format(kinds='·'.join(prepared.pii_kinds)), question=request.question)
        route = self._choose(request)
        yield events.route(route.agent, route.label, route.by)
        yield from self.agents[route.agent].respond(request)

    def _choose(self, request: ChatRequest) -> Route:
        """담당 선택. 단어 규칙에 걸린 질문은 외부 호출 없이 보미 안내로 보내 에이전트가 차단하게 합니다."""
        if regularization.rule_flagged(request.question):
            return SAFETY_ROUTE
        if not request.use_ai or self.router.fixed(request):
            return self.router.decide(request)
        return self.router.decide(request, aio.run(self.router.by_ai(request)))


_default: ChatPipeline | None = None


def default_pipeline() -> ChatPipeline:
    global _default
    if _default is None:
        _default = ChatPipeline()
    return _default

"""모든 담당 에이전트가 따르는 인터페이스와 공통 응답 타입."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Protocol

from backend.bomi import events
from backend.bomi.events import Event
from backend.bomi.phrases import BLOCKED, BLOCKED_MODE, OUTPUT_BLOCKED
from backend.bomi.regularization import Policy, Regulator
from backend.bomi.request import ChatRequest


class Agent(Protocol):
    """담당 에이전트. route·done·개인정보 notice는 파이프라인이 보내므로 에이전트는 답변 이벤트만 만듭니다."""

    id: str

    def respond(self, request: ChatRequest) -> Iterator[Event]: ...


@dataclass
class Reply:
    """한 번에 완성되는 답변. `events()`가 계약 순서(error → replace → follow_ups → notice → actions)로 바꿉니다."""

    text: str
    mode: str = ''
    source: str = ''
    follow_ups: list = field(default_factory=list)
    notice: str = ''
    actions: list = field(default_factory=list)
    error: str = ''  # 대체 답변을 보내기 전에 사용자에게 알릴 사정(예: AI 해석 실패)
    generated_by_ai: bool = False  # 외부 AI가 쓴 글이면 True. 출력 moderate를 걸지 판단합니다.

    @classmethod
    def from_legacy(cls, result: dict) -> 'Reply':
        """기존 db/·보고서·v16 모듈이 돌려주는 dict를 Reply로 바꿉니다."""
        sources = result.get('sources') or [{}]
        return cls(
            text=result['answer'],
            mode=result.get('mode', ''),
            source=sources[0].get('label', ''),
            follow_ups=list(result.get('followUps') or []),
            notice=result.get('notice', ''),
            actions=list(result.get('actions') or []),
            generated_by_ai=bool(result.get('aiGenerated')),
        )

    def events(self) -> Iterator[Event]:
        if self.error:
            yield events.error(self.error)
        yield events.replace(self.text, self.mode, self.source)
        if self.follow_ups:
            yield events.follow_ups(self.follow_ups)
        if self.notice:
            yield events.notice(self.notice)
        if self.actions:
            yield events.actions(self.actions)


class RegulatedAgent(ABC):
    """입력·출력 규제를 거치는 에이전트의 공통 틀.

    respond()가 입력 규제 → answer() → (Reply면) 출력 규제를 순서대로 처리하고,
    각 에이전트는 `answer()`에 기존 방식 그대로 답변 로직만 둡니다.
    """

    id: str
    policy: Policy
    regulator = Regulator()

    def respond(self, request: ChatRequest) -> Iterator[Event]:
        if self.regulator.screen_input(request, self.policy):
            yield events.replace(BLOCKED, BLOCKED_MODE, '')
            return
        yield from self.answer(request)

    @abstractmethod
    def answer(self, request: ChatRequest) -> Iterator[Event]:
        """규제를 통과한 요청에 대한 답변 이벤트(route·done 제외)."""

    def deliver(self, reply: Reply) -> Iterator[Event]:
        """한 번에 완성된 답변을 출력 규제(moderate API)를 거쳐 내보냅니다."""
        if self.regulator.output_flagged(reply.text, self.policy, reply.generated_by_ai):
            yield events.replace(OUTPUT_BLOCKED, BLOCKED_MODE, '')
            return
        yield from reply.events()

"""챗봇 한 번의 요청을 담는 타입과 입력 검증.

화면 맥락(`context`)과 분석 자료(`data`)는 기존 db/ 모듈이 dict로 받으므로 그대로 넘기되,
에이전트는 이 타입의 속성(`question`, `district` …)으로만 읽어 키 이름 의존을 한곳에 모읍니다.
"""

from dataclasses import dataclass, field, replace

from pydantic import ValidationError

from backend.chatbot.welfare.app.schemas import ChatRequest as MessageList

MAX_SOURCE_IDS = 10


def validate_messages(messages) -> list[dict]:
    """대화 1~40개, 각 1~6,000자, 마지막은 사용자 질문인지 검사해 dict 목록으로 돌려줍니다."""
    try:
        validated = MessageList.model_validate({'messages': messages})
    except ValidationError as exc:
        raise ValueError(
            '대화는 1~40개, 각 메시지는 1~6,000자이며 마지막 메시지는 사용자 질문이어야 합니다.'
        ) from exc
    return [message.model_dump() for message in validated.messages]


def validate_source_ids(value) -> tuple[str, ...]:
    """이전 답변에서 찾은 복지사업 id(보고서 초안 근거). 문자열 목록 최대 10개."""
    value = value or []
    if (
        not isinstance(value, list)
        or len(value) > MAX_SOURCE_IDS
        or not all(isinstance(i, str) for i in value)
    ):
        raise ValueError('참고한 사업 목록이 올바르지 않습니다.')
    return tuple(value)


@dataclass(frozen=True)
class GroupSelection:
    """종합 현황에서 열어 둔 연령·성별 그룹. `context`는 요청 값, `detail`은 조회한 그룹 자료입니다."""

    context: dict
    detail: dict

    @property
    def district(self) -> str:
        return self.context.get('district', '')

    @property
    def age(self) -> str:
        return self.context.get('age', '')

    @property
    def sex(self) -> str:
        return self.context.get('sex', '')


@dataclass(frozen=True)
class ChatRequest:
    messages: tuple[dict, ...]  # [{'role', 'content'}…]. 마지막이 이번 질문
    context: dict  # 화면에서 고른 지역·동·기준월(+사용자). db/ 모듈이 dict로 받습니다.
    data: dict  # 대시보드 분석 자료
    group: GroupSelection | None = None
    use_ai: bool = False
    source_ids: tuple[str, ...] = field(default_factory=tuple)
    welfare_state: dict = field(default_factory=dict)  # 서버가 검증한 대화 당시 사업 근거
    retrieval: dict = field(
        default_factory=dict
    )  # Router에서 확인한 검색 결과를 요청 안에서 재사용

    @property
    def question(self) -> str:
        return self.messages[-1]['content']

    @property
    def history(self) -> list[dict]:
        return list(self.messages[:-1])

    @property
    def city(self) -> str:
        return self.context.get('city', '')

    @property
    def district(self) -> str:
        return self.context.get('district', '')

    @property
    def month(self) -> str:
        return self.context.get('month', '')

    @property
    def age(self) -> str:
        return self.context.get('age', '')

    def public_context(self) -> dict:
        """외부 AI에 보내도 되는 화면 맥락(사용자 정보 제외)."""
        return {
            key: self.context[key]
            for key in ('city', 'district', 'month', 'age')
            if key in self.context
        }

    def with_messages(self, messages, use_ai: bool | None = None) -> 'ChatRequest':
        return replace(
            self, messages=tuple(messages), use_ai=self.use_ai if use_ai is None else use_ai
        )

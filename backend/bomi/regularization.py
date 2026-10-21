"""규제(regularization): 입력과 출력에 규칙과 moderate API를 적용하는 계층.

- **규칙**의 정의(정규식·단어 목록)는 chatbot/guardrails.py에 있고, 이 파일은 그 규칙을 에이전트별 정책(Policy)으로 묶어 적용합니다.
- **moderate API**는 외부 AI 창구 `llm.moderate`(OpenAI 키가 있을 때만 동작)입니다. 검사 API가 실패하면 서비스를 멈추지 않고 통과시킵니다.

적용 지점
| 단계 | 어디서 | 무엇을 |
|---|---|---|
| 요청 직후 | pipeline → `prepare` | 길이 검사, 최근 대화만 남기기, 개인정보 가리기 (담당 선택용 외부 AI 호출 전에 끝냄) |
| 입력 | 각 에이전트 → `screen_input` | 단어 규칙, moderate API(AI 모드에서만) |
| 출력 | 각 에이전트 → `redact_stream` / `redact` / `output_flagged` | 근거에 없는 연락처·URL·금액 가리기, moderate API(AI가 만든 글에만) |

외부 AI를 쓰지 않는 응답(자료 조회·고정 문구)에는 출력 moderate를 걸지 않습니다. 사람이 만든 자료이고, 호출만 늘기 때문입니다.
"""

import logging
from dataclasses import dataclass

from backend.bomi import aio
from backend.bomi.request import ChatRequest
from backend.chatbot import guardrails
from backend.chatbot.welfare.app.llm.client import LLM_ERRORS, ai_ready, llm

LOGGER = logging.getLogger(__name__)
MAX_QUESTION_CHARS = 2000
HISTORY_SIZE = 6  # 기억하는 이전 대화: 질문·답 3쌍


@dataclass(frozen=True)
class Policy:
    """에이전트 하나가 적용하는 규제."""

    blocked_words: bool = True  # 입력: 욕설·위험한 요청·지시 무력화 단어 규칙
    moderate_input: bool = True  # 입력: moderate API (AI 모드에서만 호출)
    redact_unverified: bool = False  # 출력: 근거 자료에 없는 연락처·URL·금액 가리기
    moderate_output: bool = False  # 출력: moderate API (AI가 만든 글에만 호출)


@dataclass(frozen=True)
class Prepared:
    request: ChatRequest
    pii_kinds: tuple[str, ...]


def prepare(request: ChatRequest) -> Prepared:
    """요청 직후 검사. 길이 초과는 ValueError라서 스트림 시작 전에 400이 됩니다."""
    if len(request.question) > MAX_QUESTION_CHARS:
        raise ValueError('질문은 1~2,000자로 입력하세요.')
    recent = list(request.messages[-(HISTORY_SIZE + 1) :])
    masked, kinds = guardrails.mask_messages(recent)
    # 외부 AI는 관리자 설정이 켜져 있을 때만 씁니다. 사용자가 켜도 설정이 꺼져 있으면 자료 기반으로 답합니다.
    use_ai = request.use_ai and ai_ready()
    return Prepared(request.with_messages(masked, use_ai=use_ai), tuple(kinds))


def rule_flagged(question: str) -> list[str]:
    """단어 규칙에 걸린 분류(외부 호출 없음). 빈 목록이면 통과."""
    return guardrails.blocked_words(question)


def history_rule_flagged(request: ChatRequest) -> list[str]:
    """Apply deterministic rules to every client-supplied user turn."""
    flagged = []
    for message in request.messages:
        if message.get('role') != 'user':
            continue
        for kind in rule_flagged(message.get('content', '')):
            if kind not in flagged:
                flagged.append(kind)
    return flagged


async def moderate_async(text: str) -> list[str]:
    """moderate API 결과. API 오류는 통과시키지 않고 검사 실패로 표시합니다."""
    try:
        return await llm.moderate(text)
    except (*LLM_ERRORS, AttributeError, IndexError, TimeoutError) as exc:
        LOGGER.warning('moderate API 실패, 현재 AI 처리를 안전하게 중단: %s', type(exc).__name__)
        return ['검사 실패']


class Regulator:
    """정책(Policy)에 따라 입력·출력을 규제합니다. 상태가 없어 에이전트가 공유해도 됩니다."""

    def screen_input(self, request: ChatRequest, policy: Policy) -> list[str]:
        """걸린 분류 목록. 비어 있지 않으면 에이전트는 답하지 않고 차단 안내를 보냅니다."""
        if policy.blocked_words:
            flagged = history_rule_flagged(request)
            if flagged:
                return flagged
        if policy.moderate_input and request.use_ai:
            return aio.run(moderate_async(request.question))
        return []

    def redact(self, text: str, material: str, policy: Policy) -> tuple[str, list[str]]:
        """(가린 글, 가린 정보 종류). 정책이 꺼져 있으면 그대로."""
        if not policy.redact_unverified:
            return text, []
        return guardrails.redact_unverified(text, material)

    def redact_stream(self, material: str, policy: Policy):
        """스트리밍 답변용 줄 단위 가리개. 정책이 꺼져 있으면 통과시키는 가리개를 돌려줍니다."""
        if policy.redact_unverified:
            return guardrails.StreamRedactor(material)
        return _PassThrough()

    async def output_flagged_async(
        self, text: str, policy: Policy, generated_by_ai: bool
    ) -> list[str]:
        """AI가 만든 글이 moderate API에 걸렸는지. 사람이 만든 자료·고정 문구에는 호출하지 않습니다."""
        if policy.moderate_output and generated_by_ai and text.strip():
            return await moderate_async(text)
        return []

    def output_flagged(self, text: str, policy: Policy, generated_by_ai: bool) -> list[str]:
        return aio.run(self.output_flagged_async(text, policy, generated_by_ai))


class _PassThrough:
    """StreamRedactor와 같은 인터페이스. 가리지 않습니다."""

    hidden: list = []

    def feed(self, text: str) -> str:
        return text

    def flush(self) -> str:
        return ''

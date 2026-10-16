"""지역 분석 에이전트: 동·그룹의 분석 근거와 이상신호를 설명합니다.

예전의 «지역 분석(analysis)»과 «지역 변화 신호(regional_v16)» 두 담당을 하나로 합친 것입니다.
어느 설명기로 답할지는 라우터가 아니라 이 에이전트 안에서 정합니다.

| 설명기 | 근거 | 쓰는 경우 |
|---|---|---|
| group    | 열어 둔 연령·성별 그룹 자료 (db/group_workspace) | 그룹 화면에서 그 그룹을 묻거나, v16 자료가 없을 때 |
| district | 동 분석 결과 (db/region_workspace)               | 화면 판정 용어를 묻거나, v16 자료가 없을 때 |
| v16      | DB1 SQLite 근거 (bomi/adapters/v16)              | 이상신호 목록·기준·연령별·지역 배경·소비 질문 |

v16 자료가 없는 서버에서는 group/district가 대신 답합니다. AI 해석이 실패하면 외부 AI 없이 같은 근거로 다시 답합니다.
"""
import logging
from typing import Iterator

from backend.bomi import questions
from backend.bomi.adapters import v16
from backend.bomi.agents.base import RegulatedAgent, Reply
from backend.bomi.events import Event
from backend.bomi.phrases import AI_ANALYSIS_FALLBACK_NOTICE
from backend.bomi.regularization import Policy
from backend.bomi.request import ChatRequest
from backend.chatbot.welfare.app.llm.client import LLM_ERRORS
from backend.db import group_workspace, region_workspace

LOGGER = logging.getLogger(__name__)
HISTORY_CHARS = 4000


def _recent(request: ChatRequest) -> list[dict]:
    return [{'role': m['role'], 'content': m['content'][:HISTORY_CHARS]} for m in request.history]


class RegionAnalysisAgent(RegulatedAgent):
    id = 'region_analysis'
    # AI 해석문의 연락처·URL·금액 가리기는 explain_ai가 근거 자료와 대조해 처리하고, 여기서는 moderate API를 겁니다.
    policy = Policy(blocked_words=True, moderate_input=True, redact_unverified=False, moderate_output=True)

    def answer(self, request: ChatRequest) -> Iterator[Event]:
        yield from self.deliver(self._reply(request))

    # ── 설명기 선택 ──────────────────────────────────────────────
    def _reply(self, request: ChatRequest) -> Reply:
        if self._uses_workspace(request):
            return self._workspace(request)
        return self._v16(request)

    @staticmethod
    def _uses_workspace(request: ChatRequest) -> bool:
        """동·그룹 분석 근거(workspace)가 답해야 하는지. 아니면 v16."""
        question = request.question
        if questions.is_screen_term_question(question):
            return True
        if request.group and questions.is_group_focused(question):
            return True
        return not v16.data_ready()

    # ── 설명기 ───────────────────────────────────────────────────
    def _v16(self, request: ChatRequest) -> Reply:
        group = (request.group.context, request.group.detail) if request.group else None
        result = v16.reply(request.question, request.history, request.context,
                           use_ai=request.use_ai, group=group)
        return Reply.from_legacy(result)

    def _workspace(self, request: ChatRequest) -> Reply:
        try:
            reply = Reply.from_legacy(self._explain(request, request.use_ai))
            reply.generated_by_ai = request.use_ai  # 동·그룹 설명은 AI 모드에서 외부 AI가 씁니다
            return reply
        except (*LLM_ERRORS, ValueError) as exc:
            if not request.use_ai:
                raise
            # AI 해석이 실패하면 외부 AI 없이 데이터 근거로 다시 답합니다.
            LOGGER.warning('AI 분석 해석 실패, 데이터 근거 안내로 대체: %s', type(exc).__name__)
            reply = Reply.from_legacy(self._explain(request, False))
            reply.error = AI_ANALYSIS_FALLBACK_NOTICE
            return reply

    def _explain(self, request: ChatRequest, use_ai: bool) -> dict:
        question = request.question
        if request.group:
            context, detail = request.group.context, request.group.detail
            if use_ai:
                return group_workspace.ai_explain(context, question, detail, _recent(request))
            return group_workspace.explain(context, question, detail)
        if use_ai:
            return region_workspace.ai_explain_region(request.context, question, request.data, _recent(request))
        return region_workspace.explain_region(request.context, question, request.data)

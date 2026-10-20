"""지역 분석 에이전트: 동·그룹의 분석 근거와 이상신호를 설명합니다.

예전의 «지역 분석(analysis)»과 «지역 변화 신호(regional_v16)» 두 담당을 하나로 합친 것입니다.
어느 설명기로 답할지는 라우터가 아니라 이 에이전트 안에서 정합니다.

| 설명기 | 근거 | 쓰는 경우 |
|---|---|---|
| group    | 열어 둔 연령·성별 그룹 자료 (db/group_workspace) | 그룹 화면에서 그 그룹을 묻거나, 지역 분석 자료가 없을 때 |
| district | 동 분석 결과 (db/region_workspace)               | 화면 판정 용어를 묻거나, 지역 분석 자료가 없을 때 |
| 지역 분석      | PostgreSQL·대시보드 근거 (bomi/adapters/regional_analysis)              | 이상신호 목록·기준·연령별·지역 배경·소비 질문 |

지역 분석 자료가 없는 서버에서는 group/district가 대신 답합니다. AI 해석이 실패하면 외부 AI 없이 같은 근거로 다시 답합니다.
"""
import logging
from typing import Iterator

from backend.bomi import questions
from backend.bomi.adapters import regional_analysis
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
        return self._engine_reply(request)

    @staticmethod
    def _uses_workspace(request: ChatRequest) -> bool:
        """동·그룹 분석 근거(workspace)가 답해야 하는지. 아니면 regional_analysis."""
        question = request.question
        if questions.is_screen_summary(question):
            return True
        if questions.is_screen_term_question(question):
            return True
        # 후보·이상신호 목록과 확인 여부는 화면 헤더와 같은 공식 탐지
        # 집계에서 답해야 합니다. v16 별도 저장소 결과를 섞지 않습니다.
        if (region_workspace._is_signal_list_question(question)
                or region_workspace._is_signal_presence_question(question)):
            return True
        if region_workspace._is_signal_reason_question(question):
            # A selected dashboard case is authoritative only for that same dong.
            # Explicit questions about another dong, missing selections, or missing
            # assessment payloads remain on v16 where their scope can be resolved.
            named = {match.group() for match in questions.DISTRICT_NAME.finditer(question)}
            return bool(request.district and 'assessment' in request.data
                        and (not named or request.district in named))
        # 연령대가 선택된 사회적 연결 카드의 추가 지표는 DB1 서울서베이
        # 집계 목록으로 답한다. 일반 지역 분석 신호 설명으로 보내면 현재 카드와
        # 관계없는 탐지 요약이 될 수 있다.
        if region_workspace._is_survey_metrics_question(question):
            return True
        if questions.is_tab_question(question):
            return True
        # 원본·다운로드 출처 질문은 화면에 열린 그룹의 실제 입력 메타데이터로
        # 답해야 한다. 엔진의 일반 신호 설명이나 외부 AI가 이를 대신하면,
        # 현재 화면과 무관한 탐지 요약으로 흘러갈 수 있다.
        if request.group and group_workspace._is_provenance_question(question):
            return True
        if request.group and questions.is_group_focused(question):
            return True
        return not regional_analysis.data_ready()

    # ── 설명기 ───────────────────────────────────────────────────
    def _engine_reply(self, request: ChatRequest) -> Reply:
        group = (request.group.context, request.group.detail) if request.group else None
        result = regional_analysis.reply(request.question, request.history, request.context,
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
        if (region_workspace._is_signal_list_question(question)
                or region_workspace._is_signal_presence_question(question)):
            return region_workspace.explain_region(request.context, question, request.data)
        if region_workspace._is_signal_reason_question(question):
            if use_ai:
                return region_workspace.ai_explain_region(request.context, question, request.data, _recent(request))
            return region_workspace.explain_region(request.context, question, request.data)
        # Social-connection survey questions use the DB1 annual survey context,
        # even when the dashboard also has a group selection.  Do not let the
        # generic group explanation or welfare agent turn them into a refusal.
        if questions.is_tab_question(question):
            if use_ai:
                return region_workspace.ai_explain_region(request.context, question, request.data, _recent(request))
            return region_workspace.explain_region(request.context, question, request.data)
        if region_workspace._is_survey_metrics_question(question):
            if use_ai:
                return region_workspace.ai_explain_region(request.context, question, request.data, _recent(request))
            return region_workspace.explain_region(request.context, question, request.data)
        if request.group:
            context, detail = request.group.context, request.group.detail
            if use_ai:
                return group_workspace.ai_explain(context, question, detail, _recent(request))
            return group_workspace.explain(context, question, detail)
        if use_ai:
            return region_workspace.ai_explain_region(request.context, question, request.data, _recent(request))
        return region_workspace.explain_region(request.context, question, request.data)

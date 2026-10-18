"""담당 에이전트 선택. 선택 규칙은 이 파일 한 곳에만 있습니다.

우선순위
1. 고정 규칙(fixed)  — 보고서 요청, 업무 방법 질문, 화면 용어 질문. AI를 부르지 않습니다.
2. AI 선택(ai)       — AI를 쓸 수 있을 때 ROUTER_PROMPT로 고릅니다. 실패하거나 알 수 없는 값이면 3으로 갑니다.
3. 키워드 규칙(rules) — 복지 단어 → 열린 그룹 질문 → 분석 단어 → 사업 이름 → 동 이름 → 안내.

자료 유무(v16 DB 파일 등)에 따른 대체는 여기서 하지 않습니다. 각 에이전트가 안에서 처리합니다.
"""
import json
import logging
import asyncio
from dataclasses import dataclass

from backend.bomi import questions
from backend.bomi import aio
from backend.chatbot.welfare.app.dialogue import retrieval
from backend.bomi.phrases import AGENT_LABELS, ROUTER_PROMPT
from backend.bomi.request import ChatRequest
from backend.chatbot.welfare.app.llm.client import LLM_ERRORS, llm

LOGGER = logging.getLogger(__name__)
AGENT_IDS = tuple(AGENT_LABELS)
# AI가 예전 에이전트 이름으로 답해도 같은 담당으로 받아 줍니다.
LEGACY_NAMES = {'analysis': 'region_analysis', 'regional_v16': 'region_analysis'}
BY_RULE, BY_AI = '규칙', 'AI'


@dataclass(frozen=True)
class Route:
    agent: str
    by: str

    @property
    def label(self) -> str:
        return AGENT_LABELS[self.agent]


class Router:
    def fixed(self, request: ChatRequest) -> str | None:
        """AI 사용 여부와 상관없이 규칙으로 정하는 담당. 해당하지 않으면 None."""
        question = request.question
        if questions.is_report_request(question):
            return 'report'
        if questions.work_guide(question):
            return 'guide'
        if questions.is_screen_term_question(question):
            return 'region_analysis'
        return None

    def by_rules(self, request: ChatRequest) -> str:
        question = request.question
        if any(word in question for word in questions.WELFARE_WORDS):
            return 'welfare'
        if request.group and questions.is_group_focused(question):
            return 'region_analysis'
        if any(word in question for word in questions.ANALYSIS_WORDS):
            return 'region_analysis'
        # 사업 이름(예: "세곡동행", "청년은?")을 물으면 복지사업으로 봅니다.
        if questions.program_name_hit(question, request.city):
            return 'welfare'
        if questions.mentions_district(question):
            return 'region_analysis'
        # 어느 업무에도 해당하지 않는 질문(날씨·잡담·코드 등)은 보미 안내로 답합니다.
        return 'guide'

    async def by_ai(self, request: ChatRequest) -> str | None:
        """AI가 고른 담당. 실패하거나 알 수 없는 값이면 None(호출한 쪽이 규칙으로 대체)."""
        recent = [{'role': m['role'], 'content': m['content'][:500]} for m in request.history[-4:]]
        screen = {key: request.context.get(key, '') for key in ('city', 'district', 'month')}
        if request.group:
            screen['group'] = {key: request.group.context.get(key, '') for key in ('district', 'month', 'age', 'sex')}
        messages = [{'role': 'system', 'content': ROUTER_PROMPT},
                    {'role': 'user', 'content': '선택된 화면 맥락(JSON 자료): ' + json.dumps(screen, ensure_ascii=False)},
                    *recent, {'role': 'user', 'content': request.question}]
        try:
            answer = await asyncio.wait_for(llm.complete(messages, json_mode=True, max_tokens=1000), 20)
            agent = json.loads(answer).get('agent')
        except (*LLM_ERRORS, ValueError, AttributeError, TimeoutError) as exc:
            LOGGER.warning('AI 담당 선택 실패, 규칙으로 대체: %s', type(exc).__name__)
            return None
        agent = LEGACY_NAMES.get(agent, agent)
        return agent if agent in AGENT_IDS else None

    def decide(self, request: ChatRequest, ai_agent: str | None = None) -> Route:
        """고정 규칙 → AI 선택(있으면) → 키워드 규칙 순서로 담당을 정합니다."""
        fixed = self.fixed(request)
        if fixed:
            return Route(fixed, BY_RULE)
        if request.welfare_state.get('records') and retrieval.is_followup(request.question):
            return Route('welfare', '대화 조건')
        selected = Route(ai_agent, BY_AI) if ai_agent else Route(self.by_rules(request), BY_RULE)
        if request.use_ai and selected.agent == 'guide':
            found = aio.run(retrieval.retrieve(request.question, city=request.city,
                                              district=request.district, use_ai=True))
            if found['records'] and found['mode'].startswith('hybrid_reranked'):
                request.retrieval.update(found)
                return Route('welfare', '의미 검색 확인')
        return selected

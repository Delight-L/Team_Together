"""보고서 작성 에이전트: 약식보고서 초안을 만들고 «보고서 탭에서 수정» 버튼을 붙입니다."""
from typing import Iterator

from backend.agents import report_writer
from backend.bomi.agents.base import RegulatedAgent, Reply
from backend.bomi.events import Event
from backend.bomi.phrases import GROUP_REPORT_NOTICE
from backend.bomi.regularization import Policy
from backend.bomi.request import ChatRequest
from backend.chatbot.welfare.app.dialogue.resources import get_resources_by_ids
from backend.db import mission_store, region_workspace


class ReportAgent(RegulatedAgent):
    id = 'report'
    # AI가 다듬은 문장은 report_writer.check_grounding이 근거와 대조하고, 그 위에 moderate API를 한 번 더 겁니다.
    policy = Policy(blocked_words=True, moderate_input=True, redact_unverified=False, moderate_output=True)

    def answer(self, request: ChatRequest) -> Iterator[Event]:
        reply = Reply.from_legacy(self._draft(request))
        if request.group and request.district:
            reply.notice = GROUP_REPORT_NOTICE.format(
                district=request.district, age=request.group.age, sex=request.group.sex)
        yield from self.deliver(reply)

    def _draft(self, request: ChatRequest) -> dict:
        """대화에서 찾은 사업·신규 구상안이 있으면 대화 기반 초안, 없으면 업무 기록 초안."""
        workflow, rows = {}, []
        if request.district:
            workflow = mission_store.load(request.context)
            rows = region_workspace.region_status(
                request.data, request.city, request.month, request.district)['rows']
            if request.age:
                rows = [row for row in rows if row.get('age_label') == request.age]
        sources = (request.welfare_state['records'] if request.welfare_state else
                   get_resources_by_ids(request.source_ids, city=request.city))
        return report_writer.report_reply(
            request.context, workflow, request.use_ai, request.question, rows, request.history, sources)

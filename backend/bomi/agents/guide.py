"""보미 안내: 업무 방법 질문·업무와 무관한 질문에 고정 문구로 답합니다. 외부 AI를 부르지 않습니다."""

from typing import Iterator

from backend.bomi import questions
from backend.bomi.agents.base import RegulatedAgent, Reply
from backend.bomi.events import Event
from backend.bomi.phrases import GUIDE, GUIDE_MODE
from backend.bomi.regularization import Policy
from backend.bomi.request import ChatRequest


class GuideAgent(RegulatedAgent):
    id = 'guide'
    # 고정 문구라 출력 규제는 필요 없습니다.
    policy = Policy(
        blocked_words=True, moderate_input=True, redact_unverified=False, moderate_output=False
    )

    def answer(self, request: ChatRequest) -> Iterator[Event]:
        text = questions.work_guide(request.question) or GUIDE
        yield from self.deliver(Reply(text, mode=GUIDE_MODE))

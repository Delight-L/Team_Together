"""담당 선택(4개 에이전트). 외부 AI는 가짜 응답으로 대체합니다."""
import unittest
from unittest.mock import AsyncMock, patch

from openai import OpenAIError

from backend.agents import report_writer
from backend.bomi import aio
from backend.bomi.routing import Route, Router
from backend.bomi.tests.helpers import GROUP, make_request
from backend.chatbot.tests.ai_config import ai_key
from backend.chatbot.welfare.app.llm.client import llm

ROUTER = Router()


def by_rules(question, group=None):
    return ROUTER.by_rules(make_request(question, group=group))


class RuleRoutingTest(unittest.TestCase):
    def test_rules_pick_agent_without_ai(self):
        cases = {'보고서 초안 만들어 줘': 'report', '보고서 써줘': 'report',
                 '병원에 함께 가줄 지원이 있나요?': 'welfare', '세곡동행': 'welfare',
                 '이 동의 변화를 요약해 줘': 'region_analysis', '후보 판정은 무슨 뜻인가요?': 'region_analysis'}
        for question, agent in cases.items():
            self.assertEqual(ROUTER.decide(make_request(question)).agent, agent, question)

    def test_screen_suggestions_reach_the_right_agent(self):
        # 화면 메뉴마다 보여 주는 예시 질문(frontend/src/BomiChat.jsx)이 맞는 담당으로 가는지 확인합니다.
        cases = {
            '이번 달 후보 지역을 알려 줘': 'region_analysis', '이 동의 변화를 요약해 줘': 'region_analysis',
            '이 동의 지표 변화를 설명해 줘': 'region_analysis', '후보 지역에서 다음에 확인할 일을 알려 줘': 'region_analysis',
            '이상신호 판정 기준은?': 'region_analysis', '삼성1동은?': 'region_analysis',
            '후보 판정은 무슨 뜻인가요?': 'region_analysis', '자료 부족과 기준 미해당은 어떻게 다른가요?': 'region_analysis',
            '평소 대비 차이와 전월 변화율은 어떻게 다른가요?': 'region_analysis',
            '혼자 사는 어르신 돌봄 지원': 'welfare', '이 지역의 지원사업 후보를 찾아 줘': 'welfare',
            '사업 이용 조건에서 무엇을 확인해야 하나요?': 'welfare', '사업 연계 전에 확인할 일을 알려 줘': 'welfare',
            '세곡동행': 'welfare', '청년은?': 'welfare', '외로워요': 'welfare',
            '보고서 초안 만들어 줘': 'report',
            '검토 의견에 어떤 내용을 기록해야 하나요?': 'guide', '현장에서 추가로 확인할 사항을 알려 줘': 'guide',
            '추가로 확인할 자료를 알려 줘': 'guide', '지역 집계자료를 보고서에 어떻게 설명해야 하나요?': 'guide',
            '보고서에 단정하면 안 되는 내용을 알려 줘': 'guide', '보고서 작성 방법을 알려줘': 'guide',
            '오늘 날씨 어때?': 'guide', '파이썬 코드 짜줘': 'guide',
        }
        for question, agent in cases.items():
            self.assertEqual(ROUTER.decide(make_request(question)).agent, agent, question)

    def test_how_to_report_question_is_not_a_draft_request(self):
        for question in ('보고서 작성 방법을 알려줘', '보고서 쓸 때 주의할 점은?', '보고서에 어떻게 써야 해?'):
            self.assertFalse(report_writer.is_draft_request(question), question)
        for question in ('보고서 초안 만들어 줘', '보고서 써줘', '보고서 작성해줘'):
            self.assertTrue(report_writer.is_draft_request(question), question)

    def test_open_group_sends_group_questions_to_region_analysis(self):
        self.assertEqual(by_rules('이 그룹의 변화를 요약해 줘', GROUP), 'region_analysis')
        self.assertEqual(by_rules('남성 비중은?', GROUP), 'region_analysis')
        # 그룹이 없으면 «남성 비중»은 어느 업무에도 맞지 않습니다.
        self.assertEqual(by_rules('남성 비중은?'), 'guide')

    def test_route_has_label(self):
        self.assertEqual(Route('region_analysis', '규칙').label, '지역 분석 에이전트')
        self.assertEqual(Route('guide', 'AI').label, '보미 안내')


class AiRoutingTest(unittest.TestCase):
    def ask_ai(self, answer, question='그럼 어디부터 살펴보면 될까?', history=()):
        complete = AsyncMock(side_effect=answer if isinstance(answer, Exception) else None,
                             return_value=None if isinstance(answer, Exception) else answer)
        with ai_key('test'), patch.object(llm, 'complete', complete):
            agent = aio.run(ROUTER.by_ai(make_request(question, history, use_ai=True)))
        return agent, complete

    def test_ai_choice_and_history_are_sent(self):
        history = [{'role': 'user', 'content': '2025년 하반기 확인할 지역 알려줘'},
                   {'role': 'assistant', 'content': '삼성1동에서 이동 변화가 나타났습니다.'}]
        agent, complete = self.ask_ai('{"agent": "region_analysis"}', history=history)
        self.assertEqual(agent, 'region_analysis')
        sent = complete.call_args.args[0]
        self.assertTrue(any('삼성1동' in entry['content'] for entry in sent))
        self.assertEqual(sent[-1]['content'], '그럼 어디부터 살펴보면 될까?')

    def test_legacy_agent_names_are_accepted(self):
        for legacy in ('analysis', 'regional_v16'):
            agent, _ = self.ask_ai('{"agent": "%s"}' % legacy)
            self.assertEqual(agent, 'region_analysis')

    def test_failure_or_unknown_agent_returns_none_so_rules_decide(self):
        for answer in (OpenAIError('secret'), '{"agent": "unknown"}', 'not json'):
            agent, _ = self.ask_ai(answer)
            self.assertIsNone(agent)
        route = ROUTER.decide(make_request('세곡동행', use_ai=True), ai_agent=None)
        self.assertEqual(route, Route('welfare', '규칙'))

    def test_fixed_rules_beat_ai_choice(self):
        route = ROUTER.decide(make_request('후보 판정은 무슨 뜻인가요?'), ai_agent='welfare')
        self.assertEqual(route, Route('region_analysis', '규칙'))
        route = ROUTER.decide(make_request('보고서 작성 방법을 알려줘'), ai_agent='welfare')
        self.assertEqual(route, Route('guide', '규칙'))
        self.assertEqual(ROUTER.decide(make_request('오늘 날씨 어때?'), ai_agent='guide'), Route('guide', 'AI'))


if __name__ == '__main__':
    unittest.main()

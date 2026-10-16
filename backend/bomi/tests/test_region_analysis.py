"""지역 분석 에이전트: 어떤 설명기(group / district / v16)가 답하는지, AI 실패 시 대체."""
import json
import unittest
from unittest.mock import AsyncMock, patch

from openai import OpenAIError

from backend.bomi.adapters import v16
from backend.bomi.tests.helpers import CONTEXT, GROUP, events, fake_complete
from backend.chatbot.tests.ai_config import ai_key
from backend.chatbot.welfare.app.llm.client import llm
from backend.db import group_workspace, region_workspace


class RegionAnalysisBase(unittest.TestCase):
    def setUp(self):
        for target in (ai_key(''), patch.object(llm, 'moderate', AsyncMock(return_value=[]))):
            target.start()
            self.addCleanup(target.stop)


class SelectionTest(RegionAnalysisBase):
    def test_v16_answers_regional_questions_with_history_and_context(self):
        history = [{'role': 'user', 'content': '2025년 12월 삼성1동은?'},
                   {'role': 'assistant', 'content': '삼성1동의 이동 변화 신호입니다.'}]
        reply_value = {'answer': '평일 이동이 6.1% 줄었습니다.', 'mode': '외부 AI 호출 없음',
                       'sources': [{'label': 'v16 · DB1'}]}
        with patch.object(v16, 'data_ready', return_value=True), \
                patch.object(v16, 'reply', return_value=reply_value) as reply, \
                patch.object(llm, 'complete') as complete, patch.object(llm, 'moderate') as moderate:
            result = dict(events('이동이 줄었다는 뜻이야?', history))
        self.assertEqual(result['route']['agent'], 'region_analysis')
        self.assertIn('6.1%', result['replace']['text'])
        self.assertEqual(result['replace']['source'], 'v16 · DB1')
        self.assertEqual(reply.call_args.args[1], history)
        self.assertFalse(reply.call_args.kwargs['use_ai'])
        complete.assert_not_called()
        moderate.assert_not_called()

    def test_missing_v16_data_falls_back_inside_the_agent(self):
        with patch.object(v16, 'data_ready', return_value=False), patch.object(v16, 'reply') as reply:
            result = dict(events('이 동의 변화를 요약해 줘'))
        self.assertEqual(result['route']['agent'], 'region_analysis')  # 라우터는 대체를 모릅니다
        self.assertIn('삼성1동', result['replace']['text'])
        reply.assert_not_called()

    def test_group_focused_question_uses_group_workspace_even_when_v16_ready(self):
        with patch.object(v16, 'data_ready', return_value=True), patch.object(v16, 'reply') as reply, \
                patch.object(group_workspace, 'explain',
                             return_value={'answer': '그룹 근거입니다.', 'mode': '데이터 근거 안내 · 외부 AI 호출 없음',
                                           'sources': [{'label': 'DB1 · 집단별 유동인구'}]}) as explain:
            result = dict(events('이 그룹의 변화를 요약해 줘', group=GROUP))
        reply.assert_not_called()
        explain.assert_called_once()
        self.assertEqual(result['replace']['text'], '그룹 근거입니다.')
        self.assertEqual(result['replace']['source'], 'DB1 · 집단별 유동인구')

    def test_screen_term_question_uses_district_workspace_even_when_v16_ready(self):
        with patch.object(v16, 'data_ready', return_value=True), patch.object(v16, 'reply') as reply:
            result = dict(events('자료 부족과 기준 미해당은 어떻게 다른가요?'))
        reply.assert_not_called()
        self.assertIn('«판단 보류»(이력 부족)', result['replace']['text'])

    def test_followups_notice_and_actions_follow_contract_order(self):
        questions = ['왜 삼성1동이 확인 대상인가요?', '삼성1동의 지역 배경 정보 보여줘']
        value = {'answer': '삼성1동의 이동 변화입니다.', 'followUps': questions, 'notice': '성별 구분 없음'}
        with patch.object(v16, 'data_ready', return_value=True), patch.object(v16, 'reply', return_value=value):
            result = events('2025년 하반기 이상신호 지역 알려줘')
        self.assertEqual([name for name, _ in result], ['route', 'replace', 'follow_ups', 'notice', 'done'])
        self.assertEqual(dict(result)['follow_ups']['questions'], questions)


class AiFallbackTest(RegionAnalysisBase):
    def test_admin_ai_off_keeps_v16_offline(self):
        # 사용자가 AI를 켜도 관리자가 꺼 두었으면 외부 AI를 부르지 않습니다.
        with patch.object(v16, 'data_ready', return_value=True), \
                patch.object(v16, 'reply', return_value={'answer': 'DB1 분석입니다.'}) as reply, \
                patch.object(llm, 'complete') as complete, patch.object(llm, 'moderate') as moderate:
            result = dict(events('이상신호 탐지 기준은?', ai=True))
        self.assertEqual(result['route']['agent'], 'region_analysis')
        self.assertFalse(reply.call_args.kwargs['use_ai'])
        complete.assert_not_called()
        moderate.assert_not_called()

    def test_v16_dispatch_does_not_use_legacy_analysis_generation(self):
        with ai_key('test'), patch.object(v16, 'data_ready', return_value=True), \
                patch.object(llm, 'complete', fake_complete('{"agent": "region_analysis"}')), \
                patch.object(llm, 'stream') as legacy_stream, \
                patch.object(v16, 'reply', return_value={
                    'answer': '삼성1동의 이동 변화입니다.', 'mode': 'v16 · AI 의도 판단 · DB1 근거'}) as reply:
            result = events('이 동의 변화를 요약해 줘', ai=True)
        self.assertEqual(dict(result)['route'], {'agent': 'region_analysis', 'label': '지역 분석 에이전트', 'by': 'AI'})
        self.assertIn('AI 의도 판단', dict(result)['replace']['mode'])
        self.assertTrue(reply.call_args.kwargs['use_ai'])
        legacy_stream.assert_not_called()

    def test_ai_failure_falls_back_to_data_evidence_with_error_first(self):
        async def broken(messages):
            raise OpenAIError('secret')
            yield ''
        with ai_key('test'), patch.object(v16, 'data_ready', return_value=False), \
                patch.object(llm, 'complete', fake_complete('{"agent": "region_analysis"}')), \
                patch.object(llm, 'stream', broken):
            result = events('이 동의 변화를 요약해 줘', ai=True)
        names = [name for name, _ in result]
        self.assertEqual(names, ['route', 'error', 'replace', 'done'])
        self.assertIn('외부 AI 호출 없음', dict(result)['replace']['mode'])
        self.assertNotIn('secret', json.dumps(result, ensure_ascii=False))

    def test_non_ai_value_error_is_not_swallowed(self):
        with patch.object(v16, 'data_ready', return_value=False), \
                patch.object(region_workspace, 'explain_region', side_effect=ValueError('입력 오류')), \
                patch('backend.bomi.events.LOGGER.exception'):
            result = events('이 동의 변화를 요약해 줘')
        self.assertEqual([name for name, _ in result][-2:], ['error', 'done'])


if __name__ == '__main__':
    unittest.main()

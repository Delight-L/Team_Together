"""총괄 → v16 연결 검사. 외부 AI와 v16 조회는 가짜 응답으로 대체합니다.

v16 근거 자료(DB1 SQLite)는 저장소에 없으므로 data_ready를 가짜로 바꿔 검사합니다.
"""
import json
import unittest
from unittest.mock import AsyncMock, patch

from backend.agents import supervisor
from backend.chatbot.tests.test_supervisor import CONTEXT, DATA
from backend.chatbot.tests.ai_config import ai_key
from backend.chatbot.welfare.app.llm.client import llm


class SupervisorV16Test(unittest.TestCase):
    def setUp(self):
        for target in (ai_key(''), patch.object(supervisor.v16_service, 'data_ready', return_value=True)):
            target.start()
            self.addCleanup(target.stop)

    def stream(self, question, history=(), group=None, ai=False):
        return dict(supervisor.stream([*history, {'role': 'user', 'content': question}],
                                      CONTEXT, DATA, group, use_ai=ai))

    def test_llm_chooses_v16_for_paraphrase_and_receives_history(self):
        history = [{'role': 'user', 'content': '2025년 하반기 확인할 지역 알려줘'},
                   {'role': 'assistant', 'content': '삼성1동에서 이동 변화가 나타났습니다.'}]
        complete = AsyncMock(return_value='{"agent":"regional_v16"}')
        with ai_key('test'), patch.object(llm, 'complete', complete):
            result = supervisor.route('그럼 어디부터 살펴보면 될까?', history, CONTEXT, True)
        self.assertEqual(result, ('regional_v16', 'AI'))
        complete.assert_awaited_once()
        sent = complete.call_args.args[0]
        self.assertTrue(any('삼성1동' in entry['content'] for entry in sent))
        self.assertEqual(sent[-1]['content'], '그럼 어디부터 살펴보면 될까?')

    def test_data_mode_calls_v16_with_history_and_context(self):
        history = [{'role': 'user', 'content': '2025년 12월 삼성1동은?'},
                   {'role': 'assistant', 'content': '삼성1동의 이동 변화 신호입니다.'}]
        with patch.object(supervisor.v16_service, 'reply', return_value={
                'answer': '평일 이동이 6.1% 줄었습니다.', 'mode': '외부 AI 호출 없음',
                'sources': [{'label': 'v16 · DB1'}]}) as reply, \
                patch.object(llm, 'complete') as complete, patch.object(llm, 'moderate') as moderate:
            result = self.stream('이동이 줄었다는 뜻이야?', history)
        self.assertEqual(result['route']['agent'], 'regional_v16')
        self.assertIn('6.1%', result['replace']['text'])
        self.assertEqual(reply.call_args.args[1], history)
        self.assertEqual(reply.call_args.args[2], CONTEXT)
        self.assertFalse(reply.call_args.kwargs['use_ai'])
        complete.assert_not_called()
        moderate.assert_not_called()

    def test_open_group_does_not_narrow_regional_search(self):
        group = ({'district': '삼성1동', 'age': '30대', 'sex': '남성', 'month': '2025-12'}, {})
        self.assertEqual(supervisor.rule_route('이 그룹의 변화를 요약해 줘', CONTEXT, group), 'analysis')
        with patch.object(supervisor.v16_service, 'reply', return_value={'answer': '탐지 지역: 삼성1동'}) as reply:
            result = self.stream('2025년 하반기 이상신호 탐지 지역 알려줘', group=group)
        self.assertEqual(result['route']['agent'], 'regional_v16')
        self.assertEqual(reply.call_args.kwargs['group'], group)

    def test_masking_happens_before_v16(self):
        with patch.object(supervisor.v16_service, 'reply', return_value={'answer': '지역 배경입니다.'}) as reply:
            result = self.stream('010-1234-5678 삼성1동 지역 배경 보여줘')
        self.assertNotIn('5678', reply.call_args.args[0])
        self.assertIn('notice', result)

    def test_admin_ai_off_keeps_v16_offline(self):
        # v16도 관리자 AI 설정을 따릅니다. 사용자가 AI를 켜도 관리자가 꺼 두었으면 외부 AI를 부르지 않습니다.
        with patch.object(supervisor.v16_service, 'reply', return_value={'answer': 'DB1 분석입니다.'}) as reply, \
                patch.object(llm, 'complete') as complete, patch.object(llm, 'moderate') as moderate:
            result = self.stream('이상신호 탐지 기준은?', ai=True)
        self.assertEqual(result['route']['agent'], 'regional_v16')
        self.assertFalse(reply.call_args.kwargs['use_ai'])
        complete.assert_not_called()
        moderate.assert_not_called()

    def test_missing_v16_data_falls_back_to_region_analysis(self):
        with patch.object(supervisor.v16_service, 'data_ready', return_value=False), \
                patch.object(supervisor.v16_service, 'reply') as reply:
            result = self.stream('이 동의 변화를 요약해 줘')
        self.assertEqual(result['route']['agent'], 'analysis')
        self.assertIn('삼성1동', result['replace']['text'])
        reply.assert_not_called()

    def test_answer_specific_followups_are_forwarded(self):
        questions = ['왜 삼성1동이 확인 대상인가요?', '삼성1동의 지역 배경 정보 보여줘', '이상신호 기준은 무엇인가요?']
        with patch.object(supervisor.v16_service, 'reply', return_value={
                'answer': '삼성1동의 이동 변화입니다.', 'followUps': questions}):
            result = self.stream('2025년 하반기 이상신호 지역 알려줘')
        self.assertEqual(result['follow_ups']['questions'], questions)

    def test_v16_failure_finishes_stream_without_exposing_details(self):
        with patch.object(supervisor.v16_service, 'reply', side_effect=RuntimeError('private-detail')), \
                patch.object(supervisor.LOGGER, 'exception'):
            result = self.stream('이상신호 기준은?')
        self.assertIn('error', result)
        self.assertIn('done', result)
        self.assertNotIn('private-detail', json.dumps(result))

    def test_welfare_and_report_remain_separate(self):
        with patch.object(supervisor.v16_service, 'reply') as reply, \
                patch.object(supervisor.welfare_service, 'stream_reply', return_value=iter([
                    ('replace', {'text': '복지사업 안내입니다.'}), ('done', {})])), \
                patch.object(supervisor.mission_store, 'load', return_value={}):
            self.assertEqual(self.stream('병원 동행 지원사업을 찾아줘')['route']['agent'], 'welfare')
            self.assertEqual(self.stream('보고서 초안 만들어줘')['route']['agent'], 'report')
        reply.assert_not_called()

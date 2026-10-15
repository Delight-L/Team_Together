"""총괄 에이전트의 담당 선택과 보고서 AI 문장 대조 검사. 외부 AI는 가짜 응답으로 대체합니다."""
import json
import unittest
from unittest.mock import AsyncMock, patch

from openai import OpenAIError

from backend.agents import report_writer, supervisor
from backend.chatbot.welfare.app.config import settings
from backend.chatbot.welfare.app.llm.client import llm
from backend.chatbot.tests.ai_config import ai_key

CONTEXT = {'city': '강남구', 'district': '삼성1동', 'month': '2025-12',
           'user': {'id': 'tester', 'admin': False, 'org': '강남구'}, 'workflow_mode': 'live'}
DATA = {'months': ['2025-11', '2025-12'], 'runId': 'test-run', 'assessment': [
    {'기준연월': '2025-12', '행정동명': '삼성1동', 'metric_label': '전화 연락', 'change_pct': -12.3,
     'relative_change_pp': -3.0, 'is_risk_signal': True, 'has_enough_history': True},
    {'기준연월': '2025-11', '행정동명': '삼성1동', 'metric_label': '전화 연락', 'change_pct': 1.0,
     'relative_change_pp': 0.0, 'is_risk_signal': False, 'has_enough_history': True}]}
WORKFLOW = {'done': [0, 1, 2], 'analysis_evidence': [
    {'is_risk_signal': True, 'metric_label': '전화 연락', 'change_pct': -12.3}],
    'reviews': [{'service_key': 'a', 'name': '교류 지원', 'decision': '적합', 'note': '교류 지원 검토'},
                {'service_key': 'b', 'name': '상담 지원', 'decision': '보류', 'note': '자격 확인 필요'}]}


def events(question, ai=False, history=()):
    messages = [*history, {'role': 'user', 'content': question}]
    return list(supervisor.stream(messages, CONTEXT, DATA, None, use_ai=ai))


def fake_complete(answer):
    async def complete(messages, json_mode=False, max_tokens=None):
        if isinstance(answer, Exception):
            raise answer
        return answer
    return complete


class RouteTest(unittest.TestCase):
    def setUp(self):
        key = ai_key('')
        key.start()
        self.addCleanup(key.stop)
        # 유해 콘텐츠 검사도 외부로 나가지 않게 통과 결과로 대체합니다(검사 자체는 test_guardrails에서 확인).
        moderate = patch.object(llm, 'moderate', AsyncMock(return_value=[]))
        moderate.start()
        self.addCleanup(moderate.stop)
        # v16 근거 자료(DB1 SQLite)가 없는 서버 기준: 동 분석은 기존 지역 분석 담당이 답합니다(v16 연결은 test_supervisor_v16).
        v16_data = patch.object(supervisor.v16_service, 'data_ready', return_value=False)
        v16_data.start()
        self.addCleanup(v16_data.stop)

    def test_rules_pick_agent_without_ai(self):
        cases = {'보고서 초안 만들어 줘': 'report', '보고서 써줘': 'report',
                 '병원에 함께 가줄 지원이 있나요?': 'welfare', '세곡동행': 'welfare',
                 '이 동의 변화를 요약해 줘': 'regional_v16', '후보 판정은 무슨 뜻인가요?': 'analysis'}
        for question, agent in cases.items():
            self.assertEqual(supervisor.rule_route(question, CONTEXT), agent, question)

    def test_screen_suggestions_reach_the_right_agent(self):
        # 화면 메뉴마다 보여 주는 예시 질문(frontend/src/BomiChat.jsx)이 맞는 담당으로 가는지 확인합니다.
        cases = {
            '이번 달 후보 지역을 알려 줘': 'regional_v16', '이 동의 변화를 요약해 줘': 'regional_v16',
            '이 동의 지표 변화를 설명해 줘': 'regional_v16', '후보 지역에서 다음에 확인할 일을 알려 줘': 'regional_v16',
            '이상신호 판정 기준은?': 'regional_v16', '삼성1동은?': 'regional_v16',
            '후보 판정은 무슨 뜻인가요?': 'analysis', '자료 부족과 기준 미해당은 어떻게 다른가요?': 'analysis',
            '평소 대비 차이와 전월 변화율은 어떻게 다른가요?': 'analysis',
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
            self.assertEqual(supervisor.rule_route(question, CONTEXT), agent, question)

    def test_how_to_report_question_is_not_a_draft_request(self):
        for question in ('보고서 작성 방법을 알려줘', '보고서 쓸 때 주의할 점은?', '보고서에 어떻게 써야 해?'):
            self.assertFalse(report_writer.is_draft_request(question), question)
        for question in ('보고서 초안 만들어 줘', '보고서 써줘', '보고서 작성해줘'):
            self.assertTrue(report_writer.is_draft_request(question), question)

    def test_work_guides_and_screen_terms_answer_without_v16(self):
        with patch.object(supervisor.v16_service, 'data_ready', return_value=True), \
                patch.object(supervisor.v16_service, 'reply') as reply:
            note = dict(events('검토 의견에 어떤 내용을 기록해야 하나요?'))
            report = dict(events('보고서에 단정하면 안 되는 내용을 알려 줘'))
            terms = dict(events('자료 부족과 기준 미해당은 어떻게 다른가요?'))
            score = dict(events('평소 대비 차이와 전월 변화율은 어떻게 다른가요?'))
        reply.assert_not_called()
        self.assertEqual(note['route']['agent'], 'guide')
        self.assertIn('후속 조치', note['replace']['text'])
        self.assertIn('원인을 확정하지 마세요', report['replace']['text'])
        self.assertEqual(terms['route']['agent'], 'analysis')
        self.assertIn('«판단 보류»(이력 부족)', terms['replace']['text'])
        self.assertIn('후보 판정은 전월 변화율이 아니라 평소 대비 차이로 합니다', score['replace']['text'])

    def test_fixed_rules_skip_ai_routing(self):
        complete = AsyncMock(return_value='{"agent": "regional_v16"}')
        with ai_key('test'), patch.object(llm, 'complete', complete), \
                patch.object(supervisor.v16_service, 'data_ready', return_value=True):
            self.assertEqual(supervisor.route('후보 판정은 무슨 뜻인가요?', [], CONTEXT, True), ('analysis', '규칙'))
            self.assertEqual(supervisor.route('보고서 작성 방법을 알려줘', [], CONTEXT, True), ('guide', '규칙'))
            result = dict(events('자료 부족과 기준 미해당은 어떻게 다른가요?', ai=True))
        complete.assert_not_awaited()
        self.assertEqual(result['route'], {'agent': 'analysis', 'label': '지역 분석 에이전트', 'by': '규칙'})

    def test_welfare_route_streams_sources(self):
        result = events('병원 동행')
        self.assertEqual(result[0], ('route', {'agent': 'welfare', 'label': '복지사업 에이전트', 'by': '규칙'}))
        self.assertIn('sources', [e for e, _ in result])
        self.assertEqual(result[-1], ('done', {}))

    def test_analysis_route_answers_from_data(self):
        result = dict(events('이 동의 변화를 요약해 줘'))
        self.assertEqual(result['route']['agent'], 'analysis')
        self.assertIn('삼성1동', result['replace']['text'])
        self.assertIn('외부 AI 호출 없음', result['replace']['mode'])

    def test_report_route_explains_missing_steps(self):
        with patch('backend.db.mission_store.load_all', return_value={}):
            result = dict(events('보고서 초안 만들어 줘'))
        self.assertEqual(result['route']['agent'], 'report')
        self.assertIn('근거가 아직 없어요', result['replace']['text'])
        self.assertEqual(result['actions']['actions'][0]['view'], 'report')

    def test_report_route_returns_draft_action(self):
        with patch('backend.db.mission_store.load_all', return_value={supervisor.mission_store.identity(CONTEXT): WORKFLOW}):
            result = dict(events('보고서 작성해줘'))
        draft = result['actions']['actions'][0]['reportDraft']
        self.assertEqual(draft['context']['district'], '삼성1동')
        self.assertIn('교류 지원', result['replace']['text'])

    def test_welfare_ai_gets_risk_signal_summary(self):
        seen = {}
        async def tokens(messages):
            seen['system'] = messages[0]['content']
            yield '기획안'
        with ai_key('test'), patch.object(llm, 'complete', fake_complete('{"agent": "welfare"}')), \
                patch.object(llm, 'stream', tokens):
            events('신규 사업 구상해 줘', ai=True)
        self.assertIn('후보_지표', seen['system'])
        self.assertIn('전화 연락', seen['system'])
        self.assertIn('-12.3%', seen['system'])
        summary = supervisor.signal_summary(CONTEXT, DATA, ({'age': '70대', 'sex': '여성'}, {}))
        self.assertEqual(summary['후보_지표_수'], 1)
        self.assertIn('동 전체 값', summary['선택_그룹'])
        self.assertIsNone(supervisor.signal_summary(CONTEXT | {'district': ''}, DATA))

    def test_group_report_says_district_basis(self):
        group = ({'age': '70대', 'sex': '여성', 'district': '삼성1동'}, {})
        with patch('backend.db.mission_store.load_all', return_value={}):
            result = dict(supervisor.stream([{'role': 'user', 'content': '보고서 초안 만들어 줘'}],
                                            CONTEXT, DATA, group, use_ai=False))
            without_group = dict(events('보고서 초안 만들어 줘'))
        self.assertIn('삼성1동 동 전체 기준', result['notice']['message'])
        self.assertIn('70대 · 여성', result['notice']['message'])
        self.assertNotIn('notice', without_group)

    def test_long_question_rejected_before_stream(self):
        with self.assertRaises(ValueError):
            supervisor.stream([{'role': 'user', 'content': 'x' * 2001}], CONTEXT, DATA)

    def test_ai_route_and_fallback(self):
        with ai_key('test'), \
                patch.object(llm, 'complete', fake_complete('{"agent": "guide"}')):
            result = dict(events('오늘 날씨 어때?', ai=True))
        self.assertEqual(result['route'], {'agent': 'guide', 'label': '보미 안내', 'by': 'AI'})
        self.assertIn('보고서 초안', result['replace']['text'])
        with ai_key('test'), \
                patch.object(llm, 'complete', fake_complete(OpenAIError('secret'))):
            self.assertEqual(supervisor.route('이 동의 변화 추이는?', [], CONTEXT, True), ('regional_v16', '규칙'))
        with ai_key('test'), \
                patch.object(llm, 'complete', fake_complete('{"agent": "unknown"}')):
            self.assertEqual(supervisor.route('세곡동행', [], CONTEXT, True), ('welfare', '규칙'))

    def test_v16_dispatch_does_not_use_legacy_analysis_generation(self):
        with ai_key('test'), patch.object(supervisor.v16_service, 'data_ready', return_value=True), \
                patch.object(llm, 'complete', fake_complete('{"agent": "regional_v16"}')), \
                patch.object(llm, 'stream') as legacy_stream, \
                patch.object(supervisor.v16_service, 'reply', return_value={
                    'answer': '삼성1동의 이동 변화입니다.', 'mode': 'v16 · AI 의도 판단 · DB1 근거'}) as reply:
            result = events('이 동의 변화를 요약해 줘', ai=True)
        self.assertEqual(dict(result)['route']['agent'], 'regional_v16')
        self.assertIn('AI 의도 판단', dict(result)['replace']['mode'])
        self.assertTrue(reply.call_args.kwargs['use_ai'])
        legacy_stream.assert_not_called()

    def test_ai_analysis_failure_falls_back_to_data(self):
        async def broken(messages):
            raise OpenAIError('secret')
            yield ''
        with ai_key('test'), \
                patch.object(llm, 'complete', fake_complete('{"agent": "analysis"}')), \
                patch.object(llm, 'stream', broken):
            result = events('이 동의 변화를 요약해 줘', ai=True)
        kinds = [e for e, _ in result]
        self.assertIn('error', kinds)
        self.assertIn('외부 AI 호출 없음', dict(result)['replace']['mode'])
        self.assertNotIn('secret', json.dumps(result, ensure_ascii=False))


class ReportPolishTest(unittest.TestCase):
    def setUp(self):
        key = ai_key('test')
        key.start()
        self.addCleanup(key.stop)
        self.base = report_writer.generate_draft(CONTEXT, WORKFLOW)

    def polished(self, **changes):
        result = {key: self.base[key] + ' 검토함' for key, _ in report_writer.SECTIONS}
        return result | changes

    def write(self, answer):
        with patch.object(llm, 'complete', fake_complete(answer)):
            return report_writer.write_draft(CONTEXT, WORKFLOW, use_ai=True, request='간결하게')

    def test_grounded_ai_text_is_used(self):
        draft = self.write(json.dumps(self.polished()))
        self.assertIn('대조 완료', draft['mode'])
        self.assertTrue(draft['summary'].endswith('검토함'))
        self.assertNotIn('notice', draft)

    def test_new_number_or_missing_service_falls_back(self):
        for bad in (self.polished(summary='예산 5,000만원 확보 예정'),
                    self.polished(proposal='상담 지원: 운영 조건 확인 후 재검토'),
                    self.polished(situation='변화가 큼')):
            draft = self.write(json.dumps(bad))
            self.assertEqual(draft['summary'], self.base['summary'])
            self.assertIn('자료와 일치하지 않는 내용', draft['notice'])

    def test_unverified_link_shows_plain_notice_and_original_draft(self):
        draft = self.write(json.dumps(self.polished(summary='참고 https://example.org/new')))
        self.assertEqual(draft['summary'], self.base['summary'])
        self.assertIn('확인되지 않은 링크', draft['notice'])
        self.assertIn('초안은 수정해서 사용할 수 있습니다', draft['notice'])

    def test_ai_error_and_invalid_json_fall_back(self):
        for answer in (OpenAIError('secret'), 'not json'):
            draft = self.write(answer)
            self.assertEqual(draft['proposal'], self.base['proposal'])
            self.assertIn('완료하지 못해', draft['notice'])
            self.assertNotIn('secret', draft['notice'])

    def test_without_ai_returns_template(self):
        self.assertEqual(report_writer.write_draft(CONTEXT, WORKFLOW), self.base)
        with ai_key(''):
            self.assertIn('연결 설정이 없어', report_writer.write_draft(CONTEXT, WORKFLOW, use_ai=True)['notice'])



class ConversationDraftTest(unittest.TestCase):
    """«보고서 작성해줘»: 대화에서 찾은 사업·신규 구상안으로 담당자 검토 전 초안을 만듭니다."""
    def setUp(self):
        for target in (ai_key(''), patch.object(llm, 'moderate', AsyncMock(return_value=[])),
                       patch('backend.db.mission_store.load_all', return_value={})):
            target.start()
            self.addCleanup(target.stop)

    def test_found_services_become_pending_proposals(self):
        from backend.chatbot.welfare.app.dialogue.resources import RESOURCES
        record = RESOURCES[0]
        messages = [{'role': 'user', 'content': '어르신 돌봄 사업 찾아 줘'},
                    {'role': 'assistant', 'content': '자료에서 찾았어요.'},
                    {'role': 'user', 'content': '보고서 작성해줘'}]
        result = dict(supervisor.stream(messages, CONTEXT, DATA, None, False, [record['id'], 'unknown-id']))
        draft = result['actions']['actions'][0]['reportDraft']
        self.assertIn('대화 기반 초안', draft['title'])
        self.assertIn(record['name'], draft['proposal'])
        self.assertIn(report_writer.PENDING_TEXT, draft['proposal'])
        self.assertIn('전월보다 12.3% 감소', draft['situation'])  # 이 동의 분석 수치
        self.assertEqual(draft['conversation_sources'], [{'id': record['id'], 'name': record['name']}])
        self.assertIn('검토 전 초안', result['replace']['text'])

    def test_new_program_plan_is_marked_not_running(self):
        history = [{'role': 'user', 'content': '신규 사업 구상해 줘'},
                   {'role': 'assistant', 'content': report_writer.PLANNING_LABEL + '\n\n1. 이웃 안부 모임'}]
        reply = report_writer.report_reply(CONTEXT, {}, False, '보고서 작성해줘', [], history, [])
        draft = reply['actions'][0]['reportDraft']
        self.assertIn('이웃 안부 모임', draft['proposal'])
        self.assertIn(report_writer.NOT_RUNNING_TEXT, draft['proposal'])

    def test_polish_must_keep_pending_phrase(self):
        history = [{'role': 'assistant', 'content': report_writer.PLANNING_LABEL + '\n이웃 안부 모임'}]
        base = report_writer.conversation_draft(CONTEXT, {}, [], history, [])
        bad = {key: base[key].replace(report_writer.PENDING_TEXT, '추진 확정') for key in report_writer.SECTION_KEYS}
        self.assertIn(f'판단 문구 변경 «{report_writer.PENDING_TEXT}»', report_writer.check_grounding(bad, base))

    def test_nothing_to_report_explains_next_step(self):
        reply = report_writer.report_reply(CONTEXT, {}, False, '보고서 작성해줘')
        self.assertIn('근거가 아직 없어요', reply['answer'])

    def test_only_recent_three_pairs_are_used(self):
        long_history = [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': f'메시지 {i}'} for i in range(10)]
        seen = {}
        def fake_answer(agent, question, history, *args):
            seen['history'] = history
            return {'answer': '확인', 'mode': '테스트'}, None
        with patch.object(supervisor, '_answer', fake_answer):
            list(supervisor.stream([*long_history, {'role': 'user', 'content': '이 동의 변화를 요약해 줘'}],
                                   CONTEXT, DATA, None, False))
        self.assertEqual([m['content'] for m in seen['history']], [f'메시지 {i}' for i in range(4, 10)])


if __name__ == '__main__':
    unittest.main()

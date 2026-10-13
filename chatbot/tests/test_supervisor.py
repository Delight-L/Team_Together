"""총괄 에이전트의 담당 선택과 보고서 AI 문장 대조 검사. 외부 AI는 가짜 응답으로 대체합니다."""
import json
import unittest
from unittest.mock import AsyncMock, patch

from openai import OpenAIError

from agents import report_writer, supervisor
from chatbot.welfare.app.config import settings
from chatbot.welfare.app.llm.client import llm
from chatbot.tests.ai_config import ai_key

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

    def test_rules_pick_agent_without_ai(self):
        cases = {'보고서 초안 만들어 줘': 'report', '보고서 써줘': 'report',
                 '병원에 함께 가줄 지원이 있나요?': 'welfare', '세곡동행': 'welfare',
                 '이 동의 변화를 요약해 줘': 'analysis', '후보 판정은 무슨 뜻인가요?': 'analysis'}
        for question, agent in cases.items():
            self.assertEqual(supervisor.rule_route(question, CONTEXT), agent, question)

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
        with patch('db.mission_store.load_all', return_value={}):
            result = dict(events('보고서 초안 만들어 줘'))
        self.assertEqual(result['route']['agent'], 'report')
        self.assertIn('근거가 아직 없어요', result['replace']['text'])
        self.assertEqual(result['actions']['actions'][0]['view'], 'report')

    def test_report_route_returns_draft_action(self):
        with patch('db.mission_store.load_all', return_value={supervisor.mission_store.identity(CONTEXT): WORKFLOW}):
            result = dict(events('보고서 작성해줘'))
        draft = result['actions']['actions'][0]['reportDraft']
        self.assertEqual(draft['context']['district'], '삼성1동')
        self.assertIn('교류 지원', result['replace']['text'])

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
            self.assertEqual(supervisor.route('후보 판정은 무슨 뜻', [], CONTEXT, True), ('analysis', '규칙'))
        with ai_key('test'), \
                patch.object(llm, 'complete', fake_complete('{"agent": "unknown"}')):
            self.assertEqual(supervisor.route('세곡동행', [], CONTEXT, True), ('welfare', '규칙'))

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
                       patch('db.mission_store.load_all', return_value={})):
            target.start()
            self.addCleanup(target.stop)

    def test_found_services_become_pending_proposals(self):
        from chatbot.welfare.app.agent.resources import RESOURCES
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

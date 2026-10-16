"""보고서 작성 에이전트: 초안 생성·AI 문장 다듬기 대조·대화 기반 초안·그룹 화면 안내."""
import json
import unittest
from unittest.mock import AsyncMock, patch

from openai import OpenAIError

from backend.agents import report_writer
from backend.bomi.adapters import v16
from backend.bomi.tests.helpers import CONTEXT, DATA, GROUP, WORKFLOW, events, fake_complete
from backend.chatbot.tests.ai_config import ai_key
from backend.chatbot.welfare.app.llm.client import llm
from backend.db import mission_store


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
                       patch('backend.db.mission_store.load_all', return_value={}),
                       patch.object(v16, 'data_ready', return_value=False)):
            target.start()
            self.addCleanup(target.stop)

    def test_found_services_become_pending_proposals(self):
        from backend.chatbot.welfare.app.dialogue.resources import RESOURCES
        record = RESOURCES[0]
        messages = [{'role': 'user', 'content': '어르신 돌봄 사업 찾아 줘'},
                    {'role': 'assistant', 'content': '자료에서 찾았어요.'},
                    {'role': 'user', 'content': '보고서 작성해줘'}]
        result = dict(events('보고서 작성해줘', messages[:-1], source_ids=[record['id'], 'unknown-id']))
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


class ReportAgentEventsTest(unittest.TestCase):
    def setUp(self):
        for target in (ai_key(''), patch.object(llm, 'moderate', AsyncMock(return_value=[])),
                       patch.object(v16, 'data_ready', return_value=False)):
            target.start()
            self.addCleanup(target.stop)

    def test_report_route_explains_missing_steps(self):
        with patch('backend.db.mission_store.load_all', return_value={}):
            result = events('보고서 초안 만들어 줘')
        names = [name for name, _ in result]
        self.assertEqual(names, ['route', 'replace', 'actions', 'done'])
        self.assertEqual(dict(result)['route']['agent'], 'report')
        self.assertIn('근거가 아직 없어요', dict(result)['replace']['text'])
        self.assertEqual(dict(result)['actions']['actions'][0]['view'], 'report')

    def test_report_route_returns_draft_action(self):
        with patch('backend.db.mission_store.load_all', return_value={mission_store.identity(CONTEXT): WORKFLOW}):
            result = dict(events('보고서 작성해줘'))
        draft = result['actions']['actions'][0]['reportDraft']
        self.assertEqual(draft['context']['district'], '삼성1동')
        self.assertIn('교류 지원', result['replace']['text'])

    def test_group_report_says_district_basis(self):
        group = ({'age': '70대', 'sex': '여성', 'district': '삼성1동'}, {})
        with patch('backend.db.mission_store.load_all', return_value={}):
            with_group = dict(events('보고서 초안 만들어 줘', group=group))
            without_group = dict(events('보고서 초안 만들어 줘'))
        self.assertIn('삼성1동 동 전체 기준', with_group['notice']['message'])
        self.assertIn('70대 · 여성', with_group['notice']['message'])
        self.assertNotIn('notice', without_group)


if __name__ == '__main__':
    unittest.main()

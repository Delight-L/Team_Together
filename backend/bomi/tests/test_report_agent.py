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

    def problems(self, **changes):
        with patch.object(report_writer, 'catalog_names', return_value=['노인맞춤돌봄서비스', '강남구 노인복지관', '교류 지원']):
            return report_writer.check_grounding(self.polished(**changes), self.base)

    def test_decision_must_stay_with_its_service(self):
        # 두 사업의 판정을 서로 바꾼 문장: 문구는 모두 남아 있지만 사업과 짝이 틀립니다.
        swapped = ('교류 지원: 운영 조건 확인 후 재검토\n- 검토 근거: 교류 지원 검토\n'
                   '상담 지원: 연계 가능성 검토 제안\n- 검토 근거: 자격 확인 필요')
        problems = self.problems(proposal=swapped)
        self.assertIn('판단 문구 위치 변경 «교류 지원»', problems)
        self.assertIn('판단 문구 위치 변경 «상담 지원»', problems)
        # 문체만 바꾸고 짝을 지키면 통과합니다.
        kept = ('교류 지원: 연계 가능성 검토 제안 (교류 지원 검토 결과)\n'
                '상담 지원: 운영 조건 확인 후 재검토 (자격 확인 필요)')
        self.assertEqual(self.problems(proposal=kept), [])

    def test_new_service_or_agency_name_is_rejected(self):
        problems = self.problems(proposal=self.base['proposal'] + '\n노인맞춤돌봄서비스 연계도 검토함')
        self.assertIn('근거에 없는 사업·기관 «노인맞춤돌봄서비스»', problems)
        problems = self.problems(next_steps='강남구 노인복지관에 문의 필요')
        self.assertIn('근거에 없는 사업·기관 «강남구 노인복지관»', problems)

    def test_new_causal_or_definitive_claim_is_rejected(self):
        situation = self.base['situation'] + '\n1인 가구 증가로 인해 전화 연락이 줄었음'
        self.assertIn('근거에 없는 단정 표현 «로 인해»', self.problems(situation=situation))
        # 해석 제한 문장의 '확정'은 원래 있으므로, 새로 '확정'을 쓴 경우만 걸러냅니다.
        situation = self.base['situation'] + '\n고립 위험 지역으로 확정됨'
        self.assertIn('근거에 없는 단정 표현 «확정»', self.problems(situation=situation))

    def test_number_must_stay_in_its_section_and_korean_counts_are_checked(self):
        # 지역 현황의 12.3을 사업 제안 근거로 옮기면 걸러냅니다. 검토 요지에는 요약해 쓸 수 있습니다.
        moved = self.base['proposal'] + '\n- 전화 연락 12.3% 감소 대응'
        self.assertIn('복지서비스 연계·추진 제안: 근거에 없는 숫자 12.3', self.problems(proposal=moved))
        self.assertEqual(self.problems(summary='전화 연락 12.3% 감소에 따라 연계 가능성을 검토하고자 함'), [])
        self.assertIn('근거에 없는 수량 표현 «세 곳»', self.problems(next_steps='세 곳의 기관에 확인 필요'))

    def test_fallback_notice_names_the_reason(self):
        draft = self.write(json.dumps(self.polished(summary='예산 5,000만원 확보 예정')))
        self.assertIn('자료와 일치하지 않는 내용', draft['notice'])
        self.assertIn('이유: 검토 요지: 근거에 없는 숫자 5,000', draft['notice'])

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
                       patch('backend.db.mission_store.load', return_value={}),
                       patch.object(v16, 'data_ready', return_value=False)):
            target.start()
            self.addCleanup(target.stop)

    def test_found_services_become_pending_proposals(self):
        from backend.chatbot.welfare.app.dialogue.resources import load_resources
        record = load_resources()[0]
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
        with patch('backend.db.mission_store.load', return_value={}):
            result = events('보고서 초안 만들어 줘')
        names = [name for name, _ in result]
        self.assertEqual(names, ['route', 'replace', 'actions', 'done'])
        self.assertEqual(dict(result)['route']['agent'], 'report')
        self.assertIn('근거가 아직 없어요', dict(result)['replace']['text'])
        self.assertEqual(dict(result)['actions']['actions'][0]['view'], 'report')

    def test_report_route_returns_draft_action(self):
        with patch('backend.db.mission_store.load', return_value=WORKFLOW):
            result = dict(events('보고서 작성해줘'))
        draft = result['actions']['actions'][0]['reportDraft']
        self.assertEqual(draft['context']['district'], '삼성1동')
        self.assertIn('교류 지원', result['replace']['text'])

    def test_group_report_says_district_basis(self):
        group = ({'age': '70대', 'sex': '여성', 'district': '삼성1동'}, {})
        with patch('backend.db.mission_store.load', return_value={}):
            with_group = dict(events('보고서 초안 만들어 줘', group=group))
            without_group = dict(events('보고서 초안 만들어 줘'))
        self.assertIn('삼성1동 동 전체 기준', with_group['notice']['message'])
        self.assertIn('70대 · 여성', with_group['notice']['message'])
        self.assertNotIn('notice', without_group)


if __name__ == '__main__':
    unittest.main()

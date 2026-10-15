import json
import unittest
from unittest.mock import patch
from chatbot.welfare.service import stream_reply
from chatbot.welfare.app.agent.resources import search
from chatbot.welfare.app.agent.orchestrator import llm
from chatbot.welfare.app.config import settings


def ai_key(key):
    return patch.object(settings, "openai_api_key", key)


def reply(question, context, history=()):
    result = {"answer": "", "sources": [], "mode": ""}
    for event, payload in stream_reply([*history, {"role": "user", "content": question}], context):
        if event == "token":
            result["answer"] += payload["text"]
        elif event == "sources":
            result["sources"], result["mode"] = payload["records"], payload["mode"]
        elif event == "replace":
            result["answer"], result["mode"] = payload["text"], payload["mode"]
    return result


class WelfareSearchTest(unittest.TestCase):
    context = {"city": "강남구", "district": "세곡동", "month": "2025-12"}

    def setUp(self):
        setting = ai_key("")
        setting.start()
        self.addCleanup(setting.stop)

    def test_named_program_with_particles_keeps_complete_facts(self):
        for question in ('세곡동행의 지원 대상, 담당 기관, 지원 내용을 알려줘.',
                         '세곡동행에 전화하려는데 전화번호와 신청 링크를 알려줘.',
                         '세곡 동행의 2026년 모집 마감일을 알려줘.'):
            with self.subTest(question=question):
                result = reply(question, self.context)
                self.assertEqual([r['name'] for r in result['sources']], ['세곡동행'])
                self.assertIn('태화기독교사회복지관', result['answer'])
                self.assertIn('식생활·병원 동행', result['answer'])


    def test_followup_answers_plan_procedure_and_discloses_period(self):
        history = [{'role': 'user', 'content': '세곡동행의 지원 대상, 담당 기관, 지원 내용을 알려줘.'},
                   {'role': 'assistant', 'content': '세곡동행 자료 안내'}]
        result = reply('그 사업의 신청 방법은?', self.context, history)
        for expected in ('신청·접수', '고립위험도 체크리스트', '초기면접·심층상담', '지원 결정'):
            self.assertIn(expected, result['answer'])
        self.assertIn('2025.5–12', result['answer'])
        self.assertIn('현재 모집기간이 아님', result['answer'])
        self.assertIn('현재 운영·실적 미확인', result['answer'])


    def test_two_named_programs_are_not_replaced_by_synonym_matches(self):
        records = search('세곡동행과 취약계층 홈케어의 지원 내용을 비교해줘.', city='강남구')
        names = [r['name'] for r in records]
        self.assertIn('세곡동행', names)
        self.assertIn('취약계층 홈케어', names)
        self.assertNotIn('병원 안심동행서비스', names)


    def test_housing_search_requires_housing_support_evidence(self):
        records = search('이번에는 자립준비청년의 주거 지원을 찾아줘.', city='강남구')
        names = [r['name'] for r in records]
        self.assertIn('강남형 자립준비주택', names)
        self.assertIn('주거비', names)
        self.assertNotIn('자립준비청년 생활·경제 지원', names)
        self.assertNotIn('청년 월세 지원', names)


    def test_ai_receives_procedure_period_and_verification_state(self):
        captured = []
        async def tokens(messages):
            captured.extend(messages)
            yield '자료에 기재된 절차 안내'
        with ai_key('test'), patch.object(llm, 'stream', tokens):
            reply('세곡동행의 신청 방법은?', self.context)
        material = json.loads(captured[0]['content'].split('검색된 팀 자료:\n', 1)[1])
        record = material['records'][0]
        self.assertIn('고립위험도 체크리스트', record['procedure'])
        self.assertEqual(record['plan_period'], '2025.5–12')
        self.assertFalse(record['current_operation_verified'])
        self.assertFalse(record['application_details_verified'])


    def test_extracted_procedure_keeps_its_source_cautions(self):
        record = next(r for r in search('세탁·보관 신청') if r['name'] == '세탁·보관 신청')
        self.assertEqual(record['record_kind'], '검토자료 추출항목')
        self.assertIn('독립된 개인 신청사업은 아님', record['notes'])
        self.assertFalse(record['eligibility_reviewed'])


    def test_ai_source_footer_is_present_when_model_omits_it(self):
        async def tokens(messages):
            yield '자료상 기관은 태화기독교사회복지관·세곡동 주민센터입니다.'
        with ai_key('test'), patch.object(llm, 'stream', tokens):
            result = reply('세곡동행의 담당 기관은?', self.context)
        self.assertIn('추진 계획.pdf', result['answer'])
        self.assertIn('p. 3–4', result['answer'])
        self.assertIn('현재 운영·실적 미확인', result['answer'])


    def test_unverified_residence_decision_is_replaced_with_source_guidance(self):
        async def tokens(messages):
            yield '세곡동에 한정된 사업이므로 춘천에 거주하면 신청하실 수 없습니다.'
        with ai_key('test'), patch.object(llm, 'stream', tokens):
            result = reply('춘천에 사는데 세곡동행을 신청할 수 있어?', self.context)
        self.assertNotIn('한정된', result['answer'])
        self.assertNotIn('신청하실 수 없습니다', result['answer'])
        self.assertIn('확정할 수 없습니다', result['answer'])
        self.assertIn('강남구 내 사회적 고립가구', result['answer'])
        self.assertIn('태화기독교사회복지관', result['answer'])
        self.assertIn('자료 기반', result['mode'])


    def test_uncertain_eligibility_guidance_is_kept_as_ai_answer(self):
        async def tokens(messages):
            yield '자료상 강남구 대상이며 현재 신청 가능 여부는 확인되지 않았습니다.'
        with ai_key('test'), patch.object(llm, 'stream', tokens):
            result = reply('춘천에 사는데 세곡동행을 신청할 수 있어?', self.context)
        self.assertIn('AI 대화', result['mode'])
        self.assertIn('현재 신청 가능 여부는 확인되지 않았습니다', result['answer'])

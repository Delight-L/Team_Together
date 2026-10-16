"""복지사업 에이전트: 검색·답변 후처리·AI 스트림 정리. 외부 AI는 가짜 응답으로 대체합니다."""
import asyncio
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from openai import OpenAIError

from backend.bomi.agents.welfare import WelfareAgent, search_question
from backend.bomi.request import ChatRequest, validate_messages
from backend.chatbot.tests.ai_config import ai_key
from backend.chatbot.welfare.app.config import settings
from backend.chatbot.welfare.app.dialogue.resources import local_answer, search
from backend.chatbot.welfare.app.llm.client import ai_ready, llm
from backend.chatbot.welfare.app.schemas import ChatMessage, ChatRequest as MessageList


_moderate = patch.object(llm, 'moderate', AsyncMock(return_value=[]))


def setUpModule():
    """규제 계층의 moderate API 호출이 외부로 나가지 않게 통과로 대체합니다(규제 자체는 test_regularization)."""
    _moderate.start()


def tearDownModule():
    _moderate.stop()


NO_DATA = {'assessment': [], 'months': []}  # 분석 결과가 없는 화면


def welfare_events(messages, context):
    """WelfareAgent의 이벤트를 모읍니다. 관리자 AI 설정이 꺼져 있으면 use_ai도 꺼집니다."""
    request = ChatRequest(messages=tuple(messages), context=context, data=NO_DATA, use_ai=ai_ready())
    return list(WelfareAgent().respond(request))


def reply(question, context, history=()):
    """이벤트를 모아 {'answer', 'sources', 'mode'}로 돌려줍니다."""
    result = {'answer': '', 'sources': [], 'mode': ''}
    for event, payload in welfare_events([*history, {'role': 'user', 'content': question}], context):
        if event == 'token':
            result['answer'] += payload['text']
        elif event == 'sources':
            result['sources'], result['mode'] = payload['records'], payload['mode']
        elif event == 'replace':
            # AI가 실패하면 중간까지 받은 답변을 자료 검색 안내로 통째로 바꿉니다.
            result['answer'], result['mode'] = payload['text'], payload['mode']
    return result


class FakeStream:
    def __init__(self, text):
        self.text = text
        self.closed = False

    def __aiter__(self):
        async def tokens():
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=self.text))])
        return tokens()

    async def close(self):
        self.closed = True


class WelfareTest(unittest.TestCase):
    context = {'city': '강남구', 'district': '세곡동', 'month': '2025-12'}

    def setUp(self):
        key_patch = ai_key('')
        key_patch.start()
        self.addCleanup(key_patch.stop)

    def test_local_guidance_and_sources(self):
        with patch('backend.chatbot.welfare.app.llm.openai_client.AsyncOpenAI') as factory:
            result = reply('세곡동행', self.context)
        self.assertIn('세곡동행', result['answer'])
        self.assertIn('출처:', result['answer'])
        self.assertIn('미확인', result['sources'][0]['status'])
        self.assertIn('AI 사용 안 함', result['mode'])
        factory.assert_not_called()

    def test_region_coverage(self):
        self.assertEqual(search('병원 동행', city='춘천시'), [])
        self.assertEqual(search('xyzqwerty', city='강남구'), [])

    def test_duplicate_program_keeps_known_agency_and_target(self):
        record = next(r for r in search('세곡동행') if r['name'] == '세곡동행')
        self.assertIn('태화', record['agency'])
        self.assertIn('고립', record['target'])

    def test_followup_keeps_original_program_across_turns(self):
        history = [{'role': 'user', 'content': '세곡동행'},
                   {'role': 'assistant', 'content': '자료 안내'},
                   {'role': 'user', 'content': '대상은?'},
                   {'role': 'assistant', 'content': '자료 안내'}]
        result = reply('신청 방법은?', self.context, history)
        self.assertIn('세곡동행', [r['name'] for r in result['sources']])

    def test_new_topic_does_not_reuse_previous_support_need(self):
        history = [{'role': 'user', 'content': '병원 동행'}, {'role': 'assistant', 'content': '자료 안내'}]
        new = reply('청년 월세 지원', self.context, history)
        independent = reply('청년 월세 지원', self.context)
        self.assertEqual(new['sources'], independent['sources'])

    def test_validation_uses_imported_schema(self):
        for messages in ([], [{'role': 'system', 'content': '규칙'}],
                         [{'role': 'assistant', 'content': '답변'}],
                         [{'role': 'user', 'content': ' '}],
                         [{'role': 'user', 'content': 'x' * 6001}]):
            with self.assertRaises(ValueError):
                validate_messages(messages)
        self.assertEqual(validate_messages([{'role': 'user', 'content': ' 세곡동행 '}])[0]['content'], '세곡동행')

    def test_context_reaches_search(self):
        result = reply('세곡동행', self.context)
        self.assertIn('세곡동행', result['answer'])

    def test_mocked_ai_stream_and_request_cleanup(self):
        streams = [FakeStream('첫 안내'), FakeStream('다음 안내')]
        clients = []

        def factory(**kwargs):
            client = MagicMock()
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=None)
            client.chat.completions.create = AsyncMock(return_value=streams[len(clients)])
            clients.append(client)
            return client

        with ai_key('test'), patch.object(settings, 'openai_model', 'test-model'), \
                patch('backend.chatbot.welfare.app.llm.openai_client.AsyncOpenAI', side_effect=factory):
            first = reply('병원 동행', self.context)
            second = reply('청년 월세 지원', self.context)
        # AI 답 뒤에는 검색된 사업의 출처·확인 상태가 붙습니다(source_footer).
        self.assertTrue(first['answer'].startswith('첫 안내\n\n검토 자료와 확인 상태:'))
        self.assertTrue(second['answer'].startswith('다음 안내\n\n검토 자료와 확인 상태:'))
        self.assertEqual(len(clients), 2)
        for stream, client in zip(streams, clients):
            self.assertTrue(stream.closed)
            client.__aexit__.assert_awaited_once()
            payload = client.chat.completions.create.call_args.kwargs
            self.assertTrue(payload['stream'])
            self.assertEqual(payload['model'], 'test-model')
            self.assertIn('검색된 팀 자료', payload['messages'][0]['content'])

    def test_ai_failure_replaces_partial_answer(self):
        async def fail(messages):
            yield '불완전한 AI 답변'
            raise OpenAIError('test-secret')
        with ai_key('test'), patch.object(llm, 'stream', fail):
            result = reply('병원 동행', self.context)
        self.assertIn('연결 실패', result['mode'])
        self.assertNotIn('불완전한 AI 답변', result['answer'])
        self.assertNotIn('test-secret', str(result))

    def test_new_program_is_labeled_as_idea_even_without_model_label(self):
        async def tokens(messages):
            yield '사업명(가칭): 생활기술 모임'
        with ai_key('test'), patch.object(llm, 'stream', tokens):
            result = reply('기존 사업 말고 새로운 복지사업을 추천해줘', self.context)
        self.assertIn('현재 운영 중인 사업이 아님', result['answer'])
        self.assertIn('생활기술 모임', result['answer'])

    def test_planning_without_ai_does_not_substitute_existing_programs(self):
        result = reply('기존 사업 말고 신규 사업을 구상해줘', self.context)
        self.assertIn('AI 대화 기능이 필요', result['answer'])
        self.assertNotIn('출처:', result['answer'])

    def test_stop_closes_original_async_stream(self):
        closed = []

        async def tokens(messages):
            try:
                yield '부분 답변'
                await asyncio.sleep(1)
            finally:
                closed.append(True)
        with ai_key('test'), patch.object(llm, 'stream', tokens):
            stream = WelfareAgent().respond(ChatRequest(messages=({'role': 'user', 'content': '병원 동행'},), context=self.context, data=NO_DATA, use_ai=True))
            self.assertEqual(next(stream)[0], 'sources')
            self.assertEqual(next(stream)[0], 'token')
            stream.close()
        self.assertEqual(closed, [True])

    def test_parallel_requests_have_independent_history(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(reply, '세곡동행', self.context)
            b = pool.submit(reply, 'xyzqwerty', self.context)
            first, second = a.result(), b.result()
        self.assertIn('세곡동행', first['answer'])
        self.assertEqual(second['sources'], [])


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


class WelfareOutputTest(unittest.TestCase):
    def test_invented_phone_is_hidden_before_it_is_sent(self):
        from backend.chatbot.guardrails import UNVERIFIED

        async def tokens(messages):
            yield '세곡동행은 '
            yield '010-5555-6666으로 문의하세요.'
        with ai_key('test'), patch.object(llm, 'stream', tokens):
            result = welfare_events([{'role': 'user', 'content': '세곡동행'}], {'city': '강남구'})
        streamed = ''.join(payload['text'] for event, payload in result if event == 'token')
        self.assertIn(UNVERIFIED, streamed)
        self.assertNotIn('5555', json.dumps(result, ensure_ascii=False))
        self.assertIn('연락처', dict(result)['notice']['message'])

    def test_ai_failure_event_order_is_error_then_replace(self):
        async def fail(messages):
            yield '일부'
            raise OpenAIError('secret')
        with ai_key('test'), patch.object(llm, 'stream', fail):
            result = welfare_events([{'role': 'user', 'content': '병원 동행'}], {})
        names = [name for name, _ in result]
        self.assertEqual(names[0], 'sources')
        self.assertEqual(names[-2:], ['error', 'replace'])
        self.assertNotIn('done', names)  # done은 파이프라인이 한 번만 보냅니다


class ChatTests(unittest.TestCase):
    def test_specific_program(self):
        records = search('세곡동행')
        self.assertEqual(records[0]['name'], '세곡동행')
        self.assertIn('현재', local_answer(records))
        self.assertIn('출처:', local_answer(records))

    def test_no_match(self):
        self.assertEqual(search('xyzqwerty'), [])
        self.assertIn('찾지 못', local_answer([]))

    def test_local_stream_event_names(self):
        with ai_key(''):
            result = welfare_events([{'role': 'user', 'content': '병원 동행'}], {})
        self.assertEqual([e[0] for e in result], ['sources', 'token'])  # done은 파이프라인이 보냅니다
        self.assertTrue(result[0][1]['records'])

    def test_reject_empty(self):
        with self.assertRaises(ValueError):
            MessageList(messages=[ChatMessage(role='user', content='  ')])


class SearchQuestionTest(unittest.TestCase):
    def test_new_topic_is_independent_and_followup_keeps_anchor(self):
        history = [{'role': 'user', 'content': '세곡동행'}, {'role': 'assistant', 'content': '안내'},
                   {'role': 'user', 'content': '대상은?'}]
        self.assertEqual(search_question(history), '세곡동행 대상은?')
        self.assertEqual(search_question([{'role': 'user', 'content': '청년 월세 지원'}]), '청년 월세 지원')


if __name__ == '__main__':
    unittest.main()

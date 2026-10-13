"""보미 복지사업 찾기(chatbot/welfare/service.py)의 검색·대화 처리 검사. 외부 AI는 호출하지 않습니다."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from openai import OpenAIError
from chatbot.welfare.service import stream_reply, validate_messages
from chatbot.welfare.app.agent.resources import search
from chatbot.welfare.app.agent.orchestrator import handle_chat, llm
from chatbot.welfare.app.config import settings


def reply(question, context, history=()):
    """stream_reply의 이벤트를 모아 {'answer', 'sources', 'mode'}로 돌려줍니다."""
    messages = [*history, {'role': 'user', 'content': question}]
    result = {'answer': '', 'sources': [], 'mode': ''}
    for event, payload in stream_reply(messages, context):
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
        key_patch = patch.object(settings, 'openai_api_key', '')
        key_patch.start()
        self.addCleanup(key_patch.stop)

    def test_local_guidance_and_sources(self):
        with patch('chatbot.welfare.app.llm.openai_client.AsyncOpenAI') as factory:
            result = reply('세곡동행', self.context)
        self.assertIn('세곡동행', result['answer'])
        self.assertIn('출처:', result['answer'])
        self.assertIn('미확인', result['sources'][0]['status'])
        self.assertIn('API 키 없이', result['mode'])
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

    def test_service_passes_context_to_handle_chat(self):
        with patch('chatbot.welfare.service.handle_chat', wraps=handle_chat) as imported:
            result = reply('세곡동행', self.context)
        imported.assert_called_once()
        self.assertIn('세곡동행', result['answer'])
        self.assertEqual(imported.call_args.args[1], self.context)

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

        with patch.object(settings, 'openai_api_key', 'test'), patch.object(settings, 'openai_model', 'test-model'), \
                patch('chatbot.welfare.app.llm.openai_client.AsyncOpenAI', side_effect=factory):
            first = reply('병원 동행', self.context)
            second = reply('청년 월세 지원', self.context)
        self.assertEqual(first['answer'], '첫 안내')
        self.assertEqual(second['answer'], '다음 안내')
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
        with patch.object(settings, 'openai_api_key', 'test'), patch.object(llm, 'stream', fail):
            result = reply('병원 동행', self.context)
        self.assertIn('연결 실패', result['mode'])
        self.assertNotIn('불완전한 AI 답변', result['answer'])
        self.assertNotIn('test-secret', str(result))

    def test_stop_closes_original_async_stream(self):
        closed = []

        async def tokens(messages):
            try:
                yield '부분 답변'
                await asyncio.sleep(1)
            finally:
                closed.append(True)
        with patch.object(settings, 'openai_api_key', 'test'), patch.object(llm, 'stream', tokens):
            stream = stream_reply([{'role': 'user', 'content': '병원 동행'}], self.context)
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


if __name__ == '__main__':
    unittest.main()

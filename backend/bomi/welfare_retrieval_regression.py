"""전국 참고 사례와 지원 분야 없는 목록 조회 회귀 검사."""
import unittest
from unittest.mock import AsyncMock, patch

from backend.bomi.agents.welfare import WelfareAgent, search_question
from backend.chatbot.welfare.app.dialogue import resources, retrieval, semantic
from backend.chatbot.welfare.app.dialogue.query_rules import other_region_examples


NATIONAL = '참고할만한 전국에 다른 복지 서비스들은 없어?'


class WelfareRetrievalTests(unittest.TestCase):
    def test_national_and_reference_requests_expand_scope(self):
        for question in (NATIONAL, '전국 복지서비스 보여줘', '참고할 수 있는 복지서비스 보여줘'):
            with self.subTest(question=question):
                self.assertTrue(retrieval.filters(question)['include_reference'])
        self.assertFalse(retrieval.filters('강남구 주거비 지원 찾아줘')['include_reference'])

    def test_show_followup_keeps_national_search_context(self):
        messages = [{'role': 'user', 'content': NATIONAL},
                    {'role': 'assistant', 'content': '자료를 찾지 못했어요.'},
                    {'role': 'user', 'content': '참고하려고 하니까 보여줘'}]
        query = search_question(messages)
        self.assertIn(NATIONAL, query)
        self.assertTrue(retrieval.filters(query)['include_reference'])
        self.assertTrue(resources.browse_request(query))
        self.assertTrue(retrieval.is_browse_followup(messages[-1]['content']))
        self.assertFalse(retrieval.is_browse_followup('그 사업의 대상은?'))

    def test_selected_age_is_used_for_deictic_recommendation(self):
        query = search_question([{'role': 'user', 'content':
            '이 나이대에 추천해줄만한 복지 서비스는 어떤게 있어?'}], {'age': '30대'})
        self.assertIn('30대', query)
        self.assertTrue(resources.browse_request(query))
        national = search_question([{'role': 'user', 'content': NATIONAL}], {'age': '30대'})
        self.assertIn('30대', national)
        self.assertTrue(resources.browse_request(national))

    def test_specific_needs_do_not_become_unfiltered_browse(self):
        for question in ('주거비 복지서비스 보여줘', '어르신 돌봄 사업 추천해줘',
                         '자립준비청년 복지서비스 보여줘'):
            with self.subTest(question=question):
                self.assertFalse(resources.browse_request(question))
        self.assertFalse(retrieval.filters('전국의 종료된 사업은 제외하고 보여줘')['include_past'])

    def test_browse_returns_api_records_without_query_words_in_name(self):
        record = {'id': 'api:example', 'name': '함께하는 식탁',
                  'description': '식생활과 관계 형성을 위한 활동', 'category': '식생활',
                  'region': '다른 지역', 'target': '성인 1인가구', 'agency': '운영기관',
                  'source_type': 'api', 'reference_only': True}
        with (patch.object(resources, 'load_resources', return_value=[]),
              patch.object(resources, 'resource_source', return_value='db'),
              patch.object(resources, 'database_record', side_effect=lambda row: row),
              patch.object(resources, 'search_catalog', return_value=[
                  dict(record, id='api:local', reference_only=False), record]) as catalog):
            result = resources.search(NATIONAL, city='강남구', include_reference=True)
        self.assertEqual(record, result[0])
        self.assertTrue(catalog.call_args.kwargs['browse'])
        self.assertTrue(catalog.call_args.kwargs['include_reference'])
        self.assertEqual(set(), catalog.call_args.args[1])


class WelfareConversationTests(unittest.IsolatedAsyncioTestCase):
    async def test_other_region_request_excludes_local_candidates_before_ai(self):
        reference = {'id': 'ref', 'name': '다른 지역 사업', 'reference_only': True}
        local = {'id': 'local', 'name': '서울 사업', 'reference_only': False}
        with (patch.object(resources, 'search', return_value=[local, reference]),
              patch.object(semantic, 'hybrid_search', new=AsyncMock(
                  return_value=([reference], 'hybrid_reranked'))) as hybrid):
            found = await retrieval.retrieve(NATIONAL, city='강남구', use_ai=True)
        self.assertEqual([reference], hybrid.call_args.args[1])
        self.assertEqual([reference], found['records'])
        self.assertTrue(other_region_examples('다른 지역 사례도 참고해줘'))
        self.assertFalse(other_region_examples('전국민 지원 사업 보여줘'))
        self.assertFalse(other_region_examples('강남구의 다른 사업 추천해줘'))

    async def test_show_request_searches_again_instead_of_reusing_local_snapshot(self):
        messages = [{'role': 'user', 'content': NATIONAL},
                    {'role': 'user', 'content': '참고하려고 하니까 보여줘'}]
        with patch.object(retrieval, 'retrieve', new=AsyncMock(
                return_value={'records': [], 'mode': 'keyword'})) as retrieve:
            events = [item async for item in WelfareAgent()._converse(
                messages, {'city': '강남구', 'age': '30대'}, False,
                state={'anchor': '강남구 사업', 'records': [{'name': '이전 지역 사업'}]})]
        retrieve.assert_awaited_once()
        query = retrieve.call_args.args[0]
        self.assertIn(NATIONAL, query)
        self.assertTrue(retrieval.filters(query)['include_reference'])
        self.assertEqual([], next(payload['records'] for name, payload in events if name == 'sources'))


if __name__ == '__main__':
    unittest.main()

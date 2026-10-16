"""프론트엔드와 맺은 이벤트 계약: 이름 9종, 내용 필드, 순서 보장(seal)."""
import unittest
from unittest.mock import patch

from backend.bomi import events


class ContractTest(unittest.TestCase):
    def test_exactly_nine_event_names(self):
        self.assertEqual(set(events.EVENT_NAMES),
                         {'route', 'sources', 'token', 'replace', 'follow_ups', 'actions', 'notice', 'error', 'done'})
        self.assertEqual(len(events.EVENT_NAMES), 9)

    def test_payload_fields_match_frontend(self):
        self.assertEqual(events.route('welfare', '복지사업 에이전트', '규칙'),
                         ('route', {'agent': 'welfare', 'label': '복지사업 에이전트', 'by': '규칙'}))
        self.assertEqual(events.sources([{'id': 'a'}], '모드'), ('sources', {'records': [{'id': 'a'}], 'mode': '모드'}))
        self.assertEqual(events.token('가'), ('token', {'text': '가'}))
        self.assertEqual(events.replace('답', '모드', '출처'), ('replace', {'text': '답', 'mode': '모드', 'source': '출처'}))
        self.assertEqual(events.follow_ups(['q']), ('follow_ups', {'questions': ['q']}))
        self.assertEqual(events.actions([{'view': 'report'}]), ('actions', {'actions': [{'view': 'report'}]}))
        self.assertEqual(events.error('x'), ('error', {'message': 'x'}))
        self.assertEqual(events.done(), ('done', {}))

    def test_notice_question_is_optional(self):
        self.assertEqual(events.notice('안내'), ('notice', {'message': '안내'}))
        self.assertEqual(events.notice('안내', question='가린 질문'),
                         ('notice', {'message': '안내', 'question': '가린 질문'}))


class SealTest(unittest.TestCase):
    def test_appends_single_done_and_drops_agent_done(self):
        stream = iter([events.token('가'), events.done(), events.token('나')])
        result = list(events.seal(stream))
        self.assertEqual([name for name, _ in result], ['token', 'token', 'done'])

    def test_empty_stream_still_ends_with_done(self):
        self.assertEqual(list(events.seal(iter([]))), [events.done()])

    def test_exception_becomes_error_then_done_without_details(self):
        def broken():
            yield events.token('부분')
            raise RuntimeError('private-detail')
        with patch.object(events.LOGGER, 'exception'):
            result = list(events.seal(broken()))
        self.assertEqual([name for name, _ in result], ['token', 'error', 'done'])
        self.assertNotIn('private-detail', str(result))

    def test_closing_the_consumer_closes_inner_stream(self):
        closed = []

        def inner():
            try:
                yield events.token('가')
                yield events.token('나')
            finally:
                closed.append(True)
        sealed = events.seal(inner())
        self.assertEqual(next(sealed)[0], 'token')
        sealed.close()
        self.assertEqual(closed, [True])


if __name__ == '__main__':
    unittest.main()

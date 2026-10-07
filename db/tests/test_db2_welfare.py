import unittest
from unittest.mock import Mock, patch

import requests

from collect_db2 import (ApiError, BudgetExhausted, CollectionError, WelfareApi,
                        collect, parse_date, parse_detail, parse_list, parse_xml)


def listing(ids, total=None):
    total = len(ids) if total is None else total
    items = ''.join(f'<servList><servId>{i}</servId><servNm>서비스{i}</servNm>'
                    '<ctpvNm>서울특별시</ctpvNm><sggNm>강남구</sggNm></servList>' for i in ids)
    return f'<response><resultCode>0</resultCode><totalCount>{total}</totalCount>{items}</response>'


def detail(service_id):
    return (f'<response><resultCode>0</resultCode><servId>{service_id}</servId>'
            '<servNm>복지</servNm><sprtTrgtCn>대상</sprtTrgtCn>'
            '<inqplCtadrList><wlfareInfoReldCn>111</wlfareInfoReldCn></inqplCtadrList>'
            '<inqplCtadrList><wlfareInfoReldCn>222</wlfareInfoReldCn></inqplCtadrList></response>')


def response(xml):
    return parse_xml(xml), xml


class ParserTests(unittest.TestCase):
    def test_namespaces_and_repeated_contacts(self):
        root = parse_xml(detail('a').replace('<response>', '<response xmlns="urn:test">'))
        payload = parse_detail(root, 'a')
        self.assertEqual(len(payload['inqplCtadrList']), 2)
        self.assertEqual(payload['sprtTrgtCn'], '대상')

    def test_http_200_error_envelope(self):
        with self.assertRaises(ApiError) as ctx:
            parse_xml('<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>')
        self.assertEqual(ctx.exception.code, '30')

    def test_missing_code_and_wrong_id_rejected(self):
        with self.assertRaises(CollectionError):
            parse_xml('<html/>')
        with self.assertRaises(CollectionError):
            parse_detail(parse_xml(detail('a')), 'b')

    def test_dates_and_list_validation(self):
        self.assertEqual(str(parse_date('20261007')), '2026-10-07')
        self.assertIsNone(parse_date('00000000'))
        with self.assertRaises(CollectionError):
            parse_date('20261399')
        total, items = parse_list(parse_xml(listing(['a'])))
        self.assertEqual((total, items[0]['servId']), (1, 'a'))


class ClientTests(unittest.TestCase):
    @patch('collect_db2.time.sleep')
    def test_retry_consumes_budget_and_key_is_not_double_encoded(self, sleep):
        session = Mock()
        good = Mock(status_code=200, content=listing([]).encode())
        session.get.side_effect = [requests.Timeout('SECRET'), good]
        reserve = Mock(return_value=True)
        api = WelfareApi('abc%2Bdef%3D', reserve, interval=0, session=session)
        api.get('LcgvWelfarelist')
        self.assertEqual(reserve.call_count, 2)
        self.assertEqual(session.get.call_args.kwargs['params']['serviceKey'], 'abc+def=')

    def test_budget_prevents_network(self):
        session = Mock()
        with self.assertRaises(BudgetExhausted):
            WelfareApi('SECRET', lambda: False, session=session).get('LcgvWelfarelist')
        session.get.assert_not_called()

    def test_auth_failure_not_retried(self):
        session = Mock()
        session.get.return_value = Mock(status_code=200, content=b'<response><resultCode>30</resultCode></response>')
        with self.assertRaises(ApiError):
            WelfareApi('SECRET', lambda: True, session=session).get('LcgvWelfarelist')
        self.assertEqual(session.get.call_count, 1)

    def test_network_error_redacted(self):
        session = Mock()
        session.get.side_effect = requests.ConnectionError('serviceKey=SECRET')
        with self.assertRaises(CollectionError) as ctx:
            WelfareApi('SECRET', lambda: True, retries=0, session=session).get('LcgvWelfarelist')
        self.assertNotIn('SECRET', str(ctx.exception))


class CollectorTests(unittest.TestCase):
    def test_all_pages_and_detail(self):
        store = Mock()
        store.candidates.return_value = ['a', 'b']
        api = Mock()
        api.get.side_effect = [response(listing(['a'], 2)), response(listing(['b'], 2)),
                               response(detail('a')), response(detail('b'))]
        self.assertEqual(collect(store, api, 'run', rows=1), 'completed')
        self.assertEqual(store.save_list.call_count, 2)
        self.assertEqual(store.save_detail.call_count, 2)
        self.assertEqual(api.get.call_args_list[1].kwargs['pageNo'], 2)

    def test_budget_keeps_saved_data(self):
        store = Mock()
        store.candidates.return_value = ['a', 'b']
        api = Mock()
        api.get.side_effect = [response(listing(['a','b'])), response(detail('a')), BudgetExhausted('budget')]
        self.assertEqual(collect(store, api, 'run'), 'budget_exhausted')
        self.assertEqual(store.save_detail.call_count, 1)
        store.detail_failed.assert_not_called()

    def test_one_bad_detail_does_not_stop_others(self):
        store = Mock()
        store.candidates.return_value = ['a', 'b']
        api = Mock()
        api.get.side_effect = [response(listing(['a','b'])), response(detail('wrong')), response(detail('b'))]
        self.assertEqual(collect(store, api, 'run'), 'partial')
        self.assertEqual(store.save_detail.call_count, 1)
        self.assertEqual(store.detail_failed.call_args.args[0], 'a')

    def test_duplicate_page_stops_before_details(self):
        store = Mock()
        api = Mock()
        api.get.side_effect = [response(listing(['a'],2)), response(listing(['a'],2))]
        self.assertEqual(collect(store, api, 'run', rows=1), 'failed')
        store.candidates.assert_not_called()
        self.assertEqual(store.save_list.call_count, 1)

    def test_quota_error_stops_remaining_details(self):
        store = Mock()
        store.candidates.return_value = ['a','b']
        api = Mock()
        api.get.side_effect = [response(listing(['a','b'])), ApiError('22')]
        self.assertEqual(collect(store, api, 'run'), 'failed')
        self.assertEqual(api.get.call_count, 2)


if __name__ == '__main__':
    unittest.main()

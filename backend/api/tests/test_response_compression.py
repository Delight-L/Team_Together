import gzip
import io
import json
import unittest
from email.message import Message
from unittest.mock import Mock

from backend.api.server import Handler


class ResponseCompressionTests(unittest.TestCase):
    def response(self, accept_encoding, payload):
        handler = Handler.__new__(Handler)
        handler.headers = Message()
        if accept_encoding is not None:
            handler.headers['Accept-Encoding'] = accept_encoding
        handler.wfile = io.BytesIO()
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.send_json(200, payload, cookie='session=test; HttpOnly')
        headers = dict(call.args for call in handler.send_header.call_args_list)
        body = handler.wfile.getvalue()
        self.assertEqual(int(headers['Content-Length']), len(body))
        self.assertEqual(headers['Set-Cookie'], 'session=test; HttpOnly')
        self.assertEqual(headers['Vary'], 'Accept-Encoding')
        return headers, body

    def test_gzip_preserves_korean_payload_and_reduces_transfer(self):
        payload = {'rows': [{'district': '강남구 신사동', 'value': i} for i in range(100)]}
        headers, body = self.response('br, gzip', payload)
        self.assertEqual(headers['Content-Encoding'], 'gzip')
        self.assertEqual(json.loads(gzip.decompress(body)), payload)
        self.assertLess(len(body), len(json.dumps(payload).encode()) / 2)

    def test_identity_and_disabled_gzip_remain_readable(self):
        payload = {'text': '탐지 결과' * 1000}
        for encoding in (None, 'identity', 'gzip;q=0', '*;q=1, gzip;q=0'):
            with self.subTest(encoding=encoding):
                headers, body = self.response(encoding, payload)
                self.assertNotIn('Content-Encoding', headers)
                self.assertEqual(json.loads(body), payload)

    def test_small_response_is_not_compressed(self):
        headers, body = self.response('gzip', {'ok': True})
        self.assertNotIn('Content-Encoding', headers)
        self.assertEqual(json.loads(body), {'ok': True})

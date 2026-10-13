"""관리자 AI 설정: 기본 꺼짐, 키 원문 비공개, 제공사별 호출 연결."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from chatbot import ai_settings
from chatbot.tests.ai_config import ai_key
from chatbot.welfare.app.llm import anthropic_client, client, gemini_client


class SettingsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        for target in (patch.object(ai_settings, 'STORE', Path(folder.name) / 'ai_settings.json'),
                       patch.object(ai_settings, '_env_key', return_value='')):
            target.start()
            self.addCleanup(target.stop)

    def test_default_is_off(self):
        config = ai_settings.current()
        self.assertFalse(config.enabled)
        self.assertFalse(config.ready)
        self.assertFalse(client.ai_ready())

    def test_saved_key_is_never_returned(self):
        view = ai_settings.save({'enabled': True, 'provider': 'anthropic', 'model': '', 'apiKey': 'sk-secret-1234'})
        self.assertNotIn('sk-secret', json.dumps(view))
        claude = next(p for p in view['providers'] if p['id'] == 'anthropic')
        self.assertEqual(claude['keyHint'], '…1234')
        self.assertTrue(view['ready'])
        self.assertEqual(view['model'], 'claude-opus-5-5')
        # 키를 비워 저장하면 기존 키를 유지하고, clearKey이면 지웁니다.
        self.assertTrue(ai_settings.save({'enabled': True, 'provider': 'anthropic', 'model': ''})['ready'])
        self.assertFalse(ai_settings.save({'enabled': True, 'provider': 'anthropic', 'clearKey': True})['ready'])

    def test_invalid_values_are_rejected(self):
        for bad in ({'provider': 'other'}, {'provider': 'openai', 'model': 'a b'},
                    {'provider': 'openai', 'apiKey': 'has space'}):
            with self.assertRaises(ValueError):
                ai_settings.save(bad)


class ProviderTest(unittest.TestCase):
    def test_complete_goes_to_selected_provider(self):
        for provider, module in (('anthropic', anthropic_client), ('gemini', gemini_client)):
            fenced = '```json\n{"a": 1}\n```'
            with ai_key('k', provider=provider), \
                    patch.object(module, 'complete', AsyncMock(return_value=fenced)) as call:
                answer = asyncio.run(client.llm.complete([{'role': 'user', 'content': 'x'}], json_mode=True))
            self.assertEqual(answer, '{"a": 1}')
            self.assertEqual(call.await_args.args[0].provider, provider)

    def test_disabled_ai_raises_unavailable(self):
        with ai_key(''), self.assertRaises(client.AIUnavailable):
            asyncio.run(client.llm.complete([{'role': 'user', 'content': 'x'}]))

    def test_anthropic_request_shape(self):
        config = ai_settings.AIConfig(True, 'anthropic', 'claude-opus-5-5', 'k', '.env')
        request = anthropic_client._request(config, [{'role': 'system', 'content': '규칙'},
                                                     {'role': 'user', 'content': '질문'}], 1500)
        self.assertEqual(request['system'], '규칙')
        self.assertEqual(request['messages'], [{'role': 'user', 'content': '질문'}])
        self.assertGreaterEqual(request['max_tokens'], anthropic_client.MIN_MAX_TOKENS)
        self.assertEqual(request['fallbacks'], 'default')

    def test_anthropic_refusal_is_an_error(self):
        final = SimpleNamespace(stop_reason='refusal', content=[])
        stream = MagicMock()
        stream.__aenter__ = AsyncMock(return_value=SimpleNamespace(get_final_message=AsyncMock(return_value=final)))
        stream.__aexit__ = AsyncMock(return_value=False)
        fake = MagicMock()
        fake.__aenter__ = AsyncMock(return_value=SimpleNamespace(
            beta=SimpleNamespace(messages=SimpleNamespace(stream=MagicMock(return_value=stream)))))
        fake.__aexit__ = AsyncMock(return_value=False)
        config = ai_settings.AIConfig(True, 'anthropic', 'claude-opus-5-5', 'k', '.env')
        with patch('anthropic.AsyncAnthropic', return_value=fake), self.assertRaises(anthropic_client.Refused):
            asyncio.run(anthropic_client.complete(config, [{'role': 'user', 'content': 'x'}], False, 100))

    def test_gemini_request_uses_model_role_and_system_instruction(self):
        config = ai_settings.AIConfig(True, 'gemini', 'gemini-2.5-flash', 'k', '.env')
        request = gemini_client._request(config, [{'role': 'system', 'content': '규칙'},
                                                  {'role': 'user', 'content': '질문'},
                                                  {'role': 'assistant', 'content': '답'}], 500, json_mode=True)
        self.assertEqual([c.role for c in request['contents']], ['user', 'model'])
        self.assertEqual(request['config'].system_instruction, '규칙')
        self.assertEqual(request['config'].response_mime_type, 'application/json')


if __name__ == '__main__':
    unittest.main()

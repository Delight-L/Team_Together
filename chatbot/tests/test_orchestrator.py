"""토큰 경계와 총괄 라우팅 검사. 실제 외부 AI/DB를 호출하지 않습니다."""
import os
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from chatbot.orchestrator import free_reply, topic_reply, TOPICS
from test_token_gate import mock_client

class OrchestratorTest(unittest.TestCase):
    context = {'city':'강남구','district':'','month':'2025-12'}

    def test_all_topics_bypass_client(self):
        with mock_client() as factory:
            for topic in TOPICS:
                self.assertIn('AI 호출 없음',topic_reply(topic,[],self.context)['mode'])
            factory.assert_not_called()

    def test_free_chat_routes_and_invokes_selected_agent(self):
        client = MagicMock()
        client.models.generate_content.side_effect = [SimpleNamespace(text='{"agent":"matching"}'),SimpleNamespace(text='사업 조건을 확인해 주세요.')]
        with patch.dict(os.environ,{'GEMINI_API_KEY':'test','GEMINI_MODEL':'test'}), mock_client() as factory, patch('chatbot.orchestrator.agent_material',return_value={'verified':'사업 근거'}) as material:
            factory.return_value=client
            result=free_reply('어떤 사업을 검토할까?',[],self.context)
            material.assert_called_once_with('matching',[],self.context)
            self.assertEqual(client.models.generate_content.call_count,2)
            self.assertIn('사업 매칭 에이전트',result['mode'])
            self.assertIn('사업 근거',client.models.generate_content.call_args.kwargs['contents'])

    def test_unknown_agent_cannot_run_tools(self):
        client=MagicMock()
        client.models.generate_content.return_value=SimpleNamespace(text='{"agent":"shell"}')
        with patch.dict(os.environ,{'GEMINI_API_KEY':'test','GEMINI_MODEL':'test'}), mock_client() as factory, patch('chatbot.orchestrator.agent_material') as material:
            factory.return_value=client
            self.assertIn('처리 실패',free_reply('질문',[],self.context)['mode'])
            material.assert_not_called()

    def test_missing_configuration_is_explicit(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':'','GEMINI_MODEL':''}):
            self.assertIn('AI 미연결',free_reply('안녕',[],self.context)['mode'])

if __name__=='__main__': unittest.main()

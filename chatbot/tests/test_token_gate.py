import os
import sys
from types import ModuleType
from contextlib import contextmanager
import unittest
from unittest.mock import patch, MagicMock
from chatbot.service import explain_question

@contextmanager
def mock_client():
    genai=ModuleType("google.genai")
    genai.Client=MagicMock()
    google=ModuleType("google")
    google.genai=genai
    with patch.dict(sys.modules,{"google":google,"google.genai":genai}):
        yield genai.Client

class TokenGateTests(unittest.TestCase):
    evidence = [{"metric_label":"외출 변화","is_risk_signal":True,"explanation":"저장된 분석 근거"}]
    def test_default_and_false_never_create_client(self):
        with patch.dict(os.environ,{"GEMINI_API_KEY":"test","GEMINI_MODEL":"test"}), mock_client() as client:
            for value in [False, None, "true", 1]:
                reply,mode=explain_question("왜 후보인가요?",self.evidence,allow_agent=value)
                self.assertIn("저장된 분석 근거",reply)
                self.assertIn("규칙 기반",mode)
            explain_question("왜 후보인가요?",self.evidence)
            client.assert_not_called()
    def test_explicit_opt_in_calls_once(self):
        with patch.dict(os.environ,{"GEMINI_API_KEY":"test","GEMINI_MODEL":"test"}), mock_client() as client:
            client.return_value.models.generate_content.return_value.text="테스트 응답"
            reply,mode=explain_question("왜 후보인가요?",self.evidence,allow_agent=True)
            self.assertEqual(reply,"테스트 응답")
            client.return_value.models.generate_content.assert_called_once()
    def test_no_evidence_never_calls(self):
        with mock_client() as client:
            explain_question("질문",[],allow_agent=True)
            client.assert_not_called()

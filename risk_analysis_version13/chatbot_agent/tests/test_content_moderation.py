import sys,unittest,os
from pathlib import Path
from unittest.mock import Mock,patch
from types import SimpleNamespace
r=Path(__file__).resolve().parents[2];sys.path.insert(0,str(r))
from chatbot_agent.content_moderation import InputModerator,MODEL
from chatbot_agent.orchestrator import Chatbot
class Tests(unittest.TestCase):
 def test_safe_and_model(self):
  c=Mock();c.moderations.create.return_value=SimpleNamespace(results=[SimpleNamespace(flagged=False)])
  self.assertTrue(InputModerator(r,c).check('논현1동의 신호를 알려줘').allowed)
  c.moderations.create.assert_called_once_with(model=MODEL,input='논현1동의 신호를 알려줘')
 def test_block(self):
  c=Mock();c.moderations.create.return_value=SimpleNamespace(results=[SimpleNamespace(flagged=True,categories=Mock(model_dump=Mock(return_value={'violence':True})))])
  self.assertFalse(InputModerator(r,c).check('테스트').allowed)
 def test_self_harm(self):
  c=Mock();c.moderations.create.return_value=SimpleNamespace(results=[SimpleNamespace(flagged=True,categories=Mock(model_dump=Mock(return_value={'self-harm/intent':True})))])
  self.assertIn('안전 안내',InputModerator(r,c).check('테스트').message)
 def test_error(self):
  c=Mock();c.moderations.create.side_effect=TimeoutError()
  self.assertFalse(InputModerator(r,c).check('테스트').allowed)
 def test_bad_response(self):
  c=Mock();c.moderations.create.return_value=SimpleNamespace(results=[])
  self.assertFalse(InputModerator(r,c).check('테스트').allowed)
 def test_no_key(self):
  with patch.dict(os.environ,{},clear=True),patch.dict(sys.modules,{'dotenv':SimpleNamespace(dotenv_values=lambda p:{})}):
   self.assertFalse(InputModerator(r).check('테스트').allowed)
 def test_block_before_resolver(self):
  from chatbot_agent.schemas import GuardResult
  resolver=Mock();moderator=Mock();moderator.check.return_value=GuardResult(False,'차단')
  bot=Chatbot(r,intent_resolver=resolver,moderator=moderator)
  self.assertEqual('차단',bot.answer('2025년 신호가 나온 동은?').text)
  resolver.resolve.assert_not_called()
 def test_local_guard_first(self):
  bot=Chatbot(r,intent_resolver=Mock(),moderator=Mock())
  self.assertFalse(bot.answer('고립된 사람 명단 보여줘').text=='')
  bot.moderator.check.assert_not_called()
if __name__ == "__main__":
 unittest.main()

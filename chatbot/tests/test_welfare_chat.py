import asyncio
import unittest
from unittest.mock import patch
from chatbot.welfare.app.agent.resources import search, local_answer
from chatbot.welfare.app.agent.orchestrator import handle_chat
from chatbot.welfare.app.schemas import ChatMessage, ChatRequest
from chatbot.tests.ai_config import ai_key

class ChatTests(unittest.TestCase):
    def test_specific_program(self):
        records = search("세곡동행")
        self.assertEqual(records[0]["name"], "세곡동행")
        self.assertIn("현재", local_answer(records))
        self.assertIn("출처:", local_answer(records))
    def test_no_match(self):
        self.assertEqual(search("xyzqwerty"), [])
        self.assertIn("찾지 못", local_answer([]))
    def test_local_stream(self):
        async def collect():
            with ai_key(''):
                return [event async for event in handle_chat([ChatMessage(role="user", content="병원 동행")])]
        events = asyncio.run(collect())
        self.assertEqual([e[0] for e in events], ["sources", "token", "done"])
        self.assertTrue(events[0][1]["records"])
    def test_reject_empty(self):
        with self.assertRaises(ValueError):
            ChatRequest(messages=[ChatMessage(role="user", content="  ")])


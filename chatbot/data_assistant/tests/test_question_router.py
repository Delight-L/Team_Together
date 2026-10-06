import unittest

from chatbot.data_assistant.question_router import OUT_OF_SCOPE, route_question


class QuestionRouterTests(unittest.TestCase):
    def test_all_signal_request(self):
        self.assertEqual(route_question("35건 신호별 근거 알려줘").kind, "all_signals")

    def test_methodology_request(self):
        self.assertEqual(route_question("Robust Z 기준이 뭐야?").kind, "methodology")

    def test_unrelated_question_is_rejected(self):
        route = route_question("오늘 저녁 메뉴 추천해줘")
        self.assertFalse(route.supported)
        self.assertIn("고립 문제 데이터", OUT_OF_SCOPE)


if __name__ == "__main__":
    unittest.main()

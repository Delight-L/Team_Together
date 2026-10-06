import unittest
from pathlib import Path

from chatbot.data_assistant.analysis_interpreter import explain_all_signals


class AnalysisInterpreterTests(unittest.TestCase):
    def test_all_evidence_card_records_are_explained(self):
        root = Path(__file__).resolve().parents[3]
        text = explain_all_signals(root)
        self.assertIn("Evidence Card 전체 35건", text)
        self.assertEqual(sum(1 for line in text.splitlines() if line[:1].isdigit() and ". " in line), 35)

    def test_negative_robust_z_is_visible(self):
        root = Path(__file__).resolve().parents[3]
        text = explain_all_signals(root)
        self.assertIn("-2.62", text)


if __name__ == "__main__":
    unittest.main()

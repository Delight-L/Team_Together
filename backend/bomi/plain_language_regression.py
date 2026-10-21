"""쉬운 말 답변의 핵심 안내가 다시 어려워지지 않는지 확인합니다.

Usage: ``python -m backend.bomi.plain_language_regression``.
"""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(relative_path):
    return (ROOT / relative_path).read_text(encoding='utf-8')


class PlainLanguageResponseTests(unittest.TestCase):
    def test_fixed_safety_and_failure_messages_explain_the_next_step(self):
        guardrails = source('backend/agents/regional_analysis/chatbot_agent/guardrails.py')
        welfare = source('backend/bomi/agents/welfare.py')
        phrases = source('backend/bomi/phrases.py')
        self.assertIn('동 전체', guardrails)
        self.assertIn('특정 사람', guardrails)
        self.assertIn('자료를 바탕으로', welfare)
        self.assertIn('확인된 자료', phrases)
        self.assertIn('예:', phrases)

    def test_welfare_no_result_gives_a_usable_example(self):
        resources = source('backend/chatbot/welfare/app/dialogue/resources.py')
        self.assertIn('이번에 찾은 자료에서는 관련 복지사업을 찾지 못했어요', resources)
        self.assertIn('강남구에서 어르신 식사 지원', resources)
        self.assertIn('필요한 도움을 알려 주세요', resources)

    def test_ai_welfare_instruction_requires_plain_answer_first(self):
        prompt = source('backend/bomi/agents/welfare_prompt.py')
        self.assertIn('첫 문장에서 질문에 바로 답하세요', prompt)
        self.assertIn('한 문장에는 한 가지 내용', prompt)
        self.assertIn('다음 할 일', prompt)


if __name__ == '__main__':
    unittest.main()

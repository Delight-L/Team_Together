import unittest
from pathlib import Path
from chatbot_agent.orchestrator import Chatbot
from chatbot_agent.intent_parser import parse_intent
from chatbot_agent.repository import DataRepository
from chatbot_agent.guardrails import validate_input
from chatbot_agent.knowledge_retriever import retrieve
from chatbot_agent.intent_parser import parse_intent
from chatbot_agent.schemas import QueryIntent
from chatbot_agent.llm_intent_resolver import IntentResolver, _explicit_districts

class FakeContextResolver:
    """LLM이 이전 결과의 districts를 해석해 반환하는 계약을 재현한다."""
    def resolve(self, question, districts, memory):
        if "지역적 특성" in question:
            names=tuple(memory.as_prompt_data()[-1]["districts"][:3])
            return QueryIntent("plan_review","context",dongs=names)
        return parse_intent(question,districts)

class FakeSemanticResolver:
    """실제 LLM이 기간 표현과 직전 조회 범위를 반환하는 계약을 재현한다."""
    def resolve(self, question, districts, memory):
        if "하반기" in question:
            return QueryIntent("find_region", "signals", start_month="2025-07", end_month="2025-12")
        if "왜 신호" in question:
            return QueryIntent("track_change", "reason", needs=("행정동",), use_previous_scope=True)
        return parse_intent(question, districts)

class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(__file__).resolve().parents[2]
        cls.bot=Chatbot(cls.root)
    def test_guard_rejects_personal_list(self):
        self.assertFalse(validate_input("고립된 사람 명단 보여줘").allowed)
    def test_parser_requires_dong_for_reason(self):
        intent=parse_intent("왜 신호로 잡혔나요?", self.bot.repo.districts())
        self.assertIn("행정동", intent.needs)
    def test_combined_signal_reproduces_suseo(self):
        result=self.bot.answer("2024년 12월 통신 이동 동시 신호가 나온 동은?")
        self.assertIn("수서동", result.text)
        self.assertIn("1건", result.text)
    def test_all_period_signal_count_reproduces_35(self):
        result=self.bot.answer("전체 기간 신호가 나온 동은?")
        self.assertIn("35건", result.text)
    def test_reason_has_structured_evidence(self):
        result=self.bot.answer("2024년 12월 수서동은 왜 신호로 잡혔나요?")
        self.assertEqual("선정 근거", result.evidence.title)
        self.assertIn("Robust Z", result.text)
        self.assertIn("| 확인 수치 | 쉬운 설명 |", result.text)
        self.assertIn("현장 확인 방향", result.text)
        self.assertNotIn("개인의 고립을 확정", result.text)
    def test_context_uses_typology(self):
        result=self.bot.answer("수서동의 지역 특성은?")
        self.assertIn("지역유형", result.text)
        self.assertNotIn("1) 월별", result.text)
    def test_calculation_guide_only_when_requested(self):
        self.assertEqual("", retrieve("2025년 신호가 나온 동은?", "signals"))
        self.assertIn("1) 월별", retrieve("분석 과정 1단계부터 6단계 알려줘", "signals"))
    def test_contextual_three_dongs_keeps_previous_result(self):
        bot=Chatbot(self.root,intent_resolver=FakeContextResolver())
        first=bot.answer("2025년 전체 기간 신호가 많은 세 개 동 알려줘")
        self.assertEqual(3, len(first.evidence.rows))
        expected=[row["행정동"] for row in first.evidence.rows]
        second=bot.answer("위 세 동의 지역적 특성 알려줘")
        self.assertEqual(expected, [row["dong_name"] for row in second.evidence.rows])
        self.assertIn("지역유형", second.text)

    def test_llm_period_interpretation_is_used_as_data_filter(self):
        bot=Chatbot(self.root, intent_resolver=FakeSemanticResolver())
        result=bot.answer("2025년 하반기 신호가 나온 동은?")
        months={row["date"] for row in result.evidence.rows}
        self.assertEqual({"2025-12"}, months)

    def test_activity_without_period_asks_for_period_before_query(self):
        bot=Chatbot(self.root, intent_resolver=FakeContextResolver())
        result=bot.answer("세곡동의 어떤 활동이 변했나요?")
        self.assertEqual("추가 조건 필요", result.evidence.title)
        self.assertIn("어느 기간", result.text)
        self.assertNotIn("통화 상대 수:", result.text)

    def test_all_period_is_an_explicit_scope(self):
        bot=Chatbot(self.root, intent_resolver=FakeContextResolver())
        result=bot.answer("전체 기간 세곡동의 어떤 활동이 변했나요?")
        self.assertNotEqual("추가 조건 필요", result.evidence.title)

    def test_reason_followup_uses_previous_ranked_regions(self):
        bot=Chatbot(self.root, intent_resolver=FakeContextResolver())
        first=bot.answer("2025년 하반기에 신호가 나온 동은?")
        expected={row["행정동"] for row in first.evidence.rows}
        second=bot.answer("무엇이 이상으로 탐지된 거야?")
        self.assertEqual("선정 근거", second.evidence.title)
        self.assertEqual(expected, {row["행정동"] for row in second.evidence.rows})
        self.assertNotIn("행정동을 알려주세요", second.text)

    def test_follow_up_reuses_last_result_scope_without_phrase_rules(self):
        bot=Chatbot(self.root, intent_resolver=FakeSemanticResolver())
        first=bot.answer("2025년 하반기 신호가 나온 동은?")
        expected={row["행정동"] for row in first.evidence.rows}
        second=bot.answer("왜 신호로 잡혔나요?")
        self.assertEqual("선정 근거", second.evidence.title)
        self.assertEqual(expected, {row["행정동"] for row in second.evidence.rows})
        self.assertNotIn("행정동을 알려주세요", second.text)

    def test_explicit_new_district_replaces_previous_scope(self):
        previous=QueryIntent("find_region", "signals", dongs=("삼성2동", "압구정동"))
        names=_explicit_districts("개포동만", self.bot.repo.districts())
        updated=IntentResolver._apply_explicit_districts(previous, names)
        self.assertEqual(("개포1동", "개포2동", "개포4동"), updated.dongs)
        self.assertNotIn("삼성2동", updated.dongs)

    def test_previous_answer_shows_only_detected_or_not_detected(self):
        bot=Chatbot(self.root, intent_resolver=FakeContextResolver())
        result=bot.answer("개포4동은 전월에도 탐지됐나요?")
        self.assertEqual("전월 신호 여부", result.evidence.title)
        self.assertNotIn("Robust Z", result.text)
        self.assertNotIn("강수", result.text)
        self.assertRegex(result.text, r"(탐지됨|미탐지)")

if __name__ == '__main__': unittest.main()

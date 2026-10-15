"""Supervisor specialist: semantic intent, scoped history, and offline boundary."""
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from backend.agents import v16_service as service
from backend.chatbot import ai_settings
from backend.chatbot.welfare.app.llm.client import llm
from chatbot_agent.schemas import Evidence


class Repository:
    def __init__(self, *args, **kwargs):
        pass

    def districts(self):
        return {"삼성1동", "역삼1동", "논현1동"}

    def available_period(self):
        return "2025-07", "2025-12"

    def consumption_period(self):
        return "2022-01", "2025-12"


CONTEXT = {"city": "강남구", "district": "논현1동", "month": "2025-12"}
GEMINI = ai_settings.AIConfig(True, "gemini", "configured-model", "v16-test-key", ".env")


def history(dong, month):
    return [{"role": "user", "content": f"{dong}의 변화를 알려줘"},
            {"role": "assistant", "content": f"{dong}\n기준: 2025년 {month}월 기준 (관측: 2025년 9~11월)\n평일 이동 -6.1%"}]


class V16ServiceTest(unittest.TestCase):
    def setUp(self):
        repository = patch("chatbot_agent.orchestrator.DataRepository", Repository)
        repository.start()
        self.addCleanup(repository.stop)
        configuration = patch.object(service, "_configuration", return_value=GEMINI)
        configuration.start()
        self.addCleanup(configuration.stop)

    def test_ai_off_never_calls_external_intent_moderation_or_generation(self):
        with patch("google.genai.Client", side_effect=AssertionError("external Gemini call")), \
                patch("chatbot_agent.content_moderation.InputModerator.check", side_effect=AssertionError("moderation call")), \
                patch("chatbot_agent.orchestrator.try_gemini", side_effect=AssertionError("generation call")), \
                patch("chatbot_agent.orchestrator.execute", return_value=Evidence("근거", "조회 완료")):
            answer = service.reply("2025년 하반기 이상신호 나온 지역 알려줘", [], CONTEXT, use_ai=False)
            self.assertEqual(answer["intentSource"], "local_ai_off")
            self.assertIn("외부 AI 호출 없음", answer["mode"])

    def test_gemini_semantics_are_primary_and_actual_history_is_sent(self):
        # This phrasing is not a local methodology trigger; Gemini supplies it.
        model_answer = {"purpose": "track_change", "question_type": "methodology", "districts": [],
                        "start_month": None, "end_month": None, "signal": "any", "metric": None,
                        "needs": [], "use_previous_scope": False, "all_available_period": False,
                        "age_band": None, "age_bands": [], "age_scope_explicit": False,
                        "include_values": False, "limit": None, "clarifying_question": None}
        client = Mock()
        client.models.generate_content.return_value.text = json.dumps(model_answer)
        previous = history("삼성1동", 12)
        with patch("google.genai.Client", return_value=client) as factory, \
                patch.object(service.IntentResolver, "_fallback", side_effect=AssertionError("local intent override")):
            result = service.reply("판단 과정을 순서대로 설명해", previous, CONTEXT)
        self.assertEqual(result["intentSource"], "ai")
        self.assertIn("과거", result["answer"])
        self.assertEqual(factory.call_args.kwargs["api_key"], "v16-test-key")
        options = client.models.generate_content.call_args.kwargs
        self.assertEqual(options["model"], "configured-model")
        self.assertIn(previous[1]["content"], json.loads(options["contents"].split("\n")[-1])["history"]["conversation"][1]["content"])
        client.close.assert_called_once()

    def test_explicit_regional_period_ignores_dashboard_dong_and_group_age(self):
        with patch("chatbot_agent.orchestrator.execute", return_value=Evidence("신호", "범위 확인")) as execute:
            service.reply("2025년 하반기 이상신호 탐지 지역 알려줘", [], CONTEXT,
                          use_ai=False, group=({"age": "30대", "sex": "남성"}, {}))
        intent = execute.call_args.args[1]
        self.assertEqual((intent.start_month, intent.end_month), ("2025-07", "2025-12"))
        self.assertEqual(intent.dongs, ())
        self.assertIsNone(intent.dong)
        self.assertIsNone(intent.age_band)

    def test_selected_month_and_dong_default_only_missing_contextual_slots(self):
        with patch("chatbot_agent.orchestrator.execute", return_value=Evidence("근거", "범위 확인")) as execute:
            service.reply("이동이 줄었다는 거야?", [], CONTEXT, use_ai=False)
        intent = execute.call_args.args[1]
        self.assertEqual(intent.question_type, "reason")
        self.assertEqual(intent.dong, "논현1동")
        self.assertEqual((intent.start_month, intent.end_month), ("2025-12", "2025-12"))

    def test_followups_restore_displayed_month_without_replaying_history(self):
        with patch("chatbot_agent.orchestrator.execute", return_value=Evidence("연령 변화", "범위 확인")) as execute:
            service.reply("연령별 평일 이동 변화는 어때?", history("삼성1동", 12), CONTEXT, use_ai=False)
        execute.assert_called_once()
        intent = execute.call_args.args[1]
        self.assertEqual(intent.question_type, "age_activity")
        self.assertEqual(intent.dong, "삼성1동")
        self.assertEqual((intent.start_month, intent.end_month), ("2025-12", "2025-12"))

    def test_two_chats_do_not_share_memory(self):
        with patch("chatbot_agent.orchestrator.execute", return_value=Evidence("연령 변화", "범위 확인")) as execute:
            service.reply("연령대 변화는 어때?", history("삼성1동", 12), CONTEXT, use_ai=False)
            service.reply("연령대 변화는 어때?", history("역삼1동", 11), CONTEXT, use_ai=False)
            service.reply("연령대 변화는 어때?", [], CONTEXT, use_ai=False)
        intents = [call.args[1] for call in execute.call_args_list]
        self.assertEqual([(i.dong, i.start_month, i.end_month) for i in intents],
                         [("삼성1동", "2025-12", "2025-12"), ("역삼1동", "2025-11", "2025-11"),
                          ("논현1동", "2025-12", "2025-12")])

    def test_offline_bare_summary_keeps_citywide_scope_when_no_dong_selected(self):
        with patch("chatbot_agent.orchestrator.execute", return_value=Evidence("지역 조회", "범위 확인")) as execute:
            result = service.reply("요약", [], {**CONTEXT, "district": ""}, use_ai=False)
        intent = execute.call_args.args[1]
        self.assertEqual(intent.question_type, "signals")
        self.assertEqual(intent.dongs, ())
        self.assertEqual((intent.start_month, intent.end_month), ("2025-12", "2025-12"))
        self.assertIn("강남구 전체 지역", result["answer"])

    def test_configuration_follows_admin_ai_settings(self):
        self.addCleanup(patch.stopall)
        patch.stopall()  # setUp의 가짜 설정을 풀고 실제 _configuration을 검사합니다.
        off = ai_settings.AIConfig(False, "gemini", "m", "key", ".env")
        with patch.object(ai_settings, "current", return_value=off):
            self.assertIsNone(service._configuration())
            self.assertFalse(service.ai_available())
        with patch.object(ai_settings, "current", return_value=GEMINI):
            self.assertEqual(service._configuration(), GEMINI)

    def test_other_provider_uses_shared_llm_window(self):
        model_answer = {"purpose": "track_change", "question_type": "methodology", "districts": [],
                        "start_month": None, "end_month": None, "signal": "any", "metric": None,
                        "needs": [], "use_previous_scope": False, "all_available_period": False,
                        "age_band": None, "age_bands": [], "age_scope_explicit": False,
                        "include_values": False, "limit": None, "clarifying_question": None}
        claude = ai_settings.AIConfig(True, "anthropic", "claude-test", "key", ".env")
        complete = AsyncMock(return_value=json.dumps(model_answer))
        with patch.object(service, "_configuration", return_value=claude), \
                patch.object(llm, "complete", complete), \
                patch("google.genai.Client", side_effect=AssertionError("Gemini client for non-Gemini provider")):
            result = service.reply("판단 과정을 순서대로 설명해", [], CONTEXT)
        self.assertEqual(result["intentSource"], "ai")
        self.assertIn("AI 의도 판단", result["mode"])
        self.assertTrue(complete.call_args.kwargs["json_mode"])

    def test_group_does_not_add_gender_notice_to_regional_list(self):
        with patch("chatbot_agent.orchestrator.execute", return_value=Evidence("신호", "범위 확인")):
            result = service.reply("2025년 하반기 이상신호 탐지 지역 알려줘", [], CONTEXT,
                                   use_ai=False, group=({"age": "30대", "sex": "남성"}, {}))
        self.assertNotIn("notice", result)

    def test_gender_notice_is_kept_for_explicit_gender_data_request(self):
        with patch("chatbot_agent.orchestrator.execute", return_value=Evidence("이동", "범위 확인")):
            result = service.reply("삼성1동 남성의 평일 이동 변화 알려줘", [], CONTEXT, use_ai=False)
        self.assertIn("성별을 나누지 않은", result.get("notice", ""))

    def test_quota_failure_has_specific_notice_and_truthful_mode(self):
        error = RuntimeError("private-provider-details")
        error.code = 429
        client = Mock()
        client.models.generate_content.side_effect = error
        with patch("google.genai.Client", return_value=client), \
                patch("chatbot_agent.orchestrator.execute", return_value=Evidence("신호", "범위 확인")):
            result = service.reply("2025년 하반기 이상신호 탐지 지역 알려줘", [], CONTEXT,
                                   group=({"age": "30대", "sex": "남성"}, {}))
        self.assertIn("사용 한도를 초과", result["notice"])
        self.assertNotIn("성별", result["notice"])
        self.assertNotIn("외부 AI 호출 없음", result["mode"])
        self.assertNotIn("private-provider-details", json.dumps(result))


if __name__ == "__main__":
    unittest.main()

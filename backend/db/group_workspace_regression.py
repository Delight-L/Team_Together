"""Run focused regression checks for the group-dashboard explanation paths.

Usage: ``python -m backend.db.group_workspace_regression``.
"""
import unittest
from pathlib import Path

from backend.agents.regional_v16.chatbot_agent.answer_generator import _age_activity_answer, _reason_answer
from backend.agents.regional_v16.chatbot_agent.conversation_memory import ConversationMemory
from backend.agents.regional_v16.chatbot_agent.schemas import Evidence, QueryIntent
from backend.bomi.adapters.v16 import _ScopedResolver
from backend.db.group_workspace import _is_provenance_question, _provenance_answer
from backend.db.region_workspace import (REGION_TYPE_EXPLANATION, SURVEY_OTHER_METRICS_EXPLANATION,
                                         _is_region_type_question, _is_survey_metrics_question, survey_metrics_answer)


class ProvenanceAnswerTests(unittest.TestCase):
    def test_includes_verified_and_missing_source_boundaries(self):
        answer = _provenance_answer({"sourceFiles": {"age_pop": "hash", "wkdy_pop": "hash", "time_pop": "hash"}})

        self.assertIn("OA-22267", answer)
        self.assertIn("서울서베이", answer)
        self.assertIn("외부 다운로드 URL이나 제공기관 배포 페이지가 기록돼 있지 않습니다", answer)
        self.assertIn("STD_YM", answer)

    def test_does_not_treat_a_service_source_as_dashboard_provenance(self):
        self.assertFalse(_is_provenance_question("이 복지사업의 출처를 알려줘"))
        self.assertTrue(_is_provenance_question("위 화면 데이터는 어디서 다운받았어?"))
        self.assertTrue(_is_provenance_question("위 자료의 원본데이터를 설명해줘"))

    def test_cluster_question_uses_the_fixed_machine_learning_explanation(self):
        self.assertTrue(_is_region_type_question("고활동·청년유동·1인가구 중심형은 왜 나온 거야?"))
        self.assertIn("머신러닝 군집화 결과", REGION_TYPE_EXPLANATION)
        self.assertIn("K-means(k=3)", REGION_TYPE_EXPLANATION)

    def test_survey_question_lists_only_the_available_extra_metrics(self):
        self.assertTrue(_is_survey_metrics_question("다른 지표는 더 없어?"))
        self.assertIn("금전적으로 도움받을 사람 없음", SURVEY_OTHER_METRICS_EXPLANATION)
        self.assertIn("2025년 별도 문항", SURVEY_OTHER_METRICS_EXPLANATION)
        self.assertIn("동별 수치나 개인별 고립 판정은 아닙니다", SURVEY_OTHER_METRICS_EXPLANATION)

    def test_survey_detail_question_returns_stored_gangnam_and_seoul_values(self):
        answer = survey_metrics_answer({'city': '강남구', 'age': '40대', 'month': '2025-10'}, '금전적으로 도움받을 사람 없음은?')
        self.assertIn('2025년 40대 기준', answer)
        self.assertIn('강남구 8.9%', answer)
        self.assertIn('서울 전체 23.2%', answer)
        self.assertIn('동별 수치·개인별 고립 판정·탐지 신호의 입력값', answer)

    def test_selected_dashboard_case_reason_keeps_the_age_scope(self):
        resolver = _ScopedResolver(Path('.'), 'test', ('2025-07', '2025-12'),
                                   {'district': '개포3동', 'month': '2025-10', 'age': '40대'}, None, False)
        intent = resolver.resolve('이 사례의 탐지 이유', {'개포3동'}, ConversationMemory())
        self.assertEqual(intent.question_type, 'reason')
        self.assertEqual(intent.dongs, ('개포3동',))
        self.assertEqual((intent.start_month, intent.end_month, intent.age_band), ('2025-10', '2025-10', '40s'))
        self.assertTrue(intent.age_scope_explicit)

    def test_overall_signal_omits_age_panel_but_explicit_age_keeps_its_scope(self):
        overall = _reason_answer(Evidence("signal", "", rows=[{"행정동": "역삼2동", "date": "2025-11", "signal_type": "communication"}]))[0]
        self.assertNotIn("같은 기준월의 연령별 변화도 함께 볼게요.", overall)
        intent = QueryIntent(purpose="track_change", question_type="age_activity", age_band="30s", age_scope_explicit=True)
        explicit = _age_activity_answer(intent, Evidence("age", "", rows=[{
            "행정동": "역삼2동", "date": "2025-11", "age_band": "30s",
            "call_contacts_change_pct": -2.25, "text_contacts_change_pct": -4.0,
        }]))
        self.assertIn("30대", explicit)


if __name__ == "__main__":
    unittest.main()

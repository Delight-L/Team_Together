"""Run focused regression checks for the group-dashboard explanation paths.

Usage: ``python -m backend.db.group_workspace_regression``.
"""
import unittest

from backend.agents.regional_v16.chatbot_agent.answer_generator import _age_activity_answer, _reason_answer
from backend.agents.regional_v16.chatbot_agent.schemas import Evidence, QueryIntent
from backend.db.group_workspace import _is_provenance_question, _provenance_answer


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

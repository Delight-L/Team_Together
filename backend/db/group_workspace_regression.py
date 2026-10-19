"""Run focused regression checks for the group-dashboard explanation paths.

Usage: ``python -m backend.db.group_workspace_regression``.
"""
import unittest
from pathlib import Path

from backend.agents.regional_v16.chatbot_agent.answer_generator import _age_activity_answer, _reason_answer, template_answer
from backend.agents.regional_v16.chatbot_agent.conversation_memory import ConversationMemory
from backend.agents.regional_v16.chatbot_agent.schemas import Evidence, QueryIntent
from backend.bomi.adapters.v16 import _ScopedResolver
from backend.db.group_workspace import _is_provenance_question, _provenance_answer
from backend.db.region_workspace import (REGION_TYPE_EXPLANATION, SURVEY_OTHER_METRICS_EXPLANATION,
                                         _is_region_type_question, _is_survey_metrics_question, explain_region,
                                         survey_metrics_answer)


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

    def test_dashboard_case_count_question_expands_to_all_cases(self):
        resolver = _ScopedResolver(Path('.'), 'test', ('2025-07', '2025-12'),
                                   {'district': '개포3동', 'month': '2025-10', 'age': '40대'}, None, False)
        intent = resolver.resolve('탐지가 9건인데 왜 이것만 나와?', {'개포3동', '삼성1동'}, ConversationMemory())
        self.assertEqual(intent.question_type, 'signals')
        self.assertEqual(intent.dongs, ())
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

    def test_regional_analysis_tab_questions_return_function_summaries(self):
        context = {'city': '강남구', 'district': '개포3동', 'month': '2025-12', 'age': '40대'}
        data = {'assessment': [], 'regionalStructures': [{
            'dong_name': '개포3동', 'cluster_type': '중간활동·다인가구 중심형'
        }]}

        region_answer = explain_region(context, '우리 동은 어떤 지역일까?', data)['answer']
        self.assertIn('중간활동·다인가구 중심형', region_answer)
        self.assertIn('머신러닝 군집화 결과', region_answer)

        consumption_answer = explain_region(context, '소비는 어떻게 달라졌을까?', data)['answer']
        self.assertIn('상점 소재지 기준', consumption_answer)
        self.assertIn('같은 분기 평균', consumption_answer)

        tab_answer = explain_region(context, '어느 지역을 살펴볼까요? 탭에 대해 설명해줘', data)['answer']
        self.assertIn('탐지월 전후의 지역 변화 흐름', tab_answer)

    def test_empty_reason_answer_names_the_selected_dong(self):
        intent = QueryIntent(purpose='track_change', question_type='reason', dong='개포3동', age_band='40s', age_scope_explicit=True)
        answer = template_answer(intent, Evidence('선정 근거', '조건에 맞는 신호 기록은 0건입니다.', []), '')
        self.assertIn('개포3동의 조건에 맞는 신호 기록은 0건입니다.', answer)

    def test_signal_presence_question_does_not_promote_proxy_changes_to_signals(self):
        context = {'city': '강남구', 'district': '삼성1동', 'month': '2025-12'}
        data = {'months': ['2025-11', '2025-12'], 'assessment': [
            {'행정동명': '삼성1동', '기준연월': '2025-12', 'case_id': 's1',
             'is_risk_signal': False, 'has_enough_history': True}
        ]}
        answer = explain_region(context, '삼성1동에 이상신호가 잡혔다는거야?', data)['answer']
        self.assertIn('삼성1동', answer)
        self.assertIn('공식 이상신호 탐지 0건', answer)
        self.assertIn('보조 분석', answer)

    def test_signal_list_question_does_not_treat_proxy_candidates_as_official(self):
        context = {'city': '강남구', 'month': '2025-12'}
        answer = explain_region(context, '이번 달 후보 지역을 알려 줘', {
            'months': ['2025-12'], 'assessment': []
        })['answer']
        self.assertIn('공식 이상신호 탐지 목록', answer)
        self.assertIn('대시보드의 탐지 건수가 0건이면', answer)


if __name__ == "__main__":
    unittest.main()

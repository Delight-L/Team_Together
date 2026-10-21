"""Run focused regression checks for the group-dashboard explanation paths.

Usage: ``python -m backend.db.group_workspace_regression``.
"""

import unittest
from pathlib import Path

from backend.agents.regional_analysis.chatbot_agent.answer_generator import (
    _age_activity_answer,
    _reason_answer,
    template_answer,
)
from backend.agents.regional_analysis.chatbot_agent.conversation_memory import ConversationMemory
from backend.agents.regional_analysis.chatbot_agent.schemas import Evidence, QueryIntent
from backend.bomi.adapters.regional_analysis import _ScopedResolver
from backend.bomi.agents.region_analysis import RegionAnalysisAgent
from backend.bomi.request import ChatRequest
from backend.db.group_workspace import _is_provenance_question, _provenance_answer
from backend.db.region_workspace import (
    REGION_TYPE_EXPLANATION,
    SURVEY_OTHER_METRICS_EXPLANATION,
    _is_region_type_question,
    _is_signal_presence_question,
    _is_signal_reason_question,
    _is_survey_metrics_question,
    explain_region,
    survey_metrics_answer,
)


class ProvenanceAnswerTests(unittest.TestCase):
    def test_includes_verified_and_missing_source_boundaries(self):
        answer = _provenance_answer(
            {"sourceFiles": {"age_pop": "hash", "wkdy_pop": "hash", "time_pop": "hash"}}
        )

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
        answer = survey_metrics_answer(
            {'city': '강남구', 'age': '40대', 'month': '2025-10'},
            '금전적으로 도움받을 사람 없음은?',
        )
        self.assertIn('2025년 40대 기준', answer)
        self.assertIn('강남구 8.9%', answer)
        self.assertIn('서울 전체 23.2%', answer)
        self.assertIn('동별 수치·개인별 고립 판정·탐지 신호의 입력값', answer)

    def test_selected_dashboard_case_reason_keeps_the_age_scope(self):
        resolver = _ScopedResolver(
            Path('.'),
            'test',
            ('2025-07', '2025-12'),
            {'district': '개포3동', 'month': '2025-10', 'age': '40대'},
            None,
            False,
        )
        intent = resolver.resolve('이 사례의 탐지 이유', {'개포3동'}, ConversationMemory())
        self.assertEqual(intent.question_type, 'reason')
        self.assertEqual(intent.dongs, ('개포3동',))
        self.assertEqual(
            (intent.start_month, intent.end_month, intent.age_band), ('2025-10', '2025-10', '40s')
        )
        self.assertTrue(intent.age_scope_explicit)

    def test_dashboard_case_count_question_expands_to_all_cases(self):
        resolver = _ScopedResolver(
            Path('.'),
            'test',
            ('2025-07', '2025-12'),
            {'district': '개포3동', 'month': '2025-10', 'age': '40대'},
            None,
            False,
        )
        intent = resolver.resolve(
            '탐지가 9건인데 왜 이것만 나와?', {'개포3동', '삼성1동'}, ConversationMemory()
        )
        self.assertEqual(intent.question_type, 'signals')
        self.assertEqual(intent.dongs, ())
        self.assertEqual(
            (intent.start_month, intent.end_month, intent.age_band), ('2025-10', '2025-10', '40s')
        )
        self.assertTrue(intent.age_scope_explicit)

    def test_overall_signal_omits_age_panel_but_explicit_age_keeps_its_scope(self):
        overall = _reason_answer(
            Evidence(
                "signal",
                "",
                rows=[{"행정동": "역삼2동", "date": "2025-11", "signal_type": "communication"}],
            )
        )[0]
        self.assertNotIn("같은 기준월의 연령별 변화도 함께 볼게요.", overall)
        intent = QueryIntent(
            purpose="track_change",
            question_type="age_activity",
            age_band="30s",
            age_scope_explicit=True,
        )
        explicit = _age_activity_answer(
            intent,
            Evidence(
                "age",
                "",
                rows=[
                    {
                        "행정동": "역삼2동",
                        "date": "2025-11",
                        "age_band": "30s",
                        "call_contacts_change_pct": -2.25,
                        "text_contacts_change_pct": -4.0,
                    }
                ],
            ),
        )
        self.assertIn("30대", explicit)

    def test_regional_analysis_tab_questions_return_function_summaries(self):
        context = {'city': '강남구', 'district': '개포3동', 'month': '2025-12', 'age': '40대'}
        data = {
            'assessment': [],
            'regionalStructures': [
                {'dong_name': '개포3동', 'cluster_type': '중간활동·다인가구 중심형'}
            ],
        }

        region_answer = explain_region(context, '우리 동은 어떤 지역일까?', data)['answer']
        self.assertIn('중간활동·다인가구 중심형', region_answer)
        self.assertIn('머신러닝 군집화 결과', region_answer)

        consumption_answer = explain_region(context, '소비는 어떻게 달라졌을까?', data)['answer']
        self.assertIn('상점 소재지 기준', consumption_answer)
        self.assertIn('같은 분기 평균', consumption_answer)

        tab_answer = explain_region(context, '어느 지역을 살펴볼까요? 탭에 대해 설명해줘', data)[
            'answer'
        ]
        self.assertIn('탐지월 전후의 지역 변화 흐름', tab_answer)

    def test_empty_reason_answer_names_the_selected_dong(self):
        intent = QueryIntent(
            purpose='track_change',
            question_type='reason',
            dong='개포3동',
            age_band='40s',
            age_scope_explicit=True,
        )
        answer = template_answer(
            intent, Evidence('선정 근거', '조건에 맞는 신호 기록은 0건입니다.', []), ''
        )
        self.assertIn('개포3동의 조건에 맞는 신호 기록은 0건입니다.', answer)

    def test_signal_presence_question_does_not_promote_proxy_changes_to_signals(self):
        context = {'city': '강남구', 'district': '삼성1동', 'month': '2025-12'}
        data = {
            'months': ['2025-11', '2025-12'],
            'assessment': [
                {
                    '행정동명': '삼성1동',
                    '기준연월': '2025-12',
                    'case_id': 's1',
                    'is_risk_signal': False,
                    'has_enough_history': True,
                }
            ],
        }
        answer = explain_region(context, '삼성1동에 이상신호가 잡혔다는거야?', data)['answer']
        self.assertIn('삼성1동', answer)
        self.assertIn('공식 이상신호 탐지 0건', answer)
        self.assertIn('보조 분석', answer)
        answer = explain_region(context, '왜 삼성1동이 확인 대상인가요?', data)['answer']
        self.assertIn('공식 이상신호 탐지 0건', answer)

    def test_signal_reason_phrasings_use_selected_dashboard_evidence(self):
        reason_phrases = (
            '왜 신호로 잡혔나요?',
            '왜 신호가 잡혔나요?',
            '왜 신호로 잡힌 거야?',
            '왜 신호가 나온 거야?',
            '이 사례의 탐지 이유',
            '탐지 이유가 뭐야?',
            '왜 탐지됐나요?',
            '왜 잡혔어요?',
            '이 동은 왜 후보인가요?',
            '왜 확인 대상인가요?',
            '후보 선정 이유가 뭐예요?',
            '확인 대상으로 선정된 이유',
            '이상 신호가 발생한 이유가 뭐야?',
            '어떤 근거로 탐지된 거예요?',
            '왜 탐지되지 않았나요?',
        )
        for question in reason_phrases:
            with self.subTest(question=question):
                self.assertTrue(_is_signal_reason_question(question))
                self.assertFalse(_is_signal_presence_question(question))

        context = {'city': '강남구', 'district': '역삼2동', 'month': '2025-11', 'age': '30대'}
        data = {
            'months': ['2025-10', '2025-11'],
            'assessment': [
                {
                    '행정동명': '역삼2동',
                    '기준연월': '2025-11',
                    'age_label': '30대',
                    'age_band': '30s',
                    'case_id': 'ys2-30',
                    'metric_label': '전화 연락',
                    'change_pct': -2.25,
                    'is_risk_signal': True,
                    'has_enough_history': True,
                },
                {
                    '행정동명': '역삼2동',
                    '기준연월': '2025-11',
                    'age_label': '30대',
                    'age_band': '30s',
                    'case_id': 'ys2-30',
                    'metric_label': '문자 연락',
                    'change_pct': -4.0,
                    'is_risk_signal': True,
                    'has_enough_history': True,
                },
            ],
        }
        answer = explain_region(context, '왜 신호로 잡혔나요?', data)['answer']
        self.assertIn('역삼2동', answer)
        self.assertIn('전화 연락 -2.2%', answer)
        self.assertIn('문자 연락 -4.0%', answer)
        self.assertIn('후보 기준에 해당하는 연령집단은 1개', answer)

    def test_signal_reason_workspace_scope_stays_on_selected_dashboard_case(self):
        selected = ChatRequest(
            messages=({'role': 'user', 'content': '왜 신호로 잡혔나요?'},),
            context={'city': '강남구', 'district': '역삼2동', 'month': '2025-11'},
            data={'assessment': []},
        )
        self.assertTrue(RegionAnalysisAgent._uses_workspace(selected))

        other_dong = ChatRequest(
            messages=({'role': 'user', 'content': '삼성1동은 왜 탐지됐나요?'},),
            context=selected.context,
            data=selected.data,
        )
        self.assertFalse(RegionAnalysisAgent._uses_workspace(other_dong))
        no_district = ChatRequest(
            messages=({'role': 'user', 'content': '탐지 이유가 뭐야?'},),
            context={'city': '강남구', 'month': '2025-11'},
            data=selected.data,
        )
        self.assertFalse(RegionAnalysisAgent._uses_workspace(no_district))
        no_assessment = ChatRequest(messages=selected.messages, context=selected.context, data={})
        self.assertFalse(RegionAnalysisAgent._uses_workspace(no_assessment))

        self.assertFalse(_is_signal_reason_question('지역유형 선정 근거를 알려줘'))
        self.assertFalse(_is_signal_reason_question('복지사업 선정 근거를 알려줘'))

    def test_signal_list_question_does_not_treat_proxy_candidates_as_official(self):
        context = {'city': '강남구', 'month': '2025-12'}
        answer = explain_region(
            context, '이번 달 후보 지역을 알려 줘', {'months': ['2025-12'], 'assessment': []}
        )['answer']
        self.assertIn('공식 이상신호 탐지 0건', answer)
        self.assertIn('이번 달 후보 지역은 없습니다', answer)


if __name__ == "__main__":
    unittest.main()

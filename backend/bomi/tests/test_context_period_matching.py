"""Contextual data uses a nearby comparable period when the screen period cannot."""
import unittest

from backend.bomi.adapters import v16  # Adds the regional agent package to sys.path.
from chatbot_agent.answer_generator import _commerce_lines, _reason_answer
from chatbot_agent.consumption_trends import consumption_trends
from chatbot_agent.period_matching import nearest_period
from chatbot_agent.schemas import Evidence, QueryIntent
from chatbot_agent.orchestrator import Chatbot


class FakeConsumptionRepository:
    def district_codes(self):
        return {'역삼2동': '1123065'}

    def consumption_payloads(self, table, **_filters):
        merchant = [
            {'adm_cd': '1123065', 'period': '2025Q2', 'age': '30대', 'domain': '식사',
             'daily_count': 10, 'observed_industries': 1},
            {'adm_cd': '1123065', 'period': '2025Q3', 'age': '30대', 'domain': '식사',
             'daily_count': 12, 'observed_industries': 1},
        ]
        comparison = [
            {'adm_cd': '1123065', 'period': '2025Q3', 'age': '30대', 'domain': '식사',
             'qoq_daily_change_pct': 20.0, 'qoq_matched_industry_count': 1},
        ]
        district = [
            {'period': '2025-09', 'district': '11680', 'age': '30대', 'domain': '식사',
             'daily_count': 20, 'observed_industries': 1, 'days': 30, 'observed_industry_days_min': 30,
             'matched_mom_daily_change_pct': 5.0, 'matched_industry_count': 1},
            {'period': '2025-10', 'district': '11680', 'age': '30대', 'domain': '식사',
             'daily_count': 22, 'observed_industries': 1, 'days': 31, 'observed_industry_days_min': 31,
             'matched_mom_daily_change_pct': 10.0, 'matched_industry_count': 1},
        ]
        return {'a3a_feature': merchant, 'a3a_comparison': comparison, 'a3b_feature': district}[table]


class ContextPeriodMatchingTest(unittest.TestCase):
    def test_nearest_period_prefers_the_prior_period_for_a_tie(self):
        self.assertEqual(nearest_period(['2025-09', '2025-11'], '2025-10'), '2025-09')

    def test_single_dashboard_month_uses_nearest_comparable_quarter_and_month(self):
        rows = consumption_trends(FakeConsumptionRepository(), ('역삼2동',), '2025-11', '2025-11', '30s')
        local = next(row for row in rows if row['scope'] == 'merchant_dong')
        district = next(row for row in rows if row['scope'] == 'merchant_district_shared')
        self.assertEqual(local['period'], '2025Q3')
        self.assertEqual(district['period'], '2025-10')
        for row in (local, district):
            self.assertEqual(row['selection_alignment'], 'nearest_comparable_period')
            self.assertEqual(row['requested_period'], '2025-11~2025-11')
            self.assertIsNotNone(row['change_pct'])

    def test_response_labels_a_nearby_reference_as_a_reference(self):
        rows = consumption_trends(FakeConsumptionRepository(), ('역삼2동',), '2025-11', '2025-11', '30s')
        text = '\n'.join(_commerce_lines(rows))
        self.assertIn('가장 가까운 비교 가능한 2025년 3분기 자료를 대신 보여드립니다.', text)
        self.assertIn('가장 가까운 비교 가능한 2025년 10월 자료를 대신 보여드립니다.', text)

    def test_zero_signal_reason_invites_a_search_for_other_regions(self):
        text = _reason_answer(Evidence('선정 근거', '조건에 맞는 신호 기록은 0건입니다.'))[0]
        self.assertIn('2025년의 다른 이상신호 지역을 찾아 안내해 드릴까요?', text)

        follow_ups = Chatbot._follow_ups(
            QueryIntent('track_change', 'reason', dong='역삼2동'),
            Evidence('선정 근거', '조건에 맞는 신호 기록은 0건입니다.'),
        )
        self.assertEqual(follow_ups[0], '2025년 다른 이상신호 지역 찾아줘')


if __name__ == '__main__':
    unittest.main()

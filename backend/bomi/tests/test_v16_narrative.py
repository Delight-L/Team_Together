"""Narrative responses preserve direction, age verdicts, and conversation scope."""
import math
import unittest
from unittest.mock import patch

from backend.bomi.adapters import v16 as v16_service
from chatbot_agent.answer_generator import template_answer
from chatbot_agent.schemas import Evidence, QueryIntent


class NarrativeTest(unittest.TestCase):
    def row(self, **extra):
        return {'행정동': '삼성1동', 'date': '2025-12', 'signal_type': 'mobility',
                'weekday_move_count_log_change': math.log(0.939),
                'weekend_move_count_log_change': math.log(1.036), **extra}

    @unittest.skipUnless(v16_service.data_ready(), 'v16 DB1 SQLite가 없어 건너뜀(저장소에 올리지 않는 자료)')
    def test_real_offline_reply_explains_mixed_direction_and_age_verdict_without_technical_list(self):
        with patch('google.genai.Client', side_effect=AssertionError('external AI')), \
                patch('chatbot_agent.orchestrator.try_gemini', side_effect=AssertionError('external AI')):
            reply = v16_service.reply('2025년 하반기 이상신호 탐지 지역 알려줘', [],
                                      {'city': '강남구', 'district': '삼성1동', 'month': '2025-12'}, use_ai=False)
        text = reply['answer']
        self.assertIn('평일 이동 횟수가 6.1% 줄었고, 휴일 이동 횟수가 3.6% 늘었어요.', text)
        self.assertIn('휴일 이동이 늘었는데도 신호가 잡힌 이유', text)
        self.assertIn('평소 변화 범위에서 아래쪽으로 크게 벗어나', text)
        self.assertIn('청년층의 활동과 1인 가구', text)
        for age, weekday, holiday in [('20대', '7.3', '3.5'), ('30대', '5.9', '1.7'),
                                      ('40대', '5.7', '3.4'), ('50대', '6.5', '4.6'), ('60세 이상', '5.7', '4.0')]:
            self.assertIn(f'{age}에서는 평일 이동 횟수가 {weekday}% 줄었고, 휴일 이동 횟수가 {holiday}% 늘었어요.', text)
        self.assertIn('별도의 이동 이상신호가 잡히지 않았어요', text)
        for technical in ['Robust Z', '신호 판정:', '핵심 변화:', '**', '2025년 7월 기준']:
            self.assertNotIn(technical, text)
        self.assertEqual(len(reply['followUps']), 3)

    def test_initial_and_reason_age_changes_never_include_other_month_or_dong(self):
        ages = [{'행정동': dong, 'date': date, 'age_band': age, 'age_signal': signal,
                 'changes': {'weekday_move_count': change, 'weekend_move_count': 2.0}}
                for dong, date, age, signal, change in [('삼성1동', '2025-12', '20s', True, -8.0),
                                                      ('삼성1동', '2025-12', '30s', None, None),
                                                      ('삼성1동', '2025-11', '40s', False, -99.0),
                                                      ('역삼1동', '2025-12', '50s', False, -98.0)]]
        evidence = Evidence('신호', '조회', rows=[self.row()], supplementary={'age_signal_changes': ages})
        for kind in ('signals', 'reason'):
            text = template_answer(QueryIntent('track_change', kind), evidence, '')
            self.assertIn('20대에서는 이동 신호가 연령별 판정에서도 확인됐어요.', text)
            self.assertIn('30대는 자료가 부족하거나 판정 결과가 없어', text)
            self.assertNotIn('별도의 이동 이상신호가 잡히지', text)
            self.assertNotIn('99.0%', text)
            self.assertNotIn('98.0%', text)
            self.assertNotIn('40대에서는', text)
            self.assertNotIn('50대에서는', text)

    def test_age_specific_reason_does_not_claim_local_filter_is_required(self):
        evidence = Evidence('연령 신호', '조회', rows=[self.row(age_band='30s')])
        text = template_answer(QueryIntent('track_change', 'reason', age_band='30s'), evidence, '')
        self.assertIn('연령별 판정 기준', text)
        self.assertIn('원래 변화와 강남구 공통 흐름을 감안한 변화를 각각', text)
        self.assertNotIn('두 지표의 변화가 모두 평소 변화 범위에서', text)

    def test_age_activity_uses_requested_domain_and_not_any_other_signal(self):
        row = {'행정동': '삼성1동', 'date': '2025-12', 'age_band': '20s',
               'weekday_move_count_change_pct': -7.3, 'weekend_move_count_change_pct': 3.5,
               'mobility_signal': False, 'communication_signal': True, 'any_signal': True}
        text = template_answer(QueryIntent('track_change', 'age_activity', signal='mobility'),
                               Evidence('이동', '조회', rows=[row]), '')
        self.assertIn('7.3% 줄었고', text)
        self.assertIn('별도의 이동 이상신호가 잡히지 않았어요.', text)
        self.assertNotIn('통화 상대 수', text)
        self.assertNotIn('연령별 판정에서도 확인됐어요', text)

    def test_unknown_is_not_zero_and_any_does_not_mean_simultaneous(self):
        row = {'행정동': '삼성1동', 'date': '2025-12', 'age_band': '40s',
               'weekday_move_count_change_pct': None, 'any_signal': None}
        text = template_answer(QueryIntent('track_change', 'age_activity', metric='weekday_move_count'),
                               Evidence('이동', '조회', rows=[row]), '')
        self.assertIn('비교 자료가 부족해', text)
        self.assertNotIn('0.0%', text)
        self.assertNotIn('이상신호가 잡히지', text)
        row['any_signal'] = True
        text = template_answer(QueryIntent('track_change', 'age_activity'), Evidence('활동', '조회', rows=[row]), '')
        self.assertIn('소통 또는 이동 신호', text)
        self.assertNotIn('소통·이동 신호', text)

    def test_selected_metric_stays_selected_and_zero_change_has_no_direction(self):
        row = {'행정동': '삼성1동', 'date': '2025-12', 'age_band': '50s',
               'weekday_move_count_change_pct': 0.0, 'weekend_move_count_change_pct': 4.6,
               'mobility_signal': False}
        text = template_answer(QueryIntent('track_change', 'age_activity', metric='weekday_move_count'),
                               Evidence('이동', '조회', rows=[row]), '')
        self.assertIn('변화가 없었어요', text)
        self.assertNotIn('휴일 이동', text)
        self.assertNotIn('줄었', text)
        self.assertNotIn('늘었', text)


if __name__ == '__main__':
    unittest.main()

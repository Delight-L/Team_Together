"""Nondecreasing mobility must be distinguished from a decrease signal."""
import math
import unittest
from backend.agents import v16_service
from chatbot_agent.answer_generator import template_answer
from chatbot_agent.schemas import Evidence, QueryIntent


class MobilityDirectionTest(unittest.TestCase):
    def answer(self, weekday, weekend, signal='mobility', age=None, kind='reason'):
        row={'행정동':'세곡동','date':'2025-05','signal_type':signal,'age_band':age,
             'weekday_move_count_log_change':math.log1p(weekday),
             'weekend_move_count_log_change':math.log1p(weekend)}
        return template_answer(QueryIntent('track_change',kind),Evidence('신호','조회',rows=[row]),'')

    def test_weekday_increase_explains_why_signal_can_still_be_detected(self):
        for kind in ('signals','reason'):
            text=self.answer(.091,.031,kind=kind)
            self.assertIn('평일 이동 횟수가 9.1% 늘었고',text)
            self.assertIn('휴일 이동 횟수가 3.1% 늘었어요',text)
            self.assertIn('평일 이동 횟수·휴일 이동 횟수는 실제로 줄지 않았어요',text)
            self.assertIn('실제 이동 횟수가 줄었는지를 필수 조건으로 두지 않아요',text)
            self.assertIn('모두 탐지 기준 이하',text)
            self.assertIn('점수·탐지 기준값',text)
            self.assertNotIn('두 지표의 변화가 모두 평소 변화 범위에서 아래쪽으로 크게 벗어나',text)

    def test_each_nondecreasing_direction_and_combined_signal(self):
        for weekday,weekend,signal,label in [(.1,-.1,'mobility','평일 이동 횟수'),
                (0,-.1,'mobility','평일 이동 횟수'),(-.1,.1,'mobility','휴일 이동 횟수'),
                (.1,.1,'combined','평일 이동 횟수·휴일 이동 횟수')]:
            with self.subTest(weekday=weekday,weekend=weekend,signal=signal):
                text=self.answer(weekday,weekend,signal)
                self.assertIn(label+'는 실제로 줄지 않았어요',text)
                self.assertIn('증가해도 신호가 잡힐 수 있어요',text)

    def test_age_does_not_inherit_district_detection_rule(self):
        text=self.answer(.1,.03,age='30s')
        self.assertIn('연령별 판정 기준은 동 전체 판정과 달라요',text)
        self.assertNotIn('실제 이동 횟수가 줄었는지를 필수 조건으로 두지 않아요',text)

    def test_decreasing_and_missing_values_do_not_trigger_explanation(self):
        text=self.answer(-.1,-.03)
        self.assertNotIn('실제로 줄지 않았어요',text)
        row={'행정동':'세곡동','date':'2025-05','signal_type':'mobility'}
        text=template_answer(QueryIntent('track_change','reason'),Evidence('신호','조회',rows=[row]),'')
        self.assertNotIn('실제로 줄지 않았어요',text)

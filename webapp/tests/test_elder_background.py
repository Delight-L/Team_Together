import unittest
from db.region_workspace import explain_region
from db.group_workspace import explain

STRUCTURE = {'dong_name': '신사동', 'payload': {'elderly_living_alone_rate_65plus': .2, 'elder_year': 2025, 'denominator_reference': '2025Q4'}}

class ElderBackgroundTest(unittest.TestCase):
    def test_regional_answer_uses_actual_annual_population_basis(self):
        result = explain_region({'city': '강남구', 'district': '신사동'}, '독거노인 비율', {'regionalStructures': [STRUCTURE]})
        for text in ['20.00%', '2025년 연간', '2025Q4', '개인의 고립 판정이 아닙니다']:
            self.assertIn(text, result['answer'])

    def test_other_city_does_not_borrow_gangnam_background(self):
        result = explain_region({'city': '춘천시', 'district': '신사동'}, '독거노인 비율', {'regionalStructures': [STRUCTURE]})
        self.assertIn('연결되지', result['answer'])
        self.assertNotIn('20.00%', result['answer'])

    def test_group_answer_keeps_population_scope(self):
        detail = {'current': {'district': '신사동', 'age': '30대', 'sex': '남성'}, 'regional': {'structure': STRUCTURE}, 'runId': 'test'}
        result = explain({}, '독거노인 지표 뜻', detail)
        self.assertIn('60세 이상 집단과 연령 범위가 다릅니다', result['answer'])

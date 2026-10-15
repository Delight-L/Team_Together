import unittest
from backend.db.survey_context import survey_for


class SurveyDashboardTests(unittest.TestCase):
    def test_age_and_district_scope_are_not_dong_isolation(self):
        a=survey_for(dict(city='강남구',age='40대',month='2025-10',code='1123072'))
        b=survey_for(dict(city='강남구',age='40대',month='2025-10',code='1123074'))
        self.assertEqual(a,b)
        self.assertEqual(a['scope'],'district_age')
        self.assertEqual(a['year'],2025)
        self.assertAlmostEqual(a['value']*100,6.1,delta=.05)
        self.assertNotEqual(a['value'],survey_for(dict(city='강남구',age='50대',month='2025-10'))['value'])

    def test_future_years_and_unsupported_ages_are_not_substituted(self):
        self.assertEqual(survey_for(dict(city='강남구',age='40대',month='2024-10'))['year'],2024)
        self.assertIsNone(survey_for(dict(city='춘천시',age='40대',month='2025-10')))
        self.assertIsNone(survey_for(dict(city='강남구',age='10대',month='2025-10')))
        self.assertIsNone(survey_for(dict(city='강남구',age='40대',month='2021-10')))

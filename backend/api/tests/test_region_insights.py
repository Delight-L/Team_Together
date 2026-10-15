import unittest
from backend.api.common import Request
from backend.api.routes_region_insights import detail
from backend.db.region_insights import load_region_insights


class RegionInsightsTests(unittest.TestCase):
    def test_snapshot_contains_exact_scopes_and_real_consumption(self):
        data=load_region_insights('강남구')
        self.assertEqual(len(data['typologies']),22)
        self.assertEqual(data['consumptionScope'],'merchant_dong_customer_age')
        self.assertEqual(data['surveyScope'],'district_age_annual')
        r=next(r for r in data['consumption'] if r['code']=='1123072' and r['age']=='40대' and r['period']=='2025Q4' and r['domain']=='B_여가운동')
        self.assertEqual(r['change'],200)
        self.assertEqual(r['baselinePeriods'],['2022Q4','2023Q4','2024Q4'])
        self.assertFalse(any('sex' in r for r in data['consumption']))

    def test_city_access_and_unsupported_city_do_not_leak_gangnam(self):
        user={'id':'test','org':'춘천시','admin':False}
        with self.assertRaises(PermissionError):detail(Request({'city':'강남구'},user,None))
        self.assertEqual(detail(Request({'city':'춘천시'},user,None))['consumption'],[])

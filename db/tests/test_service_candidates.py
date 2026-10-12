"""수집 테이블 조회를 임시 SQLite DB에서 실제 SQL로 검증합니다."""
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch
from sqlalchemy import create_engine, text

from db.mission_store import service_candidates, service_key
from agents.service_matching import match_services


class ServiceCandidatesTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        with self.engine.begin() as conn:
            conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS db2")
            conn.exec_driver_sql('''CREATE TABLE db2.local_welfare_services (
                service_id TEXT PRIMARY KEY, name TEXT, province TEXT, district TEXT,
                target_text TEXT, eligibility_text TEXT, summary TEXT, benefit_text TEXT,
                effective_start DATE, effective_end DATE, detail_pending BOOLEAN,
                detail_checked_at TEXT, source_url TEXT)''')
            today = datetime.now(ZoneInfo('Asia/Seoul')).date()
            fixtures = [
                ('local', '서울특별시', '강남구', None, None),
                ('province', '서울특별시', None, None, None),
                ('unknown', '서울특별시', '-', None, None),
                ('other', '서울특별시', '강북구', None, None),
                ('ended', '서울특별시', '강남구', None, today - timedelta(days=1)),
                ('future', '서울특별시', '강남구', today + timedelta(days=1), None),
                ('today', '서울특별시', '강남구', today, today),
                ('chuncheon', '강원특별자치도', '춘천시', None, None),
                ('old_province', '강원도', None, None, None),
                ('same_name', '다른시도', '강남구', None, None),
            ]
            for key, province, district, start, end in fixtures:
                conn.execute(text('''INSERT INTO db2.local_welfare_services
                    (service_id,name,province,district,benefit_text,effective_start,effective_end,detail_pending)
                    VALUES (:id,:name,:province,:district,:benefit,:start,:end,true)'''),
                    dict(id=key, name=key, province=province, district=district,
                         benefit='사회참여 교류 지원', start=start, end=end))
        self.patch = patch('db.analysis_repository.get_engine', return_value=self.engine)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.engine.dispose()

    def test_region_period_and_mapping(self):
        rows = service_candidates('강남구')
        self.assertEqual({row['service_id'] for row in rows}, {'local', 'province', 'unknown', 'today'})
        self.assertEqual({row['service_id'] for row in service_candidates('춘천시')}, {'chuncheon', 'old_province'})
        self.assertEqual(service_candidates('알수없는지역'), [])
        for row in rows:
            self.assertEqual(row['source_id'], 'local_welfare_api')
            self.assertEqual(row['external_id'], row['service_id'])
            self.assertEqual(row['support_text'], row['benefit_text'])
            self.assertEqual(row['coverage_scope'], 'unknown')

    def test_api_id_is_stable_after_name_or_region_updates(self):
        row = service_candidates('강남구')[0]
        self.assertEqual(service_key(row), service_key(row | {'name': '새 사업명', 'region_id': '새 지역'}))
        self.assertNotEqual(service_key(row), service_key(row | {'service_id': 'different'}))

    def test_matching_uses_collected_benefit_text(self):
        matches = match_services('강남구', [{'is_risk_signal': True, 'metric_label': '외출 활동'}])
        self.assertEqual(len(matches), 4)
        self.assertTrue(all(m['score'] > 0 for m in matches))
        self.assertIn('사회참여', matches[0]['reasons'][0]['service_terms'])

    def test_samsung_weekday_and_holiday_mobility_match(self):
        evidence = [
            {'metric_label': '평일 이동', 'is_risk_signal': True},
            {'metric_label': '휴일 이동', 'is_risk_signal': True},
            {'metric_label': '전화 연락', 'is_risk_signal': False},
        ]
        matches = match_services('강남구', evidence)
        self.assertTrue(all(m['score'] == 1 for m in matches))
        self.assertEqual(matches[0]['reasons'][0]['metrics'], ['평일 이동', '휴일 이동'])
        self.assertTrue(all(m['score'] == 0 for m in match_services(
            '강남구', [dict(row, is_risk_signal=False) for row in evidence])))


if __name__ == '__main__':
    unittest.main()

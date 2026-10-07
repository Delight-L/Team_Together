from pathlib import Path
from contextlib import closing
import unittest,tempfile,sqlite3,json,importlib.util
module=Path(__file__).resolve().parent/'source_semantics.py'
if not module.exists():module=Path(__file__).resolve().parents[1]/'source_semantics.py'
spec=importlib.util.spec_from_file_location('semantics_under_test',module);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Checks(unittest.TestCase):
 def test_previous_window_and_cross_year(self):
  w=m.window('2025-10-01');self.assertEqual(w['observation_months'],['2025-07','2025-08','2025-09']);self.assertEqual(w['exact_quarter'],'2025Q3')
  w=m.window('2026-01-01');self.assertEqual(w['observation_start'],'2025-10-01');self.assertEqual(w['exact_quarter'],'2025Q4')
 def test_partial_quarter_not_fabricated(self):
  w=m.window('2025-11-01');self.assertIsNone(w['exact_quarter']);self.assertEqual(w['overlap_quarters'],['2025Q3','2025Q4'])
 def test_calendar_is_not_provider_holidays(self):
  w=m.window('2025-10-01');self.assertEqual(w['calendar_days'],92);self.assertEqual(w['calendar_mon_fri_days']+w['calendar_sat_sun_days'],92);self.assertIsNone(w['provider_holiday_includes_public_holidays']);self.assertIsNone(w['available_from'])
 def test_negative_index_is_valid(self):
  s=m.sns_summary([{'value':-.5,'population':500},{'value':.1,'population':500}]);self.assertAlmostEqual(s['sns_index_mean'],-.2);self.assertEqual(s['finite_population_coverage'],1);self.assertFalse(s['time_series_comparable']);self.assertEqual(s['negative_cells'],1)
 def test_zero_is_not_absence(self):
  s=m.sns_summary([{'value':0,'population':500},{'value':-.2,'population':500}]);self.assertAlmostEqual(s['sns_index_mean'],-.1);self.assertEqual(s['quality_status'],'zero_semantics_review');self.assertFalse(s['percent_change_allowed'])
 def test_masked_missing_unavailable(self):
  s=m.sns_summary([{'value':'*','population':900},{'value':-.2,'population':100}]);self.assertIsNone(s['sns_index_mean']);self.assertEqual(s['quality_status'],'unavailable')
 def test_idempotency_and_revision_guard(self):
  with tempfile.TemporaryDirectory() as t:
   with closing(sqlite3.connect(Path(t)/'check.sqlite')) as c,c:
    c.executescript(m.SCHEMA)
    self.assertEqual(m.upsert_guard(c,'a2_observation_window',['date'],['2025-10-01'],m.window('2025-10-01')),1)
    self.assertEqual(m.upsert_guard(c,'a2_observation_window',['date'],['2025-10-01'],m.window('2025-10-01')),0)
    with self.assertRaisesRegex(ValueError,'revision'):m.upsert_guard(c,'a2_observation_window',['date'],['2025-10-01'],{'wrong':'new'})
 def test_card_window_prior_missing_is_unavailable(self):
  r=m.card_window_comparison({},['2025-07','2025-08','2025-09'],['2025-04','2025-05','2025-06'],'30대','A');self.assertIsNone(r['change_pct'])
 def test_card_window_future_complete_matches_industries(self):
  import calendar
  months=['2025-10','2025-11','2025-12'];prior=['2025-07','2025-08','2025-09'];data={}
  for period in months+prior:
   days=calendar.monthrange(int(period[:4]),int(period[5:7]))[1]
   data[(period,'30대','A','one')]=[{'use_count':days*(8 if period in months else 10),'observed_days':days}]
  r=m.card_window_comparison(data,months,prior,'30대','A');self.assertAlmostEqual(r['change_pct'],-20)
  data[(months[0],'30대','A','one')][0]['observed_days']=1
  self.assertIsNone(m.card_window_comparison(data,months,prior,'30대','A')['change_pct'])
if __name__=='__main__':unittest.main()


import unittest
from pathlib import Path
from backend.tools.export_activity_tracking import activity_tracking
from backend.db.region_insights import load_region_insights

ROOT=Path(__file__).resolve().parents[3]

class ActivityTrackingTests(unittest.TestCase):
    def test_export_preserves_existing_detection_and_recovery_results(self):
        data=activity_tracking(ROOT/'pipelines/db1')
        self.assertEqual(len(data['events']),10)
        self.assertEqual(sum(len(e['points']) for e in data['events']),29)
        event=next(e for e in data['events'] if e['code']=='1123074' and e['age']=='40대')
        self.assertEqual(event['district'],'개포3동')
        self.assertEqual(event['signals']['communication'],{'absolute':True,'local':False})
        self.assertEqual(event['signals']['mobility'],{'absolute':False,'local':False})
        self.assertEqual([p['month'] for p in event['points']],['2025-10','2025-11','2025-12'])
        self.assertEqual(event['points'][-1]['domains']['communication']['recovery_status'],'below_reference')
        self.assertEqual(event['points'][-1]['domains']['mobility']['consecutive_both_below_months'],2)

    def test_existing_city_access_and_snapshot_context_remain_separate(self):
        data=load_region_insights('강남구')
        self.assertEqual(len(data['activityTracking']['events']),10)
        self.assertEqual(len(data['typologies']),22)
        self.assertNotIn('activityTracking',load_region_insights('춘천시'))

    def test_missing_source_is_not_a_false_empty_detection_result(self):
        data=activity_tracking(ROOT/'not-a-database')
        self.assertFalse(data['available'])
        self.assertEqual(data['events'],[])

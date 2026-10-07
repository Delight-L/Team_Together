import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import math
from explain_signals import explain,percent,build

class ExplainTests(unittest.TestCase):
    def row(self,**kwargs):
        return dict(assessment_status='assessed',result_json={},**kwargs)
    def test_log_conversion(self):
        self.assertAlmostEqual(percent(math.log(.8)),-20)
        self.assertIsNone(percent(None))
    def test_single_signal_not_promoted(self):
        x=explain(self.row(communication_signal=1,mobility_signal=0))
        self.assertEqual(x['category'],'communication_only')
        self.assertFalse(x['isolation_related_candidate']);self.assertIsNone(x['probability'])
    def test_no_signal_not_no_risk(self):
        self.assertTrue(any('가능성이 없다고 판단하지' in s for s in explain(self.row())['explanation']))
    def test_missing_not_zero(self):
        x=explain({'assessment_status':'insufficient_data'})
        self.assertEqual(x['category'],'insufficient_data')
        self.assertIsNone(x['metrics'][0]['change_pct'])
    def test_actual_threshold_preserved(self):
        r=self.row(communication_signal=1)
        r['result_json']={'call_contacts_local_signal':True,'call_contacts_local_assessable':True,'call_contacts_local_rz':-4,'call_contacts_local_threshold':-3.18,'call_contacts_local_baseline_n':45}
        x=explain(r)
        self.assertEqual(x['metrics'][0]['tests'][1]['threshold'],-3.18)
        self.assertTrue(any('-3.180' in s for s in x['explanation']))
    def test_no_quarter_no_invented_comparison(self):
        x=explain(self.row(observation_consumption_json={'domains':[{'domain':'A','market_period':None,'market_change_pct':None,'card_window_change_pct':None}]}))
        self.assertTrue(any('판단할 수 없습니다' in s for s in x['explanation']))
    def test_source_quality_preserved(self):
        r=self.row(youth_reference={'applicability':'not_applicable','metrics':[]})
        self.assertEqual(explain(r)['evidence'],r)
    def test_local_only_is_independent(self):
        r=self.row(communication_signal=1)
        r['result_json']={'call_contacts_absolute_assessable':True,'call_contacts_absolute_signal':False,'call_contacts_local_assessable':True,'call_contacts_local_signal':True}
        checks=explain(r)['evidence_checks']
        self.assertEqual(checks['self_history']['status'],'not_detected')
        self.assertEqual(checks['regional_comparison']['status'],'confirmed')
    def test_missing_is_not_negative_check(self):
        checks=explain(self.row())['evidence_checks']
        self.assertEqual(checks['regional_comparison']['status'],'not_assessable')
    def test_overlapping_run_not_persistence_confirmation(self):
        r=self.row(communication_signal=1)
        r['result_json']={'adjacent_signal_run':4}
        r['activity_followup_same_label']={'consecutive_both_below_months':4,'months_since_signal':3}
        checks=explain(r)['evidence_checks']
        self.assertEqual(checks['persistence']['status'],'requires_followup')
        self.assertFalse(checks['persistence']['independent_windows_verified'])
    def domain(self,name,value,alignment='exact_full_quarter'):
        return {'domain':name,'market_alignment':alignment,'market_period':'2025Q3','market_change_pct':value,'market_comparison':{'comparison_available':True}}
    def test_market_context_never_promotes_candidate(self):
        r=self.row(communication_signal=1,observation_consumption_json={'domains':[self.domain('A',-20)]})
        x=explain(r)
        self.assertEqual(x['evidence_checks']['auxiliary']['consumption']['status'],'all_comparable_domains_decreased')
        self.assertFalse(x['isolation_related_candidate'])
    def test_cross_quarter_value_not_used(self):
        r=self.row(observation_consumption_json={'domains':[self.domain('A',-20,'no_exact_quarter_match')]})
        c=explain(r)['evidence_checks']['auxiliary']['consumption']
        self.assertEqual(c['status'],'unavailable')
        self.assertIsNone(c['domains'][0]['change_pct'])
    def test_partial_market_coverage_explicit(self):
        r=self.row(observation_consumption_json={'domains':[self.domain('A',-10),self.domain('B',None)]})
        c=explain(r)['evidence_checks']['auxiliary']['consumption']
        self.assertFalse(c['coverage_complete'])
        self.assertEqual(c['available_domain_count'],1)

if __name__=='__main__':unittest.main()

from pathlib import Path
from contextlib import closing
import sqlite3,json,unittest,sys,copy
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import consumption_enrichment as e
import evidence_context as w
import youth_detail as y
def payload():
    return {'adm_cd':'x','date':'2025-10-01','age_band':'30s','model_version':'m','observation_window':{'obs':'2025Q3'},'domains':[{'domain':'A','market_period':'2025Q3','market_alignment':'exact_full_quarter','market_comparison':None,'market_change_pct':None,'market_baseline_n':None,'card_observation_months':['2025-07','2025-08','2025-09'],'card_previous_window_months':['2025-04','2025-05','2025-06'],'card_monthly_context':[],'card_available_months':[],'card_full_window_available':False,'card_previous_window_available':False,'card_window_change_pct':None,'card_window_comparison':{'change_pct':None,'reason':'missing'},'card_comparison_reason':'missing','interpretation':'not_same_residents'}]}
def fixture():
    c=sqlite3.connect(':memory:');c.executescript(e.SCHEMA+'''
    CREATE TABLE a3_run(source TEXT,period TEXT,fingerprint TEXT,version TEXT);
    CREATE TABLE a23_observation_context(adm_cd TEXT,date TEXT,age_band TEXT,model_version TEXT,payload_json TEXT);
    CREATE TABLE a2_age_detection(adm_cd TEXT,date TEXT,age_band TEXT,model_version TEXT,result_json TEXT);
    ''')
    c.execute("INSERT INTO a2_age_detection VALUES('x','2025-10-01','30s','m','original_detection')")
    e.upsert_context(c,payload(),set());e.finish_anchors(c,{});c.commit();return c
class EvidenceChecks(unittest.TestCase):
    def test_late_market_fill_audited_and_idempotent(self):
        with closing(fixture()) as c,c:
            c.execute("INSERT INTO a3_run VALUES('market','2025Q3','sha','v')")
            anchors,added=e.anchor_changes(c);p=payload();p['domains'][0].update(market_comparison={'change_pct':-10},market_change_pct=-10,market_baseline_n=3)
            self.assertEqual(e.upsert_context(c,p,added),(0,1));e.finish_anchors(c,anchors)
            self.assertEqual(e.upsert_context(c,p,e.anchor_changes(c)[1]),(0,0))
            self.assertEqual(c.execute('SELECT COUNT(*) FROM a23_context_revision').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT result_json FROM a2_age_detection').fetchone()[0],'original_detection')
    def test_late_card_fill(self):
        with closing(fixture()) as c,c:
            c.execute("INSERT INTO a3_run VALUES('card','2025-09','sha','v')")
            anchors,added=e.anchor_changes(c);p=payload();p['domains'][0]['card_monthly_context']=[{'period':'2025-09','count':10}];p['domains'][0]['card_available_months']=['2025-09']
            self.assertEqual(e.upsert_context(c,p,added),(0,1))
    def test_existing_source_revision_blocked(self):
        with closing(fixture()) as c,c:
            c.execute("INSERT INTO a3_run VALUES('card','2025-09','old','v')");e.finish_anchors(c,e.anchor_changes(c)[0]);c.execute("UPDATE a3_run SET fingerprint='changed'")
            with self.assertRaisesRegex(ValueError,'revision'):e.anchor_changes(c)
    def test_existing_source_removal_blocked(self):
        with closing(fixture()) as c,c:
            c.execute("INSERT INTO a3_run VALUES('card','2025-09','old','v')");e.finish_anchors(c,e.anchor_changes(c)[0]);c.execute('DELETE FROM a3_run')
            with self.assertRaisesRegex(ValueError,'removal'):e.anchor_changes(c)
    def test_behavior_key_change_not_enrichment(self):
        p=payload();p['observation_window']={'changed':'2026'};self.assertFalse(e.allowed(payload(),p,{('market','2025Q3')}))
    def test_known_market_value_change_blocked(self):
        a=payload();a['domains'][0]['market_comparison']={'change_pct':-10};b=copy.deepcopy(a);b['domains'][0]['market_comparison']['change_pct']=-20
        self.assertFalse(e.allowed(a,b,{('market','2025Q3')}))
    def test_known_card_cell_change_blocked(self):
        a=payload();a['domains'][0]['card_monthly_context']=[{'period':'2025-07','count':10}];b=copy.deepcopy(a);b['domains'][0]['card_monthly_context'][0]['count']=99
        self.assertFalse(e.allowed(a,b,{('card','2025-09')}))
    def test_unrelated_new_period_does_not_allow_change(self):
        p=payload();p['domains'][0]['market_change_pct']=-10;self.assertFalse(e.allowed(payload(),p,{('market','2026Q1')}))
    def test_atomic_enrichment_rollback(self):
        with closing(fixture()) as c:
            try:
                with c:
                    p=payload();p['domains'][0].update(market_comparison={'change_pct':-10},market_change_pct=-10);e.upsert_context(c,p,{('market','2025Q3')})
                    q=copy.deepcopy(p);q['observation_window']={'wrong':True};e.upsert_context(c,q,{('market','2025Q3')})
            except ValueError:pass
            self.assertEqual(json.loads(c.execute('SELECT payload_json FROM a23_observation_context').fetchone()[0]),payload())
            self.assertEqual(c.execute('SELECT COUNT(*) FROM a23_context_revision').fetchone()[0],0)
    def test_unknown_response_excluded_not_zero(self):
        v=y.binary(pd.Series([1,7,9,None]),range(1,9),[7,8],[9]);self.assertEqual(v.iloc[0],0);self.assertEqual(v.iloc[1],1);self.assertTrue(v.iloc[2:].isna().all())
    def test_none_support_and_blank(self):
        v=y.support(pd.DataFrame({'a':[4,None,1],'b':[None,None,2]}),['a','b']);self.assertEqual(v.iloc[0],1);self.assertTrue(pd.isna(v.iloc[1]));self.assertEqual(v.iloc[2],0)
    def test_support_contradiction_blocked(self):
        with self.assertRaisesRegex(ValueError,'Contradictory'):y.support(pd.DataFrame({'a':[4],'b':[1]}),['a','b'])
    def test_weather_month_key_and_snow_dash(self):
        self.assertEqual(w.key('2025. 07'),'2025-07');self.assertEqual(w.num('-',snow=True),0);self.assertIsNone(w.num('-'))
    def test_publication_unknown_not_fabricated(self):
        with sqlite3.connect(':memory:') as c:
            c.executescript('CREATE TABLE ctx_survey_source(source_id TEXT,year INTEGER,available_from TEXT); CREATE TABLE ctx_publication_registry(kind TEXT,period TEXT,available_from TEXT,proof TEXT);')
            self.assertEqual(w.publications(c,{'evidence_publication':{'records':[{'kind':'card','period':'2026-01','available_from':None}]}}),0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM ctx_publication_registry').fetchone()[0],0)
    def test_publication_before_observation_end_blocked(self):
        with sqlite3.connect(':memory:') as c:
            c.executescript('CREATE TABLE ctx_survey_source(source_id TEXT,year INTEGER,available_from TEXT); CREATE TABLE ctx_publication_registry(kind TEXT,period TEXT,available_from TEXT,proof TEXT);')
            with self.assertRaisesRegex(ValueError,'precedes'):w.publications(c,{'evidence_publication':{'records':[{'kind':'card','period':'2026-01','available_from':'2026-01-01','proof':'test_only'}]}})
if __name__=='__main__':unittest.main()

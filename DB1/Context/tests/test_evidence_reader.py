from pathlib import Path
import sys,sqlite3,unittest,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import evidence_reader as r
def fixture():
    c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
    c.executescript('''CREATE TABLE a2_age_source(date TEXT); CREATE TABLE ctx_publication_registry(kind TEXT,period TEXT,available_from TEXT,proof TEXT,registered_at TEXT);
    CREATE TABLE ctx_weather_window(date TEXT,payload_json TEXT);
    CREATE TABLE v_a123_age_evidence_context(adm_cd TEXT,age_band TEXT,source_label_date TEXT,model_version TEXT,observation_weather_json TEXT,youth_detail_json TEXT);
    CREATE TABLE ctx_evidence_guide(source_id TEXT,age_scope TEXT,topic TEXT,payload_json TEXT);''')
    c.executemany('INSERT INTO a2_age_source VALUES(?)',[('2025-09-01',),('2025-10-01',)])
    return c
def pub(c,kind,period,day):c.execute('INSERT INTO ctx_publication_registry VALUES(?,?,?,?,?)',(kind,period,day,'synthetic_test_proof','2026-01-01'))
class ReaderChecks(unittest.TestCase):
    def test_all_prior_core_releases_required(self):
        with fixture() as c:
            for k in ['telecom','interest']:pub(c,k,'2025-10','2025-11-01')
            self.assertFalse(r.core_available(c,'2025-10-01','2025-12-31'))
            for k in ['telecom','interest']:pub(c,k,'2025-09','2025-10-01')
            self.assertTrue(r.core_available(c,'2025-10-01','2025-12-31'))
    def test_future_publication_not_available(self):
        with fixture() as c:
            pub(c,'card','2025-10','2026-02-01');self.assertFalse(r.known(c,'card','2025-10','2025-12-31'))
    def test_partial_quality_and_age_not_applicable(self):
        with fixture() as c:
            c.execute("INSERT INTO v_a123_age_evidence_context VALUES('x','40s','2025-10-01','m',NULL,'[]')")
            item={'adm_cd':'x','age_band':'40s','source_label_date':'2025-10-01','model_version':'m','assessment_status':'partially_assessed','communication_signal':0,'mobility_signal':None,'same_period_sns_json':None,'observation_consumption_json':None}
            out=r.enrich(c,item)
            self.assertEqual(out['evidence_status']['communication']['status'],'available');self.assertEqual(out['evidence_status']['mobility']['status'],'unavailable')
            self.assertEqual(out['evidence_status']['youth']['status'],'not_applicable');self.assertIsNone(out['mobility_signal'])
    def test_noncanonical_cutoff_rejected(self):
        with fixture() as c:
            with self.assertRaises(ValueError):r.enrich(c,{},'20251231')
    def tracking_fixture(self,c):
        c.execute('CREATE TABLE ctx_weather_window_tracking(date TEXT,payload_json TEXT)')
        p={'quality_status':'available','observation_months':['2025-07','2025-08','2025-09'],
           'baseline_candidates':[{'months':['2022-07','2022-08','2022-09']}],
           'metrics':{'rainfall_mm':{'current':100,'baseline_mean':50}},'not_detection_input':True}
        c.execute('INSERT INTO ctx_weather_window_tracking VALUES(?,?)',('2025-10-01',json.dumps(p)))
        for kind in ['telecom','interest']:
            for period in ['2025-09','2025-10']:pub(c,kind,period,'2025-11-01')
        return {'adm_cd':'x','age_band':'40s','source_label_date':'2025-10-01','model_version':'m','assessment_status':'assessed','communication_signal':1,'mobility_signal':0,'same_period_sns_json':None,'observation_consumption_json':None}
    def test_weather_comparison_baseline_publications_required(self):
        with fixture() as c:
            item=self.tracking_fixture(c)
            for period in ['2025-07','2025-08','2025-09']:pub(c,'weather',period,'2025-11-01')
            result=r.enrich(c,item,'2025-12-31')
            self.assertEqual(result['weather_tracking']['metrics'],{})
            self.assertEqual(result['evidence_status']['weather_tracking']['status'],'unavailable')
    def test_weather_comparison_visible_when_all_releases_known(self):
        with fixture() as c:
            item=self.tracking_fixture(c)
            for period in ['2025-07','2025-08','2025-09','2022-07','2022-08','2022-09']:pub(c,'weather',period,'2025-11-01')
            result=r.enrich(c,item,'2025-12-31')
            self.assertEqual(result['weather_tracking']['metrics']['rainfall_mm']['current'],100)
    def test_retrospective_weather_comparison_visible(self):
        with fixture() as c:
            item=self.tracking_fixture(c)
            self.assertEqual(r.enrich(c,item)['weather_tracking']['quality_status'],'available')
if __name__=='__main__':unittest.main()

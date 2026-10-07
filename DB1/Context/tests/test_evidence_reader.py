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
if __name__=='__main__':unittest.main()

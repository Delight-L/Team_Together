from pathlib import Path
import unittest
import pandas as pd
from backend.db.age_analysis_repository import SOURCE, prepare_age_analysis, detection_for

class AgeDashboardLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame=pd.read_csv(SOURCE,dtype={'행정동코드':str})
        cls.data=prepare_age_analysis(cls.frame,str(SOURCE))

    def test_exact_reviewed_cases_and_months_no_metric_double_count(self):
        self.assertEqual(self.data['signalCounts'],{'2025-07':0,'2025-08':0,'2025-09':0,'2025-10':9,'2025-11':1,'2025-12':0})
        expected={(str(r['행정동코드']),r['date'][:7],r['age_band']) for r in self.frame.to_dict('records') if r['communication_signal'] is True}
        actual={(r['code'],r['month'],r['age_band']) for r in self.data['alerts']}
        self.assertEqual(actual,expected);self.assertEqual(len(actual),10)
        self.assertEqual(len(self.data['signals']),20)
        self.assertEqual(len({r['case_id'] for r in self.data['signals']}),10)
        self.assertTrue(all(not c['mobility_signal'] for c in self.data['alerts']))

    def test_exact_age_match_and_sex_pooled_no_legacy_december_signal(self):
        base=dict(city='강남구',code='1123059',month='2025-10',age='30대',sex='남성')
        a=detection_for(base,self.data);b=detection_for({**base,'sex':'여성'},self.data)
        self.assertEqual(a['case_id'],b['case_id']);self.assertTrue(a['communication_signal'])
        self.assertFalse(detection_for({**base,'age':'20대'},self.data)['any_signal'])
        self.assertIsNone(detection_for({**base,'age':'10대'},self.data))
        self.assertFalse(detection_for({**base,'code':'1123058','month':'2025-12'},self.data)['any_signal'])
        self.assertIsNotNone(detection_for({**base,'age':'60대 이상'},self.data))

    def test_current_map_name_retains_the_same_source_code(self):
        r=detection_for(dict(city='강남구',code='1123074',month='2025-10',age='40대'),self.data)
        self.assertTrue(r['any_signal']);self.assertEqual(r['district'],'개포3동')
        self.assertEqual(r['source_district'],'일원2동')

    def test_scores_follow_the_triggering_path(self):
        case=detection_for(dict(city='강남구',code='1123065',month='2025-11',age='30대'),self.data)
        rows=[r for r in self.data['signals'] if r['case_id']==case['case_id']]
        self.assertEqual(len(rows),2)
        for r in rows:
            self.assertEqual(r['detection_path'],'공통 변화 조정')
            self.assertEqual(r['risk_robust_z'],r['local_rz'])

    def test_duplicate_versions_are_rejected(self):
        duplicate=pd.concat([self.frame,self.frame.iloc[[0]]],ignore_index=True)
        with self.assertRaises(ValueError):prepare_age_analysis(duplicate,'fixture')

    def test_input_is_unchanged_and_null_domain_preserved(self):
        frame=self.frame.copy();original=frame.copy(deep=True)
        prepare_age_analysis(frame,'fixture')
        pd.testing.assert_frame_equal(frame,original)
        frame.loc[0,'mobility_signal']=None
        data=prepare_age_analysis(frame,'fixture')
        self.assertIsNone(data['ageDetections'][0]['mobility_signal'])
        self.assertTrue(all(not r['has_enough_history'] for r in data['assessment'][:4] if r['metric'].endswith('move_count')))

    def test_matches_restored_authoritative_database(self):
        import sqlite3
        source=Path(r'C:\Users\user\Desktop\Team_Together\DB1\outputs\db1.sqlite')
        if not source.is_file():
            self.skipTest('Optional local authoritative DB1 database is not available')
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as c:
            expected=set(c.execute('SELECT adm_cd,substr(date,1,7),age_band FROM a2_age_detection WHERE communication_signal=1 OR mobility_signal=1'))
        actual={(r['code'],r['month'],r['age_band']) for r in self.data['alerts']}
        self.assertEqual(actual,expected)

    def test_dashboard_does_not_mix_legacy_district_alerts(self):
        from unittest.mock import patch
        from backend.db import analysis_repository as repository
        legacy={'alerts':[{'month':'2025-12'}],'assessment':[{'legacy':True}],
                'regionalStructures':[{'dong_name':'신사동'}]}
        with patch.object(repository,'load_district_analysis2_data',return_value=legacy):
            result=repository.load_analysis2_data()
        self.assertEqual(result['signalCounts']['2025-12'],0)
        self.assertEqual(len(result['alerts']),10)
        self.assertEqual(result['regionalStructures'],legacy['regionalStructures'])

    def test_group_detail_selects_age_detection_instead_of_district_flag(self):
        from unittest.mock import patch, MagicMock
        from backend.db.group_repository import regional_context
        engine=MagicMock()
        execute=engine.connect.return_value.__enter__.return_value.execute
        execute.return_value.mappings.return_value.first.side_effect=[None,{'mobility_signal':True,'payload':{}}]
        context=dict(city='강남구',code='1123058',month='2025-12',age='30대',sex='남성')
        with patch('backend.db.analysis_repository.get_engine',return_value=engine):
            result=regional_context(context)
        self.assertFalse(result['detection']['any_signal'])
        self.assertEqual(result['scope'],'dong_age')
        self.assertTrue(result['districtDetection']['mobility_signal'])

    def test_http_dashboard_returns_exact_age_cases(self):
        import http.client,json,threading
        from http.server import ThreadingHTTPServer
        from unittest.mock import patch
        from backend.api.server import Handler
        from backend.db import analysis_repository as repository
        with patch.object(repository,'load_district_analysis2_data',return_value={'regionalStructures':[]}):
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
                conn.request('POST','/api/login',json.dumps({'id':'gangnam01','password':'demo1234'}),{'Content-Type':'application/json'})
                response=conn.getresponse();self.assertEqual(response.status,200)
                cookie=response.getheader('Set-Cookie').split(';')[0];response.read()
                conn.request('GET','/api/dashboard',headers={'Cookie':cookie})
                response=conn.getresponse();self.assertEqual(response.status,200)
                result=json.loads(response.read());conn.close()
                self.assertEqual(result['analysisScope'],'dong_age')
                self.assertEqual(result['signalCounts']['2025-10'],9)
                self.assertEqual(result['signalCounts']['2025-11'],1)
                self.assertEqual(result['signalCounts']['2025-12'],0)
                self.assertEqual(len(result['alerts']),10)
            finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()

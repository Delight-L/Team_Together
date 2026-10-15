import json
import unittest
from unittest.mock import patch
from backend.api.common import Request, region_context, evidence_for
from backend.api import routes_work
from backend.db import mission_store, experience_store
from backend.db.age_analysis_repository import load_age_analysis
from backend.db.tests.work_db import temporary_work_store
from backend.agents.report_writer import generate_draft

class AgeCaseScopeTest(unittest.TestCase):
    def setUp(self):
        self.user={'id':'age-scope-test','org':'강남구','admin':False}
        self.params={'city':'강남구','district':'일원본동','month':'2025-10'}
        self.data=load_age_analysis() | {'geometry':{'강남구':{'units':[{'n':'일원본동'}]}}}
    def context(self,age=None):
        params=self.params | ({'age':age} if age else {})
        return region_context(Request(params,self.user,''),self.data)
    def test_scope_filters_four_metrics_and_preserves_all_age_view(self):
        self.assertEqual(len(evidence_for(self.data,self.context())),20)
        rows=evidence_for(self.data,self.context('40대'))
        self.assertEqual(len(rows),4)
        self.assertEqual({r['age_label'] for r in rows},{'40대'})
        self.assertEqual(sum(r['is_risk_signal'] for r in rows),2)
        with self.assertRaises(ValueError):self.context('10대')
    def test_legacy_identity_unchanged_and_ages_are_separate(self):
        legacy=mission_store.identity(self.context())
        self.assertEqual(json.loads(legacy),['age-scope-test','강남구','일원본동','2025-10'])
        self.assertEqual(len({legacy,mission_store.identity(self.context('30대')),mission_store.identity(self.context('40대'))}),3)
    def test_workflow_list_draft_and_report_stay_age_scoped(self):
        ctx=self.context('40대');legacy=self.context();ctx30=self.context('30대')
        rows=evidence_for(self.data,ctx)
        with temporary_work_store():
            for c in [legacy,ctx]:
                mission_store.save_event(c,0,{'run_id':'test','evidence':evidence_for(self.data,c),'source_note':'DB1'})
            self.assertEqual(routes_work.load_workflow(ctx30),{})
            mission_store.save_event(ctx,1,{'confirmed':True})
            mission_store.save_event(ctx,2,{'service_key':'test','note':'확인용','decision':'보류'})
            workflow=routes_work.load_workflow(ctx)
            self.assertEqual(len(workflow['analysis_evidence']),4)
            draft=generate_draft(ctx,workflow)
            self.assertEqual(draft['context']['age'],'40대')
            self.assertIn('40대',draft['title'])
            self.assertNotIn('30대',draft['situation'])
            self.assertIn('40대',routes_work.report_filename(ctx))
            listing=routes_work.missions(Request({},self.user,''))['items']
            self.assertEqual(len(listing),2)
            self.assertEqual({item.get('age','') for item in listing},{'','40대'})
    def test_shared_followup_records_and_history_are_separate_by_age(self):
        ctx=self.context('40대');legacy=self.context();ctx30=self.context('30대')
        with temporary_work_store():
            experience_store.save(ctx,{'version':0,'note':'40대 메모'})
            self.assertEqual(experience_store.load(ctx)['note'],'40대 메모')
            self.assertEqual(experience_store.load(ctx30)['version'],0)
            self.assertEqual(experience_store.load(legacy)['version'],0)
            self.assertEqual(len(experience_store.regional_history(ctx)),1)
            self.assertEqual(experience_store.regional_history(ctx30),[])
    def test_work_context_carries_age_to_evidence(self):
        request=Request(self.params|{'age':'40대'},self.user,'')
        with patch.object(routes_work,'dashboard_data',return_value=self.data):
            ctx,data,rows=routes_work.work_context(request)
        self.assertEqual(ctx['age'],'40대')
        self.assertEqual(len(rows),4)

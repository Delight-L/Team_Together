import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from dashboard import missions
from dashboard.workflow import match_services, explain_question
from dashboard.report import build_report
from io import BytesIO
from docx import Document

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(missions,"STORE",Path(self.temp.name)/"records.db")
        self.patch.start()
        self.request={"user":{"id":"gangnam01"},"city":"강남구","district":"역삼1동","month":"2025-12"}
        self.evidence=[{"행정동명":"역삼1동","기준연월":"2025-12","metric_label":"유동인구 감소","is_risk_signal":True,"explanation":"유동인구 감소 확인 후보","change_pct":-20.0,"relative_change_pp":-10.0,"risk_robust_z":3.0,"context_note":"","cluster_profile":""}]
    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()
    def start(self):
        missions.save_event(self.request,0,{"run_id":"run-1","evidence":self.evidence})
        missions.save_event(self.request,1,{"confirmed":True})
    def review(self,decision="적합"):
        return missions.save_event(self.request,2,{"service_key":"service-1","name":"교류 지원","decision":decision,"note":"지표와 대상 조건 확인"})
    def test_review_then_report_completes(self):
        self.start()
        reviewed=self.review("보류")
        self.assertFalse(reviewed["workflow_complete"])
        context={k:self.request[k] for k in ["city","district","month"]}
        document=build_report(context,self.evidence,"담당자","복지정책과","검토 결과 보고","run-1",workflow=reviewed)
        text="\n".join(p.text for p in Document(BytesIO(document)).paragraphs)
        self.assertIn("사업 매칭 검토",text)
        self.assertIn("보류",text)
        self.assertNotIn("연결 승인",text)
        record={"sha256":hashlib.sha256(document).hexdigest(),"filename":"report.docx","author":"담당자","department":"복지정책과","opinion":"보고","confirmed":True,"review_id":missions.review_revision(reviewed),"_document":document}
        done=missions.save_event(self.request,3,record)
        self.assertTrue(done["workflow_complete"])
        self.assertEqual(missions.load_report(self.request),document)
        self.assertEqual(done["done"],list(range(4)))
        for change in [{"district":"역삼2동"},{"month":"2026-01"},{"user":{"id":"admin"}},{"workflow_mode":"demo"}]:
            self.assertNotIn(missions.identity(dict(self.request,**change)),missions.load_all())
        with self.assertRaises(ValueError): self.review()
    def test_invalid_order_and_stale_report(self):
        with self.assertRaises(ValueError): missions.save_event(self.request,3,{})
        self.start()
        reviewed=self.review()
        old_revision=missions.review_revision(reviewed)
        self.review("부적합")
        record={"sha256":"fake","filename":"report.docx","author":"a","department":"b","opinion":"c","confirmed":True,"review_id":old_revision}
        with self.assertRaises(ValueError): missions.save_event(self.request,3,record)
        record["review_id"]=missions.review_revision(missions.load_all()[missions.identity(self.request)])
        with self.assertRaises(ValueError): missions.save_event(self.request,3,record)
        self.assertFalse(missions.load_all()[missions.identity(self.request)]["workflow_complete"])
    def test_old_workflow_migrates_without_losing_review(self):
        old={"workflow_version":2,"done":[0,1,2,3],"reviews":[{"note":"기존 검토"}],"connections":[{"note":"이전 승인"}],"questions":[]}
        migrated=missions.normalize(old)
        self.assertEqual(migrated["done"],[0,1,2])
        self.assertFalse(migrated["workflow_complete"])
        self.assertEqual(migrated["reviews"][0]["note"],"기존 검토")
        self.assertIn("legacy_connections",migrated)
    def test_matching_uses_signal_evidence(self):
        services=[{"source_id":"local","region_id":"gangnam","external_id":"1","name":"사회참여 교류 사업","target_text":"주민"},{"source_id":"local","region_id":"gangnam","external_id":"2","name":"보육료","target_text":"아동"}]
        matches=match_services("강남구",self.evidence,services)
        self.assertTrue(matches[0]["reasons"])
        self.assertFalse(matches[1]["reasons"])
        no_signal=[dict(self.evidence[0],is_risk_signal=False)]
        self.assertFalse(match_services("강남구",no_signal,services)[0]["reasons"])
        with patch.dict("os.environ", {"GEMINI_API_KEY":"","GEMINI_MODEL":""}):
            answer,mode=explain_question("왜 후보인가요?",self.evidence)
        self.assertIn("유동인구 감소 확인 후보",answer)
        self.assertIn("원인을 확정하지",answer)
    def test_legacy_completion_is_not_new_completion(self):
        with missions.connection() as db:
            db.execute("INSERT INTO missions VALUES (?,?)",(missions.identity(self.request),'{"done":[0,1,2,3,4],"card_earned":true}'))
        item=missions.load_all()[missions.identity(self.request)]
        self.assertEqual(item["done"],[])
        self.assertIn("legacy",item)

if __name__ == "__main__": unittest.main()

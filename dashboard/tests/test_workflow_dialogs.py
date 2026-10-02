import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from dashboard import missions

class DialogTests(unittest.TestCase):
    def test_review_then_report_through_forms(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(missions,"STORE",Path(folder)/"workflow.db"):
            request={"user":{"id":"gangnam01"},"city":"강남구","district":"역삼1동","month":"2025-12"}
            evidence=[{"행정동명":"역삼1동","기준연월":"2025-12","metric_label":"유동인구 감소","is_risk_signal":True,"explanation":"유동인구 감소 확인 후보","change_pct":-20.0,"relative_change_pp":-10.0,"risk_robust_z":3.0,"context_note":"","cluster_profile":""}]
            missions.save_event(request,0,{"run_id":"test-run","evidence":evidence})
            missions.save_event(request,1,{"confirmed":True})
            source = """
import streamlit as st
import dashboard.service_dialog as dialog
request={"user":{"id":"gangnam01"},"city":"강남구","district":"역삼1동","month":"2025-12"}
service={"source_id":"test","region_id":"gangnam","external_id":"test-1","name":"테스트 전용 교류사업","target_text":"주민","source_url":"https://example.org/test"}
dialog.match_services=lambda *args: [{"service":service,"key":"test-service","reasons":[{"category":"교류","metrics":["유동인구 감소"],"service_terms":["교류"]}],"score":1}]
dialog.candidates_dialog(request)
"""
            app=AppTest.from_string(source,default_timeout=20).run()
            self.assertFalse(app.exception)
            app.checkbox[0].check()
            app.text_area[0].input("분석과 사업 조건 확인")
            next(b for b in app.button if b.label=="사업 매칭 검토 저장").click().run()
            self.assertFalse(app.exception)
            self.assertIn(2,missions.load_all()[missions.identity(request)]["done"])
            item=missions.load_all()[missions.identity(request)]
            self.assertIn(2,item["done"])
            self.assertFalse(item["workflow_complete"])
            report_source = """
from dashboard.operations import report_dialog
request={"user":{"id":"gangnam01"},"city":"강남구","district":"역삼1동","month":"2025-12"}
report_dialog(request,{})
"""
            app=AppTest.from_string(report_source,default_timeout=20).run()
            self.assertFalse(app.exception)
            app.text_area[0].input("분석과 사업 검토 결과 최종 보고").run()
            next(b for b in app.button if b.label=="양식에 맞춰 보고서 생성").click().run()
            self.assertFalse(app.exception)
            app.checkbox[0].check().run()
            next(b for b in app.button if b.label=="최종 보고서 저장 및 업무 완료").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(missions.load_all()[missions.identity(request)]["workflow_complete"])
            self.assertTrue(missions.load_report(request))

if __name__ == "__main__": unittest.main()

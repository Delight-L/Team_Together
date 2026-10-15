"""메뉴 간 저장·선택·보고서 연결. 실제 운영 DB와 외부 AI를 사용하지 않습니다."""
import unittest
from io import BytesIO
from zipfile import ZipFile
from unittest.mock import patch
from backend.api import routes_work
from backend.api.common import Request
from backend.db.tests.work_db import temporary_work_store


class MenuReviewFlowTest(unittest.TestCase):
    def setUp(self):
        store = temporary_work_store()
        store.start(); self.addCleanup(store.stop)
        self.addCleanup(store.engine.dispose)
        self.context = {'city': '강남구', 'district': '삼성1동', 'month': '2025-12'}
        self.user = {'id': 'menu-flow-test', 'org': '강남구', 'admin': False}
        rows = [dict(self.context, 행정동명='삼성1동', 기준연월='2025-12', metric_label=label,
                     is_risk_signal=True, has_enough_history=True, change_pct=change)
                for label, change in [('평일 이동', -6.1), ('휴일 이동', -7.4)]]
        data = {'months': ['2025-12'], 'geometry': {'강남구': {'units': [{'n': '삼성1동'}]}},
                'assessment': rows, 'runId': 'test-v1', 'source': '검증 분석'}
        data_patch = patch.object(routes_work, 'dashboard_data', return_value=data)
        data_patch.start(); self.addCleanup(data_patch.stop)
        matches = [{'key': key, 'service': {'name': name}, 'reasons': []} for key, name in [('a', '교류 지원'), ('b', '상담 지원')]]
        match_patch = patch('backend.agents.service_matching.match_services', return_value=matches)
        match_patch.start(); self.addCleanup(match_patch.stop)
        self.call('workflow_start'); self.call('workflow_confirm')
        self.call('workflow_review', serviceKey='a', decision='보류', note='접수 확인 필요', checks={'residency': True}, need='관계·사회참여')
        self.call('workflow_review', serviceKey='b', decision='적합', note='상담 조건 확인')

    def call(self, route, **extra):
        return getattr(routes_work, route)(Request(self.context | extra, self.user, None))

    def test_conditions_saved_and_invalid_check_rejected(self):
        saved = self.call('workflow')['reviews'][0]
        self.assertEqual(saved['checks'], {'residency': True})
        self.assertEqual(saved['need'], '관계·사회참여')
        for checks in ({'unknown': True}, {'residency': 'yes'}, []):
            with self.assertRaises(ValueError):
                self.call('workflow_review', serviceKey='a', decision='보류', note='검토', checks=checks)

    def test_selected_sources_and_work_record_reach_saved_word(self):
        self.call('experience_save', version=0, note='행사 일정 확인 필요', followup='기관에 문의 예정', assignee='검증 담당자', due='2026-10-20')
        selection = {'metrics': ['평일 이동'], 'services': ['a'], 'include_note': True, 'include_followup': True}
        content = self.call('report_content', selection=selection)
        self.assertIn('행사 일정 확인 필요', content['situation'])
        self.assertIn('6.1%', content['situation']); self.assertNotIn('7.4%', content['situation'])
        self.assertIn('교류 지원', content['proposal']); self.assertNotIn('상담 지원', content['proposal'])
        self.assertIn('거주 확인', content['proposal']); self.assertIn('대상 미확인', content['proposal'])
        self.assertIn('2026-10-20', content['next_steps'])
        preview = self.call('report_preview', content=content, review_id=content['review_id'], author='검증 담당자', department='검증 부서')
        self.call('report_save', token=preview['token'], confirmed=True)
        document = self.call('saved_report').payload
        with ZipFile(BytesIO(document)) as package:
            xml = package.read('word/document.xml').decode()
        self.assertIn('행사 일정 확인 필요', xml); self.assertIn('기관에 문의 예정', xml)

    def test_updated_work_record_requires_new_draft(self):
        self.call('experience_save', version=0, note='처음 의견')
        content = self.call('report_content', selection={'metrics': [], 'services': ['a'], 'include_note': True})
        self.call('experience_save', version=1, note='변경한 의견')
        with self.assertRaisesRegex(ValueError, '업무 기록이 변경'):
            self.call('report_preview', content=content, review_id=content['review_id'], author='담당자', department='부서')

    def test_unstored_source_is_not_accepted(self):
        for selection in ({'metrics': ['없는 지표']}, {'services': ['other-region-service']}, {'include_note': 'yes'}):
            with self.assertRaises(ValueError): self.call('report_content', selection=selection)


if __name__ == '__main__': unittest.main()

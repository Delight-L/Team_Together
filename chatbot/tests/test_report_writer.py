import unittest
from io import BytesIO
from zipfile import ZipFile
from lxml import etree
from agents.report_writer import generate_draft, validate_content, report_reply, evidence_sentence
from shared.report import build_report, TEMPLATE, NS


class ReportWriterTest(unittest.TestCase):
    context = {'city': '강남구', 'district': '삼성1동', 'month': '2025-12'}

    def workflow(self):
        return {'done': [0, 1, 2], 'analysis_evidence': [
            {'is_risk_signal': True, 'metric_label': '전화 연락', 'change_pct': -12.3,
             'explanation': '삼성1동 전화 연락 · Analysis2 탐지 결과'}],
            'reviews': [
                {'service_key': 'a', 'name': '교류 지원', 'decision': '적합', 'note': '교류 지원 검토'},
                {'service_key': 'b', 'name': '상담 지원', 'decision': '보류', 'note': '자격 확인 필요'},
                {'service_key': 'c', 'name': '방문 지원', 'decision': '부적합', 'note': '대상 불일치'}]}

    def test_grounding_and_decisions(self):
        content = generate_draft(self.context, self.workflow())
        self.assertIn('전화 연락: 전월보다 12.3% 감소', content['situation'])
        self.assertNotIn('Analysis2', content['situation'])
        self.assertIn('상담 지원: 운영 조건 확인 후 재검토', content['proposal'])
        self.assertIn('방문 지원: 현재 연계 제안에서 제외', content['proposal'])
        self.assertEqual(validate_content(content)['title'], content['title'])

    def test_missing_change_is_not_described_as_zero(self):
        for change in (None, float('nan'), float('inf')):
            sentence = evidence_sentence({'metric_label': '평일 이동', 'change_pct': change})
            self.assertIn('계산할 수 없어', sentence)
            self.assertNotIn('0.0%', sentence)
        self.assertIn('3.0% 증가', evidence_sentence({'change_pct': 3}))
        self.assertIn('전월과 같은 수준', evidence_sentence({'change_pct': 0}))

    def test_legacy_source_is_readable_in_downloaded_report(self):
        workflow = self.workflow()
        document = build_report(self.context, workflow['analysis_evidence'], '담당자',
                                '복지정책과', '기관 확인', 'DB1 · Analysis2', workflow)
        with ZipFile(BytesIO(document)) as package:
            root = etree.fromstring(package.read('word/document.xml'))
            text = ''.join(root.xpath('//w:t/text()', namespaces=NS))
        self.assertNotIn('Analysis2', text)
        self.assertNotIn('DB1', text)
        self.assertIn('동별 통화·문자·이동 분석 자료', text)

    def test_latest_review_overrides_previous_decision(self):
        workflow = self.workflow()
        workflow['reviews'].append({'service_key': 'a', 'name': '교류 지원', 'decision': '부적합', 'note': '재검토 결과'})
        draft = generate_draft(self.context, workflow)
        self.assertNotIn('연계 가능성 검토 제안', draft['proposal'])
        self.assertIn('추가 확인', draft['summary'])

    def test_missing_evidence_and_completed_workflow(self):
        for workflow in ({}, self.workflow() | {'analysis_evidence': []}):
            with self.assertRaises(ValueError):
                generate_draft(self.context, workflow)
        self.assertNotIn('reportDraft', report_reply(self.context, {})['actions'][0])
        self.assertIn('title', generate_draft(self.context, self.workflow() | {'workflow_complete': True}))

    def test_long_notes_are_omitted_without_partial_sentences(self):
        workflow = self.workflow()
        workflow['reviews'][0]['note'] = '부적합 조건 확인 ' * 400
        draft = generate_draft(self.context, workflow)
        self.assertIn('원문 확인', draft['proposal'])
        self.assertNotIn('교류 지원:', draft['proposal'])
        validate_content(draft)
        with self.assertRaises(ValueError):
            validate_content(draft | {'title': 'x' * 81})

    def test_template_package_preservation_and_no_sample_text(self):
        workflow = self.workflow()
        content = generate_draft(self.context, workflow)
        document = build_report(self.context, workflow['analysis_evidence'], '홍길동',
            '복지정책과', content['next_steps'], '검증용 분석 출처', workflow, content, '02-1234-5678')
        with ZipFile(TEMPLATE) as original, ZipFile(BytesIO(document)) as generated:
            self.assertEqual(original.namelist(), generated.namelist())
            for name in original.namelist():
                if name != 'word/document.xml':
                    self.assertEqual(original.read(name), generated.read(name), name)
            xml = etree.fromstring(generated.read('word/document.xml'))
            text = ''.join(xml.xpath('//w:t/text()', namespaces=NS))
            for label in ['검토 요지', '지역 현황', '복지서비스 연계·추진 제안', '향후 조치', '홍길동', '02-1234-5678', '검증용 분석 출처']:
                self.assertIn(label, text)
            for label in ['온도탑', '2023', 'HY견고딕 17', '2133-0000', '문단 좌우 여백']:
                self.assertNotIn(label, text)
            self.assertEqual(len(xml.xpath('//w:sectPr', namespaces=NS)), 1)


if __name__ == '__main__':
    unittest.main()

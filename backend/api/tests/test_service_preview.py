"""사업 사전 조회는 업무 단계를 변경하지 않고 저장 당시 근거를 우선합니다."""
import unittest
from unittest.mock import patch

from backend.api import routes_work


class ServicePreviewTest(unittest.TestCase):
    def test_preview_before_confirmation_does_not_save_workflow(self):
        self.check_preview({}, ['current'])

    def test_existing_work_uses_saved_evidence(self):
        self.check_preview({'done': [0], 'analysis_evidence': ['saved']}, ['saved'])

    def check_preview(self, workflow, expected):
        with patch.object(routes_work, 'work_context', return_value=({'city': '강남구'}, {}, ['current'])), \
             patch.object(routes_work, 'load_workflow', return_value=workflow), \
             patch.object(routes_work.service_matching, 'match_services', return_value=['candidate']) as match, \
             patch.object(routes_work.service_matching, 'reference_matches', return_value=[]) as reference, \
             patch.object(routes_work.mission_store, 'save_event') as save:
            result = routes_work.services(object())
        self.assertEqual(result['matches'], ['candidate'])
        match.assert_called_once_with('강남구', expected)
        reference.assert_called_once_with('강남구', expected)
        save.assert_not_called()

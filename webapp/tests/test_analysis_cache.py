"""분석 결과 캐시가 요청 간 데이터와 파일 변경을 분리하는지 검사합니다."""
import unittest
from unittest.mock import patch

from db import analysis_repository as repository


class AnalysisCacheTest(unittest.TestCase):
    def tearDown(self):
        repository._load_analysis2_data.cache_clear()

    def test_requests_receive_independent_data_and_file_changes_reload(self):
        repository._load_analysis2_data.cache_clear()
        with patch.object(repository, 'monthly_upload', wraps=repository.monthly_upload) as read:
            first = repository.load_analysis2_data()
            first['assessment'][0]['행정동명'] = '수정된 요청'
            first['geometry'] = {}
            second = repository.load_analysis2_data()
            self.assertNotEqual(second['assessment'][0]['행정동명'], '수정된 요청')
            self.assertNotIn('geometry', second)
            self.assertEqual(read.call_count, 1)
            repository._load_analysis2_data(
                str(repository.DETECTION_FILE.resolve()),
                repository.DETECTION_FILE.stat().st_mtime_ns + 1,
            )
            self.assertEqual(read.call_count, 2)

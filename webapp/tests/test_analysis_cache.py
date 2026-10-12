"""분석 결과 캐시가 요청 간 데이터와 파일 변경을 분리하는지 검사합니다."""
import unittest
from unittest.mock import patch

from db import analysis_repository as repository


class AnalysisCacheTest(unittest.TestCase):
    def tearDown(self):
        repository._load_analysis2_data.cache_clear()

    def test_requests_receive_independent_data_and_file_changes_reload(self):
        repository._load_analysis2_data.cache_clear()
        with patch.dict('os.environ', {'WELFIND_DATA_SOURCE': 'csv'}), patch.object(repository, 'monthly_upload', wraps=repository.monthly_upload) as read:
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


class DataSourceTest(unittest.TestCase):
    """DB 우선 읽기와 CSV 대체 규칙을 실제 DB 접속 없이 검사합니다."""
    DB = {'DB_HOST': 'db.example', 'DB_NAME': 'team_together', 'DB_USER': 'reader', 'DB_PASSWORD': 'x'}
    FAKE = {'source': 'DB1 · Analysis2', 'assessment': [{'행정동명': '신사동'}]}

    def test_auto_prefers_db_and_returns_copies(self):
        with patch.dict('os.environ', dict(self.DB, WELFIND_DATA_SOURCE='auto')), \
                patch.object(repository, '_latest_detection_run', return_value='run-1'), \
                patch.object(repository, '_load_analysis2_from_db', return_value=self.FAKE):
            first = repository.load_analysis2_data()
            first['assessment'][0]['행정동명'] = '수정'
            self.assertEqual(repository.load_analysis2_data()['assessment'][0]['행정동명'], '신사동')
            self.assertEqual(first['source'], 'DB1 · Analysis2')

    def test_auto_falls_back_to_csv_when_db_fails(self):
        if not repository.DETECTION_FILE.exists():
            self.skipTest('로컬 Analysis2 CSV가 없습니다.')
        with patch.dict('os.environ', dict(self.DB, WELFIND_DATA_SOURCE='auto')), \
                patch.object(repository, '_latest_detection_run', side_effect=OSError('timeout')), \
                self.assertLogs(repository.LOGGER, 'WARNING'):
            self.assertEqual(repository.load_analysis2_data()['source'], '동별 통화·문자·이동 분석 자료 (저장된 파일)')

    def test_db_mode_does_not_hide_db_errors(self):
        with patch.dict('os.environ', dict(self.DB, WELFIND_DATA_SOURCE='db')), \
                patch.object(repository, '_latest_detection_run', side_effect=OSError('timeout')):
            with self.assertRaises(OSError):
                repository.load_analysis2_data()

    def test_invalid_mode_is_rejected(self):
        with patch.dict('os.environ', {'WELFIND_DATA_SOURCE': 'cloud'}):
            with self.assertRaises(ValueError):
                repository.load_analysis2_data()

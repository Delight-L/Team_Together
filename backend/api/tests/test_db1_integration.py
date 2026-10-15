"""DB1 delivery and administrator publication regressions; no production writes."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
from sqlalchemy import create_engine, event, text

from backend.db import analysis_repository as repository
from backend.db.db1_snapshot import prepare_snapshot

ROOT = Path(__file__).resolve().parents[3]


class DeliveryTests(unittest.TestCase):
    def test_delivery_keeps_history_and_approved_cluster_assignments(self):
        monthly, structure = prepare_snapshot()
        self.assertEqual(len(monthly['data']), 770)
        self.assertEqual(monthly['data'].date.min(), pd.Timestamp('2023-02-01'))
        self.assertEqual(len(structure['context']), 22)
        self.assertTrue(structure['context'].elderly_living_alone_rate_65plus.between(0, 1).all())
        self.assertTrue(structure['context'].elder_available_from.isna().all())
        legacy = pd.read_csv(ROOT / 'pipelines/db1/Analysis2/data/reference/gangnam_analysis1_final_region_typology_2025H2.csv', dtype={'adm_cd': str})
        actual = structure['context'].set_index('adm_cd').cluster.sort_index()
        pd.testing.assert_series_equal(actual, legacy.set_index('adm_cd').cluster.sort_index(), check_names=False)
        self.assertNotIn('disability_ratio', structure['context'])

    def test_adapter_uses_correct_denominator_and_matches_delivered_model(self):
        base, context, report = repository.preprocess_raw_dir(ROOT / 'pipelines/preprocessing/regional_types/raw_data')
        reference = pd.read_csv(ROOT / 'pipelines/db1/Analysis1/data/reference/reference_pca_input_2025H2.csv', dtype={'adm_cd': str})
        self.assertEqual(report['denominator_reference'], '2025Q4')
        self.assertEqual(report['rule_version'], 'analysis1_2025H2_elder_v2')
        for column in ('elderly_living_alone_rate_65plus', 'flow_per_point', 'livelihood_recipient_ratio'):
            pd.testing.assert_series_equal(base.set_index('adm_cd')[column].sort_index(), reference.set_index('adm_cd')[column].sort_index())
        self.assertEqual(len(context), 22)

    def test_month_keys_and_flags_are_validated_without_mutating_input(self):
        data = pd.read_csv(repository.DETECTION_FILE)
        before = data.copy(deep=True)
        repository.prepare_analysis2(data, 'fixture')
        pd.testing.assert_frame_equal(data, before)
        duplicate = pd.concat([data, data.iloc[[0]].assign(date='2025-07-15')], ignore_index=True)
        with self.assertRaisesRegex(ValueError, '중복'):
            repository.prepare_analysis2(duplicate, 'fixture')
        data.loc[0, 'any_signal'] = not bool(data.loc[0, 'communication_signal'] or data.loc[0, 'mobility_signal'])
        with self.assertRaisesRegex(ValueError, '일치'):
            repository.prepare_analysis2(data, 'fixture')

    def test_lfs_pointer_is_rejected_before_sqlite_open(self):
        path = ROOT / 'pipelines/db1/outputs/db1.sqlite'
        with path.open('rb') as handle:
            is_pointer = handle.read(7) == b'version'
        if is_pointer:
            with self.assertRaisesRegex(ValueError, 'Git LFS'):
                prepare_snapshot(path)

    def test_new_sqlite_bootstrap_is_idempotent_and_can_be_imported(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'db1.sqlite'
            command = [sys.executable, '-X', 'utf8', str(ROOT / 'pipelines/db1/Analysis1/update_worker.py'),
                       '--config', str(ROOT / 'pipelines/db1/config/db1_config.json'), '--db', str(path),
                       '--period', '2025H2', '--bootstrap']
            for saved in (True, False):
                result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=120)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['saved'], saved)
            monthly, structure = prepare_snapshot(path)
            self.assertEqual(len(structure['context']), 22)
            self.assertEqual(len(monthly['data']), 770)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        @event.listens_for(self.engine, 'connect')
        def attach(connection, record):
            connection.execute("ATTACH DATABASE ':memory:' AS db1")
        self.patch = patch.object(repository, 'get_engine', return_value=self.engine)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.engine.dispose()
        repository._load_analysis2_from_db.cache_clear()
        repository._RUN_CHECK.update(at=0.0, run_id=None)

    def test_admin_publication_is_visible_and_retains_previous_months(self):
        monthly, structure = prepare_snapshot()
        first = repository.publish(monthly, 'test-admin')
        repository.publish(structure, 'test-admin')
        from backend.db.analysis_views import install_views
        with self.engine.begin() as connection:
            install_views(connection)
        # Explicitly synthetic next-month fixture, not observed 2026 data.
        next_month = monthly['data'][monthly['data'].date.eq(pd.Timestamp('2025-12-01'))].copy()
        next_month['date'] = pd.Timestamp('2026-01-01')
        second = repository.publish(repository.prepare_analysis2(next_month, 'SYNTHETIC-next-month'), 'test-admin')
        data = repository._load_analysis2_from_db(second)
        self.assertEqual(len(data['assessment']), 792 * 4)
        self.assertEqual(data['runs'][0]['period'], '2023-02 ~ 2026-01')
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT COUNT(*) FROM db1.analysis2_detections WHERE run_id=:run'), {'run': first}).scalar(), 770)
            self.assertEqual(connection.execute(text('SELECT COUNT(*) FROM db1.analysis1_region_typology')).scalar(), 22)
        self.assertEqual(len(repository.load_dashboard_data()['activity']), 3)

    def test_failure_rolls_back_service_rows_and_audit_together(self):
        monthly, _ = prepare_snapshot()
        repository.publish(monthly, 'test-admin')
        with patch.object(repository, 'append_frame', side_effect=RuntimeError('audit failed')):
            with self.assertRaisesRegex(RuntimeError, 'audit failed'):
                repository.publish(monthly, 'test-admin')
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT COUNT(DISTINCT run_id) FROM db1.analysis2_detections')).scalar(), 1)
            self.assertEqual(connection.execute(text('SELECT COUNT(*) FROM db1.demo_ingestions')).scalar(), 1)


if __name__ == '__main__':
    unittest.main()

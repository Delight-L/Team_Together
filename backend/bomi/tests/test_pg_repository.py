"""PostgreSQL 구현: Db1Repository 계약을 지키는지(test_db1_repository의 mixin), 게시(run·활성 포인터)가 안전한지.

실제 PostgreSQL이 필요합니다. 기본은 pgserver(내장 PostgreSQL)로 임시 서버를 띄우고,
환경변수 TEST_DB1_PG_URL(예: postgresql+psycopg2://user:pw@host/db)을 주면 그 서버를 씁니다.
둘 다 없으면 이 파일의 테스트는 건너뜁니다.
"""
import gc
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.bomi.adapters import v16
from backend.bomi.tests import test_db1_repository as contract
from backend.bomi.tests.db1_fixture import build, build_pipeline_style
from backend.chatbot.tests.ai_config import ai_key

from chatbot_agent.pg_repository import PostgresDb1Repository  # noqa: E402
from data_pipeline import publish_postgres  # noqa: E402
from data_pipeline.publish_postgres import activate, publish  # noqa: E402

ENGINE = None
SERVER = None


def setUpModule():
    global ENGINE, SERVER
    import sqlalchemy
    url = os.getenv('TEST_DB1_PG_URL')
    if not url:
        try:
            import pgserver
        except ImportError:
            raise unittest.SkipTest('PostgreSQL이 없어 건너뜀(pip install pgserver 또는 TEST_DB1_PG_URL)')
        SERVER = pgserver.get_server(tempfile.mkdtemp(prefix='db1_pg_test_'), cleanup_mode='stop')
        url = SERVER.get_uri().replace('postgresql://', 'postgresql+psycopg2://', 1)
    ENGINE = sqlalchemy.create_engine(url)


def tearDownModule():
    if ENGINE is not None:
        ENGINE.dispose()
    if SERVER is not None:
        SERVER.cleanup()


def reset_schemas():
    with ENGINE.begin() as conn:
        conn.exec_driver_sql('DROP SCHEMA IF EXISTS db1_v16 CASCADE')
        conn.exec_driver_sql('DROP SCHEMA IF EXISTS db1 CASCADE')


def scalar(sql, params=()):
    with ENGINE.connect() as conn:
        return conn.exec_driver_sql(sql, params).scalar()


def mutate(path, statements):
    """SQLite 공개본을 고쳐 내용(해시)이 다른 새 공개본을 만듭니다."""
    with sqlite3.connect(path) as writer:
        for sql, params in statements:
            writer.execute(sql, params)
    return path


def next_month(path):
    """2025-11 행(삼성1동)을 추가한 새 공개본."""
    row = {'date': '2025-11-01', '행정동': '삼성1동', '행정동코드': '1123051', 'any_signal': False,
           'communication_signal': False, 'mobility_signal': False, 'combined_signal': False, 'signal_type': ''}
    blob = json.dumps(row, ensure_ascii=False)
    return mutate(path, [("INSERT INTO a2_detection VALUES('2025-11-01','1123051',?,'v1')", (blob,)),
                         ("INSERT INTO a2_feature VALUES('2025-11-01','1123051',?)", (blob,))])


# ── Db1Repository 계약 테스트 묶음을 PostgreSQL 구현으로 실행 ───────────────────
class PostgresFixtureMixin:
    """합성 SQLite(db1_fixture)를 한 번 게시하고 그 활성 run을 읽는 저장소를 준비합니다."""

    @classmethod
    def setUpClass(cls):
        reset_schemas()
        cls.dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.path = build(Path(cls.dir.name) / 'fixture_db1.sqlite')
        publish(cls.path, ENGINE)
        cls.repo = PostgresDb1Repository(ENGINE)

    @classmethod
    def tearDownClass(cls):
        cls.repo.close()
        gc.collect()
        cls.dir.cleanup()

    def make_repo(self):
        return PostgresDb1Repository(ENGINE)


class PostgresContractTest(PostgresFixtureMixin, contract.ContractCases, unittest.TestCase):
    def test_missing_published_run_has_no_data(self):
        reset_schemas()
        publish_postgres_schema_only()
        self.assertFalse(PostgresDb1Repository(ENGINE).has_data())
        publish(self.path, ENGINE)  # 다른 테스트가 쓰는 자료를 복구


def publish_postgres_schema_only():
    with ENGINE.begin() as conn:
        publish_postgres._ensure_schema(conn)


class PostgresEquivalenceTest(PostgresFixtureMixin, contract.EquivalenceCases, unittest.TestCase):
    def test_unsorted_dates_fall_back_to_the_mask_path(self):
        """정렬 순서와 시간 순서가 다른 날짜 형식이 섞여 있어도 결과는 같아야 합니다."""
        import pandas.testing as pdt
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            path = build(Path(directory) / 'mixed.sqlite')
            with sqlite3.connect(path) as writer:  # 한 행의 날짜 표기를 바꿔 문자열 순서와 시간 순서를 어긋나게 함
                row = writer.execute("SELECT result_json FROM a2_detection WHERE date='2025-09-01' AND adm_cd='1123051'").fetchone()
                payload = json.loads(row[0])
                payload['date'] = '2025/09/01'
                writer.execute("UPDATE a2_detection SET result_json=? WHERE date='2025-09-01' AND adm_cd='1123051'",
                               (json.dumps(payload, ensure_ascii=False),))
            reset_schemas()
            publish(path, ENGINE)
            repo = PostgresDb1Repository(ENGINE)
            try:
                for start, end in [(None, None), ('2025-08', '2025-09'), ('2025-09', '2025-10')]:
                    with self.subTest(start=start, end=end):
                        pdt.assert_frame_equal(repo.activity('삼성1동', start, end),
                                               self.reference(repo, '삼성1동', start, end, None))
            finally:
                repo.close()
                gc.collect()
        reset_schemas()
        publish(self.path, ENGINE)  # 다른 테스트가 쓰는 자료를 복구
        type(self).repo.close()
        type(self).repo = PostgresDb1Repository(ENGINE)

    def test_index_reads_only_the_requested_dongs(self):
        repo = PostgresDb1Repository(ENGINE)
        repo.activity('삼성1동', '2025-07', '2025-10', '20s')
        parts = next(iter(repo._index_cache.values()))['parts']
        self.assertEqual(list(parts), ['삼성1동'])
        repo.close()


class PostgresCacheTest(PostgresFixtureMixin, contract.CacheCases, unittest.TestCase):
    pass


class PostgresEfficiencyTest(unittest.TestCase):
    def setUp(self):
        reset_schemas()
        self.dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.dir.cleanup)
        self.addCleanup(gc.collect)
        publish(build(Path(self.dir.name) / 'fixture_db1.sqlite'), ENGINE)

    def test_one_connection_and_each_table_read_once(self):
        statements = []
        from sqlalchemy import event
        listener = lambda conn, cursor, statement, *a: statements.append(statement)  # noqa: E731
        event.listen(ENGINE, 'before_cursor_execute', listener)
        try:
            repo = PostgresDb1Repository(ENGINE)
            for _ in range(5):
                repo.activity('삼성1동', '2025-07', '2025-10')
                repo.activity('역삼1동', '2025-07', '2025-10', '60plus')
            repo.close()
        finally:
            event.remove(ENGINE, 'before_cursor_execute', listener)
        reads = [s for s in statements if 'FROM a2_detection' in s or 'FROM a2_age_detection' in s]
        self.assertEqual(len(reads), 2)


# ── 게시(run·활성 포인터) ────────────────────────────────────────────────
class PublishTest(unittest.TestCase):
    def setUp(self):
        reset_schemas()
        self.dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.dir.cleanup)
        self.addCleanup(gc.collect)
        self.first = build(Path(self.dir.name) / 'first.sqlite')

    def copy(self, name):
        target = Path(self.dir.name) / name
        shutil.copyfile(self.first, target)
        return target

    def active(self):
        return scalar('SELECT run_id FROM db1.v16_active_run WHERE id=1')

    def test_publish_creates_run_views_and_activates(self):
        result = publish(self.first, ENGINE)
        self.assertEqual(result['status'], 'published')
        self.assertEqual(self.active(), result['run_id'])
        self.assertTrue(result['run_id'].startswith('db1-202510-'))
        self.assertEqual(result['tables']['a2_detection'], 12)
        self.assertEqual(scalar('SELECT status FROM db1.v16_run WHERE run_id=%s', (result['run_id'],)), 'ready')
        # 뷰는 SQLite 테이블과 같은 이름·열이며 고정한 run이 없으면 아무것도 보이지 않습니다.
        self.assertEqual(scalar('SELECT COUNT(*) FROM db1_v16.a2_detection'), 0)

    def test_republishing_same_file_is_idempotent(self):
        first = publish(self.first, ENGINE)
        again = publish(self.first, ENGINE)
        self.assertEqual(again['status'], 'already_published')
        self.assertEqual(again['run_id'], first['run_id'])
        self.assertEqual(scalar('SELECT COUNT(*) FROM db1.v16_a2_detection'), 12)  # 중복 적재 없음
        self.assertEqual(scalar('SELECT COUNT(*) FROM db1.v16_run'), 1)

    def test_force_republish_rebuilds_the_active_run(self):
        first = publish(self.first, ENGINE)
        again = publish(self.first, ENGINE, force=True)
        self.assertEqual(again['status'], 'published')
        self.assertEqual(self.active(), first['run_id'])
        self.assertEqual(scalar('SELECT COUNT(*) FROM db1.v16_a2_detection'), 12)

    def test_new_run_switches_the_pointer_and_pinned_repo_keeps_old_data(self):
        old = publish(self.first, ENGINE)
        pinned = PostgresDb1Repository(ENGINE)
        self.assertEqual(pinned.available_period(), ('2025-07', '2025-10'))  # 여기서 old run으로 고정
        newer = publish(next_month(self.copy('second.sqlite')), ENGINE)
        self.assertNotEqual(newer['run_id'], old['run_id'])
        self.assertEqual(self.active(), newer['run_id'])
        # 한 요청(고정된 저장소)은 계속 이전 run을 읽고, 새 저장소는 새 run을 읽습니다.
        self.assertEqual(len(pinned.activity('삼성1동', '2025-07', '2025-12')), 4)
        pinned.close()
        fresh = PostgresDb1Repository(ENGINE)
        self.assertEqual(fresh.available_period(), ('2025-07', '2025-11'))
        self.assertEqual(len(fresh.activity('삼성1동', '2025-07', '2025-12')), 5)
        self.assertEqual(fresh.pipeline_status()['active_snapshot_id'], newer['run_id'])
        fresh.close()

    def test_failed_publish_keeps_the_previous_run(self):
        good = publish(self.first, ENGINE)
        broken = self.copy('broken.sqlite')
        mutate(broken, [('DROP TABLE a3b_feature', ())])
        with self.assertRaises(ValueError):
            publish(broken, ENGINE)
        notready = next_month(self.copy('notready.sqlite'))
        mutate(notready, [("UPDATE pipeline_state SET payload_json='{\"status\": \"running\"}'", ())])
        with self.assertRaises(ValueError):
            publish(notready, ENGINE)
        self.assertEqual(self.active(), good['run_id'])
        self.assertEqual(scalar('SELECT COUNT(*) FROM db1.v16_run'), 1)

    def test_row_count_mismatch_rolls_back_everything(self):
        good = publish(self.first, ENGINE)
        second = next_month(self.copy('second.sqlite'))
        real_copy = publish_postgres._copy

        def short(conn, source, table, columns, run_id):
            return real_copy(conn, source, table, columns, run_id) - (1 if table == 'a2_detection' else 0)
        with patch.object(publish_postgres, '_copy', short), self.assertRaises(ValueError):
            publish(second, ENGINE)
        self.assertEqual(self.active(), good['run_id'])
        self.assertEqual(scalar('SELECT COUNT(*) FROM db1.v16_run'), 1)  # 새 run 행도 남지 않음
        self.assertEqual(scalar('SELECT COUNT(*) FROM db1.v16_a2_detection'), 12)

    def test_prune_keeps_the_active_and_recent_runs(self):
        runs = []
        path = self.first
        for index in range(4):
            if index:
                path = next_month(self.copy(f'run{index}.sqlite'))
                mutate(path, [("UPDATE a2_detection SET model_version=? WHERE date='2025-07-01'", (f'v{index}',))])
            runs.append(publish(path, ENGINE, keep=2)['run_id'])
        remaining = [row[0] for row in ENGINE.connect().exec_driver_sql('SELECT run_id FROM db1.v16_run')]
        self.assertEqual(len(remaining), 2)
        self.assertIn(runs[-1], remaining)
        self.assertEqual(self.active(), runs[-1])
        self.assertEqual(scalar('SELECT COUNT(DISTINCT run_id) FROM db1.v16_a2_detection'), 2)

    def test_activate_rolls_back_to_a_previous_run(self):
        old = publish(self.first, ENGINE)
        newer = publish(next_month(self.copy('second.sqlite')), ENGINE)
        self.assertEqual(self.active(), newer['run_id'])
        self.assertEqual(activate(ENGINE, old['run_id'])['status'], 'activated')
        repo = PostgresDb1Repository(ENGINE)
        self.assertEqual(repo.available_period(), ('2025-07', '2025-10'))  # 되돌린 run을 읽음
        repo.close()
        with self.assertRaises(ValueError):
            activate(ENGINE, 'no-such-run')
        with ENGINE.begin() as conn:
            conn.exec_driver_sql("UPDATE db1.v16_run SET status='loading' WHERE run_id=%s", (newer['run_id'],))
        with self.assertRaises(ValueError):  # 갱신이 끝나지 않은 run은 활성으로 못 바꿈
            activate(ENGINE, newer['run_id'])
        self.assertEqual(self.active(), old['run_id'])

    def test_new_column_in_a_later_publish_is_added(self):
        publish(self.first, ENGINE)
        wider = next_month(self.copy('wider.sqlite'))
        mutate(wider, [('ALTER TABLE a3a_quarter_summary ADD COLUMN note TEXT', ())])
        publish(wider, ENGINE)
        columns = {row[0] for row in ENGINE.connect().exec_driver_sql(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='db1_v16' AND table_name='a3a_quarter_summary'")}
        self.assertIn('note', columns)
        repo = PostgresDb1Repository(ENGINE)
        self.assertEqual(repo.consumption_period(), ('2025-04', '2025-09'))
        repo.close()

    def test_loading_run_is_refused_and_missing_run_has_no_data(self):
        self.assertFalse(self._has_data_without_publish())
        run = publish(self.first, ENGINE)['run_id']
        with ENGINE.begin() as conn:
            conn.exec_driver_sql("UPDATE db1.v16_run SET status='loading' WHERE run_id=%s", (run,))
        repo = PostgresDb1Repository(ENGINE)
        self.assertFalse(repo.has_data())
        with self.assertRaises(ValueError):
            repo.available_period()
        repo.close()

    @staticmethod
    def _has_data_without_publish():
        publish_postgres_schema_only()
        return PostgresDb1Repository(ENGINE).has_data()

    def test_closing_the_repository_resets_session_settings(self):
        publish(self.first, ENGINE)
        repo = PostgresDb1Repository(ENGINE)
        repo.districts()
        repo.close()
        with ENGINE.connect() as conn:  # 풀로 돌아간 연결을 다시 받아도 설정이 남아 있지 않아야 합니다
            self.assertNotIn('db1_v16', conn.exec_driver_sql('SHOW search_path').scalar())
            self.assertIn(conn.exec_driver_sql("SELECT current_setting('db1.v16_run_id', true)").scalar(), (None, ''))

    def test_pipeline_status_matches_the_source_file(self):
        """게시본의 상태가 원천 SQLite의 pipeline_state와 같은 값을 내는지."""
        publish(self.first, ENGINE)
        with sqlite3.connect(self.first) as source:
            expected = json.loads(source.execute('SELECT payload_json FROM pipeline_state').fetchone()[0])
        repo = PostgresDb1Repository(ENGINE)
        status = repo.pipeline_status()
        repo.close()
        self.assertEqual(status['status'], expected['status'])
        self.assertEqual(status['waiting_for'], expected.get('waiting_for'))
        self.assertEqual(status['detection_rows'], 12)
        self.assertEqual(status['history_end'][:7], '2025-10')


# ── 파이프라인 산출물(pipeline_state·ctx_weather 없음) 게시 ────────────────────
class PipelineOutputPublishTest(unittest.TestCase):
    """`pipelines/db1`이 내놓는 모양의 파일을 고치지 않고 게시할 수 있는지."""

    def setUp(self):
        reset_schemas()
        self.dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.dir.cleanup)
        self.addCleanup(gc.collect)
        self.classic = build(Path(self.dir.name) / 'classic.sqlite')
        self.output = build_pipeline_style(Path(self.dir.name) / 'output.sqlite')

    def weather(self, run_path, date='2025-10-01'):
        publish(run_path, ENGINE)
        repo = PostgresDb1Repository(ENGINE)
        try:
            return repo.supplements(['삼성1동'], [date])['weather']
        finally:
            repo.close()

    def test_output_without_the_two_tables_is_published_and_noted(self):
        with sqlite3.connect(self.output) as check:
            names = {row[0] for row in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertFalse({'pipeline_state', 'ctx_weather'} & names)  # 정말 없는 모양인지
        result = publish(self.output, ENGINE)
        self.assertEqual(result['status'], 'published')
        self.assertEqual(set(result['compat']), {'pipeline_state', 'ctx_weather'})
        self.assertEqual(result['tables']['ctx_weather'], 4)

    def test_status_comes_from_the_run(self):
        publish(self.output, ENGINE)
        repo = PostgresDb1Repository(ENGINE)
        status = repo.pipeline_status()
        repo.close()
        self.assertEqual(status['status'], 'ready')
        self.assertEqual(status['history_rows'], 12)
        self.assertIsNone(status.get('waiting_for'))  # 산출물에는 대기 월 정보가 없음

    def test_converted_weather_matches_the_worker_format(self):
        converted = self.weather(self.output)
        reset_schemas()
        original = self.weather(self.classic)
        for payload in (*converted.values(), *original.values()):
            payload.pop('converted_from', None)
        self.assertEqual(converted, original)
        item = next(iter(converted.values()))
        self.assertEqual([m['month'] for m in item['observation_month_weather']], ['2025-07', '2025-08', '2025-09'])
        self.assertEqual(item['observation_month_weather'][0]['rainfall_mm'], 293.9)
        self.assertIn('label_weather', item)

    def test_months_missing_from_the_source_are_marked_missing(self):
        converted = self.weather(self.output, '2025-07-01')  # 관측기간 04~06 중 일부는 있고 일부는 없음
        months = {m['month']: m for m in next(iter(converted.values()))['observation_month_weather']}
        self.assertEqual(set(months), {'2025-04', '2025-05', '2025-06'})
        self.assertNotIn('status', months['2025-04'])

    def test_missing_weather_sources_give_an_empty_table_not_a_failure(self):
        mutate(self.output, [('DROP TABLE ctx_weather_month', ()), ('DROP TABLE ctx_weather_window', ())])
        result = publish(self.output, ENGINE)
        self.assertIn('원천 없음', result['compat']['ctx_weather'])
        repo = PostgresDb1Repository(ENGINE)
        self.assertEqual(repo.supplements(['삼성1동'], ['2025-10-01'])['weather'], {})
        repo.close()

    def test_a_real_not_ready_state_is_still_refused(self):
        mutate(self.classic, [("UPDATE pipeline_state SET payload_json='{\"status\": \"running\"}'", ())])
        with self.assertRaises(ValueError):
            publish(self.classic, ENGINE)

    def test_a_later_classic_publish_replaces_the_synthesized_view(self):
        publish(self.output, ENGINE)
        publish(next_month(self.classic), ENGINE)
        repo = PostgresDb1Repository(ENGINE)
        self.assertEqual(repo.pipeline_status()['waiting_for'], {'month': '2025-11'})  # 실제 pipeline_state 표를 읽음
        repo.close()


# ── 어댑터: 환경변수로 저장소를 고르고, 답변이 같아야 함 ──────────────────────
class AdapterTest(unittest.TestCase):
    CONTEXT = {'city': '강남구', 'district': '', 'month': '2025-10'}

    def setUp(self):
        reset_schemas()
        self.dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.dir.cleanup)
        self.addCleanup(gc.collect)
        self.sqlite = build(Path(self.dir.name) / 'fixture_db1.sqlite')
        key = ai_key('')
        key.start()
        self.addCleanup(key.stop)

    def ask(self, question):
        with patch.dict(os.environ, {}), patch.object(v16, '_engine', return_value=ENGINE):
            os.environ.pop('DB1_REPOSITORY', None)  # 값이 없으면 PostgreSQL
            return v16.reply(question, [], self.CONTEXT, use_ai=False)

    def test_reply_comes_from_the_published_run(self):
        publish(self.sqlite, ENGINE)
        for question in ('2025년 10월 이상신호 탐지 지역 알려줘', '삼성1동은 왜 신호가 났어?', '이상신호 기준은?'):
            with self.subTest(question=question):
                self.assertTrue(self.ask(question)['answer'])
        self.assertIn('삼성1동', self.ask('삼성1동은 왜 신호가 났어?')['answer'])

    def test_reply_from_a_published_pipeline_output_equals_the_classic_reply(self):
        publish(self.sqlite, ENGINE)
        questions = ('2025년 10월 이상신호 탐지 지역 알려줘', '삼성1동 지역 배경 정보 보여줘')
        classic = [self.ask(question) for question in questions]
        reset_schemas()
        publish(build_pipeline_style(Path(self.dir.name) / 'output.sqlite'), ENGINE)
        for question, expected in zip(questions, classic):
            with self.subTest(question=question):
                self.assertEqual(self.ask(question), expected)

    def test_removed_sqlite_setting_is_an_error_not_a_silent_fallback(self):
        publish(self.sqlite, ENGINE)
        with patch.dict(os.environ, {'DB1_REPOSITORY': 'sqlite'}), patch.object(v16, '_engine', return_value=ENGINE):
            with self.assertRaises(ValueError):
                v16._repository()
            with self.assertLogs(v16.LOGGER, level=logging.WARNING):
                self.assertFalse(v16.data_ready())  # 서버가 죽지 않고 «자료 없음»으로 대체 답변
        for value in ('POSTGRESQL', 'Postgres', 'postgres'):  # 같은 뜻의 값은 그대로 허용
            with patch.dict(os.environ, {'DB1_REPOSITORY': value}), patch.object(v16, '_engine', return_value=ENGINE):
                self.assertTrue(v16.data_ready())

    def test_unknown_backend_name_is_an_error_not_a_silent_fallback(self):
        with patch.dict(os.environ, {'DB1_REPOSITORY': 'postgress'}):  # 오타
            with self.assertRaises(ValueError):
                v16._repository()
            with self.assertLogs(v16.LOGGER, level=logging.WARNING):
                self.assertFalse(v16.data_ready())

    def test_data_ready_follows_the_selected_backend(self):
        with patch.object(v16, '_engine', return_value=ENGINE):
            publish_postgres_schema_only()
            self.assertFalse(v16.data_ready())   # 활성 run이 아직 없음
            publish(self.sqlite, ENGINE)
            self.assertTrue(v16.data_ready())

    def test_connection_failure_is_logged_as_an_outage_not_as_missing_data(self):
        import sqlalchemy
        dead = sqlalchemy.create_engine('postgresql+psycopg2://nobody:x@127.0.0.1:1/none',
                                        connect_args={'connect_timeout': 1})
        with patch.object(v16, '_engine', return_value=dead), \
                self.assertLogs(v16.LOGGER, level=logging.ERROR) as logs:
            self.assertFalse(v16.data_ready())
        self.assertIn('연결하지 못했습니다', logs.output[0])
        dead.dispose()


if __name__ == '__main__':
    unittest.main()

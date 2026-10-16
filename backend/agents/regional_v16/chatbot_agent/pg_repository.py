"""Db1Repository의 PostgreSQL 구현. SQLite 구현과 같은 조회 로직(SqlDb1Repository)을 그대로 씁니다.

읽는 곳은 스키마 db1_v16의 뷰입니다. 뷰는 SQLite 테이블과 같은 이름·열이고, 연결에 고정한 run의 행만 보여 줍니다
(data_pipeline/publish_postgres.py가 만듭니다). 그래서 조회 SQL은 한 줄도 바뀌지 않습니다.

요청 하나가 읽는 run은 연결을 열 때 한 번 정해 고정합니다. 도중에 새 run이 공개돼도 한 답변 안에서 버전이 섞이지 않습니다.
"""
from __future__ import annotations

import json

from .repository import SqlDb1Repository

SCHEMA = 'db1'
VIEW_SCHEMA = 'db1_v16'


class _PgConnection:
    """`?` 자리표시자를 쓰는 조회 SQL을 PostgreSQL 드라이버 형식(%s)으로 바꿔 실행하는 얇은 연결."""

    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=()):
        return self.connection.exec_driver_sql(sql.replace('?', '%s'), tuple(params))


class PostgresDb1Repository(SqlDb1Repository):
    """DB1 근거를 PostgreSQL의 고정된 run에서 읽기 전용으로 조회합니다.

    engine: SQLAlchemy 엔진(예: backend.db.connection.engine). run_id를 주지 않으면 활성 run을 씁니다.
    """
    _immutable = True  # run의 자료는 공개 후 바뀌지 않으므로 고정한 뒤에는 다시 확인하지 않습니다

    def __init__(self, engine, run_id: str | None = None):
        super().__init__()
        self.engine = engine
        self.run_id = run_id  # 고정된 run(연결을 연 뒤 확정)
        # The shared service DB can expose the existing dashboard tables
        # directly instead of db1_v16's optional run views. In that case the
        # agent reads the dashboard-compatible source without touching API,
        # screen, or shared database code.
        with engine.connect() as connection:
            has_v16 = connection.exec_driver_sql(
                "SELECT to_regclass('db1.v16_active_run')"
            ).scalar() is not None
        self._dashboard = None
        if not has_v16:
            from .dashboard_repository import DashboardDb1Repository
            self._dashboard = DashboardDb1Repository(engine)

    def _connect(self):
        connection = self.engine.connect().execution_options(isolation_level='AUTOCOMMIT')
        try:
            run_id = self.run_id or connection.exec_driver_sql(
                f'SELECT run_id FROM {SCHEMA}.v16_active_run WHERE id=1').scalar()
            if not run_id:
                raise FileNotFoundError('공개된 DB1 자료가 없습니다. publish를 먼저 실행하세요.')
            status = connection.exec_driver_sql(f'SELECT status FROM {SCHEMA}.v16_run WHERE run_id=%s', (run_id,)).scalar()
            if status != 'ready':
                raise ValueError('데이터 갱신이 완료되지 않았습니다. 처리 상태를 확인해 주세요.')
            connection.exec_driver_sql("SELECT set_config('db1.v16_run_id', %s, false)", (run_id,))
            connection.exec_driver_sql(f'SET search_path TO {VIEW_SCHEMA}')
        except BaseException:
            connection.close()
            raise
        self.run_id = run_id
        return _PgConnection(connection), run_id

    def _close_connection(self, con):
        raw = con.connection
        try:  # 풀로 돌아가는 연결에 이 설정이 남지 않게 합니다
            raw.exec_driver_sql('RESET search_path')
            raw.exec_driver_sql('RESET db1.v16_run_id')
        except Exception:
            raw.invalidate()
        finally:
            raw.close()

    def _table_names(self, con):
        return {row[0] for row in con.execute(
            'SELECT table_name FROM information_schema.tables WHERE table_schema=?', (VIEW_SCHEMA,))}

    def has_data(self):
        """활성 run이 있고 갱신이 끝났는지. DB에 연결하지 못하면 예외가 납니다(자료 없음과 장애를 구분)."""
        if self._dashboard is not None:
            return self._dashboard.has_data()
        with self.engine.connect() as connection:
            run_id = self.run_id or connection.exec_driver_sql(f'SELECT run_id FROM {SCHEMA}.v16_active_run WHERE id=1').scalar()
            if not run_id:
                return False
            return connection.exec_driver_sql(
                f'SELECT status FROM {SCHEMA}.v16_run WHERE run_id=%s', (run_id,)).scalar() == 'ready'

    def pipeline_status(self):
        """SQLite 구현(`data_pipeline.runner.status`)과 같은 항목."""
        if self._dashboard is not None:
            return self._dashboard.pipeline_status()
        with self.connection() as c:
            row = c.execute('SELECT payload_json FROM pipeline_state WHERE id=1').fetchone()
            result = json.loads(row[0]) if row else {'status': 'uninitialized'}
            result.update(
                version=16, initial_end='2025-06', active_snapshot_id=self.run_id,
                history_rows=c.execute('SELECT COUNT(*) FROM a2_feature').fetchone()[0],
                history_end=c.execute('SELECT MAX(date) FROM a2_feature').fetchone()[0],
                detection_rows=c.execute('SELECT COUNT(*) FROM a2_detection').fetchone()[0],
                age_detection_rows=c.execute('SELECT COUNT(*) FROM a2_age_detection').fetchone()[0])
            return result

    # Dashboard-compatible mode implements the public Db1Repository contract
    # directly.  Keep the normal SqlDb1Repository implementation unchanged
    # when db1_v16 is provisioned.
    def districts(self):
        return self._dashboard.districts() if self._dashboard is not None else super().districts()

    def available_period(self):
        return self._dashboard.available_period() if self._dashboard is not None else super().available_period()

    def consumption_period(self):
        return self._dashboard.consumption_period() if self._dashboard is not None else super().consumption_period()

    def district_codes(self):
        return self._dashboard.district_codes() if self._dashboard is not None else super().district_codes()

    def activity(self, *args, **kwargs):
        return self._dashboard.activity(*args, **kwargs) if self._dashboard is not None else super().activity(*args, **kwargs)

    def signals(self, *args, **kwargs):
        return self._dashboard.signals(*args, **kwargs) if self._dashboard is not None else super().signals(*args, **kwargs)

    def age_signal_cases(self, *args, **kwargs):
        return self._dashboard.age_signal_cases(*args, **kwargs) if self._dashboard is not None else super().age_signal_cases(*args, **kwargs)

    def anomalies(self, *args, **kwargs):
        return self._dashboard.anomalies(*args, **kwargs) if self._dashboard is not None else super().anomalies(*args, **kwargs)

    def evidence(self, *args, **kwargs):
        return self._dashboard.evidence(*args, **kwargs) if self._dashboard is not None else super().evidence(*args, **kwargs)

    def context(self, *args, **kwargs):
        return self._dashboard.context(*args, **kwargs) if self._dashboard is not None else super().context(*args, **kwargs)

    def supplements(self, *args, **kwargs):
        return self._dashboard.supplements(*args, **kwargs) if self._dashboard is not None else super().supplements(*args, **kwargs)

    def consumption_evidence(self, *args, **kwargs):
        return self._dashboard.consumption_evidence(*args, **kwargs) if self._dashboard is not None else super().consumption_evidence(*args, **kwargs)

    def consumption_payloads(self, *args, **kwargs):
        return self._dashboard.consumption_payloads(*args, **kwargs) if self._dashboard is not None else super().consumption_payloads(*args, **kwargs)

    def close(self):
        if self._dashboard is not None:
            return self._dashboard.close()
        return super().close()

"""Immutable serving versions published from a PostgreSQL analysis workspace."""
from sqlalchemy import text
from backend.common import get_engine
from backend.agents.regional_analysis.data_pipeline.publish_postgres import publish as publish_run


def active_snapshot(database=None):
    with get_engine().connect() as connection:
        if connection.execute(text("SELECT to_regclass('db1.v16_active_run')")).scalar() is None:
            return None
        row = connection.execute(text("SELECT run_id FROM db1.v16_active_run WHERE id=1")).fetchone()
        return {'snapshot_id': row[0], 'run_id': row[0]} if row else None


def publish(database, period=None):
    result = publish_run(database, get_engine())
    return {**result, 'snapshot_id': result['run_id']}

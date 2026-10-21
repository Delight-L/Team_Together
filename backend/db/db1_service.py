"""Append DB1 results to the tables read by the service; keep prior runs."""

from datetime import datetime, timezone
import json
import pandas as pd
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    Boolean,
    text,
    select,
)


def service_tables(connection):
    if connection.dialect.name == 'postgresql':
        connection.execute(text('CREATE SCHEMA IF NOT EXISTS db1'))
    metadata = MetaData(schema='db1')
    Table(
        'analysis2_detections',
        metadata,
        Column('run_id', String, primary_key=True),
        Column('reference_month', Date, primary_key=True),
        Column('admin_dong_code', String, primary_key=True),
        Column('dong_name', String, nullable=False),
        Column('communication_signal', Boolean, nullable=False),
        Column('mobility_signal', Boolean, nullable=False),
        Column('combined_signal', Boolean, nullable=False),
        Column('any_signal', Boolean, nullable=False),
        Column('signal_type', String),
        Column('payload', JSON, nullable=False),
        Column('source_file', String),
        Column('created_at', DateTime(timezone=True), nullable=False),
    )
    Table(
        'analysis1_region_typology',
        metadata,
        Column('run_id', String, primary_key=True),
        Column('adm_cd', String, primary_key=True),
        Column('dong_name', String, nullable=False),
        Column('cluster', Integer, nullable=False),
        Column('cluster_type', String, nullable=False),
        Column('payload', JSON, nullable=False),
        Column('source_file', String),
        Column('created_at', DateTime(timezone=True), nullable=False),
    )
    Table(
        'service_ingestion_rows',
        metadata,
        Column('run_id', String, primary_key=True),
        Column('row_number', Integer, primary_key=True),
        Column('kind', String, primary_key=True),
        Column('payload', JSON, nullable=False),
    )
    metadata.create_all(connection)
    # Reflect existing column types too (production may use UUID/JSONB).
    existing = MetaData(schema='db1')
    return {
        name: Table(name, existing, autoload_with=connection)
        for name in ('analysis2_detections', 'analysis1_region_typology', 'service_ingestion_rows')
    }


def save_results(connection, prepared, run_id):
    if connection.dialect.name == 'postgresql':
        # Serialize the CLI and web publisher so concurrent snapshots retain each other's months.
        connection.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': 67834001})
    tables = service_tables(connection)
    created = datetime.now(timezone.utc)
    if prepared['kind'] == 'monthly':
        frame = prepared['data']
        table = tables['analysis2_detections']
        items = []
        for payload in json.loads(
            frame.to_json(orient='records', date_format='iso', force_ascii=False)
        ):
            items.append(
                dict(
                    run_id=run_id,
                    reference_month=pd.Timestamp(payload['date']).date(),
                    admin_dong_code=str(payload['행정동코드']),
                    dong_name=payload['행정동'],
                    communication_signal=bool(payload['communication_signal']),
                    mobility_signal=bool(payload['mobility_signal']),
                    combined_signal=bool(payload['combined_signal']),
                    any_signal=bool(payload['any_signal']),
                    signal_type=payload['signal_type'],
                    payload=payload,
                    source_file=prepared['source'],
                    created_at=created,
                )
            )
        # A monthly upload must not remove earlier months from the latest snapshot.
        latest = connection.execute(
            select(table.c.run_id).order_by(table.c.created_at.desc()).limit(1)
        ).scalar()
        incoming_keys = {(item['reference_month'], item['admin_dong_code']) for item in items}
        if latest:
            for row in connection.execute(select(table).where(table.c.run_id == latest)).mappings():
                if (row['reference_month'], row['admin_dong_code']) not in incoming_keys:
                    retained = {
                        key: row[key]
                        for key in (
                            'reference_month',
                            'admin_dong_code',
                            'dong_name',
                            'communication_signal',
                            'mobility_signal',
                            'combined_signal',
                            'any_signal',
                            'signal_type',
                            'payload',
                            'source_file',
                        )
                    }
                    items.append(dict(retained, run_id=run_id, created_at=created))
    else:
        table = tables['analysis1_region_typology']
        items = []
        for payload in json.loads(prepared['context'].to_json(orient='records', force_ascii=False)):
            items.append(
                dict(
                    run_id=run_id,
                    adm_cd=str(payload['adm_cd']),
                    dong_name=payload['dong_name'],
                    cluster=int(payload['cluster']),
                    cluster_type=payload['cluster_type'],
                    payload=payload,
                    source_file=prepared['source'],
                    created_at=created,
                )
            )
    if not items:
        raise ValueError('DB1 반영할 결과가 없습니다.')
    connection.execute(table.insert(), items)
    raw = json.loads(
        prepared['data'].to_json(orient='records', date_format='iso', force_ascii=False)
    )
    connection.execute(
        tables['service_ingestion_rows'].insert(),
        [
            dict(run_id=run_id, row_number=i, kind=prepared['kind'], payload=payload)
            for i, payload in enumerate(raw)
        ],
    )

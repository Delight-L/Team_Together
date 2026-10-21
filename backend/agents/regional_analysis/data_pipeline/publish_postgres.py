"""DB1 PostgreSQL 분석 결과를 PostgreSQL에 «run» 단위로 적재하고 활성 run을 바꿉니다(공개).

저장 구조 (스키마 db1)
- v16_run(run_id, status, coverage_end, source_sha256, tables, published_at)   적재 이력
- v16_active_run(id=1, run_id)                                                 챗봇이 읽는 활성 run 포인터
- v16_<테이블>(run_id, <분석 테이블의 열 그대로>)                              run별 자료
- 스키마 db1_v16의 뷰 <테이블>                                                  활성(고정된) run만 보이는 읽기 전용 창구.
  분석 테이블과 같은 이름·열이라 챗봇의 조회 SQL이 그대로 동작합니다.

원칙
- 적재와 포인터 변경은 한 트랜잭션입니다. 읽는 쪽은 이전 run 또는 새 run 중 하나만 보고, 중간 상태를 보지 않습니다.
- JSON 열은 TEXT로 저장합니다. JSON 형식은 NaN 같은 값을 거부하고 키 순서를 바꿀 수 있어서, 원문 그대로 보존해 분석 DB와 같은 결과를 냅니다.
- 같은 공개본(내용 해시)을 다시 올리면 새로 적재하지 않고 활성 run만 그 run으로 맞춥니다.
- 파이프라인 산출물에는 없는 `pipeline_state`·`ctx_weather`는 **원본을 고치지 않고** 게시 때 만들어 줍니다(data_pipeline/db1_compat.py):
  pipeline_state는 run 상태(v16_run)에서 뷰로, ctx_weather는 ctx_weather_month·ctx_weather_window에서 변환해 적재합니다.
"""

from __future__ import annotations

import hashlib
import json
from psycopg2.extras import execute_values
from pipelines.db1 import database

from . import db1_compat

SCHEMA = 'db1'
VIEW_SCHEMA = 'db1_v16'
PREFIX = 'v16_'
LOCK_KEY = 67834016  # 동시 공개를 직렬화하는 advisory lock 번호

# 챗봇이 읽는 테이블. REQUIRED는 없으면 공개를 거부하고, OPTIONAL은 있으면 함께 올립니다.
REQUIRED = (
    'a1_context',
    'a1_input',
    'db1_run',
    'a2_detection',
    'a2_evidence',
    'a2_feature',
    'a2_age_detection',
    'a3a_feature',
    'a3a_comparison',
    'a3a_quarter_summary',
    'a3b_feature',
    'a3b_month_summary',
)
# 없어도 게시할 수 있는 테이블(pipeline_state·ctx_weather는 없으면 변환해서 만듭니다)
OPTIONAL = (
    'pipeline_state',
    'ctx_weather',
    'ctx_survey_annual',
    'ctx_elder_annual',
    'ctx_youth_reference',
    'ctx_sns_index',
    'a2_activity_followup',
)
INDEXED = ('date', 'adm_cd', 'period', 'age_band', 'age', 'district', 'year')
BATCH = 5000


def _fingerprint(source, tables):
    digest = hashlib.sha256()
    for table in sorted(tables):
        hashes = []
        for row in source.execute('SELECT * FROM ' + _quote(table)):
            payload = json.dumps(list(row), ensure_ascii=False, separators=(',', ':'), default=str)
            hashes.append(hashlib.sha256(payload.encode()).hexdigest())
        digest.update((table + ''.join(sorted(hashes))).encode())
    return digest.hexdigest()


def _pg_type(declared: str) -> str:
    declared = (declared or '').upper()
    if 'INT' in declared:
        return 'BIGINT'
    if any(word in declared for word in ('REAL', 'FLOA', 'DOUB', 'NUM', 'DEC')):
        return 'DOUBLE PRECISION'
    return 'TEXT'


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _columns(source: database.Connection, table: str) -> list[tuple[str, str]]:
    return [(name, _pg_type(kind)) for name, kind in source.columns(table)]


def _ensure_schema(conn) -> None:
    conn.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS {SCHEMA}')
    conn.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS {VIEW_SCHEMA}')
    conn.exec_driver_sql(f'''CREATE TABLE IF NOT EXISTS {SCHEMA}.{PREFIX}run(
        run_id TEXT PRIMARY KEY, status TEXT NOT NULL, coverage_end TEXT, source_sha256 TEXT NOT NULL,
        tables TEXT, published_at TIMESTAMPTZ NOT NULL DEFAULT now())''')
    conn.exec_driver_sql(f'''CREATE TABLE IF NOT EXISTS {SCHEMA}.{PREFIX}active_run(
        id INTEGER PRIMARY KEY CHECK(id=1), run_id TEXT NOT NULL REFERENCES {SCHEMA}.{PREFIX}run(run_id))''')


def _ensure_table(conn, table: str, columns: list[tuple[str, str]]) -> None:
    target = f'{SCHEMA}.{PREFIX}{table}'
    body = ', '.join(f'{_quote(name)} {kind}' for name, kind in columns)
    conn.exec_driver_sql(f'CREATE TABLE IF NOT EXISTS {target}(run_id TEXT NOT NULL, {body})')
    existing = {
        row[0]
        for row in conn.exec_driver_sql(
            'SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s',
            (SCHEMA, PREFIX + table),
        )
    }
    for name, kind in columns:  # 새 공개본에 열이 늘었으면 추가
        if name not in existing:
            conn.exec_driver_sql(f'ALTER TABLE {target} ADD COLUMN {_quote(name)} {kind}')
    conn.exec_driver_sql(f'CREATE INDEX IF NOT EXISTS ix_{PREFIX}{table}_run ON {target}(run_id)')
    for name, _ in columns:
        if name in INDEXED:
            conn.exec_driver_sql(
                f'CREATE INDEX IF NOT EXISTS ix_{PREFIX}{table}_{name} ON {target}(run_id, {_quote(name)})'
            )
    # 읽기 창구 뷰: 고정된 run의 행만, 원래 분석 테이블과 같은 이름·열로 보입니다.
    names = ', '.join(_quote(name) for name, _ in columns)
    conn.exec_driver_sql(f'DROP VIEW IF EXISTS {VIEW_SCHEMA}.{_quote(table)}')
    conn.exec_driver_sql(
        f"CREATE VIEW {VIEW_SCHEMA}.{_quote(table)} AS SELECT {names} FROM {target} "
        f"WHERE run_id = current_setting('db1.v16_run_id', true)"
    )


def _copy(
    conn, source: database.Connection, table: str, columns: list[tuple[str, str]], run_id: str
) -> int:
    names = [name for name, _ in columns]
    insert = (
        f'INSERT INTO {SCHEMA}.{PREFIX}{table}(run_id, {", ".join(_quote(n) for n in names)}) '
        'VALUES %s'
    )
    cursor = source.execute(f'SELECT {", ".join(_quote(n) for n in names)} FROM {_quote(table)}')
    total = 0
    while True:
        rows = cursor.fetchmany(BATCH)
        if not rows:
            return total
        with conn.connection.driver_connection.cursor() as target:
            execute_values(target, insert, [(run_id, *row) for row in rows], page_size=500)
        total += len(rows)


def publish(
    workspace_schema, engine, *, run_id: str | None = None, keep: int = 3, force: bool = False
) -> dict:
    """PostgreSQL 분석 결과를 새 run으로 올리고 활성 run으로 지정합니다. 결과 요약(dict)을 돌려줍니다."""
    with database.connect(workspace_schema, readonly=True) as source:
        present = db1_compat.table_names(source)
        readiness_known = 'pipeline_state' in present
        if readiness_known:  # 작업기가 만든 DB는 «갱신 완료» 표지를 확인하고, 산출물에는 그 개념이 없어 확인할 수 없습니다
            state = source.execute('SELECT payload_json FROM pipeline_state WHERE id=1').fetchone()
            if not state or json.loads(state[0]).get('status') != 'ready':
                raise ValueError('완료(ready) 상태의 DB1만 공개할 수 있습니다.')
        missing = [name for name in REQUIRED if name not in present]
        if missing:
            raise ValueError('공개에 필요한 테이블이 없습니다: ' + ', '.join(missing))
        tables = [name for name in (*REQUIRED, *OPTIONAL) if name in present]
        digest = _fingerprint(source, tables)
        coverage = source.execute('SELECT MAX(date) FROM a2_feature').fetchone()[0]
        run_id = run_id or f"db1-{str(coverage)[:7].replace('-', '')}-{digest[:12]}"
        schema = {name: _columns(source, name) for name in tables}
        expected = {
            name: source.execute(f'SELECT COUNT(*) FROM {_quote(name)}').fetchone()[0]
            for name in tables
        }

        # 산출물에 없는 테이블 변환
        compat, synthesized = {}, {}
        if 'ctx_weather' not in present:
            rows = db1_compat.weather_rows(source)
            synthesized['ctx_weather'] = rows or []
            expected['ctx_weather'] = len(rows or [])
            compat['ctx_weather'] = (
                'ctx_weather_month·ctx_weather_window에서 변환'
                if rows is not None
                else '원천 없음(빈 표: 날씨 보조 자료 없이 답함)'
            )
        if not readiness_known:
            compat['pipeline_state'] = (
                'v16_run 상태에서 만든 뷰(산출물에 갱신 완료 표지가 없어 준비 상태는 확인하지 못함)'
            )

        with engine.begin() as conn:
            conn.exec_driver_sql('SELECT pg_advisory_xact_lock(%s)', (LOCK_KEY,))
            _ensure_schema(conn)
            found = conn.exec_driver_sql(
                f'SELECT status, source_sha256 FROM {SCHEMA}.{PREFIX}run WHERE run_id=%s', (run_id,)
            ).fetchone()
            if found and found[0] == 'ready' and found[1] == digest and not force:
                _activate(conn, run_id)
                return {
                    'run_id': run_id,
                    'status': 'already_published',
                    'tables': expected,
                    'compat': compat,
                }
            if found:  # 같은 run_id를 다시 적재(강제): 자료 행만 지우고 처음부터(활성 run이 참조하는 run 행은 유지)
                _clear_rows(conn, run_id)
                conn.exec_driver_sql(
                    f'UPDATE {SCHEMA}.{PREFIX}run SET status=%s, coverage_end=%s, source_sha256=%s, tables=%s, '
                    f'published_at=now() WHERE run_id=%s',
                    ('loading', str(coverage), digest, json.dumps(expected), run_id),
                )
            else:
                conn.exec_driver_sql(
                    f'INSERT INTO {SCHEMA}.{PREFIX}run(run_id,status,coverage_end,source_sha256,tables) '
                    f'VALUES(%s,%s,%s,%s,%s)',
                    (run_id, 'loading', str(coverage), digest, json.dumps(expected)),
                )
            copied = {}
            for name in tables:
                _ensure_table(conn, name, schema[name])
                copied[name] = _copy(conn, source, name, schema[name], run_id)
            for name, rows in synthesized.items():
                columns = [('date', 'TEXT'), ('payload_json', 'TEXT')]
                _ensure_table(conn, name, columns)
                if rows:
                    conn.exec_driver_sql(
                        f'INSERT INTO {SCHEMA}.{PREFIX}{name}(run_id, date, payload_json) VALUES (%s,%s,%s)',
                        [(run_id, date, payload) for date, payload in rows],
                    )
                copied[name] = len(rows)
            if not readiness_known:
                _status_view(conn)
            wrong = {
                name: (expected[name], count)
                for name, count in copied.items()
                if expected[name] != count
            }
            if wrong:  # 트랜잭션이 되돌려져 활성 run은 그대로입니다.
                raise ValueError(f'적재 행 수가 원본과 다릅니다: {wrong}')
            conn.exec_driver_sql(
                f'UPDATE {SCHEMA}.{PREFIX}run SET status=%s WHERE run_id=%s', ('ready', run_id)
            )
            _activate(conn, run_id)
            pruned = _prune(conn, keep)
    return {
        'run_id': run_id,
        'status': 'published',
        'tables': copied,
        'pruned_runs': pruned,
        'compat': compat,
    }


def _status_view(conn) -> None:
    """산출물에 pipeline_state가 없을 때, run 상태에서 같은 이름·열의 뷰를 만듭니다(고정된 run의 상태)."""
    conn.exec_driver_sql(f'DROP VIEW IF EXISTS {VIEW_SCHEMA}.pipeline_state')
    conn.exec_driver_sql(
        f"CREATE VIEW {VIEW_SCHEMA}.pipeline_state AS "
        f"SELECT 1::bigint AS id, json_build_object('status', status, 'source', 'v16_run')::text AS payload_json "
        f"FROM {SCHEMA}.{PREFIX}run WHERE run_id = current_setting('db1.v16_run_id', true)"
    )


def activate(engine, run_id: str) -> dict:
    """이미 적재된 run을 활성으로 바꿉니다(롤백·재전환). 갱신이 끝난(ready) run만 가능합니다."""
    with engine.begin() as conn:
        conn.exec_driver_sql('SELECT pg_advisory_xact_lock(%s)', (LOCK_KEY,))
        status = conn.exec_driver_sql(
            f'SELECT status FROM {SCHEMA}.{PREFIX}run WHERE run_id=%s', (run_id,)
        ).scalar()
        if status != 'ready':
            raise ValueError(f'활성으로 바꿀 수 없는 run입니다: {run_id} ({status or "없음"})')
        _activate(conn, run_id)
    return {'run_id': run_id, 'status': 'activated'}


def _activate(conn, run_id: str) -> None:
    conn.exec_driver_sql(
        f'INSERT INTO {SCHEMA}.{PREFIX}active_run(id, run_id) VALUES(1,%s) '
        f'ON CONFLICT (id) DO UPDATE SET run_id=EXCLUDED.run_id',
        (run_id,),
    )


def _data_tables(conn) -> list[str]:
    rows = conn.exec_driver_sql(
        'SELECT table_name FROM information_schema.columns WHERE table_schema=%s AND column_name=%s '
        'AND table_name LIKE %s AND table_name NOT IN (%s,%s)',
        (SCHEMA, 'run_id', PREFIX + '%', PREFIX + 'run', PREFIX + 'active_run'),
    )
    return sorted({row[0] for row in rows})


def _clear_rows(conn, run_id: str) -> None:
    for table in _data_tables(conn):
        conn.exec_driver_sql(f'DELETE FROM {SCHEMA}.{table} WHERE run_id=%s', (run_id,))


def _delete_run(conn, run_id: str) -> None:
    _clear_rows(conn, run_id)
    conn.exec_driver_sql(f'DELETE FROM {SCHEMA}.{PREFIX}run WHERE run_id=%s', (run_id,))


def _prune(conn, keep: int) -> list[str]:
    """최근 keep개 run과 활성 run만 남깁니다. 요청 중인 챗봇이 읽는 이전 run을 곧바로 지우지 않도록 keep ≥ 2를 권장합니다."""
    if keep < 1:
        return []
    old = [
        row[0]
        for row in conn.exec_driver_sql(
            f'SELECT run_id FROM {SCHEMA}.{PREFIX}run WHERE status=%s '
            f'AND run_id <> (SELECT run_id FROM {SCHEMA}.{PREFIX}active_run WHERE id=1) '
            f'ORDER BY published_at DESC OFFSET %s',
            ('ready', max(keep - 1, 0)),
        )
    ]
    for run in old:
        _delete_run(conn, run)
    return old

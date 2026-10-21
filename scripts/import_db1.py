"""Validate DB1 delivery; --publish appends it to the configured service DB."""

from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.db.db1_snapshot import prepare_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--workspace', help='Read a PostgreSQL analysis workspace without modifying it'
    )
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    monthly, structure = prepare_snapshot(args.workspace)
    result = dict(
        status='PASS',
        monthly_rows=len(monthly['data']),
        structure_rows=len(structure['context']),
        period=monthly['period'],
        model_version=structure['report']['rule_version'],
        published=False,
    )
    if args.publish:
        from backend.db import analysis_repository as repository
        from backend.db.db1_service import save_results
        from uuid import uuid4

        run_id = str(uuid4())
        # Both result sets are published atomically; the snapshot is read-only.
        with repository.get_engine().begin() as connection:
            save_results(connection, monthly, run_id)
            save_results(connection, structure, run_id)
            from sqlalchemy import text

            connection.execute(
                text('''CREATE TABLE IF NOT EXISTS db1.service_imports
                (run_id TEXT PRIMARY KEY, source_name TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
            )
            connection.execute(
                text('INSERT INTO db1.service_imports(run_id,source_name) VALUES(:run,:source)'),
                dict(run=run_id, source=args.workspace or 'delightL DB1 delivery'),
            )
        result.update(published=True, run_id=run_id)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

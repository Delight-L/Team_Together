"""분석 조회 뷰 설치: 먼저 점검하고 --apply로 공용 DB에 적용합니다."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.db.connection import engine
from backend.db.analysis_views import install_views
from sqlalchemy import text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    with engine.begin() as connection:
        permitted = connection.execute(
            text("SELECT has_schema_privilege(current_user, 'db1', 'CREATE')")
        ).scalar_one()
        print('db1 CREATE permission:', permitted)
        for table in ('analysis2_detections', 'analysis1_region_typology'):
            count = connection.execute(text(f'SELECT COUNT(*) FROM db1.{table}')).scalar_one()
            print(table, count)
        if args.apply:
            install_views(connection)
            for view in ('latest_detection_run', 'latest_region_typology'):
                count = connection.execute(text(f'SELECT COUNT(*) FROM db1.{view}')).scalar_one()
                print(view, count)
            print('Applied analysis views')


if __name__ == '__main__':
    main()

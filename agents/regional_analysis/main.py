"""DB1 실행기: 신규 파이프라인과 서비스 반영을 연결합니다."""
from pathlib import Path
import argparse
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--command', default='service-preview', choices=[
        'service-preview', 'initialize', 'scan', 'status', 'export', 'analysis1', 'analysis2',
        'analysis1-elder', 'analysis2-age', 'analysis2-age-detect', 'analysis2-activity'])
    parser.add_argument('--publish', action='store_true', help='서비스 DB에 분석 결과 반영')
    parser.add_argument('--db', help='Git LFS 실파일 또는 별도 운영 SQLite 경로')
    parser.add_argument('--config')
    parser.add_argument('--period')
    parser.add_argument('--month')
    parser.add_argument('--no-download', action='store_true', help='호환 옵션: service-preview는 로컬 전달본만 읽습니다.')
    args = parser.parse_args()
    if args.no_download and args.command != 'service-preview':
        parser.error('--no-download는 service-preview에서만 사용하세요.')
    if args.command != 'service-preview':
        command = [sys.executable, '-X', 'utf8', str(ROOT / 'DB1/run_db1.py'), args.command]
        for key in ('db', 'config', 'period', 'month'):
            if getattr(args, key):
                command.extend(['--' + key, getattr(args, key)])
        subprocess.run(command, check=True)
    if args.command == 'service-preview' or args.publish:
        command = [sys.executable, '-X', 'utf8', str(ROOT / 'scripts/import_db1.py')]
        snapshot = args.db
        if args.command != 'service-preview' and not snapshot:
            from DB1.db1_settings import load_settings
            settings = load_settings(args.config or ROOT / 'DB1/config/db1_config.json')
            snapshot = str(ROOT / 'DB1' / settings['database'])
        if snapshot:
            command.extend(['--sqlite', snapshot])
        if args.publish:
            command.append('--publish')
        subprocess.run(command, check=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

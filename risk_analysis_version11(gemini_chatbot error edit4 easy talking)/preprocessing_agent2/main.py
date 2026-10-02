"""로컬 ZIP/XLSX → Analysis2 전처리. python main.py --help"""
import argparse
import csv
import json
import os
import math
from pathlib import Path
import tempfile
import traceback
from preprocessing.archives import discover, sha256
from preprocessing.readers import read_workbook, month_from_name
from preprocessing.features import months, load_weather, assemble
from preprocessing.validation import validate, compare
from preprocessing.temporary import temporary_directory

BASE = Path(__file__).resolve().parent


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', action='append', help='ZIP/XLSX/폴더. 여러 번 지정 가능')
    parser.add_argument('--output', help='결과 폴더')
    parser.add_argument('--config', default=str(BASE / 'config.json'))
    parser.add_argument('--compare', help='기존 Analysis2 CSV: 검증 비교 전용')
    parser.add_argument('--full', action='store_true', help='기존 방식으로 전체 기간을 다시 전처리')
    parser.add_argument('--no-download', action='store_true', help='공식 페이지 확인 없이 raw_data만 처리')
    args = parser.parse_args(argv)
    config_path = Path(args.config).resolve()
    config = {}
    def configured(name):
        p = Path(config[name])
        return p if p.is_absolute() else config_path.parent / p
    out = Path(args.output).resolve() if args.output else BASE / 'outputs'
    filename = out / 'gangnam_analysis2_feature_table_2022_2025.csv'
    manifest = {'status': 'RUNNING', 'files': [], 'name_normalizations': set(), 'config': config,
                'warnings': ['1123074의 2024-01 이후 관심집단 구조 플래그를 보존합니다.']}
    report = {'status': 'FAIL', 'errors': []}
    try:
        config = json.loads(config_path.read_text(encoding='utf-8-sig'))
        if not isinstance(config, dict):
            raise ValueError('설정은 JSON 객체여야 합니다.')
        manifest['config'] = config
        if not args.full:
            from auto_update import run_incremental
            result = run_incremental(config_path.parent, config, no_download=args.no_download)
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
            return 0
        if not args.output:
            out = configured('output').resolve()
            filename = out / filename.name
        out.mkdir(parents=True, exist_ok=True)
        tolerance = config['comparison_absolute_tolerance']
        if not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool) or not math.isfinite(tolerance) or tolerance < 0:
            raise ValueError('비교 허용오차는 유한한 비음수 필요')
        for key, value in config['archive_limits'].items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f'압축 제한은 양의 정수 필요: {key}')
        dates = months(config['start_month'], config['end_month'])
        areas = json.loads((BASE / 'reference/areas.json').read_text(encoding='utf-8'))
        columns = json.loads((BASE / 'reference/columns.json').read_text(encoding='utf-8'))
        weather_path = configured('weather')
        weather_hash = sha256(weather_path)
        provenance = json.loads((BASE / 'reference/provenance.json').read_text(encoding='utf-8'))
        if weather_hash != provenance['weather_sha256']:
            provenance = {'source': '사용자 지정 날씨 CSV', 'upstream_source': '확인되지 않음'}
            manifest['warnings'].append('사용자 지정 날씨 CSV를 사용합니다. 원 관측소와 상위 출처는 확인되지 않았습니다.')
        else:
            manifest['warnings'].append('날씨는 기존 Analysis2 CSV에서 재사용한 보조자료이며 관측소와 원출처는 확인되지 않았습니다.')
        manifest['weather'] = {'path': str(weather_path.resolve()), 'sha256': weather_hash, 'provenance': provenance}
        weather = load_weather(weather_path)
        data, seen = {}, {}
        scratch_root = out / '.work'
        scratch_root.mkdir(exist_ok=True)
        with temporary_directory(scratch_root) as temp:
            files = discover(args.input or [configured('input')], temp, config['archive_limits'], manifest)
            for index, (path, name, entry) in enumerate(files, 1):
                print(f'[{index}/{len(files)}] {name}', flush=True)
                month = month_from_name(name)
                if month not in dates:
                    entry.update(month=month, status='excluded_outside_period')
                    continue
                month, kind, groups, digest, row_count = read_workbook(path, name, areas, manifest, config['demographics'], config['archive_limits']['max_file_bytes'])
                entry.update(month=month, kind=kind, normalized_sha256=digest, gangnam_rows=row_count)
                if month not in dates:
                    entry['status'] = 'excluded_outside_period'
                    continue
                key = (month, kind)
                if key in seen:
                    if seen[key] != digest:
                        raise ValueError(f'같은 종류·월 자료 충돌: {key} ({entry["source"]})')
                    entry['status'] = 'normalized_duplicate'
                    continue
                seen[key], data[key] = digest, groups
                entry['status'] = 'processed'
            rows = assemble(data, dates, areas, weather)
            report = validate(rows, dates, areas, columns)
            if report['status'] != 'PASS':
                raise ValueError('; '.join(report['errors']))
            if args.compare:
                report['comparison'] = compare(rows, args.compare, columns, config['comparison_absolute_tolerance'])
                manifest['comparison_source'] = {'path': str(Path(args.compare).resolve()), 'sha256': sha256(args.compare)}
            temporary = filename.with_suffix('.csv.tmp')
            with temporary.open('w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
        # Cleanup must finish before publishing the new result.
        output_digest = sha256(temporary)
        os.replace(temporary, filename)
        manifest.update(status='PASS', monthly_inputs=len(data), output=str(filename), output_sha256=output_digest)
        print(f'PASS: {len(rows)}행 × {len(columns)}열 → {filename}', flush=True)
        return 0
    except Exception as exc:
        manifest['status'] = 'FAIL'
        report['status'] = 'FAIL'
        report.setdefault('errors', []).append(str(exc))
        report['existing_output_is_not_current_run'] = filename.exists()
        print(f'FAIL: {exc}', flush=True)
        return 1
    finally:
        out.mkdir(parents=True, exist_ok=True)
        manifest['name_normalizations'] = sorted(manifest['name_normalizations'])
        save_json(out / 'preprocessing_manifest.json', manifest)
        save_json(out / 'validation_report.json', report)


if __name__ == '__main__':
    raise SystemExit(main())

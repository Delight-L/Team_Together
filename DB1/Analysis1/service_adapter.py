"""Service uploads use the approved elder v2 model in an isolated process."""
from pathlib import Path
import argparse
import json
import pandas as pd

from preprocessing.pipeline import build_analysis1_pca_input
from preprocessing.resident import preprocess_resident
from preprocessing.loader import read_local
from elder_context import read_source
from analysis.change_detector import detect_changes

ROOT = Path(__file__).resolve().parents[1]
MODEL_VERSION = 'analysis1_2025H2_elder_v2'


def one(folder, pattern):
    matches = sorted(Path(folder).glob(pattern))
    if len(matches) != 1:
        raise ValueError(f'{pattern}: 원본 파일을 정확히 한 개 선택하세요.')
    return matches[0]


def prepare(folder):
    resident = one(folder, '*등록인구*.csv')
    # The repository also preserves a July-only legacy file. Prefer the delivered H2 aggregate.
    canonical = Path(folder) / 'gangnam_db1_features_2025H2.csv'
    skt = canonical if canonical.is_file() else one(folder, '*gangnam_db1_features*.csv')
    base = build_analysis1_pca_input(
        skt_feature=skt,
        resident_file=resident, household_file=one(folder, '*세대원수별*.csv'),
        welfare_file=one(folder, '*국민기초생활 수급자 동별 현황*.xlsx'),
    )
    base['adm_cd'] = base.adm_cd.astype(str)
    mapping = dict(zip(base.dong_name, base.adm_cd))
    if '개포3동' in mapping:
        mapping['일원2동'] = mapping['개포3동']
    candidates = list(Path(folder).glob('*.csv'))
    elder_files = []
    for path in candidates:
        if {'독거노인별', '성별', '항목', '단위'}.issubset(read_local(path, nrows=0).columns):
            elder_files.append(path)
    if len(elder_files) != 1:
        raise ValueError('독거노인 원본 CSV 한 개와 등록인구·세대수·SKT·수급자 자료를 선택하세요.')
    cells, source = read_source(elder_files[0], mapping, allow_terminal_error=True)
    counts = {r['adm_cd']: r['value'] for r in cells
              if r['year'] == 2025 and r['category'] == '합계' and r['sex'] == '계'}
    population = preprocess_resident(resident, year=2025, quarters=(4,))
    denominators = population.set_index('dong_name').eval('resident_total * resident_ratio_65_plus')
    base['elderly_living_alone_rate_65plus'] = base.adm_cd.map(counts) / base.dong_name.map(denominators)
    if not base.elderly_living_alone_rate_65plus.between(0, 1).all():
        raise ValueError('2025년 독거노인 수와 2025Q4의 65세 이상 인구를 확인하세요.')
    features, _, changes = detect_changes(
        base, ROOT / 'Analysis1/models/2025H2_elder_v2/analysis1_baseline_2025H2.joblib', '2025H2')
    context = base.merge(features.drop(columns=['dong_name']), on='adm_cd', validate='one_to_one', suffixes=('_raw', ''))
    labels = changes.set_index('adm_cd')
    context['cluster'] = context.adm_cd.map(labels.current_cluster)
    context['cluster_type'] = context.adm_cd.map(labels.current_cluster_type)
    context['model_version'] = MODEL_VERSION
    context['context_period'] = '2025H2'
    context['elder_year'] = 2025
    context['denominator_reference'] = '2025Q4'
    context['elder_available_from'] = None
    context['elder_time_alignment'] = 'retrospective_annual_to_Q4'
    context['context_note'] = '2025년 독거노인 수와 2025년 4분기 65세 이상 등록인구를 비교한 연간 지역 배경자료입니다. 공개 시점 미확인으로 과거 월 당시 정보나 개인 고립 판정에 사용하지 않습니다.'
    report = dict(status='PASS', rows=len(base), period='2025H2 구조자료',
                  rule_version=MODEL_VERSION, elderly_source=source,
                  denominator_reference='2025Q4', available_from=None,
                  note=context.context_note.iloc[0])
    return base, context, report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw-dir', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    base, context, report = prepare(args.raw_dir)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    base.to_csv(output / 'input.csv', index=False, encoding='utf-8-sig')
    context.to_csv(output / 'context.csv', index=False, encoding='utf-8-sig')
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')

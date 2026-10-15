"""Age-preserving Analysis2 preprocessing; does not produce isolation detections."""
from pathlib import Path
from contextlib import closing
import argparse
import hashlib
import json
import sqlite3

import numpy as np
import pandas as pd

try:
    from preprocessing.monthly_features import build_month_feature_frames
except ModuleNotFoundError:
    from monthly_features import build_month_feature_frames

VERSION = 'a2_age_features_v1'
AGES = tuple(range(20, 80, 5))
BANDS = ('20s', '30s', '40s', '50s', '60plus')
KEY = ['date', '행정동코드', 'age_band']
RAW_KEY = ['행정동코드', '성별', '연령대']
CORE = ['call_contacts', 'text_contacts', 'weekday_move_count', 'weekend_move_count']
MOVE = [
    ('weekday_move_count', '평일 총 이동 횟수', '평일 총 이동 횟수 미추정 인구수'),
    ('weekend_move_count', '휴일 총 이동 횟수 평균', '휴일 이동 미추정 인구수'),
    ('weekday_move_distance', '평일 총 이동 거리 합계', '평일 총 이동 거리 미추정 인구수'),
    ('weekend_move_distance', '휴일 총 이동 거리 합계', '휴일 총 이동 거리 미추정 인구수'),
]
INTEREST = ['커뮤니케이션이 적은 집단', '평일 외출이 적은 집단', '휴일 외출이 적은 집단']


def band(age):
    return f'{int(age)//10*10}s' if int(age) < 60 else '60plus'


def raw_check(frame, kind, expected_codes=None):
    frame = frame.loc[frame['자치구'].eq('강남구')].copy()
    for col in RAW_KEY:
        frame[col] = pd.to_numeric(frame[col], errors='raise')
        if frame[col].isna().any() or not frame[col].eq(frame[col].astype(int)).all():
            raise ValueError(f'{kind}: invalid {col}')
        frame[col] = frame[col].astype(int)
    if frame.duplicated(RAW_KEY).any():
        raise ValueError(f'{kind}: duplicate dong/sex/age cells')
    codes = sorted(frame['행정동코드'].unique())
    if len(codes) != 22 or (expected_codes is not None and codes != sorted(expected_codes)):
        raise ValueError(f'{kind}: dong codes changed or missing')
    grid = pd.MultiIndex.from_product([codes, [1, 2], AGES], names=RAW_KEY)
    actual = pd.MultiIndex.from_frame(frame[RAW_KEY])
    if set(grid) != set(actual):
        raise ValueError(f'{kind}: incomplete/unexpected sex-age grid: missing={list(grid.difference(actual))[:5]}')
    name_col = '행정동' if kind == 'telecom' else '행정동명'
    if frame.groupby('행정동코드')[name_col].nunique().ne(1).any():
        raise ValueError(f'{kind}: inconsistent dong names')
    population_cols = ['총인구수', '1인가구수'] if kind == 'telecom' else ['1인가구수']
    for col in population_cols:
        v = pd.to_numeric(frame[col], errors='raise')
        if not np.isfinite(v).all() or v.lt(0).any():
            raise ValueError(f'{kind}: invalid population {col}')
        frame[col] = v
    if kind == 'telecom':
        if frame['1인가구수'].gt(frame['총인구수']).any():
            raise ValueError('one-person estimate exceeds total population')
        for out, value, missing in MOVE:
            m = pd.to_numeric(frame[missing], errors='raise')
            if not np.isfinite(m).all() or m.lt(0).any() or m.gt(frame['총인구수']).any():
                raise ValueError(f'invalid missing-population count: {missing}')
            frame[missing] = m
    else:
        for col in INTEREST:
            v = pd.to_numeric(frame[col], errors='raise')
            if not np.isfinite(v).all() or v.lt(0).any() or v.gt(frame['1인가구수']).any():
                raise ValueError(f'invalid interest count: {col}')
            frame[col] = v
    return frame


def build_age_frames(telecom, interest, rain, diary, year, month, expected_codes=None):
    telecom = raw_check(telecom, 'telecom', expected_codes)
    interest = raw_check(interest, 'interest', telecom['행정동코드'].unique())
    name_a = telecom.groupby('행정동코드')['행정동'].first()
    name_b = interest.groupby('행정동코드')['행정동명'].first()
    if not name_a.equals(name_b.rename('행정동')):
        raise ValueError('telecom/interest dong names differ')
    frames = []
    for scheme, age_labels in [('five_year', AGES), ('service', BANDS)]:
        ta = telecom.assign(age_band=telecom['연령대'].map(band) if scheme == 'service' else telecom['연령대'].astype(str))
        ia = interest.assign(age_band=interest['연령대'].map(band) if scheme == 'service' else interest['연령대'].astype(str))
        for label in age_labels:
            label = str(label)
            tg, ig = ta.loc[ta.age_band.eq(label)], ia.loc[ia.age_band.eq(label)]
            features = build_month_feature_frames(tg, ig, rain, diary, year, month)
            features['age_scheme'] = scheme
            features['age_band'] = label
            features['model_version'] = VERSION
            features['phase'] = 'baseline' if pd.Timestamp(year, month, 1) <= pd.Timestamp('2025-06-01') else 'update'
            pops = tg.groupby('행정동코드').agg(total_population=('총인구수', 'sum'), telecom_one_person_population=('1인가구수', 'sum'), source_cells=('연령대', 'size'))
            pops['interest_one_person_population'] = ig.groupby('행정동코드')['1인가구수'].sum()
            for out, value, missing in MOVE:
                valid = pd.to_numeric(tg[value], errors='coerce').notna()
                weights = (tg['총인구수'] - tg[missing]).where(valid, 0)
                pops[out + '_valid_population'] = weights.groupby(tg['행정동코드']).sum()
            for out, value in [('call_contacts', '평균 통화대상자 수'), ('text_contacts', '평균 문자대상자 수')]:
                valid = pd.to_numeric(tg[value], errors='coerce').notna()
                pops[out + '_valid_population'] = tg['총인구수'].where(valid, 0).groupby(tg['행정동코드']).sum()
            features = features.merge(pops.reset_index(), on='행정동코드', validate='one_to_one')
            features['quality_status'] = np.where(
                features[CORE].apply(pd.to_numeric, errors='coerce').gt(0).all(axis=1)
                & features['interest_one_person_population'].gt(0)
                & ~features['interest_structural_issue'],
                'available', 'review_required')
            features['quality_note'] = 'available is preprocessing completeness, not validated detection readiness; no population cutoff calibrated'
            frames.append(features)
    return pd.concat(frames, ignore_index=True), telecom, interest


def find_file(directory, period, keyword):
    found = list(Path(directory).glob(f'{period.year}.{period.month}월*{keyword}*.xlsx'))
    if len(found) != 1:
        raise ValueError(f'{period:%Y-%m} {keyword}: expected 1 file, found {len(found)}')
    return found[0]


def sources(settings, period):
    return (find_file(settings['telecom_dir'], period, '29개'), find_file(settings['interest_dir'], period, '10개'))


def reconcile(age, legacy):
    result = []
    for code, group in age.loc[age.age_scheme.eq('service')].groupby('행정동코드'):
        old = legacy.set_index('행정동코드').loc[code]
        for col in CORE + ['weekday_move_distance', 'weekend_move_distance']:
            w = group[col + '_valid_population']
            mask = group[col].notna() & w.gt(0)
            value = np.average(group.loc[mask, col], weights=w[mask]) if mask.any() else np.nan
            result.append({'date': str(old['date'].date()), '행정동코드': int(code), 'metric': col, 'rebuilt': value, 'existing_method': old[col], 'difference': value-old[col]})
        for col in ['comm_low_rate', 'weekday_outing_low_rate', 'weekend_outing_low_rate']:
            w = group.interest_one_person_population
            value = np.average(group[col], weights=w) if w.sum() > 0 else np.nan
            result.append({'date': str(old['date'].date()), '행정동코드': int(code), 'metric': col, 'rebuilt': value, 'existing_method': old[col], 'difference': value-old[col]})
    result = pd.DataFrame(result)
    if not np.allclose(result.rebuilt, result.existing_method, rtol=1e-10, atol=1e-10, equal_nan=True):
        raise ValueError('age-to-dong weighted reconciliation failed')
    return result


SCHEMA = '''
CREATE TABLE IF NOT EXISTS a2_age_feature (
 adm_cd TEXT NOT NULL, date TEXT NOT NULL, age_scheme TEXT NOT NULL, age_band TEXT NOT NULL,
 model_version TEXT NOT NULL, phase TEXT NOT NULL, quality_status TEXT NOT NULL, feature_json TEXT NOT NULL,
 PRIMARY KEY(adm_cd,date,age_scheme,age_band));
CREATE TABLE IF NOT EXISTS a2_age_source (
 date TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, metadata_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS a2_age_raw (
 date TEXT NOT NULL, kind TEXT NOT NULL, adm_cd TEXT NOT NULL, sex INTEGER NOT NULL, age_code INTEGER NOT NULL,
 raw_json TEXT NOT NULL, PRIMARY KEY(date,kind,adm_cd,sex,age_code));
'''


def serial(frame):
    return json.loads(frame.to_json(orient='records', date_format='iso', force_ascii=False, double_precision=15))


def persist(db, monthly, raw_t, raw_i, metadata):
    date = pd.Timestamp(monthly.date.iloc[0]).strftime('%Y-%m-%d')
    raw_payload = {'telecom': serial(raw_t.sort_values(RAW_KEY)), 'interest': serial(raw_i.sort_values(RAW_KEY)), 'version': VERSION}
    digest = hashlib.sha256(json.dumps(raw_payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as con, con:
        con.executescript(SCHEMA)
        existing = con.execute('SELECT fingerprint FROM a2_age_source WHERE date=?', (date,)).fetchone()
        if existing:
            if existing[0] != digest:
                raise ValueError(f'{date}: stored age data differ; explicit source revision required')
            stored = [json.loads(row[0]) for row in con.execute('SELECT feature_json FROM a2_age_feature WHERE date=?', (date,))]
            order = lambda row: (row['행정동코드'], row['age_scheme'], row['age_band'])
            if sorted(stored, key=order) != sorted(serial(monthly), key=order):
                raise ValueError(f'{date}: derived features/weather differ; explicit revision required')
            return False
        latest = con.execute('SELECT MAX(date) FROM a2_age_source').fetchone()[0]
        expected = (pd.Period(latest, freq='M') + 1).to_timestamp().strftime('%Y-%m-%d') if latest else '2022-01-01'
        if date != expected:
            raise ValueError(f'nonconsecutive age update: expected {expected}, got {date}')
        for row in serial(monthly):
            con.execute('INSERT INTO a2_age_feature VALUES (?,?,?,?,?,?,?,?)', (str(row['행정동코드']), date, row['age_scheme'], row['age_band'], VERSION, row['phase'], row['quality_status'], json.dumps(row, ensure_ascii=False, allow_nan=False)))
        for kind, records in raw_payload.items():
            if kind == 'version':
                continue
            for row in records:
                con.execute('INSERT INTO a2_age_raw VALUES (?,?,?,?,?,?)', (date, kind, str(row['행정동코드']), int(row['성별']), int(row['연령대']), json.dumps(row, ensure_ascii=False, allow_nan=False)))
        con.execute('INSERT INTO a2_age_source VALUES (?,?,?)', (date, digest, json.dumps(metadata, ensure_ascii=False)))
    return True


def export(db, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as con:
        frame = pd.DataFrame([json.loads(r[0]) for r in con.execute('SELECT feature_json FROM a2_age_feature ORDER BY date,adm_cd,age_scheme,age_band')])
    for scheme in ['service', 'five_year']:
        selected = frame.loc[frame.age_scheme.eq(scheme)].copy()
        selected.to_csv(output/f'analysis2_age_{scheme}_history.csv', index=False, encoding='utf-8-sig')
        if scheme == 'service':
            for phase in ['baseline', 'update']:
                selected.loc[selected.phase.eq(phase)].to_csv(output/f'analysis2_age_service_{phase}.csv', index=False, encoding='utf-8-sig')


def run(config, db, output, start='2022-01', end='2025-12', month=None):
    settings = (config if isinstance(config, dict) else json.loads(Path(config).read_text(encoding='utf-8')))['analysis2']
    rain = pd.read_csv(settings['rain'], encoding='utf-8-sig')
    diary = pd.read_csv(settings['diary'], encoding='utf-8-sig')
    periods = [pd.Period(month, freq='M').to_timestamp()] if month else pd.date_range(start, end, freq='MS')
    inventory = [{'month': p.strftime('%Y-%m'), 'telecom': str(sources(settings, p)[0]), 'interest': str(sources(settings, p)[1])} for p in periods]
    # Validate inventory before any new monthly data are stored.
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(inventory).to_csv(output/'source_inventory.csv', index=False, encoding='utf-8-sig')
    reports = []; checks = []; expected_codes = None
    if Path(db).exists():
        with closing(sqlite3.connect(db)) as con:
            if con.execute("SELECT 1 FROM sqlite_master WHERE name='a2_age_feature'").fetchone():
                expected_codes = [int(row[0]) for row in con.execute('SELECT DISTINCT adm_cd FROM a2_age_feature')]
                if not expected_codes: expected_codes = None
    for period, source in zip(periods, inventory):
        t = pd.read_excel(source['telecom']); i = pd.read_excel(source['interest'])
        age, t, i = build_age_frames(t, i, rain, diary, period.year, period.month, expected_codes)
        expected_codes = sorted(t['행정동코드'].unique())
        old = build_month_feature_frames(t, i, rain, diary, period.year, period.month)
        check = reconcile(age, old); checks.append(check)
        metadata = {**source, 'telecom_columns': list(t.columns), 'interest_columns': list(i.columns)}
        saved = persist(db, age, t, i, metadata)
        reports.append({'month': source['month'], 'raw_telecom_rows': len(t), 'raw_interest_rows': len(i), 'service_rows': int(age.age_scheme.eq('service').sum()), 'five_year_rows': int(age.age_scheme.eq('five_year').sum()), 'review_required': int(age.quality_status.eq('review_required').sum()), 'max_reconciliation_error': float(check.difference.abs().max()), 'saved': saved})
        print(json.dumps(reports[-1], ensure_ascii=False), flush=True)
    merge_report(pd.DataFrame(reports), output/'monthly_quality_report.csv', ['month'])
    merge_report(pd.concat(checks), output/'weighted_reconciliation.csv', ['date', '행정동코드', 'metric'])
    with closing(sqlite3.connect(db)) as con:
        all_sources = [json.loads(row[0]) for row in con.execute('SELECT metadata_json FROM a2_age_source ORDER BY date')]
    pd.DataFrame([{k: row[k] for k in ['month','telecom','interest']} for row in all_sources]).to_csv(output/'source_inventory.csv', index=False, encoding='utf-8-sig')
    export(db, output)
    return reports


def merge_report(frame, path, keys):
    if Path(path).exists():
        old = pd.read_csv(path, encoding='utf-8-sig')
        frame = pd.concat([old, frame], ignore_index=True).drop_duplicates(keys, keep='last')
    frame.sort_values(keys).to_csv(path, index=False, encoding='utf-8-sig')


def sync_age_history(settings, db, through, output):
    """Backfill only missing months; used by the ordinary DB1 scan/month worker."""
    with closing(sqlite3.connect(db)) as con:
        con.executescript(SCHEMA)
        latest = con.execute('SELECT MAX(date) FROM a2_age_source').fetchone()[0]
    start = (pd.Period(latest, freq='M') + 1).to_timestamp() if latest else pd.Timestamp('2022-01-01')
    through = pd.Timestamp(through)
    if start <= through:
        run(settings, db, output, start.strftime('%Y-%m'), through.strftime('%Y-%m'))
    elif latest:
        export(db, output)


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(root/'config/db1_config.json'))
    parser.add_argument('--db', default=str(root/'outputs/db1.sqlite'))
    parser.add_argument('--output', default=str(root/'Analysis2/outputs/age'))
    parser.add_argument('--start', default='2022-01'); parser.add_argument('--end', default='2025-12')
    parser.add_argument('--month')
    parser.add_argument('--export-only', action='store_true')
    a = parser.parse_args()
    if a.export_only: export(a.db, a.output)
    else: run(a.config, a.db, a.output, a.start, a.end, a.month)


if __name__ == '__main__':
    main()

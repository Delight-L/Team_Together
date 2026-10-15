"""집단별 유동인구 마트. 기존 동별 Analysis2와 독립적으로 보관한다.

python -m db.group_repository --build --publish
공개 집계 CSV만 읽으며 원본/기존 분석 테이블은 변경하지 않는다.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / 'data/processed/group_dashboard.json'
VERSION = 'flow-groups-v2'
CITY_PREFIXES = {'강남구': '11230', '춘천시': '32010'}


def belongs_to_city(code, city):
    prefix = CITY_PREFIXES.get(city)
    return bool(prefix and re.fullmatch(prefix + r'\d{2}', str(code)))
AGES = ['10대', '20대', '30대', '40대', '50대', '60대 이상']
SEXES = ['남성', '여성']
DAYS = ['월', '화', '수', '목', '금', '토', '일']
DAY_COLS = ['FLOW_POP_CNT_' + d for d in ['MON', 'TUS', 'WED', 'THU', 'FRI', 'SAT', 'SUN']]
HOUR_COLS = [f'TMST_{h:02}' for h in range(24)]
AGE_COLS = {f'{prefix}_FLOW_POP_CNT_{age}': (label, sex)
            for prefix, sex in [('MAN', '남성'), ('WMAN', '여성')]
            for age, label in zip(['10G', '20G', '30G', '40G', '50G', '60GU'], AGES)}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def clean_frame(frame, columns, codes):
    """블록 접두 7자리와 제공 지역코드표를 연결. 좌표도 셀 키에 포함한다."""
    required = ['STD_YM', 'BLOCK_CD', 'X_COORD', 'Y_COORD', *columns]
    if not set(required).issubset(frame.columns):
        raise ValueError('원자료 필수 열 누락')
    frame = frame.copy()
    frame['code'] = frame.BLOCK_CD.astype(str).str[:7]
    frame = frame[frame.code.str.startswith(tuple(CITY_PREFIXES.values()))].copy()
    if frame.empty or not set(frame.code).issubset(codes):
        raise ValueError('지원 지역의 지역코드 매핑을 확인하세요.')
    if frame.duplicated(['STD_YM', 'BLOCK_CD', 'X_COORD', 'Y_COORD']).any():
        raise ValueError('월·블록·좌표 중복: 합산하지 않습니다.')
    values = frame[list(columns)].apply(pd.to_numeric, errors='raise')
    if not np.isfinite(values.to_numpy()).all() or (values < 0).any().any():
        raise ValueError('유동인구 값에 누락·음수·비유한 값이 있습니다.')
    if not np.isfinite(frame[['X_COORD', 'Y_COORD']].to_numpy(dtype=float)).all():
        raise ValueError('좌표 누락')
    frame[list(columns)] = values
    frame['month'] = pd.to_datetime(frame.STD_YM.astype(str), format='%Y%m', errors='raise').dt.strftime('%Y-%m')
    return frame


def aggregate_age(frame, names):
    records = []
    for (month, code), part in frame.groupby(['month', 'code'], sort=True):
        totals = part[list(AGE_COLS)].sum()
        total = float(totals.sum())
        previous = (pd.Period(month, freq='M') - 1).strftime('%Y-%m')
        old = frame[(frame.month == previous) & (frame.code == code)]
        keys = ['BLOCK_CD', 'X_COORD', 'Y_COORD']
        # 같은 격자끼리 비교해서 월별 관측 범위 변화와 구분한다.
        matched = part.merge(old, on=keys, suffixes=('_new', '_old'), validate='one_to_one')
        for col, (age, sex) in AGE_COLS.items():
            before = float(matched[col + '_old'].mean()) if len(matched) else None
            after = float(matched[col + '_new'].mean()) if len(matched) else None
            change = (after / before - 1) * 100 if before is not None and before > 0 else None
            records.append(dict(month=month, code=code, district=names[code], age=age, sex=sex,
                                value=float(totals[col]), mean=float(totals[col] / len(part)),
                                share=float(totals[col] / total * 100) if total else None,
                                points=len(part), matched_points=len(matched), previous_points=len(old),
                                matched_before=before, matched_after=after, change_pct=change))
    return records


def build_snapshot(source_dir=ROOT / 'data/processed'):
    mapping = ROOT / 'backend/resources/data/flow_region_codes.csv'
    regions = pd.read_csv(mapping, dtype=str)
    names = dict(regions[regions.city.isin(CITY_PREFIXES)][['region_code', 'region_name']].itertuples(index=False, name=None))
    sources = {name: source_dir / (name + '.csv') for name in ['age_pop', 'wkdy_pop', 'time_pop']}
    hashes = {name: digest(path) for name, path in sources.items()}
    hashes['region_codes'] = digest(mapping)
    identity = hashlib.sha256(json.dumps([VERSION, hashes], sort_keys=True).encode()).hexdigest()
    age = clean_frame(pd.read_csv(sources['age_pop'], dtype={'BLOCK_CD': str}), list(AGE_COLS), names)
    groups = aggregate_age(age, names)
    activity = {}
    for kind, columns in [('wkdy_pop', DAY_COLS), ('time_pop', HOUR_COLS)]:
        frame = clean_frame(pd.read_csv(sources[kind], dtype={'BLOCK_CD': str}), columns, names)
        for (month, code), part in frame.groupby(['month', 'code']):
            entry = activity.setdefault(month + '/' + code, dict(month=month, code=code))
            # 데이터 축을 교차시키지 않고 각 자료 안에서 별도로 집계한다.
            values = part[columns].sum().to_numpy(dtype=float)
            if kind == 'wkdy_pop':
                denominator = float(values.mean())
                entry['weekdays'] = activity_values(DAYS, values, denominator)
                entry['weekday_points'] = len(part)
            else:
                denominator = float(values.max())
                labels = [f'{hour}시' for hour in range(len(values))]
                entry['hours'] = activity_values(labels, values, denominator)
                entry['hour_points'] = len(part)
    result = dict(version=VERSION, run_id=identity, source_files=hashes, months=sorted(age.month.unique()),
                  districts=[dict(code=k, name=v, city=next(city for city in CITY_PREFIXES if belongs_to_city(k, city))) for k, v in names.items()], ages=AGES, sexes=SEXES,
                  groups=groups, activity=list(activity.values()),
                  mapping='BLOCK_CD 앞 7자리 → backend/resources/data/flow_region_codes.csv (강남구 22동 · 춘천시 25개 읍·면·동)',
                  unit='원자료 유동량', note='추정 유동량의 공간 집계이며 고유 인원·거주 인구·고립 인구가 아닙니다.')
    return result


def activity_values(labels, values, denominator):
    """요일은 평균=100, 시간대는 최대=100으로 표시합니다. 기준이 0이면 지수는 비웁니다."""
    result = []
    for label, value in zip(labels, values):
        index = None
        if denominator:
            index = float(value / denominator * 100)
        result.append(dict(label=label, value=float(value), index=index))
    return result


def publish(snapshot):
    from backend.db.analysis_repository import get_engine
    with get_engine().begin() as conn:
        conn.execute(text('''CREATE TABLE IF NOT EXISTS db1.group_flow_snapshots (
            run_id text PRIMARY KEY, version text NOT NULL, payload jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now())'''))
        conn.execute(text('''INSERT INTO db1.group_flow_snapshots(run_id,version,payload)
            VALUES (:id,:version,CAST(:payload AS jsonb)) ON CONFLICT (run_id) DO NOTHING'''),
            dict(id=snapshot['run_id'], version=VERSION, payload=json.dumps(snapshot, ensure_ascii=False, allow_nan=False)))
    _database_payload.cache_clear()


@lru_cache(maxsize=3)
def _database_payload(run_id):
    from backend.db.analysis_repository import get_engine
    with get_engine().connect() as conn:
        return conn.execute(text('SELECT payload FROM db1.group_flow_snapshots WHERE run_id=:id'), {'id': run_id}).scalar_one()


def load_snapshot():
    """실제 DB1을 읽는다. 연결 실패 시 조용히 CSV/예시로 대체하지 않는다."""
    from backend.db.analysis_repository import get_engine
    with get_engine().connect() as conn:
        run_id = conn.execute(text('SELECT run_id FROM db1.group_flow_snapshots ORDER BY created_at DESC, run_id LIMIT 1')).scalar()
    if not run_id:
        raise ValueError('집단별 유동인구를 먼저 적재하세요: python -m db.group_repository --build --publish')
    return _database_payload(run_id)


def catalogue(city, month, snapshot=None):
    """선택 월의 그룹 목록을 복사하여 캐시 원본이 화면 처리로 바뀌지 않게 합니다."""
    data = snapshot if snapshot is not None else load_snapshot()
    city_groups = [row for row in data['groups'] if belongs_to_city(row['code'], city)]
    districts = [row for row in data['districts'] if belongs_to_city(row['code'], city)]
    return dict(source='DB1 · 집단별 유동인구', runId=data['run_id'],
                months=sorted({row['month'] for row in city_groups}), ages=AGES, sexes=SEXES,
                groups=deepcopy([row for row in city_groups if row['month'] == month]),
                districts=deepcopy(districts), note=data['note'], mapping=data['mapping'], telecomAvailable=False)


def group_detail(context, snapshot=None):
    """같은 연령·성별의 월별 추이, 다른 동 비교, 선택 동의 구성비를 나눠 조회합니다."""
    data = snapshot if snapshot is not None else load_snapshot()
    if context.get('city') not in CITY_PREFIXES or context.get('age') not in AGES or context.get('sex') not in SEXES:
        raise ValueError('유효한 지역·연령대·성별을 선택하세요.')
    code = str(context.get('code', ''))
    if not belongs_to_city(code, context['city']):
        raise ValueError('행정동 코드가 올바르지 않습니다.')
    series = []
    peers = []
    composition = []
    current = None
    for row in data['groups']:
        if not belongs_to_city(row['code'], context['city']):
            continue
        same_group = row['age'] == context['age'] and row['sex'] == context['sex']
        same_month = row['month'] == context['month']
        if row['code'] == code and same_group and row['month'] <= context['month']:
            series.append(row)
            if same_month and current is None:
                current = row
        if same_month and same_group:
            peers.append(row)
        if same_month and row['code'] == code:
            composition.append(row)
    if current is None:
        raise ValueError('선택한 집단·월의 자료가 없습니다.')
    regional = next((r for r in data['activity'] if r['month'] == context['month'] and r['code'] == code), {})
    by_month = {r['month']: r for r in series}
    # 자료가 없는 중간 월도 남겨 그래프가 누락 구간을 건너 이어지지 않게 합니다.
    timeline = []
    for period in pd.period_range(min(by_month), context['month'], freq='M'):
        month = period.strftime('%Y-%m')
        row = by_month.get(month, {'month': month, 'mean': None})
        timeline.append(deepcopy(row))
    return dict(current=deepcopy(current), series=timeline,
                peers=deepcopy(peers), composition=deepcopy(composition), activity=deepcopy(regional),
                source='DB1 · age_pop / wkdy_pop / time_pop', runId=data['run_id'],
                note=data['note'], mapping=data['mapping'], sourceFiles=data['source_files'], telecomAvailable=False)


def regional_context(context):
    """DB1 동별 분석을 별도 scope로 전달한다. 집단 신호로 재명명하지 않는다."""
    if context['city'] != '강남구':
        return dict(scope='district', structure=None, detection=None)
    from backend.db.analysis_repository import get_engine
    with get_engine().connect() as conn:
        structure = conn.execute(text('''SELECT cluster_type, payload, source_file FROM db1.latest_region_typology
            WHERE adm_cd=:code'''), {'code': context['code']}).mappings().first()
        detection = conn.execute(text('''SELECT communication_signal, mobility_signal, payload, source_file
            FROM db1.analysis2_detections WHERE admin_dong_code=:code
            AND CAST(reference_month AS text) LIKE :month ORDER BY created_at DESC LIMIT 1'''),
            {'code': context['code'], 'month': context['month'] + '%'}).mappings().first()
    return dict(scope='district', structure=dict(structure) if structure else None,
                detection=dict(detection) if detection else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    if args.build:
        data = build_snapshot()
        SNAPSHOT.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    else:
        data = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    if args.publish:
        publish(data)
    print(json.dumps(dict(run_id=data['run_id'], groups=len(data['groups']), months=data['months'], published=args.publish)))


if __name__ == '__main__':
    main()

import csv
import math
from .readers import TELECOM


def validate(rows, dates, areas, columns):
    errors = []
    expected = {(m, c) for m in dates for c in areas}
    actual = [(r['date'], r['행정동코드']) for r in rows]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        errors.append('월×동 패널 누락/중복/초과')
    for row in rows:
        context = f"{row['date']}/{row['행정동코드']}"
        if set(row) != set(columns):
            errors.append(f'{context} 출력 열 불일치')
        for col in columns[3:-1]:
            val = row[col]
            if not isinstance(val, (float, int)) or not math.isfinite(val) or val < 0:
                errors.append(f'{context}/{col} 숫자 범위 오류')
            if col.endswith(('_ratio', '_rate')) and not 0 <= val <= 1:
                errors.append(f'{context}/{col} 0~1 범위 오류')
            if col in TELECOM and val <= 0:
                errors.append(f'{context}/{col} Analysis2 로그 입력은 양수 필요')
        if any(row[c] > row['days_in_month'] for c in ['rain_days', 'snow_days']):
            errors.append(f'{context} 날씨 일수가 월 일수 초과')
    return {'status': 'FAIL' if errors else 'PASS', 'rows': len(rows), 'columns': len(columns), 'expected_rows': len(expected), 'errors': errors}


def compare(rows, path, columns, tolerance):
    if not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool) or not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('비교 허용오차는 유한한 비음수 필요')
    with open(path, encoding='utf-8-sig', newline='') as stream:
        reference = list(csv.DictReader(stream))
    ref = {(r['date'], str(r['행정동코드'])): r for r in reference}
    keys = {(r['date'], str(r['행정동코드'])) for r in rows}
    if len(ref) != len(reference) or keys != set(ref):
        raise ValueError('비교 CSV 월×동 키가 출력과 불일치 또는 중복')
    numeric = columns[3:-1]
    stats = {c: {'max_absolute_difference': 0.0, 'mismatch_count': 0} for c in numeric}
    text_mismatches = []
    for row in rows:
        other = ref[(row['date'], row['행정동코드'])]
        for col in numeric:
            value = float(other[col])
            if not math.isfinite(value):
                raise ValueError(f'비교 CSV 비유한 값: {col}')
            diff = abs(row[col] - value)
            stats[col]['max_absolute_difference'] = max(stats[col]['max_absolute_difference'], diff)
            stats[col]['mismatch_count'] += diff > tolerance
        if row['행정동'] != other['행정동'] or str(row['interest_structural_issue']).lower() != other['interest_structural_issue'].lower():
            text_mismatches.append([row['date'], row['행정동코드']])
    mismatch = any(s['mismatch_count'] for s in stats.values()) or bool(text_mismatches)
    return {'status': 'DIFFERENT' if mismatch else 'MATCH', 'absolute_tolerance': tolerance, 'numeric_columns': stats, 'name_or_flag_mismatches': text_mismatches,
            'interpretation': '차이가 있으면 원본 버전·집계 규칙·날씨 출처를 확인하세요. 비교표의 행동값은 계산에 사용하지 않았습니다.'}

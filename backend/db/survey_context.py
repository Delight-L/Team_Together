"""Read-only annual district/age context exported from DB1; never a dong isolation rate."""
import json
import csv
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / 'data/processed/survey_dashboard.json'
FULL_SOURCE = Path(__file__).resolve().parents[2] / 'pipelines/db1/outputs/integrated/v_survey_annual.csv'
AGES = {'20대': '20s', '30대': '30s', '40대': '40s', '50대': '50s', '60대 이상': '60plus'}


def survey_for(context, snapshot=None):
    if context.get('city') != '강남구' or context.get('age') not in AGES:
        return None
    if snapshot is None:
        if not SOURCE.is_file():
            return None
        snapshot = json.loads(SOURCE.read_text(encoding='utf-8'))
    year = int(context['month'][:4])
    rows = [r for r in snapshot['rows'] if r['district'] == 'gangnam'
            and r['age_band'] == AGES[context['age']] and r['year'] <= year
            and r['metric'] == 'no_support_emotion' and r['unit'] == 'proportion']
    if not rows:
        return None
    row = max(rows, key=lambda r: r['year'])
    return {**row, 'scope': 'district_age', 'mode': 'annual_retrospective_context',
            'source': 'DB1 · 서울서베이',
            'note': '강남구 연령별 연간 조사 참고값이며 동별 고립률이나 탐지 입력이 아닙니다. 공표 시점 기준의 당시 가용값을 뜻하지 않습니다.'}


def _annual_rows(snapshot=None):
    """Return the complete DB1 export used for detail answers.

    The dashboard JSON intentionally contains only the one card metric.  The
    complete annual export is packaged with the DB1 pipeline and is the source
    of truth for questions about metrics that are not visible as cards.
    """
    if snapshot is not None:
        return snapshot.get('rows', [])
    if not FULL_SOURCE.is_file():
        return []
    # The DB1 CSV is Excel-compatible and may carry a UTF-8 BOM in its first
    # header; utf-8-sig keeps the `survey` field name stable in either form.
    with FULL_SOURCE.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def survey_metrics_for(context, snapshot=None):
    """Return selected-age (or 15+ default) Gangnam and Seoul survey values.

    This deliberately keeps the district-level, annual scope visible so callers
    cannot present the values as dong-level measurements or individual scores.
    """
    if context.get('city') != '강남구':
        return None
    try:
        selected_year = int(str(context.get('month', ''))[:4])
    except ValueError:
        return None
    # The regional-context screen has no age selector.  Its survey questions
    # should still return the published 15세 이상 전체 values rather than
    # repeating a generic instruction to choose an age.
    requested_age = context.get('age')
    age_band = AGES.get(requested_age, 'all15plus')
    age_label = requested_age if requested_age in AGES else '15세 이상 전체'
    rows = _annual_rows(snapshot)
    normalized = []
    for row in rows:
        if row.get('survey') != 'seoul_survey' or row.get('age_band') != age_band:
            continue
        try:
            year = int(row.get('year'))
        except (TypeError, ValueError):
            continue
        if year <= selected_year and row.get('district') in {'gangnam', 'seoul'}:
            normalized.append({**row, 'year': year, 'value': _number(row.get('value')),
                               'n_valid': _number(row.get('n_valid')),
                               'effective_n': _number(row.get('effective_n'))})
    gangnam = [row for row in normalized if row['district'] == 'gangnam']
    if not gangnam:
        return None
    survey_year = max(row['year'] for row in gangnam)
    values = {}
    for metric in sorted({row.get('metric') for row in gangnam if row['year'] == survey_year}):
        district_row = next((row for row in gangnam if row['year'] == survey_year and row.get('metric') == metric), None)
        seoul_row = next((row for row in normalized if row['district'] == 'seoul' and row['year'] == survey_year and row.get('metric') == metric), None)
        if district_row:
            values[metric] = {'gangnam': district_row, 'seoul': seoul_row}
    return {'year': survey_year, 'age': age_label, 'metrics': values,
            'scope': 'district_age', 'mode': 'annual_retrospective_context',
            'source': 'DB1 · 서울서베이',
            'note': '강남구 연령별 연간 조사 참고값이며 동별 고립률이나 탐지 입력이 아닙니다. 공표 시점 기준의 당시 가용값을 뜻하지 않습니다.'}

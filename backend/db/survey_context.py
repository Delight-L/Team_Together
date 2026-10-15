"""Read-only annual district/age context exported from DB1; never a dong isolation rate."""
import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / 'data/processed/survey_dashboard.json'
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

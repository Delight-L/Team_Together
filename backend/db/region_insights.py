"""Read-only Analysis1/3 and survey aggregates for the regional context screen."""

import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / 'data/processed/region_insights.json'


def load_region_insights(city):
    if city != '강남구':
        return {
            'city': city,
            'typologies': [],
            'consumption': [],
            'surveys': [],
            'scope': 'regional_context',
        }
    if not SOURCE.is_file():
        raise ValueError('지역 유형·소비·조사 자료가 아직 연결되지 않았습니다.')
    return json.loads(SOURCE.read_text(encoding='utf-8'))

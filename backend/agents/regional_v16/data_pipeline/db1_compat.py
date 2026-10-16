"""파이프라인 산출물(`pipelines/db1`의 db1.sqlite)과 v16 엔진의 스키마 차이를 메우는 변환.

v16 월별 작업기가 만드는 DB에는 있고, 파이프라인 산출물에는 없는 것
- pipeline_state : 작업기의 «갱신 완료» 표지. 산출물에는 없습니다.
- ctx_weather    : 작업기가 월마다 만드는 날씨 보조 자료(`weather_context`의 결과). 산출물에는 같은 정보가
                   ctx_weather_month(월별 값)와 ctx_weather_window(기준월별 3개월 관측기간)로 나뉘어 있습니다.

이 모듈은 산출물을 고치지 않고, 게시(PostgreSQL)·측정 준비 때 작업기가 만드는 모양으로 **변환한 값**을 만듭니다.
"""
from __future__ import annotations

import json
import sqlite3

SNOW_NOTE = 'Legacy feature reproduction uses zero; user-facing context preserves the missing symbol.'


def table_names(source: sqlite3.Connection) -> set[str]:
    return {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}


def weather_rows(source: sqlite3.Connection) -> list[tuple[str, str]] | None:
    """(기준월 날짜, payload JSON 문자열) 목록. 변환에 필요한 두 테이블이 없으면 None.

    payload는 작업기의 `weather_context`와 같은 모양입니다.
      label_weather            기준월의 값
      observation_month_weather 관측기간(3개월) 각 달의 값 — 챗봇 답변이 읽는 것
    한계: 산출물의 월별 값에는 «눈 기록이 '-'(확인 불가)였는지» 정보가 없어 snow_status를 모두 observed로 둡니다.
    """
    if not {'ctx_weather_month', 'ctx_weather_window'} <= table_names(source):
        return None
    monthly = {period: json.loads(payload)
               for period, payload in source.execute('SELECT period, payload_json FROM ctx_weather_month')}

    def month_values(month: str) -> dict:
        value = monthly.get(month)
        if value is None:
            return {'month': month, 'rainfall_mm': None, 'rain_days': None, 'snow_days': None, 'status': 'missing'}
        return {'month': month, 'rainfall_mm': value.get('rainfall_mm'), 'rain_days': value.get('rain_days'),
                'snow_days': value.get('snow_days'), 'snow_status': 'observed'}

    rows = []
    for date, payload in source.execute('SELECT date, payload_json FROM ctx_weather_window ORDER BY date'):
        window = json.loads(payload)
        label = window.get('label_month') or date[:7]
        converted = {
            'label_weather': month_values(label),
            'observation_month_weather': [month_values(month) for month in window.get('observation_months', [])],
            'scope': 'Seoul_city_shared_context', 'legacy_snow_dash_to_zero': True,
            'snow_dash_explanation': SNOW_NOTE, 'signal_rule_uses_weather': False,
            'converted_from': 'ctx_weather_month + ctx_weather_window',
        }
        rows.append((date, json.dumps(converted, ensure_ascii=False)))
    return rows

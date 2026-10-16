"""DB1 SQLite 공개본과 같은 테이블 구성을 가진 작은 합성 DB. 저장소 계약 테스트용입니다(실제 자료 아님)."""
import json
import sqlite3
from pathlib import Path

SCHEMA = '''
CREATE TABLE pipeline_state(id INTEGER PRIMARY KEY, payload_json TEXT NOT NULL);
CREATE TABLE a1_context(adm_cd TEXT, adm_nm TEXT, period TEXT, cluster INTEGER, cluster_type TEXT,
                        feature_json TEXT, effective_from TEXT, model_version TEXT);
CREATE TABLE a1_input(adm_cd TEXT, period TEXT, input_json TEXT);
CREATE TABLE db1_run(analysis TEXT, period TEXT, metadata_json TEXT);
CREATE TABLE a2_detection(date TEXT, adm_cd TEXT, result_json TEXT, model_version TEXT);
CREATE TABLE a2_evidence(date TEXT, adm_cd TEXT, evidence_json TEXT);
CREATE TABLE a2_feature(date TEXT, adm_cd TEXT, feature_json TEXT);
CREATE TABLE a2_age_detection(age_scheme TEXT, age_band TEXT, date TEXT, adm_cd TEXT, result_json TEXT);
CREATE TABLE a3a_feature(period TEXT, adm_cd TEXT, age TEXT, domain TEXT, payload_json TEXT, PRIMARY KEY(period, adm_cd, age, domain));
CREATE TABLE a3a_comparison(period TEXT, adm_cd TEXT, age TEXT, domain TEXT, payload_json TEXT, PRIMARY KEY(period, adm_cd, age, domain));
CREATE TABLE a3a_quarter_summary(period TEXT, adm_cd TEXT, payload_json TEXT);
CREATE TABLE a3b_feature(period TEXT, district TEXT, age TEXT, domain TEXT, payload_json TEXT);
CREATE TABLE a3b_month_summary(period TEXT, district TEXT, payload_json TEXT);
CREATE TABLE ctx_weather(date TEXT PRIMARY KEY, payload_json TEXT);
'''
DONGS = {'1123051': '삼성1동', '1123052': '역삼1동', '1123074': '일원2동'}
MONTHS = ['2025-07-01', '2025-08-01', '2025-09-01', '2025-10-01']


# 월별 날씨(강수일수, 강수량, 적설일수). 관측기간(기준월의 앞 세 달)을 채울 만큼 둡니다.
WEATHER = {'2025-04': (4.0, 80.5, 0.0), '2025-05': (6.0, 120.0, 0.0), '2025-06': (9.0, 210.4, 0.0),
           '2025-07': (10.0, 293.9, 0.0), '2025-08': (12.0, 290.3, 0.0), '2025-09': (13.0, 370.7, 0.0)}


def previous_months(label, count=3):
    year, month = int(label[:4]), int(label[5:7])
    result = []
    for step in range(count, 0, -1):
        index = year * 12 + month - 1 - step
        result.append(f'{index // 12:04d}-{index % 12 + 1:02d}')
    return result


def weather_payload(date):
    """v16 작업기(`weather_context`)가 ctx_weather에 넣는 모양."""
    def month_values(month):
        if month not in WEATHER:
            return {'month': month, 'rainfall_mm': None, 'rain_days': None, 'snow_days': None, 'status': 'missing'}
        rain_days, rainfall, snow = WEATHER[month]
        return {'month': month, 'rainfall_mm': rainfall, 'rain_days': rain_days, 'snow_days': snow, 'snow_status': 'observed'}
    label = date[:7]
    return {'label_weather': month_values(label),
            'observation_month_weather': [month_values(m) for m in previous_months(label)],
            'scope': 'Seoul_city_shared_context', 'legacy_snow_dash_to_zero': True,
            'snow_dash_explanation': 'Legacy feature reproduction uses zero; user-facing context preserves the missing symbol.',
            'signal_rule_uses_weather': False}


def _detection(date, code, name, index):
    # 삼성1동은 8월에 통신 신호, 10월에 이동 신호. 나머지는 신호 없음.
    comm = name == '삼성1동' and date == '2025-08-01'
    mob = name == '삼성1동' and date == '2025-10-01'
    return {'date': date, '행정동': name, '행정동코드': code, 'communication_signal': comm, 'mobility_signal': mob,
            'combined_signal': False, 'any_signal': comm or mob, 'signal_type': '',
            'call_contacts': 10.0 + index, 'text_contacts': 5.0 + index,
            'weekday_move_count': 20.0 + index, 'weekend_move_count': 8.0 + index,
            'call_contacts_rz': -2.5 if comm else 0.1 * index, 'text_contacts_rz': -2.2 if comm else 0.0,
            'weekday_move_count_rz': -3.0 if mob else 0.2, 'weekend_move_count_rz': -2.4 if mob else 0.1,
            'call_contacts_log_change': -0.12 if comm else 0.01, 'text_contacts_log_change': -0.10 if comm else 0.0,
            'weekday_move_count_log_change': -0.15 if mob else 0.02, 'weekend_move_count_log_change': -0.09 if mob else 0.01}


def build(path: Path) -> Path:
    path = Path(path)
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.execute('INSERT INTO pipeline_state VALUES(1,?)', (json.dumps({'status': 'ready', 'waiting_for': {'month': '2025-11'}}),))
    for index, (code, name) in enumerate(DONGS.items()):
        con.execute('INSERT INTO a1_context VALUES(?,?,?,?,?,?,?,?)',
                    (code, name, '2025H2', index % 2, f'유형{index % 2}',
                     json.dumps({'cluster': index % 2, 'elderly_living_alone_rate_65plus': 0.1 * (index + 1)}),
                     '2025-07-01', 'analysis1_2025H2_elder_v2'))
        con.execute('INSERT INTO a1_input VALUES(?,?,?)', (code, '2025H2', json.dumps(
            {'dong_name': name, 'hh_1_ratio': 0.3, 'hh_2_ratio': 0.25, 'age_60_plus_ratio': 0.2,
             'disability_ratio': 0.04, 'livelihood_recipient_ratio': 0.02})))
        for month_index, date in enumerate(MONTHS):
            detection = _detection(date, code, name, month_index)
            con.execute('INSERT INTO a2_detection VALUES(?,?,?,?)', (date, code, json.dumps(detection, ensure_ascii=False), 'v1'))
            con.execute('INSERT INTO a2_feature VALUES(?,?,?)', (date, code, json.dumps(detection, ensure_ascii=False)))
            if detection['any_signal']:
                con.execute('INSERT INTO a2_evidence VALUES(?,?,?)', (date, code, json.dumps(
                    dict(detection, signal_status='New'), ensure_ascii=False)))
            for band in ('20s', '60plus'):
                local = dict(detection, adjacent_signal_run=2 if detection['any_signal'] else 0,
                             **{key.replace('_rz', '_local_rz'): value for key, value in detection.items() if key.endswith('_rz')})
                con.execute('INSERT INTO a2_age_detection VALUES(?,?,?,?,?)',
                            ('service', band, date, code, json.dumps(local, ensure_ascii=False)))
        con.execute('INSERT INTO a3a_quarter_summary VALUES(?,?,?)', ('2025Q3', code, json.dumps({'domain': '전체', 'daily_count': 100 + index})))
        con.execute('INSERT INTO a3a_feature VALUES(?,?,?,?,?)', ('2025Q3', code, '20대', '음식', json.dumps(
            {'adm_cd': code, 'period': '2025Q3', 'age': '20대', 'domain': '음식', 'daily_count': 50.0 + index})))
        con.execute('INSERT INTO a3a_feature VALUES(?,?,?,?,?)', ('2025Q2', code, '20대', '음식', json.dumps(
            {'adm_cd': code, 'period': '2025Q2', 'age': '20대', 'domain': '음식', 'daily_count': 40.0 + index})))
        con.execute('INSERT INTO a3a_comparison VALUES(?,?,?,?,?)', ('2025Q3', code, '20대', '음식', json.dumps(
            {'adm_cd': code, 'period': '2025Q3', 'age': '20대', 'domain': '음식', 'qoq_daily_change_pct': 25.0,
             'qoq_matched_industry_count': 3})))
        # 기본키 순서(교육 < 음식)와 저장 순서(음식 먼저)가 다르게 넣어, 정렬이 명시됐는지 확인할 수 있게 함
        con.execute('INSERT INTO a3a_comparison VALUES(?,?,?,?,?)', ('2025Q3', code, '20대', '교육', json.dumps(
            {'adm_cd': code, 'period': '2025Q3', 'age': '20대', 'domain': '교육', 'qoq_daily_change_pct': 5.0,
             'qoq_matched_industry_count': 2})))
    for date in MONTHS:
        month = date[:7]
        con.execute('INSERT INTO a3b_month_summary VALUES(?,?,?)', (month, '11680', json.dumps({'domain': '전체', 'daily_count': 900})))
        con.execute('INSERT INTO a3b_feature VALUES(?,?,?,?,?)', (month, '11680', '20대', '음식', json.dumps(
            {'period': month, 'age': '20대', 'domain': '음식', 'district': '11680', 'daily_count': 300.0})))
        con.execute('INSERT INTO ctx_weather VALUES(?,?)', (date, json.dumps(weather_payload(date), ensure_ascii=False)))
    con.execute('INSERT INTO db1_run VALUES(?,?,?)', ('analysis1', '2025H2', json.dumps({'retrospective_context': True})))
    con.commit()
    con.close()
    return path


def build_pipeline_style(path: Path) -> Path:
    """`pipelines/db1`이 내놓는 모양: pipeline_state·ctx_weather가 없고, 날씨는 ctx_weather_month·ctx_weather_window에 있음."""
    path = build(path)
    con = sqlite3.connect(path)
    con.executescript('''
        DROP TABLE pipeline_state;
        DROP TABLE ctx_weather;
        CREATE TABLE ctx_weather_month(period TEXT PRIMARY KEY, payload_json TEXT NOT NULL);
        CREATE TABLE ctx_weather_window(date TEXT PRIMARY KEY, payload_json TEXT NOT NULL);
    ''')
    for month, (rain_days, rainfall, snow) in WEATHER.items():
        con.execute('INSERT INTO ctx_weather_month VALUES(?,?)', (month, json.dumps(
            {'period': month, 'rain_days': rain_days, 'rainfall_mm': rainfall, 'snow_days': snow})))
    for date in MONTHS:
        observation = previous_months(date[:7])
        con.execute('INSERT INTO ctx_weather_window VALUES(?,?)', (date, json.dumps(
            {'label_month': date[:7], 'observation_months': observation,
             'monthly_values': [{'period': m, 'rain_days': WEATHER[m][0], 'rainfall_mm': WEATHER[m][1], 'snow_days': WEATHER[m][2]}
                                for m in observation if m in WEATHER]})))
    con.commit()
    con.close()
    return path

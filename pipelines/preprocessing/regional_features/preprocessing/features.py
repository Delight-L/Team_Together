import calendar
import csv
from datetime import date
from .readers import TELECOM, INTEREST, number


def months(start, end):
    a, b = date.fromisoformat(start + '-01'), date.fromisoformat(end + '-01')
    if a > b:
        raise ValueError('시작월이 종료월보다 늦음')
    result = []
    while a <= b:
        result.append(a.isoformat())
        a = date(a.year + (a.month == 12), a.month % 12 + 1, 1)
    return result


def load_weather(path):
    weather = {}
    with open(path, encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            key = row['date']
            if key in weather:
                raise ValueError(f'날씨 월 중복: {key}')
            weather[key] = {col: number(row[col], f'weather/{key}/{col}') for col in ['rain_days', 'rainfall_mm', 'snow_days']}
    return weather


def assemble(data, dates, areas, weather):
    missing = [f'{m}/{kind}/{c}' for m in dates for kind in ['telecom', 'interest'] for c in areas if c not in data.get((m, kind), {})]
    missing += [f'{m}/weather' for m in dates if m not in weather]
    if missing:
        raise ValueError('필수 월·동·날씨 누락: ' + ', '.join(missing))
    result = []
    for month in dates:
        y, m, _ = map(int, month.split('-'))
        days = calendar.monthrange(y, m)[1]
        weekdays = sum(date(y, m, d).weekday() < 5 for d in range(1, days + 1))
        for code, name in sorted(areas.items()):
            t, i = data[(month, 'telecom')][code], data[(month, 'interest')][code]
            row = {'date': month, '행정동코드': code, '행정동': name}
            for out, (_, _, ratio) in TELECOM.items():
                if t[out + '_weight'] <= 0 or t['population'] <= 0:
                    raise ValueError(f'통신 분모 0: {month}/{code}/{out}')
                row[out] = t[out + '_sum'] / t[out + '_weight']
                if ratio:
                    row[ratio] = t[out + '_weight'] / t['population']
            if i['households'] <= 0:
                raise ValueError(f'관심집단 분모 0: {month}/{code}')
            for out in INTEREST:
                row[out] = i[out] / i['households']
            row.update(weather[month])
            row.update(days_in_month=days, weekday_days=weekdays, weekend_days=days-weekdays,
                       interest_structural_issue=code == '1123074' and month >= '2024-01-01')
            result.append(row)
    return result

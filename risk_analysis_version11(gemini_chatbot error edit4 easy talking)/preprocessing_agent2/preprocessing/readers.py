import hashlib
import json
import math
import re
import zipfile
import openpyxl

TELECOM = {
    'call_contacts': ('평균 통화대상자 수', None, None),
    'text_contacts': ('평균 문자대상자 수', None, None),
    'weekday_move_count': ('평일 총 이동 횟수', '평일 총 이동 횟수 미추정 인구수', 'weekday_count_est_ratio'),
    'weekend_move_count': ('휴일 총 이동 횟수 평균', '휴일 이동 미추정 인구수', 'weekend_count_est_ratio'),
    'weekday_move_distance': ('평일 총 이동 거리 합계', '평일 총 이동 거리 미추정 인구수', 'weekday_distance_est_ratio'),
    'weekend_move_distance': ('휴일 총 이동 거리 합계', '휴일 총 이동 거리 미추정 인구수', 'weekend_distance_est_ratio'),
}
INTEREST = {'comm_low_rate': '커뮤니케이션이 적은 집단', 'weekday_outing_low_rate': '평일 외출이 적은 집단', 'weekend_outing_low_rate': '휴일 외출이 적은 집단'}


def number(value, context):
    if isinstance(value, bool) or value is None or isinstance(value, str) and not value.strip():
        raise ValueError(f'숫자 누락/오류: {context}: {value!r}')
    try:
        n = float(value)
    except (ValueError, TypeError):
        raise ValueError(f'숫자 오류: {context}: {value!r}') from None
    if not math.isfinite(n) or n < 0:
        raise ValueError(f'유한한 비음수 필요: {context}: {value!r}')
    return n


def month_from_name(name):
    matches = set(re.findall(r'(?<!\d)(20\d{2})[.\-_년 ]+(\d{1,2})(?:월|[.\-_ ]|$)', name))
    if len(matches) != 1:
        raise ValueError(f'기준월을 하나로 식별할 수 없음: {name}')
    y, m = next(iter(matches))
    if not 1 <= int(m) <= 12:
        raise ValueError(f'잘못된 기준월: {name}')
    return f'{y}-{int(m):02d}-01'


def read_workbook(path, name, areas, manifest, demographics=None, xlsx_limit=2147483648):
    month = month_from_name(name)
    with zipfile.ZipFile(path) as container:
        if sum(i.file_size for i in container.infolist()) > xlsx_limit or len(container.infolist()) > 10000:
            raise ValueError(f'XLSX 내부 압축 해제 크기/파일 수 제한 초과: {name}')
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    groups, fingerprints, demographic_keys = {}, [], set()
    kind = None
    try:
        for sheet in book:
            iterator = sheet.iter_rows(values_only=True)
            raw = next(iterator, ())
            headers = [re.sub(r'\s+', ' ', str(x)).strip() if x is not None else '' for x in raw]
            headers = [{'행정동': '행정동명', '총인구수': '총인구'}.get(x, x) for x in headers]
            if not any(headers):
                continue
            detected = 'telecom' if '평균 통화대상자 수' in headers else 'interest' if '커뮤니케이션이 적은 집단' in headers else None
            if detected is None:
                raise ValueError(f'알 수 없는 시트/필수 열 누락: {name}/{sheet.title}')
            if kind and kind != detected:
                raise ValueError(f'한 파일에 여러 자료 종류: {name}')
            kind = detected
            required = ['행정동코드', '자치구', '행정동명', '성별', '연령대']
            if kind == 'telecom':
                required += ['총인구'] + [x for v in TELECOM.values() for x in v[:2] if x]
            else:
                required += ['1인가구수'] + list(INTEREST.values())
            missing = set(required) - set(headers)
            if missing:
                raise ValueError(f'{name} 필수 열 누락: {sorted(missing)}')
            if any(headers.count(x) != 1 for x in required):
                raise ValueError(f'{name} 필수 열 중복')
            for lineno, values in enumerate(iterator, 2):
                row = dict(zip(headers, values))
                if str(row.get('자치구', '')).strip() != '강남구':
                    continue
                context = f'{name}/{sheet.title}:{lineno}'
                numeric_code = number(row['행정동코드'], context)
                if not numeric_code.is_integer():
                    raise ValueError(f'비정수 동코드: {context}')
                code = str(int(numeric_code))
                if code not in areas:
                    raise ValueError(f'알 수 없는 강남구 동코드: {code} ({context})')
                source_name = str(row['행정동명']).strip()
                allowed = {areas[code]}
                if code == '1123074':
                    allowed.add('개포3동')
                if source_name not in allowed:
                    raise ValueError(f'동코드/동명 불일치: {code}/{source_name} ({context})')
                if source_name != areas[code]:
                    manifest['name_normalizations'].add((month, code, source_name, areas[code]))
                demographic = (code, number(row['성별'], context), number(row['연령대'], context))
                if demographic in demographic_keys:
                    raise ValueError(f'인구 셀 중복: {demographic} ({context})')
                demographic_keys.add(demographic)
                normalized = {k: number(row[k], f'{context}/{k}') for k in required if k not in ['행정동코드', '자치구', '행정동명']}
                fingerprint = [code, *sorted(normalized.items())]
                fingerprints.append(json.dumps(fingerprint, ensure_ascii=False, separators=(',', ':')))
                g = groups.setdefault(code, {})
                def add(key, value):
                    g[key] = g.get(key, 0.0) + value
                if kind == 'telecom':
                    population = normalized['총인구']
                    add('population', population)
                    for out, (source, missing, ratio) in TELECOM.items():
                        weight = population - normalized[missing] if missing else population
                        if weight < 0:
                            raise ValueError(f'음수 유효 인구: {context}/{out}')
                        add(out + '_sum', normalized[source] * weight)
                        add(out + '_weight', weight)
                else:
                    add('households', normalized['1인가구수'])
                    for out, source in INTEREST.items():
                        add(out, normalized[source])
    finally:
        book.close()
    if not groups:
        raise ValueError(f'강남구 자료 없음: {name}')
    demographics = demographics or {'sex': [1, 2], 'age': list(range(20, 80, 5))}
    expected = {(code, float(sex), float(age)) for code in groups for sex in demographics['sex'] for age in demographics['age']}
    if demographic_keys != expected:
        raise ValueError(f'인구 셀 누락/초과: {name}; 누락={sorted(expected-demographic_keys)}; 초과={sorted(demographic_keys-expected)}')
    digest = hashlib.sha256('\n'.join(sorted(fingerprints)).encode()).hexdigest()
    return month, kind, groups, digest, len(fingerprints)

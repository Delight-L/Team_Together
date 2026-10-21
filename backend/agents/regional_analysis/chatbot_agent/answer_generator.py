"""Render exact calculations and separately scoped contextual evidence."""

from __future__ import annotations
import json
import math
import os
from .schemas import Evidence, QueryIntent
from .repository import CORE, AGE_LABEL
from .llm_intent_resolver import _api_key
from .observation_period import observation_period_text, observation_range_text

METRICS = dict(zip(CORE, ('통화 상대 수', '문자 상대 수', '평일 이동 횟수', '휴일 이동 횟수')))
COLUMN_NAMES = {
    'date': '관측기간',
    '행정동': '행정동',
    'signal_type': '신호 종류',
    '신호 건수': '신호 건수',
    'dong_name': '행정동',
    'cluster_type': '지역유형',
    'period': '자료 기간',
    'age_band': '연령',
    'call_contacts': '통화 상대 수',
    'text_contacts': '문자 상대 수',
    'weekday_move_count': '평일 이동 횟수',
    'weekend_move_count': '휴일 이동 횟수',
    'hh_1_ratio': '1인가구 비율',
    'hh_2_ratio': '2인가구 비율',
    'age_60_plus_ratio': '60세 이상 활동인구 비율',
    'disability_ratio': '장애인 비율',
    'livelihood_recipient_ratio': '기초생활수급자 비율',
    'assessment_status': '평가 상태',
    'communication_signal': '통신 신호',
    'mobility_signal': '이동 신호',
    'count': '관측 거래 건수',
    'daily_count': '일평균 거래 건수',
    'domain': '소비 분야',
    'age': '고객 연령',
    'compared_age_domain_cells': '비교 가능한 연령·분야 묶음',
    'below_prior_min_cells': '과거 동분기 최솟값 미만 묶음',
    'above_prior_max_cells': '과거 동분기 최댓값 초과 묶음',
    'observed_industries': '관측 업종 수',
    'change_pct': '과거 같은 분기 평균 대비 일평균 건수 변화율(%)',
}
SIGNAL_LABEL = {
    'communication': '통신',
    'mobility': '이동',
    'combined': '통신·이동 동시',
    'none': '미탐지',
}


def age_capabilities_answer():
    return (
        '네. 통화 상대 수·문자 상대 수·평일 이동 횟수·휴일 이동 횟수의 월별 값과 변화율을 '
        '20대·30대·40대·50대·60세 이상으로 나누어 비교할 수 있습니다. '
        '앞서 확인한 지역과 기간이 있으면 그 범위를 이어서 보여드립니다. '
        '각 결과는 기준월 직전 3개월 관측값이며, 변화율은 바로 앞 3개월 관측값과 비교합니다.'
    )


def consumption_criteria_answer():
    return (
        '어떤 소비 분야가 많이 늘었는지 순서대로 보여주는 데는 별도의 탐지 기준이 필요하지 않습니다. '
        '현재는 같은 업종의 일평균 거래 건수를 이전 분기 또는 이전 달과 비교합니다. '
        '다만 ‘이례적인 급증’으로 판정하려면 비교 기간·최소 거래량·계절성 등을 고려한 기준을 따로 정해야 합니다. '
        '지금 보여드리는 것은 증가율 비교이며, 공식 이상신호 판정은 아닙니다.'
    )


def provenance_answer():
    """Describe only source facts that are recorded in the DB1 configuration/code.

    The dashboard joins several source families.  A source URL or a physical
    raw-file name is intentionally omitted when the repository has no verified
    record for it; presenting a plausible-looking link would be misleading.
    """
    return '''이 화면은 하나의 원본 파일이 아니라, 카드별로 다른 원본을 가공해 보여줍니다.

통화·문자·평일·휴일 이동 변화는 서울 열린데이터광장의 [29개 통신정보](https://data.seoul.go.kr/dataList/OA-22267/F/1/datasetView.do) 월별 파일에서 만들었습니다. 원본에서 `행정동코드`, `행정동`, `성별`, `연령대`, `총인구수`, `평균 통화대상자 수`, `평균 문자대상자 수`, `평일 총 이동 횟수`, `휴일 총 이동 횟수 평균`과 각 이동 지표의 미추정 인구수를 읽습니다. 화면값은 성별·연령 셀을 인구 가중해 행정동(또는 선택 연령) 단위로 만든 값이고, 기준월은 직전 3개월 관측을 가리킵니다.

오른쪽 유동량·연령 비율과 가구 구성 카드는 프로젝트에 보관된 SKT 유동인구 원본 `flow_age_pop_YYYYMM`, `flow_time_pop_YYYYMM`, `flow_wkdy_pop_YYYYMM`과 서울시 등록인구·세대원수별 세대수 파일을 사용합니다. SKT 쪽에서는 연령별 유동량, 시간대별 유동량, 평일/휴일 유동량을 행정동 경계에 맞춰 집계하고, 등록인구에서는 연령 구성, 세대수에서는 1·2·3·4인 이상 가구 비율을 추출합니다. 이 저장소에는 해당 SKT 원본의 외부 다운로드 URL이나 공급자 배포 페이지가 기록돼 있지 않아, 링크를 임의로 안내하지 않습니다.

65세 이상 독거 비율은 서울 열린데이터광장의 [독거노인 현황(성별/동별)](https://data.seoul.go.kr/bsp/wgs/dataView/data300View/91.do)과 같은 연도 4분기 65세 이상 등록인구를 결합한 값입니다. 원본에서는 동·연도·구분·성별별 독거노인 수를 읽고, 화면에는 `독거노인 수 ÷ 65세 이상 등록인구`를 사용합니다.

관계망·외로움 같은 설문 배경값은 2022~2025 서울서베이 가구원 조사에서 가져옵니다. 자치구, 연령, 가구 식별자, 가중치와 연도별 설문 문항(도움 요청 가능 여부·가족 밖 외로움 관련 문항)을 추출해 강남구·연령대 참고값으로 계산합니다. 동 단위 추정치나 개인별 추적 자료는 아닙니다.

소비 카드가 있을 때는 별도 신한카드 상권 원본에서 상점 소재지·기간·고객 연령·소비 분야·거래 건수를 추출해 일평균 거래 건수 변화를 계산합니다. 이 프로젝트에 보관된 설정에는 그 원본의 외부 다운로드 URL이 없어, 확인되지 않은 출처 링크는 표시하지 않습니다.

화면에 실제 적재 파일명·기간·열을 보여 주는 기능은 아직 연결돼 있지 않습니다. 원본 파일이나 열 구성이 갱신되면, 적재 메타데이터를 읽는 방식으로 이 안내도 함께 갱신해야 합니다.'''


def _age_activity_answer(intent, evidence):
    if not evidence.rows:
        return '선택한 지역과 기간에는 연령별 활동 자료가 없어 변화를 비교하기 어려워요.'
    paragraphs = [
        '연령별로 활동이 얼마나 달라졌는지 살펴볼게요. 각 수치는 바로 앞 3개월 관측기간과 비교한 변화율이에요.'
    ]
    rows = sorted(
        evidence.rows, key=lambda r: (r['date'], r['행정동'], list(AGE_LABEL).index(r['age_band']))
    )
    if len(rows) > 30:
        rows = rows[-30:]
    signal = (
        'communication'
        if intent.metric in CORE[:2]
        else 'mobility'
        if intent.metric in CORE[2:]
        else intent.signal
    )
    selected = (intent.metric,) if intent.metric else _signal_metrics(signal)
    groups = {}
    for row in rows:
        groups.setdefault((row['행정동'], row['date']), []).append(row)
    for (dong, date), entries in groups.items():
        lines = [f"{dong}의 {observation_period_text(date)} 자료를 보면 다음과 같아요."]
        for row in entries:
            clauses = [_change_clause(METRICS[m], row.get(m + '_change_pct')) for m in selected]
            line = f"{_age_label(row['age_band'])}에서는 " + _join_change_clauses(clauses)
            if intent.include_values:
                line += (
                    ' 현재 집계값은 '
                    + ', '.join(f'{METRICS[m]} {_value(row.get(m))}' for m in selected)
                    + '이에요.'
                )
            lines.append(line)
        statuses = [
            {'age_band': row['age_band'], 'age_signal': row.get(signal + '_signal')}
            for row in entries
        ]
        lines += ['', _age_status_story(statuses, signal)]
        paragraphs.append('\n'.join(lines))
    if len(evidence.rows) > len(rows):
        paragraphs.append(
            f"전체 {len(evidence.rows)}개 월·지역·연령 기록 중 최근 {len(rows)}개를 보여드렸어요. 지역이나 월을 좁히면 더 자세히 확인할 수 있어요."
        )
    if any(not _number(r.get(m + '_change_pct')) for r in rows for m in selected):
        paragraphs.append('자료가 부족하거나 비교할 수 없는 값은 0%로 표시하지 않았어요.')
    return '\n\n'.join(paragraphs)


def _period_label(period):
    if len(period) == 6 and period[4] == 'Q':
        return f'{period[:4]}년 {period[-1]}분기'
    if len(period) == 7 and period[4] == '-' and period[:4].isdigit() and period[5:].isdigit():
        return f'{period[:4]}년 {int(period[5:])}월'
    return period


def _commerce_lines(rows, limit=12):
    """Render matched changes with scope and small denominators visible."""
    groups = {}
    for row in rows:
        scope = row.get('행정동') or row.get('district', '강남구')
        key = (scope, row['scope'], row['period'], row.get('comparison_period'))
        groups.setdefault(key, []).append(row)
    lines = []
    per_group_limit = max(1, limit // len(groups))
    for (name, scope, period, previous), entries in groups.items():
        where = (
            f'{name} 소재 상점'
            if scope == 'merchant_dong'
            else '강남구 전체 상점 (동별 자료와 별도 · 월별 비교)'
        )
        lines += [
            '',
            f"{where} · {_period_label(period)}"
            + (f" / {_period_label(previous)} 대비" if previous else ''),
        ]
        reference = next(
            (
                row
                for row in entries
                if row.get('selection_alignment') == 'nearest_comparable_period'
            ),
            None,
        )
        if reference:
            requested = reference.get('requested_period', '선택한 기간')
            lines.append(
                f"선택한 {requested} 자료는 같은 단위로 비교할 수 없어, 가장 가까운 비교 가능한 {_period_label(period)} 자료를 대신 보여드립니다."
            )
        if scope == 'merchant_dong' and any(
            r.get('alignment') == 'separate_prior_complete_quarter' for r in entries
        ):
            lines.append(
                '신호 관측기간과 정확히 같지 않은 분기의 참고 변화입니다. 신호와 동시에 변한 것으로 해석하지 않습니다.'
            )
        elif scope == 'merchant_dong' and any(
            r.get('alignment') == 'partly_after_signal_observation' for r in entries
        ):
            lines.append(
                '신호 관측기간과 일부 겹치지만, 분기 마지막 달은 이후 자료를 포함한 참고 변화입니다.'
            )
        elif scope == 'merchant_dong' and any(
            r.get('alignment') == 'available_period_reference' for r in entries
        ):
            lines.append(
                '선택한 신호 기간이 없어, 현재 공개된 소비자료 범위의 참고 변화로 보여드립니다.'
            )
        ready = [
            r
            for r in entries
            if r.get('change_pct') is not None
            and r['status'] in {'ready', 'ready_matched_change_only'}
        ]
        if not ready:
            if any(r['status'] == 'quarter_not_fully_selected' for r in entries):
                lines.append(
                    '해당 동 자료는 분기 단위여서, 선택한 일부 월만의 증감은 계산할 수 없습니다. 분기 전체를 선택하면 비교할 수 있습니다.'
                )
            elif any(r['status'] == 'ready_partial_day_coverage' for r in entries):
                lines.append('관측된 날짜가 부족해, 이 달의 증가 순위는 표시하지 않았습니다.')
            else:
                lines.append('비교할 이전 자료가 없거나 충분하지 않아 증가율을 확인할 수 없습니다.')
            continue
        if not any(r['change_pct'] > 0 for r in ready):
            lines.append('비교 가능한 분야에서 증가가 확인되지 않았습니다. 감소가 작은 순서입니다.')
        for row in ready[:per_group_limit]:
            domain = str(row.get('domain', '소비 분야')).split('_', 1)[-1]
            age = row.get('age') or '연령 확인 불가'
            rate = row['change_pct']
            current = row.get('current_daily_count')
            prior = row.get('previous_daily_count')
            value = f"{rate:+.1f}%"
            if current is not None and prior is not None:
                value += f" (일평균 {prior:,.2f} → {current:,.2f}건)"
            lines.append(f'- {age} 고객 · {domain}: {value}')
            if prior is not None and prior < 1:
                lines.append('  이전 거래량이 하루 1건 미만이어서 증가율이 크게 보일 수 있습니다.')
        if len(ready) > per_group_limit:
            lines.append(
                '먼저 증가율이 큰 일부 분야만 표시했습니다. 월·연령을 좁히면 더 자세히 볼 수 있습니다.'
            )
    return lines


def _consumption_answer(intent, evidence):
    request = evidence.supplementary.get('requested_period', {})
    lines = [
        f"{request.get('start', intent.start_month)}~{request.get('end', intent.end_month)}의 소비 분야 변화를 확인했습니다.",
        '금액이 아닌 일평균 거래 건수의 전기 대비 증가율이며, 동일 업종끼리 비교했습니다. 고객 연령·분야별 증가가 큰 순서입니다.',
    ]
    lines += _commerce_lines(evidence.supplementary.get('consumption_trends', []))
    lines += [
        '',
        '개별 품목 자료는 없어 소비 분야로 보여드립니다. 상점 소재지 기준이며 해당 동 주민의 소비나 신호의 원인을 뜻하지 않습니다.',
        '‘급증’ 판정 기준은 따로 적용하지 않았습니다.',
    ]
    return '\n'.join(lines)


def _value(v):
    if v is None or str(v).lower() in {'nan', '<na>'}:
        return '확인 불가'
    if isinstance(v, float):
        return f'{v:,.2f}'
    return str(v)


def _format_row(row):
    values = []
    for key, v in row.items():
        if v is None:
            continue
        if key in {
            'adm_cd',
            'district',
            'amount',
            'interpretation',
            'scope',
            'age_capture_ratio',
            'baseline_periods',
            'matched_industries',
            'resident_scope',
            'location_basis',
        }:
            continue
        if (
            key not in COLUMN_NAMES
            and not key.endswith('_residual_change_expanding_rz')
            and key not in {'범위'}
            and not any(ch in key for ch in '월수력기')
        ):
            continue
        if key == 'age_band':
            v = AGE_LABEL.get(v, v)
        if key in {'date', 'comparison_month', 'reference_date', 'label_month'}:
            v = observation_period_text(v)
        if key == 'signal_type':
            v = SIGNAL_LABEL.get(str(v).lower(), v)
        if key == 'assessment_status':
            v = {
                'assessed': '평가됨',
                'partially_assessed': '일부 지표만 평가됨',
                'deferred': '평가 보류',
            }.get(v, v)
        if key.endswith('_ratio') and isinstance(v, (int, float)):
            v = f'{v * 100:.1f}%'
        elif isinstance(v, bool):
            v = '탐지됨' if v else '미탐지'
        label = COLUMN_NAMES.get(key, key)
        for m in CORE:
            if key == m + '_residual_change_expanding_rz':
                label = METRICS[m] + ' Robust Z'
        values.append(f'{label}: {_value(v)}')
    return ' · '.join(values)


def _age_label(band):
    return '60세 이상' if band == '60plus' else AGE_LABEL.get(band, str(band))


def _topic(word):
    last = word[-1] if word else ''
    has_final = bool(last and '\uac00' <= last <= '\ud7a3' and (ord(last) - 0xAC00) % 28)
    return word + ('은' if has_final else '는')


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _change_clause(label, value):
    if not _number(value):
        return _topic(label) + ' 비교 자료가 부족해 변화를 확인하기 어려웠'
    last = label[-1] if label else ''
    has_final = bool(last and '\uac00' <= last <= '\ud7a3' and (ord(last) - 0xAC00) % 28)
    subject = label + ('이' if has_final else '가')
    if value == 0:
        return subject + ' 변화가 없었'
    return f"{subject} {abs(value):.1f}% " + ('줄었' if value < 0 else '늘었')


def _join_change_clauses(clauses):
    if not clauses:
        return '비교할 자료가 부족해 증감을 확인하기 어려워요.'
    return '고, '.join(clauses) + '어요.'


def _signal_metrics(signal):
    return CORE[:2] if signal == 'communication' else CORE[2:] if signal == 'mobility' else CORE


def _row_changes(row, metrics):
    changes = {}
    for metric in metrics:
        value = row.get(metric + '_log_change')
        changes[metric] = (
            math.expm1(value) * 100
            if _number(value) and row.get(metric + '_valid') is not False
            else None
        )
    return changes


def _signal_story(row):
    dong = row.get('행정동', '해당 지역')
    signal = str(row.get('signal_type', '')).lower()
    age = row.get('age_band')
    subject = dong + (f" {_age_label(age)}" if age else '')
    period = observation_period_text(row.get('date'))
    metrics = _signal_metrics(signal)
    changes = _row_changes(row, metrics)
    if signal not in {'communication', 'mobility', 'combined'}:
        return [f"{subject}의 {period} 자료에는 확인된 변화 신호가 없어요."]
    kind = SIGNAL_LABEL.get(signal, '활동')
    paragraphs = [
        f"{period} 자료에서 {subject}의 {kind} 변화 신호가 확인됐어요.\n"
        "직전 관측기간과 비교하면 "
        + _join_change_clauses([_change_clause(METRICS[m], changes[m]) for m in metrics])
    ]
    if (
        signal == 'mobility'
        and _number(changes.get('weekend_move_count'))
        and changes['weekend_move_count'] > 0
    ):
        opening = '휴일 이동이 늘었는데도 신호가 잡힌 이유가 있어요. '
    else:
        opening = '얼마나 줄거나 늘었는지만으로 신호를 판단하지는 않아요. '
    if age:
        paragraphs.append(
            opening
            + f"{dong} {_age_label(age)}의 과거 변화와 연령별 판정 기준에 비춰 확인이 필요한 수준으로 나타났어요. "
            '연령별 판정에서는 원래 변화와 강남구 공통 흐름을 감안한 변화를 각각 살펴봐요.'
        )
    elif signal == 'combined':
        finding = '소통과 이동의 짝 지표가 각각 확인이 필요한 수준으로 나타나 신호가 잡혔어요.'
        paragraphs.append(
            opening
            + f"강남구 전체에서 함께 나타난 흐름을 감안하고 {dong}의 과거 변화와 비교했을 때, "
            + finding
        )
    else:
        finding = '두 지표의 변화가 모두 평소 변화 범위에서 아래쪽으로 크게 벗어나 신호가 잡혔어요.'
        paragraphs.append(
            opening
            + f"강남구 전체에서 함께 나타난 흐름을 감안하고 {dong}의 과거 변화와 비교했을 때, "
            + finding
        )
    # 실제 이동 감소와 보정 후 신호를 혼동하지 않도록 방향을 먼저 설명합니다.
    nondecreasing = [
        m for m in CORE[2:] if m in metrics and _number(changes.get(m)) and changes[m] >= 0
    ]
    if signal in {'mobility', 'combined'} and nondecreasing:
        labels = '·'.join(METRICS[m] for m in nondecreasing)
        direction = f"{labels}는 실제로 줄지 않았어요. "
        if age:
            explanation = (
                direction
                + '연령별 판정 기준은 동 전체 판정과 달라요. 원래 변화와 강남구 공통 흐름을 감안한 변화를 각각 살펴봐요. '
                '증가한 지표를 실제 감소로 해석해서는 안 돼요. '
                '저장된 신호가 어떤 연령별 판정 경로에서 나왔는지와 점수·기준값을 확인해야 정확한 이유를 설명할 수 있어요.'
            )
        else:
            explanation = (
                direction
                + '그런데 현재 동 전체의 이동 신호는 실제 이동 횟수가 줄었는지를 필수 조건으로 두지 않아요. '
                '각 지표의 변화에서 강남구 공통 흐름을 뺀 뒤, 그 변화가 해당 동의 과거 변화 범위보다 얼마나 낮은지 점수로 비교해요. '
                '평일과 휴일의 보정된 변화 점수가 모두 탐지 기준 이하면, 실제 이동 횟수가 증가해도 신호가 잡힐 수 있어요. '
                '즉 이번 표시는 실제 이동 감소가 아니라 보정한 변화가 과거보다 이례적으로 낮다는 뜻이에요. '
                '다만 이 사례의 구체적인 판정 이유를 검증하려면 강남구 변화와 보정 점수·탐지 기준값을 함께 확인해야 해요.'
            )
        paragraphs[1] = explanation + ' 이 결과만으로 고립 위험이 커졌다고 판단할 수는 없어요.'
    if row.get('review_reasons') or row.get('interest_structural_issue'):
        paragraphs.append(
            '자료 품질도 함께 확인할 필요가 있어요. 확인할 수 없는 값을 0으로 보지는 않아요.'
        )
    return paragraphs


def _cluster_story(row, evidence):
    dong = row.get('행정동')
    region = next(
        (r for r in evidence.supplementary.get('analysis1', []) if r.get('dong_name') == dong), {}
    )
    cluster = row.get('cluster_type') or row.get('a1_cluster_type') or region.get('cluster_type')
    if not cluster:
        return ''
    if cluster == '고활동·청년유동·1인가구 중심형':
        background = f"{dong}은 청년층의 활동과 1인 가구가 두드러지는 지역 유형으로 분류돼 있어요."
    else:
        background = f"{dong}의 지역 배경은 '{cluster}' 유형으로 분류돼 있어요."
    return (
        background
        + ' 이런 배경을 참고해 지역 이용 방식이나 생활 여건이 달라졌는지 살펴볼 수 있어요. 배경과 이번 변화가 실제로 연결되는지는 추가 확인이 필요해요.'
    )


def _age_status_story(rows, signal):
    kind = '소통 또는 이동' if signal == 'any' else SIGNAL_LABEL.get(signal, '활동')
    detected = [_age_label(r.get('age_band')) for r in rows if r.get('age_signal') is True]
    undetected = [_age_label(r.get('age_band')) for r in rows if r.get('age_signal') is False]
    unknown = [_age_label(r.get('age_band')) for r in rows if r.get('age_signal') is None]
    sentences = []
    if detected:
        sentences.append('·'.join(detected) + f"에서는 {kind} 신호가 연령별 판정에서도 확인됐어요.")
    elif undetected:
        sentences.append(f"판정할 수 있었던 연령대에서는 별도의 {kind} 이상신호가 잡히지 않았어요.")
    if unknown:
        sentences.append(
            _topic('·'.join(unknown))
            + ' 자료가 부족하거나 판정 결과가 없어 신호 여부를 확인하기 어려워요.'
        )
    sentences.append(
        '연령별 증감과 이상신호 여부는 달라요. 각 연령대의 과거 변화와 판정 기준으로 따로 살펴봐요.'
    )
    return ' '.join(sentences)


def _reason_answer(evidence):
    if not evidence.rows:
        return [
            '선택한 지역·기간에는 이상신호 기록이 0건입니다. 이 결과는 해당 기준월에 추가 확인 기준에 해당하는 변화가 없었다는 뜻이며, 지역의 문제가 없다고 단정하는 것은 아닙니다.\n\n'
            '2025년의 다른 이상신호 지역을 찾아 안내해 드릴까요? 아래의 “2025년 다른 이상신호 지역 찾아줘”를 누르면 같은 해에 신호가 기록된 지역을 확인할 수 있어요.'
        ]
    paragraphs = []
    for row in evidence.rows[:3]:
        paragraphs += _signal_story(row)
    if len(evidence.rows) > 3:
        paragraphs.append(
            f"먼저 {len(evidence.rows)}건 중 3건을 보여드렸어요. 지역이나 기준월을 좁히면 나머지도 확인할 수 있어요."
        )
    paragraphs.append('지역 집계만으로 개인의 고립 여부나 변화의 원인을 판단할 수는 없어요.')
    return ['\n\n'.join(paragraphs)]


def _query_story_period(intent):
    start, end = intent.start_month, intent.end_month
    if start and end:
        if start[:4] == end[:4] and start[5:] == '07' and end[5:] == '12':
            return start[:4] + '년 하반기 자료에서는'
        if start[:4] == end[:4] and start[5:] == '01' and end[5:] == '06':
            return start[:4] + '년 상반기 자료에서는'
        if start[:4] == end[:4] and start[5:] == '01' and end[5:] == '12':
            return start[:4] + '년 자료에서는'
        if start == end:
            return observation_period_text(start) + ' 자료에서는'
    return '조회한 자료에서는'


def _previous_month_label(value):
    """Return the calendar month immediately before a YYYY-MM result month."""
    month = str(value or '')[:7]
    try:
        year, number = map(int, month.split('-'))
        if not 1 <= number <= 12:
            raise ValueError
    except ValueError:
        return '전월'
    index = year * 12 + number - 2
    return f'{index // 12}년 {index % 12 + 1}월'


def _group_signal_rows_by_dong(rows):
    """답변에 표시할 신호 행을 행정동별로 입력 순서대로 묶는다."""
    groups = {}
    for row in rows:
        dong = row.get('행정동') or '해당 지역'
        groups.setdefault(dong, []).append(row)
    return list(groups.items())


def _numbered_signal_groups(rows, evidence):
    """여러 지역의 긴 설명을 동별 번호가 붙은 블록으로 만든다."""
    blocks = []
    for index, (dong, dong_rows) in enumerate(_group_signal_rows_by_dong(rows), start=1):
        details = []
        for row in dong_rows:
            if row.get('신호 건수') is not None:
                details.append(f"선택한 기간에 변화 신호가 {row['신호 건수']}건 확인됐어요.")
                continue
            details += _signal_story(row)
        cluster = _cluster_story(dong_rows[0], evidence)
        if cluster:
            details.append(cluster)
        blocks.append(f"{index}. {dong}\n" + '\n\n'.join(details))
    return blocks


def _concise_signal_list(intent, evidence):
    rows = evidence.rows
    if not rows:
        return evidence.summary + ' 추가로 확인할 변화 신호는 나오지 않았어요.'
    names = list(dict.fromkeys(r.get('행정동') for r in rows))
    prefix = _query_story_period(intent)
    if len(names) == 1:
        paragraphs = [f"{prefix} {names[0]}을 한 번 더 살펴볼 필요가 있어요."]
    else:
        paragraphs = [f"{prefix} 확인이 필요한 지역이 {len(names)}곳 나왔어요."]
    displayed = rows[:10]
    if len(names) > 1:
        paragraphs += _numbered_signal_groups(displayed, evidence)
    else:
        for row in displayed:
            if row.get('신호 건수') is not None:
                paragraphs.append(
                    f"{row.get('행정동')}에서는 선택한 기간에 변화 신호가 {row['신호 건수']}건 확인됐어요."
                )
                continue
            paragraphs += _signal_story(row)
            cluster = _cluster_story(row, evidence)
            if cluster:
                paragraphs.append(cluster)
    if len(rows) > 10:
        paragraphs.append(f"전체 {len(rows)}건 중 먼저 10건을 보여드렸어요.")
    if intent.limit and len(names) < intent.limit:
        paragraphs.append(
            f"요청하신 {intent.limit}곳보다 적은 이유는, 이번 조건에서 신호가 확인된 지역이 {len(names)}곳이기 때문이에요."
        )
    age_count = evidence.supplementary.get('age_case_count')
    age_districts = evidence.supplementary.get('age_case_district_count')
    if age_count is not None and age_count != len(rows):
        paragraphs.append(
            f"참고로 위 목록은 동 단위 신호 기준이에요. 연령별 신호 자료까지 별도로 세면 {age_count}건, {age_districts}개 동이며 동 단위 기록과 합산하지 않습니다."
        )
    paragraphs.append('지역 집계만으로 주민의 고립 여부나 변화의 원인을 판단할 수는 없어요.')
    return '\n\n'.join(paragraphs)


def _metric_value_answer(intent, evidence):
    rows = sorted(
        evidence.rows, key=lambda item: (str(item.get('date', '')), str(item.get('행정동', '')))
    )
    row = rows[0] if rows else {}
    if not row:
        return '선택한 조건의 활동 집계값을 찾지 못했습니다.'
    metric = METRICS[intent.metric]
    subject = (
        f"{row.get('행정동')} {_age_label(row.get('age_band'))}"
        if row.get('age_band')
        else str(row.get('행정동'))
    )
    if len(rows) > 1:
        changes = []
        for item in rows:
            value = item.get(intent.metric + '_log_change')
            if isinstance(value, (int, float)) and math.isfinite(value):
                changes.append((item, math.expm1(value) * 100))
        if changes:
            first, last = changes[0], changes[-1]
            low = min(changes, key=lambda item: item[1])
            high = max(changes, key=lambda item: item[1])
            return (
                f"{subject}의 {metric} 전월 변화율은 {first[0]['date']}~{last[0]['date']}에 확인됩니다. "
                f"가장 낮은 달은 {low[0]['date']} {low[1]:.1f}%, 가장 높은 달은 {high[0]['date']} {high[1]:.1f}%입니다. "
                '이 수치는 선택한 동의 집계 변화이며, 개인의 상태를 뜻하지 않습니다.'
            )
    return f"{observation_period_text(row.get('date'))} {subject}의 집계값은 {metric} {_value(row.get(intent.metric))}입니다."


def _pct(value):
    return f"{float(value) * 100:.2f}%" if _number(value) else '확인 불가'


def _context_answer(evidence):
    row = evidence.rows[0] if evidence.rows else {}
    if not row:
        return '선택한 동의 저장된 클러스터 자료가 없습니다. 동별 수치가 아닌 강남구 전체 참고자료가 필요하면 그렇게 요청해 주세요.'
    cluster = row.get('cluster_type')
    if not cluster:
        return f"{row.get('dong_name')}의 클러스터 분류가 저장되어 있지 않습니다. 동별 수치가 아닌 강남구 전체 참고자료가 필요하면 그렇게 요청해 주세요."
    lines = [
        f"{row.get('dong_name')}은 “{cluster}” 클러스터입니다. "
        '비슷한 지역 구조를 가진 동끼리 묶은 분류이며, 개인의 위험도나 신호 원인을 뜻하지 않습니다.'
    ]
    # “지역 배경”은 유형명만이 아니라 신호 판정 밖의 보조 맥락도 함께
    # 보여 주는 메뉴다. 소비·기상은 아래 함수가 범위와 한계를 표시한다.
    lines.extend(_context_lines(evidence, skip_regions=True))
    return '\n'.join(lines)


def _support_answer(evidence):
    """Show the numbers people can act on, then explain their limited relation."""
    lines = [
        '신호와 함께 볼 수 있는 지역 수치입니다. 이 자료는 원인을 확정하는 근거가 아니라, 현장에서 무엇을 확인할지 정하는 참고자료입니다.'
    ]
    if evidence.rows:
        row = evidence.rows[0]
        lines += [
            '',
            f"현재 신호: {row.get('행정동')} · {observation_period_text(row.get('date'))} · {SIGNAL_LABEL.get(str(row.get('signal_type', '')).lower(), '변화')} 변화",
        ]
        lines.append(
            '이 수치는 해당 동의 변화가 강남구 전체 흐름과 과거 변화 범위에 비해 이례적이었는지로 판단한 결과입니다.'
        )
    supplementary = evidence.supplementary
    regions = supplementary.get('analysis1', [])
    if regions:
        region = regions[0]
        lines += ['', f"지역 구조 수치 (자료 기간: {region.get('period', '확인 불가')})"]
        if region.get('retrospective_context'):
            lines.append('해당 기간 전체 자료로 만든 사후 참고자료입니다.')
        for key, label, relation in (
            (
                'hh_1_ratio',
                '1인 가구 비율',
                '이동 변화가 반복될 때 안부 확인이나 생활지원 접근성을 우선 점검할 집단 규모를 가늠하는 데 참고합니다.',
            ),
            (
                'age_60_plus_ratio',
                '60세 이상 활동인구 비율',
                '고령층의 이동 여건이나 시설 접근성도 함께 확인할 필요가 있는지 살펴보는 배경입니다.',
            ),
            (
                'disability_ratio',
                '장애인 비율',
                '이동지원·방문 안내 같은 지원 접근성을 검토할 때 참고합니다.',
            ),
            (
                'livelihood_recipient_ratio',
                '기초생활수급자 비율',
                '기존 지원 대상에게 안내와 연결이 닿고 있는지 점검할 우선순위를 정하는 데 참고합니다.',
            ),
            (
                'elderly_living_alone_rate_65plus',
                '65세 이상 독거 비율',
                '고령 1인 가구의 생활지원 접근성을 함께 점검할 필요가 있는지 살펴보는 배경입니다.',
            ),
        ):
            value = region.get(key)
            if isinstance(value, (int, float)):
                lines.append(f"- {label} {value * 100:.1f}%: {relation}")
        lines.append(
            '이 비율들만으로 현재 변화 신호의 원인이나 특정 집단의 상태를 판단할 수는 없습니다.'
        )
    surveys = supplementary.get('survey_district_shared', [])
    if surveys:
        labels = {
            'no_support_all3': '아플 때·금전적으로 어려울 때·낙심했을 때 모두 도움을 줄 사람이 없다는 응답',
            'loneliness_outside_agree': '가족 밖 관계에서 외로움을 느낀다는 응답',
        }
        age_label = AGE_LABEL.get(surveys[0].get('age_band'), '15세 이상 전체')
        lines += ['', f'강남구 {age_label} 관계망·외로움 조사 배경:']
        for item in surveys[:2]:
            value = item.get('value')
            rendered = (
                f'{value * 100:.1f}%'
                if isinstance(value, (int, float)) and item.get('unit') == 'proportion'
                else '확인 불가'
            )
            if item.get('quality_status') != 'available':
                rendered = '표본·응답 품질 확인 필요'
            lines.append(
                f"- {labels.get(item.get('metric'), item.get('metric'))}: {rendered} · {item.get('year')}년 강남구 조사"
            )
        lines.append(
            '강남구 연령대 전체의 설문 참고값입니다. 삼성1동 주민의 고립률이나 이번 신호의 원인을 뜻하지 않습니다.'
        )
    trends = supplementary.get('consumption_trends', [])
    local = supplementary.get('analysis3_dong', [])
    if trends:
        lines += [
            '',
            '상권 이용 변화:',
            '고객 연령·분야별 일평균 거래 건수의 전기 대비 증가율입니다. 동일 업종끼리 비교했습니다.',
        ]
        lines += _commerce_lines(trends, limit=6)
        lines.append(
            '상점 소재지 기준 자료이므로 해당 동 주민의 소비나 신호의 원인을 뜻하지 않습니다.'
        )
        lines.append('증가율 비교이며, 공식적인 급증 판정 기준은 적용하지 않았습니다.')
    elif local:
        item = local[0]
        count = item.get('count')
        daily = item.get('daily_count')
        below = item.get('below_prior_min_cells')
        pieces = []
        if isinstance(count, (int, float)):
            pieces.append(f"거래 건수 {_value(count)}건")
        if isinstance(daily, (int, float)):
            pieces.append(f"일평균 {_value(daily)}건")
        if below is not None:
            pieces.append(f"과거 동분기 최솟값 미만 묶음 {_value(below)}개")
        if pieces:
            lines += [
                '',
                '상권 이용 변화',
                '소비 분야별로 비교 가능한 자료가 부족해 증가율을 제시하지 않습니다.',
            ]
            lines.append(
                '상점 소재지 기준 자료이며, 해당 동 주민의 소비나 신호의 원인을 뜻하지 않습니다.'
            )
            if item.get('alignment') == 'separate_prior_complete_quarter':
                lines.append(
                    '이 상권 자료는 신호의 관측기간과 정확히 같은 기간이 아니므로, 직접적인 동시 변화로 비교하지 않습니다.'
                )
    weather = next(iter(supplementary.get('weather', {}).values()), None)
    if weather and weather.get('observation_month_weather'):
        pieces = []
        for item in weather['observation_month_weather']:
            pieces.append(
                f"{item.get('month')} 강수량 {_value(item.get('rainfall_mm'))}mm·강수일 {_value(item.get('rain_days'))}일"
            )
        lines += ['', '관측기간 날씨', '- ' + ' / '.join(pieces)]
        lines.append(
            '비나 눈 같은 계절 요인이 이동에 영향을 주었을 가능성을 현장에서 확인할 수 있습니다. 날씨는 신호 판정 기준에는 사용하지 않았습니다.'
        )
    return '\n'.join(lines)


def _context_lines(evidence, skip_regions=False, skip_local=False):
    s = evidence.supplementary
    if not s:
        return []
    lines = []
    if s.get('analysis1'):
        if not skip_regions:
            lines += ['', '지역 배경:']
            for r in s['analysis1'][:3]:
                lines.append('- ' + _format_row(r))
        if any(r.get('retrospective_context') for r in s['analysis1']):
            lines.append(
                '2025H2 지역유형은 하반기 자료로 만든 사후 설명용 배경입니다. 당시 이미 알 수 있었던 정보로 간주하지 않습니다.'
            )
    local = s.get('analysis3_dong', [])
    trends = s.get('consumption_trends', [])
    if (local or trends) and not skip_local:
        lines += [
            '',
            '소비 패턴 변화 (상점 소재지 기준):',
            '같은 업종의 일평균 거래 건수를 이전 기간과 비교한 결과입니다. 고객 연령·소비 분야별로 봅니다.',
        ]
        lines += (
            _commerce_lines(trends, limit=6)
            if trends
            else ['비교할 소비 분야 자료가 충분하지 않습니다.']
        )
        lines.append('이 수치는 해당 동 주민의 소비나 이상신호의 원인을 뜻하지 않습니다.')
    shared = s.get('analysis3_district_shared', [])
    if shared and not trends:
        lines += [
            '',
            '강남구 공통 소비 패턴 변화:',
            '동별 소비 분야 비교 자료가 없어 강남구 전체 자료만 확인할 수 있습니다.',
        ]
    if s.get('non_exact_quarter_windows'):
        lines.append(
            '일부 3개월 관측기간이 두 분기에 걸칩니다. 이 경우 직전 완료 분기 자료를 별도 배경으로 표시하며 같은 기간의 변화로 비교하지 않습니다.'
        )
    # Dashboard-compatible storage has no weather supplement and represents
    # that absence as an empty list.  The original DB1 repository uses a
    # date-keyed dictionary.  Optional context must never stop a core
    # dashboard-summary answer from rendering.
    weather = s.get('weather', {})
    for date, w in list(weather.items())[:1] if isinstance(weather, dict) else []:
        parts = []
        for r in w['observation_month_weather']:
            parts.append(
                f"{r['month']} 강수량 {_value(r.get('rainfall_mm'))}㎜·강수일 {_value(r.get('rain_days'))}일·적설일 {_value(r.get('snow_days'))}"
            )
        lines += [
            '',
            '관측기간의 서울 공통 기상 보조정보: ' + ' / '.join(parts),
            '적설일의 ‘-’는 확인 불가로 표시합니다. 기상값은 신호 판정 조건에 사용하지 않습니다.',
        ]
        if w.get('selection_alignment') == 'nearest_available_period':
            lines.append(
                f"선택한 {w.get('requested_period')} 기상자료가 없어, 가장 가까운 {w.get('reference_period')} 자료를 참고로 보여드립니다."
            )
    sns = s.get('sns_same_period', [])
    if sns:
        r = sns[0]
        lines.append(
            f"같은 기간 {r.get('adm_nm')} {AGE_LABEL.get(r.get('age_band'), '')}의 SNS 표준화 지수는 {_value(r.get('sns_index_mean'))}입니다. 사용 건수나 시계열 증감률로 해석하지 않습니다."
        )
    elder = s.get('elder_65plus_dong', [])
    if elder:
        lines += ['', '독거노인 연간 배경:']
        for r in elder[:3]:
            lines.append(
                f"- {r['adm_nm']} · {r['year']}년 · 65세 이상 독거노인 {_value(r['elderly_living_alone_total'])}명"
            )
        lines.append(
            '65세 이상 통계로 60세 이상 행동 자료와 연령 범위가 일부 다릅니다. 독거 여부를 고립 여부로 해석하지 않습니다.'
        )
    surveys = s.get('survey_district_shared', [])
    if surveys:
        labels = {
            'no_support_all3': '세 지원 상황 모두 도움 줄 사람 없음',
            'loneliness_outside_agree': '가족 밖 관계에서 외로움을 느낀다는 응답',
        }
        lines += ['', '강남구 연간 조사 배경:']
        for r in surveys[:2]:
            v = r['value']
            value = f'{v * 100:.1f}%' if v is not None and r['unit'] == 'proportion' else _value(v)
            if r['quality_status'] != 'available':
                value = '표본·응답 품질 확인 필요'
            lines.append(
                f"- {r['year']}년 · {AGE_LABEL.get(r['age_band'], '15세 이상 전체')} · {labels.get(r['metric'], r['metric'])}: {value} · 유효 응답 {_value(r['n_valid'])} · 가중치 기반 유효 표본 {_value(r['effective_n'])}"
            )
        lines.append(
            '동별 통계로 배분하지 않는 연간 조사 배경입니다. 공개일이 미확인된 자료는 사후 설명에만 사용합니다.'
        )
    youth = s.get('youth_reference_shared', [])
    if youth:
        lines += ['', '2022년 청년 가구조사 참고:']
        for r in youth[:2]:
            label = (
                '외출 제한 응답 비율'
                if r['metric'] == 'limited_outing_share'
                else '네 지원 상황 모두 도움 줄 사람 없음'
            )
            age = '19~29세' if r['age_band'] == '19to29' else '30대'
            value = (
                f"{r['value'] * 100:.1f}%"
                if r['value'] is not None and r['quality_status'] == 'available'
                else '확인 필요'
            )
            lines.append(f"- 강남구 · {age} · {label}: {value} · 유효 응답 {_value(r['n_valid'])}")
        lines.append(
            '가중 가구조사 응답의 참고값입니다. 19~29세는 20대와 정확히 일치하지 않으며 현재 동별 고립률이나 탐지 정답이 아닙니다.'
        )
    tracks = s.get('activity_followup', [])
    if tracks:
        states = {
            'both_below_reference': '두 지표 모두 비교 수준 미만',
            'recovered_to_reference': '두 지표 모두 비교 수준 이상',
            'mixed_recovery': '두 지표의 방향이 다름',
            'unavailable': '비교 불가',
        }
        lines += ['', '신호 이후 소통 수준 추적:']
        for r in tracks[:3]:
            lines.append(
                f"- {r['adm_nm']} · {AGE_LABEL[r['age_band']]} · {observation_period_text(r['date'])} · 직전 관측기간 {observation_period_text(r['reference_date'])} 대비: 원값 {states[r['raw_state']]}, 과거 같은 달 정규화 {states[r['seasonal_state']]}, 구 공통변화 분리 {states[r['local_state']]}"
            )
        lines.append(
            '추가 변화 신호가 없음과 활동 수준의 회복은 구분합니다. 작은 부호 차이를 유의한 회복이나 같은 개인의 상태 변화로 단정하지 않습니다.'
        )
    if local or shared:
        lines.append('소비 보조자료는 사후 설명용이며, 신호의 원인을 판정하지 않습니다.')
    return lines


def template_answer(
    intent: QueryIntent, evidence: Evidence, knowledge: str, explanation: str = ''
) -> str:
    if intent.question_type == 'provenance':
        return provenance_answer()
    if intent.question_type == 'age_activity':
        return _age_activity_answer(intent, evidence)
    if intent.question_type == 'age_data_coverage':
        if not evidence.rows:
            return '직전 신호 사례와 같은 기준월의 연령별 자료를 찾지 못했습니다.'
        start = next(
            (r.get('age_data_start') for r in evidence.rows if r.get('age_data_start')), None
        )
        end = next((r.get('age_data_end') for r in evidence.rows if r.get('age_data_end')), None)
        month_label = (
            lambda value: f'{value[:4]}년 {int(value[5:7])}월' if value else '기준월 확인 불가'
        )
        lines = []
        if start and end:
            lines.append(
                f'연령별 자료는 {month_label(start)}~{month_label(end)} 기준월에만 제공되기 때문이에요.'
            )
        for index, row in enumerate(evidence.rows, start=1):
            dong = row.get('행정동', '해당 지역')
            month = row.get('date')
            if row.get('age_data_available'):
                detail = '동일 기준월의 20대·30대·40대·50대·60세 이상 자료가 있어 함께 보여드릴 수 있어요.'
            elif start and month and month < start:
                detail = f'해당 기준월이 연령별 자료 시작 시점인 {month_label(start)}보다 앞서 동일 기준월 자료가 없어요.'
            elif end and month and month > end:
                detail = f'해당 기준월이 연령별 자료 마지막 시점인 {month_label(end)}보다 뒤라 동일 기준월 자료가 없어요.'
            else:
                detail = '동일 기준월의 연령별 자료가 없어 함께 비교할 수 없어요.'
            lines.append(f'{index}. {dong} · {month_label(month)} 기준\n{detail}')
        lines.append(
            '다른 두 동도 연령별 자료 자체가 전혀 없는 것은 아니며, 이상신호가 나온 기준월과 같은 달의 자료가 없는 것입니다.'
        )
        return '\n\n'.join(lines)
    if intent.question_type == 'consumption':
        return _consumption_answer(intent, evidence)
    if intent.question_type == 'activity' and intent.metric:
        return _metric_value_answer(intent, evidence)
    if intent.question_type == 'context':
        return _context_answer(evidence)
    if intent.question_type in {'rank_regions', 'signals'}:
        return _concise_signal_list(intent, evidence)
    if intent.question_type == 'support':
        return _support_answer(evidence)
    if intent.question_type == 'reason' and not evidence.rows:
        dong = intent.dong or '선택한 지역'
        return f'{dong}의 조건에 맞는 신호 기록은 0건입니다. 현재 조회 범위와 선택한 연령대에서 확인된 신호 근거가 없어 탐지 이유를 설명할 수 없습니다.'
    if intent.question_type == 'reason' and evidence.rows:
        # Explain this signal and same-month age changes; detailed contextual
        # evidence remains available through the background-information follow-up.
        return '\n'.join(_reason_answer(evidence))
    if intent.question_type == 'previous':
        if not evidence.rows:
            return '조회 기간에 전월과 비교할 탐지 결과가 없습니다.'
        # “전월에도 탐지됐나요?” is a follow-up about the current result, not
        # a request for every historical row inherited from the prior scope.
        # Use the most recent result month and state only its prior-month flag.
        r = max(evidence.rows, key=lambda row: str(row.get('date') or ''))
        flag = r.get('consecutive_signal')
        label = '확인 불가' if flag is None else '탐지됨' if flag else '미탐지'
        return f"{r.get('행정동', '선택한 지역')}의 전월({_previous_month_label(r.get('date'))}) 탐지 여부: {label}"
    lines = [evidence.summary]
    if evidence.rows:
        lines += [''] + ['- ' + _format_row(r) for r in evidence.rows[:10]]
        if len(evidence.rows) > 10:
            lines.append(f'총 {len(evidence.rows)}건 중 10건을 표시했습니다.')
    lines += _context_lines(
        evidence,
        skip_regions=intent.question_type == 'context',
        skip_local=intent.question_type == 'consumption',
    )
    if knowledge:
        lines += ['', knowledge]
    if evidence.limitations:
        lines += ['', '확인 범위: ' + ' / '.join(evidence.limitations)]
    return '\n'.join(lines)


def try_gemini(question, intent, evidence, knowledge, explanation, model, project_root=None):
    key = _api_key(project_root) if project_root else os.getenv('GEMINI_API_KEY', '').strip()
    if not key:
        return None
    try:
        from google import genai

        # Code controls totals; the language model sees a bounded factual extract.
        facts = {
            'summary': evidence.summary,
            'rows': _display_fact_periods(evidence.rows[:10]),
            'supplementary': _display_fact_periods(
                {
                    k: (v[:10] if isinstance(v, list) else v)
                    for k, v in evidence.supplementary.items()
                }
            ),
            'limitations': evidence.limitations,
            'total_rows': len(evidence.rows),
        }
        prompt = f'''강남구 지역 변화 신호 설명 도우미입니다. 아래 조회 결과의 사실만 사용해 한국어로 답하세요.
연간 조사·독거노인 자료는 보조 배경이며 행정동·구·연령·표본 범위를 유지하세요. 65세 이상을 60세 이상 전체로 바꾸지 마세요.
청년 가구조사의 19~29세는 20대와 일부 다릅니다. 가중 가구 응답과 비가중 개인 응답을 섞거나 현재 동별 고립률로 바꾸지 마세요.
활동 수준 추적은 원값·같은 달 정규화·구 공통변화 분리의 상태를 구분하세요. 추가 신호 없음과 수준 회복을 동일시하지 마세요.
행정동 소비의 alignment가 separate_prior_complete_quarter이면 관측기간과 다른 분기의 별도 배경입니다. 동시 변화로 비교하지 마세요.
조회 합계는 summary의 코드 계산값을 쓰세요. 일부 행만 전달되므로 행을 세어 전체 수치를 다시 계산하지 마세요.
내부 기준월은 숫자만 쓰지 말고 기준월과 실제 관측기간을 함께 쓰세요. 예: 2025-12는 “2025년 12월 기준 (관측: 2025년 9~11월)”입니다. 행정동 상권과 강남구 공통 카드자료는 각각의 소재지 기준 보조정보입니다.
공통 구 자료를 해당 동 주민의 소비로 바꾸거나 동별로 중복 합산하지 마세요. 소비가 신호의 원인이라고 단정하지 마세요.
분석1 2025H2와 분석3은 사후 설명용입니다. 실제 공개일이 미확인된 자료로 과거 시점 예측 능력을 주장하지 마세요.
reason 답변에는 한 줄 결론, | 확인 수치 | 쉬운 설명 | 표, 현장 확인 방향을 포함하고 지표의 실제 값과 판정 기준을 쓰세요.
연령별 기준은 absolute/local_threshold의 수치를 사용하세요. 모든 연령에 -2를 일괄 적용하지 마세요.
기상정보는 weather의 observation_month_weather만 관측기간 보조정보로 쓰세요. snow_days null은 확인 불가이며 0으로 바꾸지 마세요.
SNS 지수는 같은 기간 상대적 표준화 지수이며 건수·시계열 증감률을 만들지 마세요.
previous 답변은 동·관측기간별 직전 관측기간의 신호 여부만 탐지됨/미탐지/확인 불가로 쓰세요. 추가 수치나 보조자료를 붙이지 마세요.
개인의 고립 여부나 원인을 확정하지 마세요. 신호가 없으면 탐지 기준에 해당하는 결과가 없다고만 설명하세요.
Markdown 문법을 쓰지 마세요. 굵게 표시 기호, 제목 기호, 표는 사용하지 말고 일반 문장과 번호 목록만 사용하세요.
읽기 쉬운 평문으로 배치하세요. 첫 문장에 답을 말하고, 빈 줄로 구획을 나눈 뒤 “핵심 수치”, “해석”, “확인 범위”처럼 짧은 제목 아래에 관련 수치만 묶으세요. 원값 변화와 판정값, 공식 신호와 보조자료를 섞지 마세요. 긴 수치 나열보다 질문에 필요한 상위 항목을 먼저 보여주세요.
[질문] {question}\n[결과] {json.dumps(facts, ensure_ascii=False, allow_nan=False)}\n[계산 원리] {knowledge}\n[설명 기준] {explanation}'''
        client = genai.Client(api_key=key)
        try:
            result = client.models.generate_content(model=model, contents=prompt)
        finally:
            client.close()
        return getattr(result, 'text', None)
    except Exception:
        return None


def _display_fact_periods(value):
    """Remove source labels from facts passed to the prose model."""
    if isinstance(value, list):
        return [_display_fact_periods(item) for item in value]
    if not isinstance(value, dict):
        return value
    converted = {}
    for key, item in value.items():
        if key == 'source_row_key':
            continue
        if key in {'date', 'comparison_month', 'reference_date', 'label_month'}:
            converted[
                {
                    'date': '관측기간',
                    'comparison_month': '비교 관측기간',
                    'reference_date': '기준 관측기간',
                    'label_month': '관측기간',
                }[key]
            ] = observation_period_text(item)
        elif key in {'start_month', 'end_month'}:
            # A range is handled as one phrase after both endpoints are available.
            continue
        else:
            converted[key] = _display_fact_periods(item)
    if 'start_month' in value or 'end_month' in value:
        converted['조회 관측기간'] = observation_range_text(
            value.get('start_month'), value.get('end_month')
        )
    return converted

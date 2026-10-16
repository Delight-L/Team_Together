"""Compute query results in code, and attach explicitly scoped context."""
from __future__ import annotations
import json
import math
import pandas as pd
from .schemas import Evidence,QueryIntent
from .db1_repository import Db1Repository
from .repository import SOURCES,CORE,AGE_LABEL
from .consumption_trends import consumption_trends
from .observation_period import observation_range_text, observation_period_text, observation_period

LABEL={'communication':'통신','mobility':'이동','combined':'통신·이동 동시','any':'전체'}
METRIC_LABEL=dict(zip(CORE,('통화 상대 수','문자 상대 수','평일 이동 횟수','휴일 이동 횟수')))

def _records(f,cols=None):
    f=f[[c for c in cols if c in f]].copy() if cols else f.copy()
    if 'date' in f:f['date']=f.date.astype(str).str[:7]
    return json.loads(f.to_json(orient='records',force_ascii=False,double_precision=15))

def _signal_flag(value):
    """Keep an unassessable DB flag unknown instead of bool(None/NaN)."""
    if value is None or pd.isna(value):return None
    return bool(value) if value in (True,False) else None

def _metric_change(row,metric):
    value=row.get(metric+'_log_change')
    valid=_signal_flag(row.get(metric+'_valid'))
    return math.expm1(value)*100 if isinstance(value,(int,float)) and math.isfinite(value) and valid is not False else None

def _age_signal_changes(repo,signal_rows):
    """Attach only the ages at each displayed overall signal's dong/month."""
    changes=[]
    for signal_row in signal_rows:
        dong,date=signal_row.get('행정동'),signal_row.get('date')
        if not dong or not date:continue
        kind=str(signal_row.get('signal_type',''))
        metrics=CORE[:2] if kind=='communication' else CORE[2:] if kind=='mobility' else CORE
        flag={'communication':'communication_signal','mobility':'mobility_signal',
              'combined':'combined_signal'}.get(kind,'any_signal')
        for band in AGE_LABEL:
            frame=repo.activity(dong,date,date,band)
            row=frame.iloc[0] if not frame.empty else {}
            changes.append({
                '행정동':dong,'date':date,'age_band':band,'signal_type':kind,
                'changes':{metric:_metric_change(row,metric) for metric in metrics},
                'age_signal':_signal_flag(row.get(flag)),
                'assessment_status':row.get('assessment_status','missing'),
                'signal_status':row.get('signal_status','not_available'),
                'component_signals':{domain:_signal_flag(row.get(domain+'_signal'))
                                     for domain in ('communication','mobility','combined')},
                'any_signal':_signal_flag(row.get('any_signal')),
            })
    return changes

def execute(repo:Db1Repository,intent:QueryIntent)->Evidence:
    names=intent.dongs or ((intent.dong,) if intent.dong else ())
    start,end,age=intent.start_month,intent.end_month,intent.age_band
    kind=intent.question_type
    signal_age_changes=None
    if kind=='data_status':
        data=repo.pipeline_status()
        return Evidence('데이터 처리 상태','초기 이력과 새 원본 처리 범위입니다.',
            [{'초기 이력 마지막 관측기간':observation_period_text('2025-06'),
              '현재 이력 마지막 관측기간':observation_period_text(str(data.get('history_end',''))[:7]),
              '전체 이력 행 수':data.get('history_rows'),'새 관측 기록 수':data.get('detection_rows'),
              '연령별 관측 기록 수':data.get('age_detection_rows'),
              '다음 대기 관측기간':observation_period_text((data.get('waiting_for') or {}).get('month'))}],
            ['DB1 처리 이력'],['초기 이력은 학습·기준 이력이며 7월부터 새 탐지 결과를 저장합니다.'])
    available_start,available_end=repo.available_period()
    limits=[f'초기 이력은 기준을 만드는 데만 사용했습니다. 새 탐지 결과는 {observation_range_text(available_start, available_end)}을 다루며, 건수는 '+
            ('동×연령 묶음 기록' if age else '동별 기록')+' 수입니다.',
            '각 기준월은 그 직전 3개월 관측을 뜻합니다. 개인의 고립이나 신호 원인을 확정하지 않습니다.']
    if age:limits.append(f'연령 범위: {AGE_LABEL[age]}. 연령별 판정은 초기 이력으로 보정한 지표·비교범위별 기준을 사용합니다.')
    source='DB1: a2_age_detection' if age else SOURCES['detection']
    def selected(method,*extra):
        frames=[method(n,start,end,*extra) for n in names] if names else [method(None,start,end,*extra)]
        return pd.concat(frames,ignore_index=True)
    if kind=='age_activity':
        bands=intent.age_bands or ((age,) if age else tuple(AGE_LABEL))
        frames=[repo.activity(name,start,end,band) for name in names for band in bands]
        cols=['date','행정동','age_band','assessment_status','signal_status','signal_type',
              'communication_signal','mobility_signal','combined_signal','any_signal',*CORE]
        for m in CORE:cols += [m+'_log_change',m+'_valid']
        rows=[row for frame in frames for row in _records(frame,cols)]
        for row in rows:
            row['comparison_month']=str(pd.Period(row['date'],freq='M')-1)
            row['age_signal']=_signal_flag(row.get({'communication':'communication_signal',
                'mobility':'mobility_signal','combined':'combined_signal'}.get(intent.signal,'any_signal')))
            row['component_signals']={domain:_signal_flag(row.get(domain+'_signal'))
                                     for domain in ('communication','mobility','combined')}
            for m in CORE:
                row[m+'_change_pct']=_metric_change(row,m)
        return Evidence('연령별 활동 변화',f'{"·".join(names)}의 연령별 주요 지표 변화입니다.',rows,
                        ['DB1: a2_age_detection'],['각 결과는 기준월 직전 3개월 관측이며 변화율은 바로 앞 관측기간 대비입니다. 연령별 값을 합산하지 않습니다.'])
    elif kind=='rank_regions':
        signal_reader = repo.age_signal_cases if intent.age_scope_explicit else repo.signals
        f=signal_reader(start,end,None,intent.signal,age)
        if names:f=f.loc[f['행정동'].isin(names)]
        grouped=f.groupby('행정동',as_index=False).size().rename(columns={'size':'신호 건수'}).sort_values(['신호 건수','행정동'],ascending=[False,True]).head(intent.limit or 3)
        e=Evidence('신호가 많은 지역',f'{LABEL[intent.signal]} 신호 건수가 많은 동 {len(grouped)}곳입니다.',_records(grouped),[source],limits)
    elif kind=='signals':
        # Explicit 연령 범위(특히 "전체 연령")는 동 단위 a2_detection이
        # 아니라 a2_age_detection의 사례를 보여준다. 명시하지 않은 경우는
        # 기존 동 단위 조회를 유지해 화면의 선택 범위와 호환한다.
        signal_reader = repo.age_signal_cases if intent.age_scope_explicit else repo.signals
        f=selected(lambda n,s,e,a:signal_reader(s,e,n,intent.signal,a),age)
        if intent.summary_only and not f.empty:
            counts=f.groupby('행정동').size().rename('신호 건수')
            f=f.sort_values('date').drop_duplicates('행정동', keep='last').copy()
            f['신호 건수']=f['행정동'].map(counts).astype(int)
        cols=['date','행정동','age_band','signal_type','assessment_status','cluster_type','a1_cluster_type']
        for metric in CORE:
            cols += [metric+'_log_change',metric+'_valid',metric+'_residual_change_expanding_rz']
            if age:
                cols += [metric+'_local_rz',metric+'_local_threshold',metric+'_local_signal',
                         metric+'_absolute_rz',metric+'_absolute_threshold',metric+'_absolute_signal']
        if intent.age_scope_explicit:
            source='DB1: a2_age_detection'
            cols += ['communication_signal','mobility_signal','combined_signal','any_signal']
            for metric in CORE:
                cols += [metric+'_log_change',metric+'_valid']
        e=Evidence('신호가 나온 지역',f'조건에 맞는 {LABEL[intent.signal]} 신호는 {len(f)}건입니다.',_records(f,cols),[source],limits)
    elif kind=='anomaly':
        f,rz=repo.anomalies(start,end,intent.metric,age,names)
        e=Evidence('이례적 감소 후보',f'{METRIC_LABEL.get(intent.metric,"평일 이동 횟수")}의 지역 공통변화를 제외한 Robust Z가 낮은 순입니다.',_records(f,['date','행정동','age_band',rz]),[source],limits)
    elif kind=='activity':
        f=selected(repo.activity,age)
        cols=['date','행정동','age_band',*CORE,'communication_signal','mobility_signal','assessment_status']
        cols += [metric+'_log_change' for metric in CORE]
        e=Evidence('활동 변화',f'{len(f)}건의 지역 활동 집계값을 확인했습니다.',_records(f,cols),[source],limits)
    elif kind=='previous':
        f=selected(repo.activity,age);rows=[]
        for row in _records(f,['date','행정동','signal_type']):
            previous=(pd.Period(row['date'],freq='M')-1).strftime('%Y-%m')
            p=repo.activity(row['행정동'],previous,previous,age)
            flag=None if p.empty else p.iloc[0].get({'any':'any_signal','communication':'communication_signal','mobility':'mobility_signal','combined':'combined_signal'}[intent.signal])
            row['consecutive_signal']=None if flag is None or pd.isna(flag) else bool(flag)
            rows.append(row)
        return Evidence('전월 신호 여부','전월 탐지 결과입니다.',rows,[source],['전월 결과가 없거나 평가가 보류되면 미탐지로 처리하지 않습니다.'])
    elif kind in {'reason','support'}:
        f=selected(repo.evidence,age)
        if intent.signal!='any' and not f.empty:f=f.loc[f[intent.signal+'_signal'].fillna(False).eq(True)]
        cols=['date','행정동','age_band','signal_type','signal_status','assessment_status','review_reasons',
              'previous_signal_date','consecutive_signal','interest_structural_issue']
        for m in CORE:cols+=[m,m+'_residual_change_expanding_rz',m+'_log_change']+[m+'_'+scope+'_'+key for scope in ('absolute','local') for key in ('rz','threshold','signal')]
        e=Evidence('선정 근거' if kind=='reason' else '보조 근거',f'조건에 맞는 신호 기록은 {len(f)}건입니다.',_records(f,cols),[source],limits)
        # Legacy evidence cards lack original values; merge exact detection values.
        if not age:
            for r in e.rows:
                a=repo.activity(r['행정동'],r['date'],r['date'])
                if not a.empty:
                    for m in CORE:
                        for key in [m,m+'_log_change']:r[key]=float(a.iloc[0][key])
    elif kind=='context':
        frames=[repo.context(n,(end or available_end)+'-01') for n in names]
        f=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
        e=Evidence('지역 특성','저장된 k-means 지역유형과 구조적 특성입니다.',_records(f,['dong_name','period','cluster_type','hh_1_ratio','hh_2_ratio','age_60_plus_ratio','disability_ratio','livelihood_recipient_ratio','elderly_living_alone_rate_65plus']),[SOURCES['typology']],['지역유형은 지역의 배경이며 위험 등급이나 신호 원인 판정이 아닙니다.'])
    elif kind=='consumption':
        # Direct consumption queries use requested calendar periods, not telecom label periods.
        rows,shared=repo.consumption_evidence(names,start,end,age)
        e=Evidence('소비 보조자료','해당 동 상권 자료와 강남구 공통 소비자료입니다.',rows,['DB1: Analysis3'],['상점 소재지를 기준으로 한 자료이며 해당 동 주민의 소비를 뜻하지 않습니다.'],
            {'analysis3_district_shared':list(shared.values()),'analysis3_dong':rows,'analysis1':[],'direct_calendar_query':True,
             'consumption_trends':consumption_trends(repo,names,start,end,age),
             'requested_period':{'start':start,'end':end}})
        return e
    else:raise ValueError('지원하지 않는 질문 유형입니다.')
    if age is None and kind in {'signals','reason'} and e.rows and not intent.age_scope_explicit:
        signal_age_changes=_age_signal_changes(repo,e.rows)
    if age:
        assessed=selected(repo.activity,age)
        statuses=assessed.get('assessment_status',pd.Series(dtype=object)).value_counts()
        e.limitations.append(f"연령별 평가 상태: 조회 {len(assessed)}건 중 전체 지표 평가 {int(statuses.get('assessed',0))}건, 일부 지표만 평가 {int(statuses.get('partially_assessed',0))}건, 보류 {int(statuses.get('deferred',0))}건. 평가 보류를 무신호로 해석하지 않습니다.")
    context_names=names or tuple(dict.fromkeys(r.get('행정동') for r in e.rows if r.get('행정동')))
    dates=sorted({r['date'] for r in e.rows if r.get('date')})
    if not dates and start and end:dates=[str(p) for p in pd.period_range(start,end,freq='M')]
    if not dates and kind=='context':dates=[available_end]
    if context_names:
        e.supplementary=repo.supplements(context_names[:10],dates,age)
        if signal_age_changes is not None:
            e.supplementary['age_signal_changes']=signal_age_changes
        # A regional-background question without a selected signal month should
        # not expand into every available quarter of consumption data.
        if kind == 'support' and dates:
            trends=[];quarters={}
            signal_observation_end=None
            if kind=='support' and dates:
                window=observation_period(dates[-1])
                signal_observation_end=window[1] if window else None
            for row in e.supplementary.get('analysis3_dong',[]):
                quarters[(row['행정동'],row['period'])]=row.get('alignment')
            for (name,quarter),alignment in quarters.items():
                period=pd.Period(quarter,freq='Q')
                entries=consumption_trends(repo,(name,),period.start_time.strftime('%Y-%m'),period.end_time.strftime('%Y-%m'),age,include_district=False)
                trends += [{**r,'alignment':alignment} for r in entries if r['scope']=='merchant_dong']
            shared_months=sorted({r['period'] for r in e.supplementary.get('analysis3_district_shared',[])})
            if shared_months:
                if signal_observation_end:
                    trends += consumption_trends(repo,(),signal_observation_end,signal_observation_end,age)
                else:
                    trends += consumption_trends(repo,(),shared_months[0],shared_months[-1],age)
            # A three-month signal can cross two quarters. Include the nearby
            # completed quarter as a separately marked reference, rather than
            # hiding it merely because its final month falls after the signal.
            if signal_observation_end:
                signal_quarter=pd.Period(signal_observation_end,freq='Q')
                trend_start=signal_quarter.start_time.strftime('%Y-%m')
                trend_end=signal_quarter.end_time.strftime('%Y-%m')
            else:
                trend_start,trend_end=(start,end) if start and end else repo.consumption_period()
            if trend_start and trend_end:
                existing={(r.get('행정동'),r.get('scope'),r.get('period'),r.get('age'),r.get('domain')) for r in trends}
                relation='partly_after_signal_observation' if start and end else 'available_period_reference'
                for row in consumption_trends(repo,context_names,trend_start,trend_end,age,include_district=False):
                    key=(row.get('행정동'),row.get('scope'),row.get('period'),row.get('age'),row.get('domain'))
                    if key not in existing:
                        trends.append({**row,'alignment':relation})
                        existing.add(key)
            if signal_observation_end:
                signal_quarter=str(pd.Period(signal_observation_end,freq='Q'))
                trends=[row for row in trends if row['scope']!='merchant_dong' or row.get('period')==signal_quarter]
            # Some contextual records have only a summary row.  In that case,
            # query the selected calendar range directly so the answer can
            # still show the available domain/age pattern rather than totals.
            if not trends and start and end:
                trends += consumption_trends(repo,context_names,start,end,age,include_district=False)
                trends += consumption_trends(repo,(),start,end,age)
            e.supplementary['consumption_trends']=trends
        if len(context_names)>10:e.supplementary['shown_context_dongs']=10
        e.sources+=['DB1: Analysis1 지역유형','DB1: Analysis3 보조자료','서울 기상 원본']
    return e

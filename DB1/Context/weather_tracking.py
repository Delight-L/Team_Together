"""Season-matched weather context, with a fixed 2022-01..2025-06 reference."""
import hashlib
import json
import math
import calendar
import csv
from pathlib import Path
from statistics import mean,median
from source_semantics import window,canonical

VERSION='weather_season_tracking_v1'
START='2022-01'
END='2025-06'
TRACK_START='2025-07'
METRICS={'rainfall_mm':'mm','rain_days':'days','snow_days':'days'}
SCHEMA='''
CREATE TABLE IF NOT EXISTS ctx_weather_tracking_reference(version TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ctx_weather_month_tracking(period TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ctx_weather_window_tracking(date TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ctx_weather_tracking_revision(id INTEGER PRIMARY KEY,scope TEXT NOT NULL,period TEXT NOT NULL,previous_json TEXT NOT NULL,current_json TEXT NOT NULL,registered_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE VIEW IF NOT EXISTS v_weather_month_tracking AS SELECT period,payload_json FROM ctx_weather_month_tracking;
CREATE VIEW IF NOT EXISTS v_a2_weather_tracking_context AS SELECT b.*,t.payload_json AS weather_tracking_json FROM v_a123_age_source_context b LEFT JOIN ctx_weather_window_tracking t ON t.date=b.source_label_date;
'''

def finite(value):
    return isinstance(value,(float,int)) and math.isfinite(value) and value>=0

def months(start=START,end=END):
    y,m=map(int,start.split('-'));last_y,last_m=map(int,end.split('-'))
    result=[]
    while (y,m)<=(last_y,last_m):
        result.append(f'{y:04d}-{m:02d}')
        m+=1
        if m==13:y,m=y+1,1
    return result

def summary(current,candidates,metric):
    usable=[c for c in candidates if finite(c['values'].get(metric))]
    values=[c['values'][metric] for c in usable]
    avg=mean(values) if values else None
    ready=finite(current) and len(values)>=3
    quality='available' if ready else 'current_value_missing' if not finite(current) else 'insufficient_same_season_history'
    delta=current-avg if ready else None
    pct=(current/avg-1)*100 if ready and avg>0 else None
    position=('above_historical_max' if current>max(values) else 'below_historical_min' if current<min(values) else 'within_historical_range') if ready else None
    return {'current':current,'unit':METRICS[metric],'baseline_n':len(values),
            'baseline_mean':avg,'baseline_median':median(values) if values else None,
            'baseline_min':min(values) if values else None,'baseline_max':max(values) if values else None,
            'baseline_periods':[c['period'] for c in usable],
            'difference':delta,'change_pct':pct,
            'percent_status':'available' if pct is not None else 'zero_baseline_mean' if ready else 'comparison_unavailable',
            'historical_range_position':position,'quality_status':quality,
            'not_statistical_significance_or_weather_alert':True}

def candidates_for_month(stored,current_period):
    return [{'period':p,'months':[p],'values':stored[p]} for p in sorted(stored)
            if START<=p<=END and p<current_period and p[5:]==current_period[5:]]

def candidates_for_window(stored,label):
    result=[]
    for year in range(int(START[:4]),int(END[:4])+2):
        candidate=f'{year:04d}'+label[4:]
        w=window(candidate)
        periods=w['observation_months']
        if candidate>=label or periods[0]<START or periods[-1]>END:continue
        values={metric:sum(stored[p][metric] for p in periods)
                if all(p in stored and finite(stored[p].get(metric)) for p in periods) else None
                for metric in METRICS}
        result.append({'period':candidate,'months':periods,'values':values})
    return result

def payload(stored,current_period,observation=None):
    if observation is None:
        periods=[current_period];candidates=candidates_for_month(stored,current_period)
        values=stored[current_period]
        scope='actual_weather_month';observed_start=current_period+'-01'
        year,month=map(int,current_period.split('-'))
        observed_end=f'{current_period}-{calendar.monthrange(year,month)[1]:02d}'
    else:
        periods=observation['observation_months'];candidates=candidates_for_window(stored,current_period)
        values=observation['totals'];scope='behavior_observation_three_month_window'
        observed_start=observation['observation_start'];observed_end=observation['observation_end']
    metrics={metric:summary(values.get(metric),candidates,metric) for metric in METRICS}
    return {'method_version':VERSION,'period':current_period,'scope':scope,
            'observation_months':periods,'observation_start':observed_start,'observation_end':observed_end,
            'baseline_start':START,'baseline_end':END,'tracking_start':TRACK_START,
            'baseline_method':'fixed_prior_same_calendar_month' if observation is None else 'fixed_prior_same_three_calendar_months',
            'minimum_reference_windows':3,'baseline_candidates':candidates,'metrics':metrics,
            'quality_status':'available' if all(m['quality_status']=='available' for m in metrics.values()) else 'partial' if any(m['quality_status']=='available' for m in metrics.values()) else 'unavailable',
            'geography':'same_source_weather_common_context_not_dong_specific',
            'station_scope_verified':False,'retrospective_only':True,
            'not_detection_input':True,'causal_adjustment_applied':False,
            'note':'Historical-range position is descriptive, not an anomaly threshold. Compare overlapping windows as context, not independent repeated events.'}

def upsert(c,scope,period,p):
    table='ctx_weather_month_tracking' if scope=='month' else 'ctx_weather_window_tracking'
    key='period' if scope=='month' else 'date'
    text=canonical(p);old=c.execute(f'SELECT payload_json FROM {table} WHERE {key}=?',(period,)).fetchone()
    if old and old[0]==text:return 0
    if old:
        previous=json.loads(old[0])
        if previous['method_version']!=VERSION:raise ValueError('Weather tracking version migration required')
        changed=[]
        for metric in METRICS:
            a=previous['metrics'][metric]['current'];b=p['metrics'][metric]['current']
            if a!=b:
                if a is not None or not finite(b):raise ValueError('Historical tracked weather change blocked '+period)
                changed.append(metric)
        if not changed:raise ValueError('Historical weather comparison revision blocked '+period)
        c.execute('INSERT INTO ctx_weather_tracking_revision(scope,period,previous_json,current_json) VALUES(?,?,?,?)',(scope,period,old[0],text))
        c.execute(f'UPDATE {table} SET payload_json=? WHERE {key}=?',(text,period))
    else:c.execute(f'INSERT INTO {table} VALUES(?,?)',(period,text))
    return 1

def run(c):
    stored={p:json.loads(j) for p,j in c.execute('SELECT period,payload_json FROM ctx_weather_month')}
    reference={p:stored.get(p) for p in months()}
    fingerprint=hashlib.sha256(canonical(reference).encode()).hexdigest()
    old=c.execute('SELECT fingerprint FROM ctx_weather_tracking_reference WHERE version=?',(VERSION,)).fetchone()
    if old and old[0]!=fingerprint:raise ValueError('Weather baseline revision requires explicit new method version')
    if not old:c.execute('INSERT INTO ctx_weather_tracking_reference VALUES(?,?,?)',(VERSION,fingerprint,canonical(reference)))
    month_n=0;window_n=0
    for period in sorted(stored):
        if period>=TRACK_START:month_n+=upsert(c,'month',period,payload(stored,period))
    for label,j in c.execute('SELECT date,payload_json FROM ctx_weather_window ORDER BY date').fetchall():
        if label[:7]>=TRACK_START:window_n+=upsert(c,'window',label,payload(stored,label,json.loads(j)))
    return {'new_or_enriched_months':month_n,'new_or_enriched_windows':window_n,'baseline_fingerprint':fingerprint,'existing_detection_modified':False}

def export(c,output):
    path=Path(output);path.mkdir(parents=True,exist_ok=True)
    fields=['period','observation_months','metric','current','unit','baseline_n','baseline_mean','baseline_median','baseline_min','baseline_max','difference','change_pct','percent_status','historical_range_position','quality_status','baseline_periods']
    for table,filename,key in [('ctx_weather_month_tracking','weather_month_tracking.csv','period'),('ctx_weather_window_tracking','weather_window_tracking.csv','date')]:
        with (path/filename).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
            for (j,) in c.execute('SELECT payload_json FROM '+table+' ORDER BY '+key):
                p=json.loads(j)
                for metric,m in p['metrics'].items():
                    row={k:m.get(k) for k in fields}
                    row.update(period=p['period'],observation_months=','.join(p['observation_months']),metric=metric,baseline_periods=','.join(m['baseline_periods']))
                    writer.writerow(row)

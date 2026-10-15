"""Descriptive seasonal level tracking; never writes detection flags or risk scores."""
from pathlib import Path
from statistics import median
from collections import defaultdict
from contextlib import closing
import argparse,csv,hashlib,json,math,sqlite3

METRICS=('call_contacts','text_contacts')
BASELINE_END='2025-06-01'
SETTINGS={'method':'a2_activity_level_v1','baseline_end':BASELINE_END,'min_same_month_years':3,'min_peer_dongs':11,'min_valid_population':200,'min_coverage':0.8,'recovery_reference':'month_immediately_before_signal','interpretation':'descriptive_not_isolation_risk'}
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False)
def prior_month(date):
    y,m=map(int,date[:7].split('-'));return f'{y if m>1 else y-1:04d}-{m-1 if m>1 else 12:02d}-01'
def valid(row,m):
    if not row:return False
    value=row.get(m);pop=row.get(m+'_valid_population');total=row.get('total_population')
    return all(isinstance(v,(int,float)) and math.isfinite(v) for v in (value,pop,total)) and value>0 and total>0 and pop>=SETTINGS['min_valid_population'] and SETTINGS['min_coverage']<=pop/total<=1.00000001
def state(values):
    if any(v is None for v in values):return 'unavailable'
    # Zero means equality to the pre-signal comparison level, not a risk threshold.
    if all(v>=-1e-10 for v in values):return 'recovered_to_reference'
    if all(v<-1e-10 for v in values):return 'both_below_reference'
    return 'mixed_recovery'
def compute(features,events):
    rows={};dates=set();codes=set();ages=set()
    for source in features:
        r=dict(source);r['date']=r['date'][:10];r['adm_cd']=str(r.get('adm_cd',r.get('행정동코드')))
        key=(r['adm_cd'],r['age_band'],r['date'])
        if key in rows:raise ValueError('Duplicate feature key')
        rows[key]=r;dates.add(r['date']);codes.add(r['adm_cd']);ages.add(r['age_band'])
    if not rows:raise ValueError('No service features')
    expected={(code,age) for code in codes for age in ages}
    for date in dates:
        if {(code,age) for code,age,d in rows if d==date}!=expected:raise ValueError('Incomplete monthly service grid')
        if date[8:10]!='01':raise ValueError('Expected month start dates')
    ordered=sorted(dates)
    if any(prior_month(b)!=a for a,b in zip(ordered,ordered[1:])):raise ValueError('Missing monthly feature history')
    hist=defaultdict(list)
    for (code,age,date),r in rows.items():
        if date<=BASELINE_END:
            for m in METRICS:
                if valid(r,m):hist[(code,age,date[5:7],m)].append((date,r[m]))
    baseline={};levels={}
    for key,values in hist.items():
        values=sorted(values);baseline[key]={'n':len(values),'periods':[x[0] for x in values],'value':median(x[1] for x in values)}
    for (code,age,date),r in sorted(rows.items()):
        payload={'adm_cd':code,'adm_nm':r.get('행정동',r.get('adm_nm')),'age_band':age,'date':date,'raw':{},'seasonal_reference':{},'seasonal_index':{},'quality':{},'interpretation':'retrospective_descriptive_not_risk'}
        for m in METRICS:
            b=baseline.get((code,age,date[5:7],m),{'n':0,'periods':[],'value':None})
            usable=valid(r,m) and b['n']>=SETTINGS['min_same_month_years']
            payload['raw'][m]=r.get(m);payload['seasonal_reference'][m]=b
            payload['seasonal_index'][m]=r[m]/b['value'] if usable else None
            payload['quality'][m]='ready' if usable else ('current_invalid' if not valid(r,m) else 'insufficient_same_month_history')
        levels[(code,age,date)]=payload
    tracks=[]
    for event in sorted(events,key=lambda e:(e['date'],e['adm_cd'],e['age_band'],e['model_version'])):
        code,age,start=event['adm_cd'],event['age_band'],event['date'];anchor=prior_month(start)
        streak=0
        for date in sorted(d for d in dates if d>=start):
            current=levels.get((code,age,date));pre=levels.get((code,age,anchor))
            if current is None:raise ValueError('Missing tracked month')
            result={'adm_cd':code,'adm_nm':current['adm_nm'],'age_band':age,'signal_date':start,'date':date,'detection_model_version':event['model_version'],'reference_date':anchor,'trigger_domains':[m for m in ('communication','mobility') if event.get(m+'_signal')==1],'raw_change_pct':{},'seasonal_change_pct':{},'common_change_pct':{},'local_change_pct':{},'peer_n':{},'quality':current['quality'],'comparison_note':'same_calendar_month_baseline_normalization_then_pre_signal_ratio; district_median_includes_target; overlapping_source_windows_not_independent'}
            for m in METRICS:
                a=current['seasonal_index'][m];b=pre['seasonal_index'][m] if pre else None
                seasonal=(a/b-1)*100 if a is not None and b is not None else None
                pairs=[]
                for peer in codes:
                    pc=levels.get((peer,age,date));pp=levels.get((peer,age,anchor))
                    if pc and pp and pc['seasonal_index'][m] is not None and pp['seasonal_index'][m] is not None:
                        pairs.append(pc['seasonal_index'][m]/pp['seasonal_index'][m])
                common=median(pairs) if len(pairs)>=SETTINGS['min_peer_dongs'] else None
                result['peer_n'][m]=len(pairs)
                result['raw_change_pct'][m]=(current['raw'][m]/pre['raw'][m]-1)*100 if pre and valid(rows[(code,age,date)],m) and valid(rows[(code,age,anchor)],m) else None
                result['seasonal_change_pct'][m]=seasonal
                result['common_change_pct'][m]=(common-1)*100 if common is not None else None
                result['local_change_pct'][m]=((1+seasonal/100)/common-1)*100 if seasonal is not None and common is not None else None
            result['raw_state']=state(list(result['raw_change_pct'].values()))
            result['seasonal_state']=state(list(result['seasonal_change_pct'].values()))
            result['local_state']=state(list(result['local_change_pct'].values()))
            streak=streak+1 if result['seasonal_state']=='both_below_reference' else 0
            result['consecutive_both_below_months']=streak
            result['months_since_signal']=(int(date[:4])-int(start[:4]))*12+int(date[5:7])-int(start[5:7])
            tracks.append(result)
    source_baseline=[{'key':list(key),'values':{m:r.get(m) for m in (*METRICS,*(m+'_valid_population' for m in METRICS),'total_population')}} for key,r in sorted(rows.items()) if key[2]<=BASELINE_END]
    signature=hashlib.sha256(canonical({'settings':SETTINGS,'source_baseline':source_baseline,'baseline':[{ 'key':list(k),**v} for k,v in sorted(baseline.items())]}).encode()).hexdigest()
    return [v for (_,_,date),v in sorted(levels.items()) if date>BASELINE_END],tracks,signature

SCHEMA='''
CREATE TABLE IF NOT EXISTS a2_activity_model(version TEXT PRIMARY KEY,settings_json TEXT NOT NULL,baseline_fingerprint TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS a2_activity_level(adm_cd TEXT NOT NULL,date TEXT NOT NULL,age_band TEXT NOT NULL,version TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(adm_cd,date,age_band,version),FOREIGN KEY(version) REFERENCES a2_activity_model(version));
CREATE TABLE IF NOT EXISTS a2_activity_followup(adm_cd TEXT NOT NULL,signal_date TEXT NOT NULL,date TEXT NOT NULL,age_band TEXT NOT NULL,detection_model_version TEXT NOT NULL,version TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(adm_cd,signal_date,date,age_band,detection_model_version,version),FOREIGN KEY(version) REFERENCES a2_activity_model(version));
CREATE VIEW IF NOT EXISTS v_a2_activity_followup AS SELECT adm_cd,signal_date,date,age_band,detection_model_version,version,json_extract(payload_json,'$.raw_state') AS raw_state,json_extract(payload_json,'$.seasonal_state') AS seasonal_state,json_extract(payload_json,'$.local_state') AS local_state,payload_json FROM a2_activity_followup;
CREATE VIEW IF NOT EXISTS v_a2_activity_followup_latest AS SELECT t.* FROM v_a2_activity_followup t WHERE t.date=(SELECT MAX(x.date) FROM a2_activity_followup x WHERE x.adm_cd=t.adm_cd AND x.age_band=t.age_band AND x.signal_date=t.signal_date AND x.detection_model_version=t.detection_model_version AND x.version=t.version);
'''
def run(db,output=None):
    with closing(sqlite3.connect(db)) as c:
        c.execute('PRAGMA foreign_keys=ON')
        features=[json.loads(r[0]) for r in c.execute("SELECT feature_json FROM a2_age_feature WHERE age_scheme='service' ORDER BY date,adm_cd,age_band")]
        events=[dict(zip(['adm_cd','date','age_band','model_version','communication_signal','mobility_signal'],r)) for r in c.execute('SELECT adm_cd,date,age_band,model_version,communication_signal,mobility_signal FROM a2_age_detection WHERE communication_signal=1 OR mobility_signal=1 ORDER BY date,adm_cd,age_band,model_version')]
        levels,tracks,fingerprint=compute(features,events)
        version=SETTINGS['method']+'_'+fingerprint[:12]
        c.executescript(SCHEMA)
        with c:
            prior_versions={r[0] for r in c.execute('SELECT version FROM a2_activity_model')}
            if prior_versions and version not in prior_versions:raise ValueError('Baseline/settings changed; explicit model migration required')
            c.execute('INSERT OR IGNORE INTO a2_activity_model VALUES(?,?,?)',(version,canonical(SETTINGS),fingerprint))
            inserted={}
            for table,records,fields in [('a2_activity_level',levels,['adm_cd','date','age_band']),('a2_activity_followup',tracks,['adm_cd','signal_date','date','age_band','detection_model_version'])]:
                count=0
                for record in records:
                    key=[record[k] for k in fields]+[version];payload=canonical(record)
                    where=' AND '.join(f'{k}=?' for k in fields+['version'])
                    existing=c.execute(f'SELECT payload_json FROM {table} WHERE {where}',key).fetchone()
                    if existing and existing[0]!=payload:raise ValueError('Changed historical tracking result; explicit revision required: '+str(key))
                    if not existing:
                        c.execute(f"INSERT INTO {table} VALUES({','.join('?' for _ in key)},?)",key+[payload]);count+=1
                inserted[table]=count
        report={'version':version,'baseline_fingerprint':fingerprint,'level_rows':len(levels),'followup_rows':len(tracks),'events':len(events),'inserted':inserted,'existing_detection_untouched':True}
    if output:export(db,output)
    return report
def export(db,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(db)) as c:
        for table,name in [('a2_activity_level','activity_level.csv'),('a2_activity_followup','activity_followup.csv')]:
            cursor=c.execute(f'SELECT * FROM {table} ORDER BY adm_cd,date,age_band,version')
            with (output/name).open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.writer(f);w.writerow([col[0] for col in cursor.description]);w.writerows(cursor)
        (output/'activity_followup_latest.json').write_text(json.dumps([json.loads(r[0]) for r in c.execute('SELECT t.payload_json FROM a2_activity_followup t WHERE t.date=(SELECT MAX(x.date) FROM a2_activity_followup x WHERE x.adm_cd=t.adm_cd AND x.age_band=t.age_band AND x.signal_date=t.signal_date AND x.detection_model_version=t.detection_model_version AND x.version=t.version) ORDER BY signal_date,adm_cd,age_band')],ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--db',required=True);parser.add_argument('--output');parser.add_argument('--export-only',action='store_true');args=parser.parse_args()
    if args.export_only:
        if not args.output:parser.error('--output required for export-only')
        export(args.db,args.output)
    else:print(json.dumps(run(args.db,args.output),ensure_ascii=False,indent=2))

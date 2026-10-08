"""Descriptive seasonal level tracking; never writes detection flags or risk scores."""
from pathlib import Path
from statistics import median
from collections import defaultdict
from contextlib import closing
import argparse,csv,hashlib,json,math,sqlite3

METRICS=('call_contacts','text_contacts','weekday_move_count','weekend_move_count')
DOMAINS={'communication':METRICS[:2],'mobility':METRICS[2:]}
BASELINE_END='2025-06-01'
SETTINGS={'method':'a2_activity_level_v2','tracked_metrics':list(METRICS),'baseline_end':BASELINE_END,'min_same_month_years':3,'min_peer_dongs':11,'min_valid_population':200,'min_coverage':0.8,'recovery_reference':'month_immediately_before_signal','interpretation':'descriptive_not_isolation_risk'}
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

def metric_state(value):
    return 'unavailable' if value is None else 'at_or_above_reference' if value>=-1e-10 else 'below_reference'

def episode_events(events):
    """Keep the first event of consecutive signals; retain later separate episodes."""
    selected=[];previous={}
    for event in sorted(events,key=lambda e:(e['date'],e['adm_cd'],e['age_band'],e['model_version'])):
        key=(event['adm_cd'],event['age_band'],event['model_version'])
        if previous.get(key)!=prior_month(event['date']):selected.append(event)
        previous[key]=event['date']
    return selected

def recovery_status(states):
    # Relative recovery cannot override a raw/seasonal shortfall.
    raw,seasonal=states['raw_state'],states['seasonal_state']
    if 'unavailable' in (raw,seasonal):return 'unavailable'
    if raw==seasonal=='recovered_to_reference':return 'reference_level_reached'
    if raw==seasonal=='both_below_reference':return 'below_reference'
    return 'mixed_recovery_or_basis'
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
    for event in episode_events(events):
        code,age,start=event['adm_cd'],event['age_band'],event['date'];anchor=prior_month(start)
        streaks={domain:0 for domain in DOMAINS};all_streak=0
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
            result['tracked_metrics']=list(METRICS)
            result['reference_quality']=pre['quality'] if pre else {m:'reference_missing' for m in METRICS}
            result['metric_states']={m:{scope:metric_state(result[scope+'_change_pct'][m]) for scope in ['raw','seasonal','local']} for m in METRICS}
            result['domain_states']={}
            for domain,metrics in DOMAINS.items():
                states={scope+'_state':state([result[scope+'_change_pct'][m] for m in metrics]) for scope in ['raw','seasonal','local']}
                streaks[domain]=streaks[domain]+1 if states['seasonal_state']=='both_below_reference' else 0
                states.update(metrics=list(metrics),consecutive_both_below_months=streaks[domain],recovery_status=recovery_status(states))
                result['domain_states'][domain]=states
            result['overall_states']={scope+'_state':{'both_below_reference':'all_below_reference','recovered_to_reference':'all_at_or_above_reference'}.get(state(list(result[scope+'_change_pct'].values())),state(list(result[scope+'_change_pct'].values()))) for scope in ['raw','seasonal','local']}
            domain_statuses=[s['recovery_status'] for s in result['domain_states'].values()]
            result['overall_recovery_status']='unavailable_or_partial' if 'unavailable' in domain_statuses else 'reference_level_reached' if all(s=='reference_level_reached' for s in domain_statuses) else 'partial_recovery' if 'reference_level_reached' in domain_statuses else 'below_reference' if all(s=='below_reference' for s in domain_statuses) else 'mixed_recovery_or_basis'
            all_streak=all_streak+1 if result['overall_states']['seasonal_state']=='all_below_reference' else 0
            result['consecutive_all_below_months']=all_streak
            # Legacy fields retain their original communication-only meaning.
            for field in ['raw_state','seasonal_state','local_state','consecutive_both_below_months']:
                result[field]=result['domain_states']['communication'][field]
            result['legacy_state_scope']='communication'
            result['recovery_confirmation']='descriptive_level_comparison_only_not_sustained_recovery_confirmation'
            result['months_since_signal']=(int(date[:4])-int(start[:4]))*12+int(date[5:7])-int(start[5:7])
            tracks.append(result)
    source_baseline=[{'key':list(key),'values':{m:r.get(m) for m in (*METRICS,*(m+'_valid_population' for m in METRICS),'total_population')}} for key,r in sorted(rows.items()) if key[2]<=BASELINE_END]
    signature=hashlib.sha256(canonical({'settings':SETTINGS,'source_baseline':source_baseline,'baseline':[{ 'key':list(k),**v} for k,v in sorted(baseline.items())]}).encode()).hexdigest()
    return [v for (_,_,date),v in sorted(levels.items()) if date>BASELINE_END],tracks,signature

SCHEMA='''
CREATE TABLE IF NOT EXISTS a2_activity_model(version TEXT PRIMARY KEY,settings_json TEXT NOT NULL,baseline_fingerprint TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS a2_activity_level(adm_cd TEXT NOT NULL,date TEXT NOT NULL,age_band TEXT NOT NULL,version TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(adm_cd,date,age_band,version),FOREIGN KEY(version) REFERENCES a2_activity_model(version));
CREATE TABLE IF NOT EXISTS a2_activity_followup(adm_cd TEXT NOT NULL,signal_date TEXT NOT NULL,date TEXT NOT NULL,age_band TEXT NOT NULL,detection_model_version TEXT NOT NULL,version TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(adm_cd,signal_date,date,age_band,detection_model_version,version),FOREIGN KEY(version) REFERENCES a2_activity_model(version));
CREATE TABLE IF NOT EXISTS a2_activity_active_model(singleton INTEGER PRIMARY KEY CHECK(singleton=1),version TEXT NOT NULL REFERENCES a2_activity_model(version));
DROP VIEW IF EXISTS v_a2_activity_followup_latest;
DROP VIEW IF EXISTS v_a2_activity_followup;
DROP VIEW IF EXISTS v_a2_activity_level;
CREATE VIEW v_a2_activity_level AS SELECT l.* FROM a2_activity_level l JOIN a2_activity_active_model a ON a.version=l.version;
CREATE VIEW v_a2_activity_followup AS SELECT t.adm_cd,t.signal_date,t.date,t.age_band,t.detection_model_version,t.version,json_extract(t.payload_json,'$.raw_state') AS raw_state,json_extract(t.payload_json,'$.seasonal_state') AS seasonal_state,json_extract(t.payload_json,'$.local_state') AS local_state,json_extract(t.payload_json,'$.overall_recovery_status') AS overall_recovery_status,t.payload_json FROM a2_activity_followup t JOIN a2_activity_active_model a ON a.version=t.version;
CREATE VIEW v_a2_activity_followup_latest AS SELECT t.* FROM v_a2_activity_followup t WHERE t.date=(SELECT MAX(x.date) FROM v_a2_activity_followup x WHERE x.adm_cd=t.adm_cd AND x.age_band=t.age_band AND x.signal_date=t.signal_date AND x.detection_model_version=t.detection_model_version);
CREATE VIEW IF NOT EXISTS v_a2_activity_followup_all_versions AS SELECT * FROM a2_activity_followup;
'''
def run(db,output=None,migrate_from_v1=False):
    with closing(sqlite3.connect(db)) as c:
        c.execute('PRAGMA foreign_keys=ON')
        features=[json.loads(r[0]) for r in c.execute("SELECT feature_json FROM a2_age_feature WHERE age_scheme='service' ORDER BY date,adm_cd,age_band")]
        events=[dict(zip(['adm_cd','date','age_band','model_version','communication_signal','mobility_signal'],r)) for r in c.execute('SELECT adm_cd,date,age_band,model_version,communication_signal,mobility_signal FROM a2_age_detection WHERE communication_signal=1 OR mobility_signal=1 ORDER BY date,adm_cd,age_band,model_version')]
        events=episode_events(events)
        levels,tracks,fingerprint=compute(features,events)
        version=SETTINGS['method']+'_'+fingerprint[:12]
        exists=c.execute("SELECT 1 FROM sqlite_master WHERE name='a2_activity_model'").fetchone()
        prior={v:json.loads(s) for v,s in c.execute('SELECT version,settings_json FROM a2_activity_model')} if exists else {}
        if prior and version not in prior:
            if any(s.get('method')==SETTINGS['method'] for s in prior.values()):raise ValueError('Baseline/settings changed; explicit model migration required')
            if not migrate_from_v1 or any(s.get('method')!='a2_activity_level_v1' for s in prior.values()):raise ValueError('Four-metric tracking requires explicit --migrate-from-v1')
        with c:
            c.executescript('BEGIN IMMEDIATE;'+SCHEMA)
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
            c.execute('INSERT INTO a2_activity_active_model VALUES(1,?) ON CONFLICT(singleton) DO UPDATE SET version=excluded.version',(version,))
        report={'version':version,'baseline_fingerprint':fingerprint,'tracked_metrics':list(METRICS),'level_rows':len(levels),'followup_rows':len(tracks),'events':len(events),'inserted':inserted,'existing_detection_untouched':True,'legacy_v1_preserved':any(s.get('method')=='a2_activity_level_v1' for s in prior.values())}
    if output:export(db,output)
    return report
def export(db,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(db)) as c:
        for table,name in [('v_a2_activity_level','activity_level.csv'),('v_a2_activity_followup','activity_followup.csv')]:
            cursor=c.execute(f'SELECT * FROM {table} ORDER BY adm_cd,date,age_band,version')
            with (output/name).open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.writer(f);w.writerow([col[0] for col in cursor.description]);w.writerows(cursor)
        (output/'activity_followup_latest.json').write_text(json.dumps([json.loads(r[0]) for r in c.execute('SELECT payload_json FROM v_a2_activity_followup_latest ORDER BY signal_date,adm_cd,age_band')],ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--db',required=True);parser.add_argument('--output');parser.add_argument('--export-only',action='store_true');parser.add_argument('--migrate-from-v1',action='store_true');args=parser.parse_args()
    if args.export_only:
        if not args.output:parser.error('--output required for export-only')
        export(args.db,args.output)
    else:print(json.dumps(run(args.db,args.output,args.migrate_from_v1),ensure_ascii=False,indent=2))

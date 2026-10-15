"""Replay one label month at a time, keeping June-only seed history immutable."""
from __future__ import annotations
import argparse,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'DB1/Analysis2'),str(ROOT/'DB1'),str(ROOT/'DB1/Context')]
import pandas as pd
import db1_store as store
import age_features as ages
import age_detection as detect_age
import source_semantics
import activity_level
from preprocessing.monthly_features import build_month_feature_frames
from data.monthly_validation import validate_history,validate_feature_rows
from analysis.sequential import run_month
from analysis.outputs import build_evidence_card

EXTRA_SCHEMA='''
CREATE TABLE IF NOT EXISTS pipeline_state(id INTEGER PRIMARY KEY CHECK(id=1),payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS month_run(period TEXT PRIMARY KEY,input_hash TEXT,method_version TEXT NOT NULL,stage TEXT NOT NULL,output_json TEXT,error TEXT,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS a2_month_input(date TEXT NOT NULL,adm_cd TEXT NOT NULL,feature_json TEXT NOT NULL,PRIMARY KEY(date,adm_cd));
CREATE TABLE IF NOT EXISTS a2_age_month_input(date TEXT NOT NULL,adm_cd TEXT NOT NULL,age_scheme TEXT NOT NULL,age_band TEXT NOT NULL,feature_json TEXT NOT NULL,PRIMARY KEY(date,adm_cd,age_scheme,age_band));
CREATE TABLE IF NOT EXISTS input_import(path TEXT PRIMARY KEY,sha256 TEXT NOT NULL,kind TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ctx_weather(date TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ctx_elder_annual(adm_cd TEXT NOT NULL,year INTEGER NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(adm_cd,year));
CREATE TABLE IF NOT EXISTS ctx_survey_annual(survey TEXT NOT NULL,year INTEGER NOT NULL,district TEXT NOT NULL,age_band TEXT NOT NULL,metric TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(survey,year,district,age_band,metric));
CREATE TABLE IF NOT EXISTS ctx_youth_reference(kind TEXT NOT NULL,year INTEGER NOT NULL,district TEXT NOT NULL,age_band TEXT NOT NULL,metric TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(kind,year,district,age_band,metric));
CREATE TABLE IF NOT EXISTS ctx_evidence_guide(guide_id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
'''

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def state(db,**kwargs):
    with store.connect(db) as con:
        con.execute('INSERT OR REPLACE INTO pipeline_state VALUES(1,?)',(store.payload(kwargs),))

def import_once(con,path,kind):
    name=str(path.relative_to(ROOT)).replace('\\','/');sha=digest(path)
    old=con.execute('SELECT sha256 FROM input_import WHERE path=?',(name,)).fetchone()
    if old and old[0]!=sha:raise ValueError(f'Approved input changed; explicit revision required: {name}')
    if old:return False
    con.execute('INSERT INTO input_import VALUES(?,?,?)',(name,sha,kind));return True

def seed_supplements(con):
    ref=ROOT/'data/reference/analysis3'
    definitions={
        'a3a_feature':('period','adm_cd','age','domain','observed_industries'),
        'a3a_comparison':('period','adm_cd','age','domain','baseline_n','comparison_available'),
        'a3b_feature':('period','district','age','domain','observed_industries'),
        'a3b_total':('period','district','age'),
        'a3a_quarter_summary':('period','adm_cd'),
        'a3b_month_summary':('period','district')}
    for table,keys in definitions.items():
        path=ref/(table+'.csv')
        if not import_once(con,path,'provided_analysis3_export'):continue
        frame=pd.read_csv(path,dtype={'adm_cd':str,'district':str})
        keycols=keys[:4] if table.endswith(('feature','comparison')) else keys
        if frame.duplicated(list(keycols)).any():raise ValueError('Duplicate Analysis3 keys: '+table)
        for row in store.records(frame):
            values=[int(row[k]) if k in {'baseline_n','comparison_available','observed_industries'} else row[k] for k in keys]
            con.execute(f'INSERT INTO {table} VALUES({",".join("?" for _ in range(len(keys)+1))})',(*values,store.payload(row)))
    path=ref/'a3_run.csv'
    if import_once(con,path,'provided_analysis3_export'):
        for row in store.records(pd.read_csv(path)):
            metadata=json.loads(row['metadata_json'])
            metadata.update(import_mode='provided_preprocessed_export',export_sha256=digest(path),retrospective_only=True)
            con.execute('INSERT INTO a3_run(source,period,fingerprint,version,available_from,metadata_json) VALUES(?,?,?,?,?,?)',
                (row['source'],row['period'],row['fingerprint'],row['version'],row['available_from'],store.payload(metadata)))
    con.execute('INSERT OR IGNORE INTO a3_dimension SELECT DISTINCT age,domain FROM a3a_feature')

def seed_annual_context(con):
    ref=ROOT/'data/reference/context'
    path=ref/'analysis1_elder_annual.csv'
    if import_once(con,path,'provided_annual_context'):
        for row in store.records(pd.read_csv(path,dtype={'adm_cd':str})):
            payload=json.loads(row['payload_json']);payload.update(available_from=row['available_from'],retrospective_only=True)
            con.execute('INSERT INTO ctx_elder_annual VALUES(?,?,?)',(row['adm_cd'],int(row['year']),store.payload(payload)))
    for name,table,first in [('v_survey_annual.csv','ctx_survey_annual','survey'),('v_youth_detail.csv','ctx_youth_reference','kind')]:
        path=ref/name
        if not import_once(con,path,'provided_annual_context'):continue
        for row in store.records(pd.read_csv(path)):
            row['definition']=json.loads(row.pop('payload_json'));row['not_detection_input']=True
            con.execute(f'INSERT INTO {table} VALUES(?,?,?,?,?,?)',
                (row[first],int(row['year']),row['district'],row['age_band'],row['metric'],store.payload(row)))
    path=ref/'ctx_evidence_guide.csv'
    if import_once(con,path,'provided_explanation_guide'):
        for row in store.records(pd.read_csv(path)):
            row['definition']=json.loads(row.pop('payload_json'))
            con.execute('INSERT INTO ctx_evidence_guide VALUES(?,?)',(row['guide_id'],store.payload(row)))

def initialize(cfg):
    db=cfg['database'];store.initialize(db)
    with store.connect(db) as con:
        con.executescript(ages.SCHEMA+detect_age.SCHEMA+activity_level.SCHEMA+source_semantics.SCHEMA+EXTRA_SCHEMA)
        con.executescript((ROOT/'DB1/Analysis3/db/schema.sql').read_text(encoding='utf-8'))
        con.executescript((ROOT/'data_pipeline/integrated.sql').read_text(encoding='utf-8'))
    initial_path=ROOT/'data/reference/analysis2_initial_history_202201_202506.csv'
    initial=pd.read_csv(initial_path);initial['date']=pd.to_datetime(initial.date);validate_history(initial)
    store.seed_history(db,initial)
    with store.connect(db) as con:
        con.execute('BEGIN IMMEDIATE');import_once(con,initial_path,'initial_overall_history')
        for scheme,expected in [('service',4620),('five_year',11088)]:
            path=ROOT/'data/reference/age'/f'{scheme}_baseline.csv'
            if not import_once(con,path,'initial_age_history'):continue
            f=pd.read_csv(path);f['date']=pd.to_datetime(f.date,format='mixed')
            if len(f)!=expected or f.date.max()!=pd.Timestamp('2025-06-01') or f.date.min()!=pd.Timestamp('2022-01-01'):
                raise ValueError('Age seed must contain January 2022 through June 2025 only')
            if f.duplicated(['date','행정동코드','age_scheme','age_band']).any():raise ValueError('Duplicate age seed')
            if scheme=='service':detect_age.validate_features(f,detect_age.DEFAULT)
            expected_bands=set(ages.BANDS if scheme=='service' else map(str,ages.AGES))
            seed_codes=set(initial['행정동코드'])
            for _,g in f.groupby('date'):
                if set(g['행정동코드'])!=seed_codes or set(g.age_band.astype(str))!=expected_bands or len(g)!=22*len(expected_bands):
                    raise ValueError('Incomplete initial age grid')
            for row in store.records(f):
                con.execute('INSERT INTO a2_age_feature VALUES(?,?,?,?,?,?,?,?)',
                    (str(row['행정동코드']),str(pd.Timestamp(row['date']).date()),scheme,str(row['age_band']),
                     ages.VERSION,'baseline',row['quality_status'],store.payload(row)))
        for month in pd.date_range('2022-01-01','2025-06-01',freq='MS'):
            con.execute('INSERT OR IGNORE INTO a2_age_source VALUES(?,?,?)',
                (str(month.date()),'provided_baseline_'+str(month.date()),store.payload({'mode':'provided_preprocessed_initial_history','raw_available':False})))
        seed_supplements(con)
        seed_annual_context(con)

def find_file(directory,period,keyword):
    pattern=re.compile(rf'{period.year}[^0-9]+0?{period.month}월.*{keyword}')
    found=[p for p in Path(directory).glob('*.xlsx') if pattern.search(p.name) and not p.name.startswith('~$')]
    if len(found)>1:raise ValueError(f'Multiple raw files for {period:%Y-%m}: {keyword}')
    return found[0] if found else None

def weather_context(cfg,period):
    rain=pd.read_csv(cfg['analysis2']['rain'],encoding='utf-8-sig')
    diary=pd.read_csv(cfg['analysis2']['diary'],encoding='utf-8-sig')
    def month_values(month):
        y,m=map(int,month.split('-'));key=f'{y}. {m:02d}'
        if key not in rain or not diary['시점'].eq(key).any():
            return {'month':month,'rainfall_mm':None,'rain_days':None,'snow_days':None,'status':'missing'}
        snow=diary.loc[diary['시점'].eq(key),'눈'].iloc[0]
        return {'month':month,'rainfall_mm':float(rain.loc[rain['항목'].eq('강수량 (㎜)'),key].iloc[0]),
            'rain_days':float(rain.loc[rain['항목'].eq('강수일수 (일)'),key].iloc[0]),
            'snow_days':None if str(snow).strip()=='-' else float(snow),
            'snow_status':'missing_symbol' if str(snow).strip()=='-' else 'observed'}
    label=period.strftime('%Y-%m');window=source_semantics.window(label+'-01')
    return {'label_weather':month_values(label),'observation_month_weather':[month_values(m) for m in window['observation_months']],
        'scope':'Seoul_city_shared_context','legacy_snow_dash_to_zero':True,
        'snow_dash_explanation':'Legacy feature reproduction uses zero; user-facing context preserves the missing symbol.',
        'signal_rule_uses_weather':False}

def source_metadata(cfg,period,t,i):
    weather=weather_context(cfg,period)
    def name(path):
        try:return str(path.relative_to(ROOT)).replace('\\','/')
        except ValueError:return path.name
    return {'telecom':{'path':name(t),'sha256':digest(t)},
        'interest':{'path':name(i),'sha256':digest(i)},
        'weather_sha256':hashlib.sha256(store.payload(weather).encode()).hexdigest(),
        'label_month':period.strftime('%Y-%m'),'mode':'local_raw_replay','network_download':False}

def verify_saved_sources(cfg):
    with store.connect(cfg['database']) as con:
        runs=con.execute("SELECT period,metadata_json FROM db1_run WHERE analysis='analysis2'").fetchall()
    for date,payload in runs:
        old=json.loads(payload);p=pd.Timestamp(date)
        t=find_file(cfg['analysis2']['telecom_dir'],p,'29개');i=find_file(cfg['analysis2']['interest_dir'],p,'10개')
        if t is None and i is None:continue
        if t is None or i is None:raise ValueError(f'{date}: incomplete historical raw pair')
        new=source_metadata(cfg,p,t,i)
        for key in ['telecom','interest']:
            if new[key]['sha256']!=old[key]['sha256']:raise ValueError(f'{date}: historical {key} changed; overwrite blocked')
        if new['weather_sha256']!=old['weather_sha256']:raise ValueError(f'{date}: historical weather changed; overwrite blocked')

def refresh(cfg):
    db=cfg['database'];output=Path(cfg['exports'])
    with store.connect(db) as con: count=con.execute('SELECT COUNT(*) FROM a2_detection').fetchone()[0]
    if count:
        results,common,calibration,model=detect_age.pipeline(detect_age.load_features(db))
        results=results.loc[results.date.ge(pd.Timestamp(model['settings']['detection_start']))].copy()
        common=common.loc[common.date.ge(pd.Timestamp(model['settings']['detection_start']))].copy()
        with store.connect(db) as con:
            old=[r[0] for r in con.execute('SELECT model_version FROM a2_age_model')]
            if old and model['model_version'] not in old:raise ValueError('Age baseline/model changed; explicit migration required')
            results=detect_age.add_context(con,results,model['model_version'])
            detect_age.commit(con,results,common,model)
        source_semantics.run(db)
        activity_level.run(db,output/'activity')
        output.mkdir(parents=True,exist_ok=True)
        calibration.to_csv(output/'age_calibration.csv',index=False,encoding='utf-8-sig')
        (output/'age_model.json').write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8')
        detect_age.export(db,output/'age_detection')
    export_all(cfg)

def export_all(cfg):
    db=cfg['database'];output=Path(cfg['exports'])
    store.export_csv(db,output,output/'analysis2')
    with store.connect(db) as con:
        for view,filename in [('v_v15_monthly_context','analysis123_monthly.csv'),('v_v15_age_context','analysis123_age.csv')]:
            frame=pd.read_sql_query(f'SELECT * FROM {view}',con)
            temporary=output/(filename+'.tmp')
            frame.to_csv(temporary,index=False,encoding='utf-8-sig')
            temporary.replace(output/filename)

def _staged_frames(con, date):
    """The ledger's preprocessing rows, rather than an in-memory raw parse, are
    the only inputs allowed into detection after they have been committed."""
    current=pd.DataFrame([json.loads(row[0]) for row in con.execute(
        'SELECT feature_json FROM a2_month_input WHERE date=? ORDER BY adm_cd',(date,))])
    monthly=pd.DataFrame([json.loads(row[0]) for row in con.execute(
        'SELECT feature_json FROM a2_age_month_input WHERE date=? ORDER BY adm_cd,age_scheme,age_band',(date,))])
    if len(current)!=22 or monthly.empty:
        raise ValueError(f'{date}: 저장된 전처리 입력이 완전하지 않습니다.')
    current['date']=pd.to_datetime(current['date'])
    monthly['date']=pd.to_datetime(monthly['date'])
    return current,monthly

def _remove_unpublished_output(con, date):
    """A crash after analysis leaves candidate rows in the work DB.  Remove only
    that unpublished month, then replay it from its immutable staged input."""
    for table in ('a2_feature','a2_detection','a2_evidence','a2_age_feature','a2_age_raw',
                  'a2_age_source','ctx_weather'):
        con.execute(f'DELETE FROM {table} WHERE date=?',(date,))
    con.execute("DELETE FROM db1_run WHERE analysis='analysis2' AND period=?",(date,))

def process(cfg,period,t,i):
    db=cfg['database'];a2=cfg['analysis2']
    telecom=pd.read_excel(t);interest=pd.read_excel(i)
    rain=pd.read_csv(a2['rain'],encoding='utf-8-sig');diary=pd.read_csv(a2['diary'],encoding='utf-8-sig')
    parsed_current=build_month_feature_frames(telecom,interest,rain,diary,period.year,period.month)
    validate_feature_rows(parsed_current)
    parsed_monthly,raw_t,raw_i=ages.build_age_frames(telecom,interest,rain,diary,period.year,period.month)
    ages.reconcile(parsed_monthly,parsed_current)
    date=str(period.date());metadata=source_metadata(cfg,period,t,i)
    input_hash=hashlib.sha256((metadata['telecom']['sha256']+metadata['interest']['sha256']).encode()).hexdigest()
    with store.connect(db) as con:
        existing=con.execute('SELECT input_hash,stage FROM month_run WHERE period=?',(date,)).fetchone()
        if existing and existing[0] != input_hash:
            raise ValueError(f'{date}: 중단된 월의 원천 입력 hash가 변경되었습니다. 명시적 revision이 필요합니다.')
        if not existing:
            con.execute("INSERT INTO month_run(period,input_hash,method_version,stage,output_json,error) VALUES(?,?,?,?,?,NULL)",
                        (date,input_hash,store.BASELINE_VERSION,'raw_validated',store.payload({'core_rows':len(parsed_current),'age_rows':len(parsed_monthly)})))
            for row in store.records(parsed_current): con.execute('INSERT INTO a2_month_input VALUES(?,?,?)',(date,str(row['행정동코드']),store.payload(row)))
            for row in store.records(parsed_monthly): con.execute('INSERT INTO a2_age_month_input VALUES(?,?,?,?,?)',(date,str(row['행정동코드']),row['age_scheme'],str(row['age_band']),store.payload(row)))
        current,monthly=_staged_frames(con,date)
        _remove_unpublished_output(con,date)
        con.execute("UPDATE month_run SET stage='preprocessed',error=NULL,updated_at=CURRENT_TIMESTAMP WHERE period=?",(date,))
        history=store.history(con);context_period,context=store.context_for(con,period)
    validate_history(history)
    full=run_month(history,current,context,return_history=True)
    result=full.loc[full.date.eq(period)].copy()
    evidence=build_evidence_card(full.loc[full.date.ge(pd.Timestamp('2025-07-01'))])
    evidence=evidence.loc[pd.to_datetime(evidence.date).eq(period)].copy()
    if len(result)!=22 or result[['cluster','cluster_type']].isna().any().any():raise ValueError('Incomplete core detection')
    with store.connect(db) as con:
        con.execute('BEGIN IMMEDIATE')
        last=con.execute('SELECT MAX(date) FROM a2_feature').fetchone()[0]
        if period!=(pd.Timestamp(last).to_period('M')+1).to_timestamp():raise ValueError('Concurrent/out-of-order update')
        for row in store.records(current):
            con.execute('INSERT INTO a2_feature VALUES(?,?,?,?,?)',(str(row['행정동코드']),date,row['행정동'],0,store.payload(row)))
        for row in store.records(result):
            con.execute('INSERT INTO a2_detection VALUES(?,?,?,?,?,?,?,?,?,?)',
                (str(row['행정동코드']),date,context_period,store.BASELINE_VERSION,int(row['any_signal']),
                 int(row['communication_signal']),int(row['mobility_signal']),int(row['combined_signal']),row['signal_status'],store.payload(row)))
        for row in store.records(evidence):
            con.execute('INSERT INTO a2_evidence VALUES(?,?,?)',(str(row['행정동코드']),date,store.payload(row)))
        for row in store.records(monthly):
            con.execute('INSERT INTO a2_age_feature VALUES(?,?,?,?,?,?,?,?)',
                (str(row['행정동코드']),date,row['age_scheme'],row['age_band'],ages.VERSION,row['phase'],row['quality_status'],store.payload(row)))
        for kind,raw in [('telecom',raw_t),('interest',raw_i)]:
            for row in store.records(raw):
                con.execute('INSERT INTO a2_age_raw VALUES(?,?,?,?,?,?)',
                    (date,kind,str(row['행정동코드']),int(row['성별']),int(row['연령대']),store.payload(row)))
        con.execute('INSERT INTO a2_age_source VALUES(?,?,?)',(date,store.fingerprint(monthly,['행정동코드','age_scheme','age_band']),store.payload(metadata)))
        con.execute('INSERT INTO ctx_weather VALUES(?,?)',(date,store.payload(weather_context(cfg,period))))
        con.execute('INSERT INTO db1_run(analysis,period,fingerprint,model_version,metadata_json) VALUES(?,?,?,?,?)',
            ('analysis2',date,store.fingerprint(current,['date','행정동코드']),store.BASELINE_VERSION,store.payload(metadata)))
        con.execute('INSERT OR REPLACE INTO pipeline_state VALUES(1,?)',(store.payload({'status':'refresh_required','month':date}),))
        con.execute("UPDATE month_run SET stage='analyzed',output_json=?,updated_at=CURRENT_TIMESTAMP WHERE period=?",(store.payload({'core_rows':len(result),'age_rows':len(monthly)}),date))
    refresh(cfg)
    with store.connect(db) as con: con.execute("UPDATE month_run SET stage='complete',updated_at=CURRENT_TIMESTAMP WHERE period=?",(date,))
    print(json.dumps({'month':period.strftime('%Y-%m'),'core_rows':len(current),'age_feature_rows':len(monthly),
        'signals':int(result.any_signal.sum()),'structural_issue_rows':int(current.interest_structural_issue.sum())}),flush=True)

def run(cfg,initialize_only=False,through=None):
    initialize(cfg);db=cfg['database'];processed=[]
    with store.connect(db) as con:old=con.execute('SELECT payload_json FROM pipeline_state WHERE id=1').fetchone()
    repair=bool(old and json.loads(old[0]).get('status') in {'refresh_required','failed','processing'})
    state(db,status='processing')
    try:
        verify_saved_sources(cfg)
        with store.connect(db) as con:
            core=con.execute('SELECT COUNT(*) FROM a2_detection').fetchone()[0]
            age=con.execute('SELECT COUNT(*) FROM a2_age_detection').fetchone()[0]
            contextual=con.execute('SELECT COUNT(*) FROM a23_observation_context').fetchone()[0]
            activity=con.execute('SELECT COUNT(*) FROM a2_activity_level').fetchone()[0]
        if core and (core*5!=age or core*5!=contextual or core*5!=activity or repair):refresh(cfg)
        waiting=None
        while not initialize_only:
            with store.connect(db) as con:
                pending=con.execute("SELECT period,stage FROM month_run WHERE stage!='published' ORDER BY period LIMIT 1").fetchone()
                last=con.execute('SELECT MAX(date) FROM a2_feature').fetchone()[0]
            # Always resume the earliest unpublished ledger item.  MAX(feature)
            # can include a candidate that crashed after analysis, so it is not a
            # valid recovery cursor by itself.
            period=pd.Timestamp(pending[0]) if pending else (pd.Timestamp(last).to_period('M')+1).to_timestamp()
            if through and period>pd.Timestamp(through):break
            t=find_file(cfg['analysis2']['telecom_dir'],period,'29개');i=find_file(cfg['analysis2']['interest_dir'],period,'10개')
            if t is None or i is None:
                waiting={'month':period.strftime('%Y-%m'),'missing':[k for k,v in [('telecom',t),('interest',i)] if v is None]};break
            if pending and pending[1]=='complete':
                processed.append(period.strftime('%Y-%m'))
            else:
                process(cfg,period,t,i);processed.append(period.strftime('%Y-%m'))
            # A completed month becomes a separately readable release before the
            # coordinator starts mutating the next candidate month.
            state(db,status='ready',processed_this_run=processed,waiting_for=None,mode='local_raw_replay',network_download=False)
            from snapshot_manager import publish
            publish(db, period.strftime('%Y-%m-01'))
            with store.connect(db) as con:
                con.execute("UPDATE month_run SET stage='published',updated_at=CURRENT_TIMESTAMP WHERE period=?",(str(period.date()),))
        if not core and not processed:refresh(cfg)
        elif not processed:export_all(cfg)
        state(db,status='ready',processed_this_run=processed,waiting_for=waiting,mode='local_raw_replay',network_download=False)
        # This module is also executed as a script by runner.py.  Initialization
        # and no-op recovery still need an initial/readable snapshot.
        if not processed:
            from snapshot_manager import active_snapshot, publish
            # A no-op start must not replace the pointer that a dashboard has
            # already pinned.  Only the first cold start needs an initial one.
            if active_snapshot(db) is None:
                publish(db, None)
    except Exception as exc:
        state(db,status='failed',processed_this_run=processed,error=str(exc));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--initialize-only',action='store_true');p.add_argument('--through');a=p.parse_args()
    if a.through and not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',a.through):p.error('--through must be YYYY-MM')
    run(json.loads(Path(a.config).read_text(encoding='utf-8')),a.initialize_only,a.through)

"""Aligned weather, youth survey details and explicit publication metadata; no detector changes."""
from pathlib import Path
from contextlib import closing
from datetime import date
import argparse,sqlite3,json,csv,hashlib,math,re,calendar
import youth_detail
from source_semantics import window,canonical
SCHEMA='''
CREATE TABLE IF NOT EXISTS ctx_weather_month(period TEXT PRIMARY KEY,payload_json TEXT);
CREATE TABLE IF NOT EXISTS ctx_weather_file(sha256 TEXT PRIMARY KEY,path TEXT,registered_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS ctx_weather_month_source(period TEXT,sha256 TEXT,PRIMARY KEY(period,sha256));
CREATE TABLE IF NOT EXISTS ctx_weather_window(date TEXT PRIMARY KEY,payload_json TEXT);
CREATE TABLE IF NOT EXISTS ctx_weather_revision(id INTEGER PRIMARY KEY,date TEXT,previous_json TEXT,current_json TEXT,added_months_json TEXT,registered_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS ctx_publication_registry(kind TEXT,period TEXT,available_from TEXT NOT NULL,proof TEXT NOT NULL,registered_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(kind,period));
DROP VIEW IF EXISTS v_a123_age_evidence_context;
CREATE VIEW v_a123_age_evidence_context AS SELECT b.*,w.payload_json AS observation_weather_json,
 (SELECT json_group_array(json_object('kind',s.kind,'year',s.year,'source_id',m.source_id,'district',m.district,'age_band',m.age_band,'metric',m.metric,'value',m.value,'unit',m.unit,'n_total',m.n_total,'n_valid',m.n_valid,'n_event',m.n_event,'effective_n',m.effective_n,'quality_status',m.quality_status,'metadata',json(m.payload_json))) FROM ctx_youth_metric m JOIN ctx_youth_source s USING(source_id) WHERE m.district='gangnam' AND (m.age_band=b.age_band OR (b.age_band='20s' AND s.kind='household' AND m.age_band='19to29'))) AS youth_detail_json
 FROM v_a123_age_source_context b LEFT JOIN ctx_weather_window w ON w.date=b.source_label_date;
'''
def key(s):
    match=re.fullmatch(r'\s*(\d{4})\.\s*(\d{1,2})\s*',str(s))
    if not match:return None
    year,month=map(int,match.groups())
    if not 1<=month<=12:raise ValueError('Invalid weather month')
    return f'{year:04d}-{month:02d}'
def num(v,snow=False):
    if snow and str(v).strip()=='-':return 0.
    try:n=float(v)
    except (ValueError,TypeError):return None
    if not math.isfinite(n) or n<0:raise ValueError('Invalid weather value')
    return n
def read_weather(options):
    paths=[Path(options['rain']),Path(options['diary'])]
    with paths[0].open(encoding='utf-8-sig',newline='') as f:rain=list(csv.DictReader(f))
    with paths[1].open(encoding='utf-8-sig',newline='') as f:diary=list(csv.DictReader(f))
    amounts=[r for r in rain if r.get('항목')=='강수량 (㎜)'];days=[r for r in rain if r.get('항목')=='강수일수 (일)']
    if len(amounts)!=1 or len(days)!=1:raise ValueError('Weather required item missing/duplicate')
    snow={}
    for row in diary:
        period=key(row.get('시점'))
        if period:
            if period in snow:raise ValueError('Duplicate weather diary month')
            snow[period]=num(row.get('눈'),snow=True)
    months={}
    for col in amounts[0]:
        period=key(col)
        if not period:continue
        months[period]={'period':period,'rainfall_mm':num(amounts[0][col]),'rain_days':num(days[0].get(col)),'snow_days':snow.get(period)}
    return months,[(hashlib.sha256(p.read_bytes()).hexdigest(),str(p.resolve())) for p in paths]
def weather(c,options):
    incoming,files=read_weather(options);added=[]
    for period,p in incoming.items():
        old=c.execute('SELECT payload_json FROM ctx_weather_month WHERE period=?',(period,)).fetchone()
        if old and json.loads(old[0])!=p:raise ValueError('Historical weather correction requires explicit revision '+period)
        if not old:c.execute('INSERT INTO ctx_weather_month VALUES(?,?)',(period,canonical(p)));added.append(period)
    for sha,path in files:
        c.execute('INSERT OR IGNORE INTO ctx_weather_file(sha256,path) VALUES(?,?)',(sha,path))
        c.executemany('INSERT OR IGNORE INTO ctx_weather_month_source VALUES(?,?)',[(period,sha) for period in incoming])
    stored={p:json.loads(j) for p,j in c.execute('SELECT period,payload_json FROM ctx_weather_month')};n=0
    for (label,) in c.execute('SELECT DISTINCT date FROM a2_age_feature').fetchall():
        w=window(label);rows=[stored.get(p,{'period':p,'rainfall_mm':None,'rain_days':None,'snow_days':None}) for p in w['observation_months']]
        ready=[r['period'] for r in rows if all(r[k] is not None for k in ['rainfall_mm','rain_days','snow_days'])]
        totals={k:sum(r[k] for r in rows) if all(r[k] is not None for r in rows) else None for k in ['rainfall_mm','rain_days','snow_days']}
        p={'label_month':label[:7],'observation_start':w['observation_start'],'observation_end':w['observation_end'],'observation_months':w['observation_months'],'monthly_values':rows,'totals':totals,'quality_status':'available' if len(ready)==3 else 'partial' if ready else 'unavailable','available_months':ready,'calendar_days':w['calendar_days'],'calendar_mon_fri_days':w['calendar_mon_fri_days'],'calendar_sat_sun_days':w['calendar_sat_sun_days'],'provider_holiday_includes_public_holidays':None,'scope':'source_weather_context_not_dong_specific; station_scope_not_verified','aggregation':'sum_of_monthly_observations_over_actual_three_month_window','not_detection_input':True,'method_version':'weather_window_v1'}
        old=c.execute('SELECT payload_json FROM ctx_weather_window WHERE date=?',(label,)).fetchone();text=canonical(p)
        if old and old[0]!=text:
            a=json.loads(old[0]);before={r['period']:r for r in a['monthly_values']};after={r['period']:r for r in rows}
            changed=[month for month in before if before[month]!=after[month]]
            if not changed or any(month not in added for month in changed):raise ValueError('Weather window revision blocked '+label)
            c.execute('INSERT INTO ctx_weather_revision(date,previous_json,current_json,added_months_json) VALUES(?,?,?,?)',(label,old[0],text,canonical(added)))
            c.execute('UPDATE ctx_weather_window SET payload_json=? WHERE date=?',(text,label));n+=1
        elif not old:c.execute('INSERT INTO ctx_weather_window VALUES(?,?)',(label,text));n+=1
    return n
def publications(c,config):
    records=[]
    for sid,year,available in c.execute('SELECT source_id,year,available_from FROM ctx_survey_source WHERE available_from IS NOT NULL'):
        records.append({'kind':'survey','period':sid,'available_from':available,'proof':'existing_ctx_survey_source_registered_release_metadata'})
    manifest=config.get('evidence_publication',{})
    if isinstance(manifest,str):manifest=json.loads(Path(manifest).read_text(encoding='utf-8'))
    records+=manifest.get('records',[]);inserted=0
    for r in records:
        if r.get('available_from') is None:continue
        kind,period,available,proof=[r.get(k) for k in ['kind','period','available_from','proof']]
        if kind not in ['telecom','interest','market','card','survey','weather'] or not period or not proof:raise ValueError('Publication record needs kind/period/date/proof')
        if date.fromisoformat(available).isoformat()!=available:raise ValueError('Invalid publication date')
        if kind in ['telecom','interest','card','weather'] and not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',period):raise ValueError('Invalid publication period')
        if kind=='market' and not re.fullmatch(r'\d{4}Q[1-4]',period):raise ValueError('Invalid quarter')
        if kind in ['card','weather']:
            y,m=map(int,period.split('-'));end=date(y,m,calendar.monthrange(y,m)[1]).isoformat()
        elif kind in ['telecom','interest']:end=window(period+'-01')['observation_end']
        elif kind=='market':
            y,q=int(period[:4]),int(period[-1]);m=q*3;end=date(y,m,calendar.monthrange(y,m)[1]).isoformat()
        else:
            row=c.execute('SELECT year FROM ctx_survey_source WHERE source_id=?',(period,)).fetchone()
            if not row:raise ValueError('Unknown survey publication source')
            end=f'{row[0]}-01-01'
        if available<end:raise ValueError('Publication precedes observation end')
        old=c.execute('SELECT available_from,proof FROM ctx_publication_registry WHERE kind=? AND period=?',(kind,period)).fetchone()
        if old and old[0]!=available:raise ValueError('Known publication date correction blocked '+str((kind,period)))
        if not old:c.execute('INSERT INTO ctx_publication_registry(kind,period,available_from,proof) VALUES(?,?,?,?)',(kind,period,available,proof));inserted+=1
    return inserted
def run(db,config,output=None):
    if not isinstance(config,dict):config=json.loads(Path(config).read_text(encoding='utf-8'))
    with closing(sqlite3.connect(db)) as c:
        c.execute('PRAGMA foreign_keys=ON');c.executescript(youth_detail.SCHEMA+SCHEMA)
        with c:
            y=youth_detail.run(c,config);w=weather(c,config['analysis2']);p=publications(c,config)
        summary={'new_youth_metric_rows':y,'new_or_enriched_weather_windows':w,'new_publication_records':p,'existing_detection_modified':False}
    if output:export(db,output)
    return summary
def export(db,output):
    path=Path(output);path.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(db)) as c:
        for table in ['v_youth_detail','ctx_weather_window','ctx_publication_registry','a23_context_revision','ctx_weather_revision']:
            cur=c.execute('SELECT * FROM '+table)
            with (path/(table+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.writer(f);w.writerow([r[0] for r in cur.description]);w.writerows(cur)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--config',required=True);p.add_argument('--output');a=p.parse_args();print(json.dumps(run(a.db,a.config,a.output),ensure_ascii=False))

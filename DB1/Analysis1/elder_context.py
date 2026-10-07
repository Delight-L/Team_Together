"""Annual dong-level living-alone elderly context, separate from fitted PCA."""
from pathlib import Path
import argparse,calendar,csv,glob,hashlib,io,json,re,sqlite3
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
VERSION='a1_elder_context_v1'
SOURCE_URL='https://data.seoul.go.kr/bsp/wgs/dataView/data300View/91.do'
CATEGORIES=('합계','국민기초생활보장수급권자','저소득노인','일반')
SEXES=('계','남','여')
TABLES=('a1_elder_source','a1_elder_year','a1_elder_observation','a1_elder_annual')
SCHEMA='''
CREATE TABLE IF NOT EXISTS a1_elder_source(sha256 TEXT PRIMARY KEY,source_path TEXT NOT NULL,metadata_json TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS a1_elder_year(year INTEGER PRIMARY KEY,fingerprint TEXT NOT NULL,available_from TEXT,metadata_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS a1_elder_observation(adm_cd TEXT NOT NULL,year INTEGER NOT NULL,category TEXT NOT NULL,sex TEXT NOT NULL,value INTEGER,raw_value TEXT NOT NULL,PRIMARY KEY(adm_cd,year,category,sex),FOREIGN KEY(year) REFERENCES a1_elder_year(year));
CREATE TABLE IF NOT EXISTS a1_elder_annual(adm_cd TEXT NOT NULL,year INTEGER NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(adm_cd,year),FOREIGN KEY(year) REFERENCES a1_elder_year(year));
CREATE VIEW IF NOT EXISTS v_a1_elder_annual AS
 SELECT a.adm_cd,a.year,y.available_from,a.payload_json FROM a1_elder_annual a JOIN a1_elder_year y ON a.year=y.year;
CREATE VIEW IF NOT EXISTS v_a1_elder_context AS
 SELECT c.adm_cd,c.adm_nm,c.period,c.cluster_type AS a1_cluster_type,a.year AS elder_year,
 a.payload_json AS elder_context_json,y.available_from AS elder_available_from,
 'retrospective_latest_completed_reference_year' AS elder_alignment
 FROM a1_context c LEFT JOIN a1_elder_annual a ON a.adm_cd=c.adm_cd AND a.year=(
 SELECT MAX(e.year) FROM a1_elder_annual e WHERE e.adm_cd=c.adm_cd
 AND e.year<=CAST(substr(c.period,1,4) AS INTEGER)-CASE WHEN substr(c.period,6,1)='1' THEN 1 ELSE 0 END)
 LEFT JOIN a1_elder_year y ON y.year=a.year;
'''
LINK_SCHEMA='''
CREATE VIEW IF NOT EXISTS v_a123_age_elder_context AS
 SELECT m.*,e.year AS elder_year,e.payload_json AS elder_context_json,y.available_from AS elder_available_from,
 CASE WHEN m.age_band='60plus' THEN 'partial_overlap_65plus_vs_60plus' ELSE 'not_applicable_to_age_band' END AS elder_age_alignment,
 'retrospective_reference_year_not_monthly_observation' AS elder_time_alignment
 FROM a23_age_monthly m LEFT JOIN a1_elder_annual e ON m.age_band='60plus' AND e.adm_cd=m.adm_cd AND e.year=(
 SELECT MAX(a.year) FROM a1_elder_annual a WHERE a.adm_cd=m.adm_cd AND a.year<=CAST(substr(m.date,1,4) AS INTEGER))
 LEFT JOIN a1_elder_year y ON y.year=e.year;
CREATE VIEW IF NOT EXISTS v_a123_age_elder_available_context AS
 SELECT m.*,e.year AS elder_year,e.payload_json AS elder_context_json,y.available_from AS elder_available_from,
 CASE WHEN m.age_band='60plus' THEN 'partial_overlap_65plus_vs_60plus' ELSE 'not_applicable_to_age_band' END AS elder_age_alignment,
 'known_publication_and_completed_reference_year_by_event_month_end' AS elder_time_alignment
 FROM a23_age_available_context m LEFT JOIN a1_elder_annual e ON m.age_band='60plus' AND e.adm_cd=m.adm_cd AND e.year=(
 SELECT MAX(a.year) FROM a1_elder_annual a JOIN a1_elder_year p ON p.year=a.year
 WHERE a.adm_cd=m.adm_cd AND printf('%04d-12-31',a.year)<=date(substr(m.date,1,7)||'-01','+1 month','-1 day')
 AND p.available_from IS NOT NULL AND p.available_from<=date(substr(m.date,1,7)||'-01','+1 month','-1 day'))
 LEFT JOIN a1_elder_year y ON y.year=e.year;
'''

def dumps(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)
def norm(value):return re.sub(r'\s+','',value)
def ratio(n,d):return None if n is None or d is None or d==0 else n/d
def number(value):
    if value in ('','-','…','..','N/A'):return None
    if not re.fullmatch(r'\d+',value.replace(',','')):raise ValueError(f'Invalid nonnegative integer: {value!r}')
    return int(value.replace(',',''))

def read_source(path,mapping,allow_terminal_error=False):
    data=Path(path).read_bytes();sha=hashlib.sha256(data).hexdigest()
    try:text=data.decode('utf-8-sig')
    except UnicodeDecodeError:text=data.decode('cp949')
    rows=[];reader=csv.reader(io.StringIO(text),strict=True);quarantine=[];last_good_line=0
    try:
        for row in reader:rows.append(row);last_good_line=reader.line_num
    except csv.Error as exc:
        districts=[r[0].strip() for r in rows[1:] if r and r[0].strip().endswith('구')]
        # Only a single incomplete terminal record outside the closed Gangnam section.
        lines=text.splitlines();tail=lines[-1]
        if not (allow_terminal_error and str(exc)=='unexpected end of data' and reader.line_num==len(lines) and reader.line_num==last_good_line+1
                and districts and districts[-1]!='강남구' and '강남구' in districts
                and len(tail.split(','))==len(rows[0])-1 and tail.count('"')%2==1
                and all(r[0].strip() not in mapping for r in rows[-1:])):
            raise ValueError(f'{path}: malformed CSV at line {reader.line_num}; cannot safely use Gangnam') from exc
        quarantine=[{'line':reader.line_num,'district':districts[-1],'raw':tail,'reason':'incomplete_terminal_record_outside_gangnam'}]
    if not rows:raise ValueError('Empty source')
    header=rows[0]
    required=['동별','독거노인별','성별','항목','단위']
    if header[:5]!=required:raise ValueError('Unexpected elderly source schema')
    years={i:int(re.fullmatch(r'(20\d{2})\s*년',h).group(1)) for i,h in enumerate(header) if re.fullmatch(r'(20\d{2})\s*년',h)}
    if not years or len(set(years.values()))!=len(years):raise ValueError('Missing/duplicate annual columns')
    if any(h and i>=5 and i not in years for i,h in enumerate(header)):raise ValueError('Unknown period columns')
    selected=[];district=[];active=False;closed=False
    for row in rows[1:]:
        if len(row)!=len(header):raise ValueError('Source record length mismatch')
        name=row[0].strip()
        if name.endswith('区'):raise ValueError('Unexpected geography')
        if name.endswith('구'):
            if active and name!='강남구':closed=True
            active=name=='강남구'
        if not active:continue
        if name!='강남구' and name not in mapping:raise ValueError(f'Unmapped Gangnam dong: {name}')
        cat=norm(row[1]);sex=row[2].strip()
        if cat not in CATEGORIES or sex not in SEXES or row[3].strip()!='독거노인현황(성별)' or row[4].strip() not in ('','명'):raise ValueError('Unknown elderly categories/sex/unit')
        for index,year in years.items():
            rec={'adm_cd':mapping.get(name),'year':year,'category':cat,'sex':sex,'value':number(row[index].strip()),'raw_value':row[index].strip()}
            (district if name=='강남구' else selected).append(rec)
    if not selected:raise ValueError('No Gangnam observations')
    keys=[(r['adm_cd'],r['year'],r['category'],r['sex']) for r in selected]
    if len(set(keys))!=len(keys):raise ValueError('Duplicate source cell')
    expected={(cd,year,cat,sex) for cd in set(mapping.values()) for year in years.values() for cat in CATEGORIES for sex in SEXES}
    if set(keys)!=expected:raise ValueError('Incomplete 22 dong × categories × sexes source grid')
    dkeys=[(r['year'],r['category'],r['sex']) for r in district]
    if len(set(dkeys))!=len(dkeys) or len(dkeys)!=len(years)*12:raise ValueError('Missing/duplicate district controls')
    cells={k:r['value'] for k,r in zip(keys,selected)};checks=[]
    def reconcile(values,total,label):
        if total is None:checks.append({'check':label,'status':'missing_total'});return
        if sum(v for v in values if v is not None)>total:raise ValueError('Partial subtotal exceeds total: '+label)
        if all(v is not None for v in values):
            if sum(values)!=total:raise ValueError('Arithmetic mismatch: '+label)
            checks.append({'check':label,'status':'matched'})
        else:checks.append({'check':label,'status':'missing_components_not_zero'})
    for year in years.values():
        for cd in set(mapping.values()):
            for cat in CATEGORIES:reconcile([cells[cd,year,cat,s] for s in ('남','여')],cells[cd,year,cat,'계'],f'{cd}/{year}/{cat}/sex')
            for sex in SEXES:reconcile([cells[cd,year,cat,sex] for cat in CATEGORIES[1:]],cells[cd,year,'합계',sex],f'{cd}/{year}/{sex}/category')
        for d in [r for r in district if r['year']==year]:reconcile([cells[cd,year,d['category'],d['sex']] for cd in set(mapping.values())],d['value'],f'{year}/{d["category"]}/{d["sex"]}/district')
    metadata={'source_path':str(Path(path).resolve()),'sha256':sha,'source_url':SOURCE_URL,'version':VERSION,'source_age_minimum':65,'source_reference_precision':'year','quarantined_records':quarantine,'gangnam_section_closed':closed,'arithmetic_checks':checks,'district_controls':district}
    return selected,metadata

def mappings(con):
    rows=con.execute('SELECT DISTINCT adm_nm,adm_cd FROM a1_context').fetchall()
    result=dict(rows)
    if len(set(result.values()))!=22 or len(result)!=22:raise ValueError('Ambiguous DB1 region mapping')
    if '개포3동' in result:result['일원2동']=result['개포3동']
    return result

def make_annual(con):
    rows=con.execute('SELECT adm_cd,year,category,sex,value FROM a1_elder_observation').fetchall()
    cells={(cd,y,cat,s):value for cd,y,cat,s,value in rows}
    names={cd:n for n,cd in con.execute('SELECT DISTINCT adm_nm,adm_cd FROM a1_context')}
    for cd,year in sorted({(r[0],r[1]) for r in rows}):
        def get(cat,sex='계'):return cells.get((cd,year,cat,sex))
        total=get('합계');prior=cells.get((cd,year-1,'합계','계'));benefit=get(CATEGORIES[1]);low=get(CATEGORIES[2])
        economic=None if benefit is None or low is None else benefit+low
        female=get('합계','여');male=get('합계','남')
        payload={'adm_cd':cd,'adm_nm':names[cd],'year':year,'source_age_minimum':65,'reference_precision':'year','elderly_living_alone_total':total,'male':male,'female':female,'female_share':ratio(female,total),'beneficiary_total':benefit,'low_income_total':low,'general_total':get('일반'),'beneficiary_share_among_living_alone_elderly':ratio(benefit,total),'low_income_share_among_living_alone_elderly':ratio(low,total),'economic_vulnerability_total':economic,'economic_vulnerability_share_among_living_alone_elderly':ratio(economic,total),'previous_year':year-1 if (cd,year-1,'합계','계') in cells else None,'previous_total':prior,'yoy_count_change':None if total is None or prior is None else total-prior,'yoy_count_change_pct':None if total is None else (None if ratio(total,prior) is None else (total/prior-1)*100),'rate_among_all_65plus_residents':None,'all_65plus_denominator_status':'not_added_reference_population_and_date_unverified','missing_cells':sum(cells[cd,year,cat,sex] is None for cat in CATEGORIES for sex in SEXES),'interpretation':'annual_structural_living_arrangement_and_economic_context_not_isolation_cases','version':VERSION}
        con.execute('INSERT INTO a1_elder_annual VALUES(?,?,?) ON CONFLICT(adm_cd,year) DO UPDATE SET payload_json=excluded.payload_json',(cd,year,dumps(payload)))

def ingest(db,settings):
    options=settings.get('analysis1',{}).get('elderly_living_alone')
    if not options:return {'status':'elderly_source_not_configured'}
    paths=sorted({Path(p).resolve() for pattern in options['sources'] for p in glob.glob(pattern)})
    if not paths:raise FileNotFoundError('Configured elderly living-alone source not found')
    with sqlite3.connect(db,timeout=60) as con:
        mapping=mappings(con);packets=[read_source(p,mapping,options.get('allow_non_gangnam_terminal_error',False)) for p in paths]
        if options.get('source_archive'):
            archive=(ROOT/options['source_archive']).resolve();archive.mkdir(parents=True,exist_ok=True)
            for path,(_,metadata) in zip(paths,packets):
                data=path.read_bytes()
                if hashlib.sha256(data).hexdigest()!=metadata['sha256']:raise ValueError('Source changed during ingestion')
                saved=archive/(metadata['sha256']+'.csv')
                if saved.exists():
                    if saved.read_bytes()!=data:raise ValueError('Archived source checksum mismatch')
                else:saved.write_bytes(data)
                metadata['archived_source']=str(saved)
        pending={};assets=[]
        for cells,meta in packets:
            assets.append(meta)
            for year in sorted({r['year'] for r in cells}):
                selected=sorted([r for r in cells if r['year']==year],key=lambda r:(r['adm_cd'],r['category'],r['sex']))
                digest=hashlib.sha256(dumps([{k:v for k,v in r.items() if k!='raw_value'} for r in selected]).encode()).hexdigest()
                if year in pending and pending[year]['fingerprint']!=digest:raise ValueError(f'{year}: conflicting source files')
                packet=pending.setdefault(year,{'fingerprint':digest,'cells':selected,'source_sha256':[],'district_total':next(r['value'] for r in meta['district_controls'] if r['year']==year and r['category']=='합계' and r['sex']=='계')})
                packet['source_sha256'].append(meta['sha256'])
        con.execute('PRAGMA foreign_keys=ON');con.executescript(SCHEMA)
        inserted=[]
        with con:
            last=con.execute('SELECT MAX(year) FROM a1_elder_year').fetchone()[0]
            for year,p in sorted(pending.items()):
                published=options.get('available_from',{}).get(str(year))
                if published:
                    try:published=pd.Timestamp(published).strftime('%Y-%m-%d')
                    except Exception as exc:raise ValueError('Invalid annual publication date') from exc
                    if published<f'{year}-12-31':raise ValueError('Publication cannot precede completed reference year')
                stored=con.execute('SELECT fingerprint,available_from FROM a1_elder_year WHERE year=?',(year,)).fetchone()
                if stored:
                    if stored[0]!=p['fingerprint']:raise ValueError(f'{year}: historical elderly snapshot changed; explicit versioned correction required')
                    if published and stored[1] not in (None,published):raise ValueError('Publication correction requires explicit migration')
                    if published and stored[1] is None:con.execute('UPDATE a1_elder_year SET available_from=? WHERE year=?',(published,year))
                    continue
                if last is not None and year<last:raise ValueError('Historical backfill requires explicit migration')
                meta={k:v for k,v in p.items() if k!='cells'}
                meta.update(version=VERSION,reference_precision='year',source_age_minimum=65)
                con.execute('INSERT INTO a1_elder_year VALUES(?,?,?,?)',(year,p['fingerprint'],published,dumps(meta)))
                con.executemany('INSERT INTO a1_elder_observation VALUES(?,?,?,?,?,?)',[(r['adm_cd'],year,r['category'],r['sex'],r['value'],r['raw_value']) for r in p['cells']]);inserted.append(year)
            for meta in assets:con.execute('INSERT OR IGNORE INTO a1_elder_source(sha256,source_path,metadata_json) VALUES(?,?,?)',(meta['sha256'],meta['source_path'],dumps(meta)))
            make_annual(con)
        return {'inserted_years':inserted,'source_files':len(paths),'quarantined_outside_gangnam_records':sum(len(a['quarantined_records']) for a in assets)}

def export(db,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    names={'v_a1_elder_annual':'analysis1_elder_annual','a1_elder_observation':'analysis1_elder_observations','v_a1_elder_context':'analysis1_elder_context','v_a123_age_elder_context':'analysis123_age_elder_context','v_a123_age_elder_available_context':'analysis123_age_elder_available_context'}
    with sqlite3.connect(db) as con:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE name='a1_elder_annual'").fetchone():return {'status':'elderly_context_unavailable'}
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='a23_age_monthly'").fetchone():con.executescript(LINK_SCHEMA)
        for table,name in names.items():
            if not con.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():continue
            frame=pd.read_sql_query('SELECT * FROM '+table,con)
            for column,prefix in [('payload_json',''),('elder_context_json','elder_')]:
                if column not in frame:continue
                values=pd.DataFrame([{} if pd.isna(v) else json.loads(v) for v in frame[column]],index=frame.index)
                for key in values:
                    target=prefix+key
                    if target not in frame:frame[target]=values[key]
            for column in frame:
                frame[column]=frame[column].map(lambda x:dumps(x) if isinstance(x,(list,dict)) else x)
            tmp=directory/(name+'.csv.tmp');frame.to_csv(tmp,index=False,encoding='utf-8-sig');tmp.replace(directory/(name+'.csv'))
        report={'annual_rows':con.execute('SELECT COUNT(*) FROM a1_elder_annual').fetchone()[0],'observation_rows':con.execute('SELECT COUNT(*) FROM a1_elder_observation').fetchone()[0],'missing_observation_cells':con.execute('SELECT COUNT(*) FROM a1_elder_observation WHERE value IS NULL').fetchone()[0],'district_totals_by_year':dict(con.execute("SELECT year,SUM(value) FROM a1_elder_observation WHERE category='합계' AND sex='계' GROUP BY year")), 'source_age_minimum':65,'isolation_detection_flags_changed':False}
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='v_a123_age_elder_context'").fetchone():
            report['monthly_rows']=con.execute('SELECT COUNT(*) FROM v_a123_age_elder_context').fetchone()[0]
            report['monthly_60plus_context_rows']=con.execute('SELECT COUNT(*) FROM v_a123_age_elder_context WHERE elder_year IS NOT NULL').fetchone()[0]
            report['current_behavior_signal_rows_with_age_applicable_elder_context']=con.execute("SELECT COUNT(*) FROM v_a123_age_elder_context WHERE elder_year IS NOT NULL AND json_extract(payload_json,'$.behavior_signal')=1").fetchone()[0]
        (directory/'elder_context_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');return report

def run(db,settings,directory):
    result=ingest(db,settings)
    if result.get('status'):return result
    return {**result,**export(db,directory)}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--db',required=True);parser.add_argument('--config',default=str(ROOT/'config/db1_config.json'));parser.add_argument('--output',default=str(ROOT/'outputs/integrated'));args=parser.parse_args()
    print(dumps(run(args.db,json.loads(Path(args.config).read_text(encoding='utf-8')),args.output)))

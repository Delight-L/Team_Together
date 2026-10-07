from pathlib import Path
import csv,importlib.util,io,json,sqlite3
import pytest

spec=importlib.util.spec_from_file_location('elder_context',Path(__file__).parents[1]/'elder_context.py')
elder=importlib.util.module_from_spec(spec);spec.loader.exec_module(elder)

@pytest.fixture
def fixture(tmp_path):
    db=tmp_path/'db.sqlite';source=tmp_path/'source.csv'
    with sqlite3.connect(db) as c:
        c.executescript('''CREATE TABLE a1_context(adm_cd,adm_nm,period,cluster_type);
        CREATE TABLE a23_age_monthly(adm_cd,date,age_band,model_version,payload_json);
        CREATE TABLE a23_age_available_context(adm_cd,date,age_band,model_version,payload_json);''')
        c.executemany('INSERT INTO a1_context VALUES(?,?,?,?)',[(str(i),f'동{i}','2025H2','type') for i in range(22)])
        for age in ('30s','60plus'):
            for date in ('2025-07-01','2026-01-01'):
                row=('0',date,age,'m',json.dumps({'behavior_signal':True}))
                c.execute('INSERT INTO a23_age_monthly VALUES(?,?,?,?,?)',row);c.execute('INSERT INTO a23_age_available_context VALUES(?,?,?,?,?)',row)
    write_source(source)
    config={'analysis1':{'elderly_living_alone':{'sources':[str(source)],'available_from':{},'allow_non_gangnam_terminal_error':True}}}
    return db,source,config,tmp_path

def write_source(path,years=(2024,2025),delta=0,missing=False):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,quoting=csv.QUOTE_ALL)
        w.writerow(['동별','독거노인별','성별','항목','단위',*[f'{y} 년' for y in years],''])
        # Count controls: per-dong category totals 30+10+60=100, sex totals 40+60=100.
        values={'합계':{'계':100,'남':40,'여':60},'국민기초생활보장수급권자':{'계':30,'남':12,'여':18},'저소득노인':{'계':10,'남':4,'여':6},'일반':{'계':60,'남':24,'여':36}}
        for name in ('강남구',*[f'동{i}' for i in range(22)]):
            for cat in elder.CATEGORIES:
                for sex in elder.SEXES:
                    nums=[str((values[cat][sex]+delta)*(22 if name=='강남구' else 1)) for year in years]
                    if missing and name=='동0' and cat=='저소득노인' and sex=='남':nums[0]='-'
                    w.writerow([name,cat,sex,'독거노인현황(성별)','',*nums,''])
        w.writerow(['송파구','합계','계','독거노인현황(성별)','',*['1' for y in years],''])

def test_ingestion_annual_sex_category_no_double_count(fixture):
    db,path,settings,out=fixture;r=elder.run(db,settings,out/'out')
    assert r['annual_rows']==44 and r['observation_rows']==528
    assert r['district_totals_by_year']=={2024:2200,2025:2200}
    with sqlite3.connect(db) as c:v=json.loads(c.execute('SELECT payload_json FROM a1_elder_annual WHERE adm_cd=? AND year=?',('0',2025)).fetchone()[0])
    assert v['economic_vulnerability_share_among_living_alone_elderly']==.4
    assert v['yoy_count_change_pct']==0 and v['rate_among_all_65plus_residents'] is None

def test_null_and_zero_semantics(fixture):
    db,path,settings,out=fixture;write_source(path,missing=True)
    elder.run(db,settings,out/'out')
    with sqlite3.connect(db) as c:assert c.execute('SELECT value FROM a1_elder_observation WHERE adm_cd=? AND year=? AND category=? AND sex=?',('0',2024,'저소득노인','남')).fetchone()[0] is None
    assert elder.number('0')==0 and elder.ratio(0,100)==0 and elder.ratio(0,0) is None

def test_age_and_time_alignment(fixture):
    db,path,settings,out=fixture;elder.run(db,settings,out/'out')
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM v_a123_age_elder_context WHERE age_band='30s' AND elder_year IS NOT NULL").fetchone()[0]==0
        assert c.execute("SELECT elder_year FROM v_a123_age_elder_context WHERE date='2026-01-01' AND age_band='60plus'").fetchone()[0]==2025
        assert c.execute('SELECT COUNT(*) FROM v_a123_age_elder_available_context WHERE elder_year IS NOT NULL').fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM a23_age_monthly').fetchone()[0]==4

def test_publication_latest_prior_and_no_future_year(fixture):
    db,path,settings,out=fixture;settings['analysis1']['elderly_living_alone']['available_from']={'2024':'2025-06-01','2025':'2026-06-01'}
    elder.run(db,settings,out/'out')
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT elder_year FROM v_a123_age_elder_available_context WHERE date='2025-07-01' AND age_band='60plus'").fetchone()[0]==2024
        assert c.execute("SELECT elder_year FROM v_a123_age_elder_available_context WHERE date='2026-01-01' AND age_band='60plus'").fetchone()[0]==2024

def test_rerun_append_and_preserve_existing(fixture):
    db,path,settings,out=fixture;elder.run(db,settings,out/'out')
    with sqlite3.connect(db) as c:before=c.execute('SELECT * FROM a1_elder_observation').fetchall();behavior=c.execute('SELECT * FROM a23_age_monthly').fetchall()
    assert elder.run(db,settings,out/'out')['inserted_years']==[]
    write_source(path,years=(2024,2025,2026));r=elder.run(db,settings,out/'out');assert r['inserted_years']==[2026]
    with sqlite3.connect(db) as c:
        assert before==c.execute('SELECT * FROM a1_elder_observation WHERE year<2026').fetchall()
        assert behavior==c.execute('SELECT * FROM a23_age_monthly').fetchall()

def test_changed_snapshot_blocked_atomic(fixture):
    db,path,settings,out=fixture;elder.run(db,settings,out/'out')
    text=path.read_text(encoding='utf-8-sig').replace('"동0","합계","계","독거노인현황(성별)","","100","100"','"동0","합계","계","독거노인현황(성별)","","101","100"')
    path.write_text(text,encoding='utf-8-sig')
    with pytest.raises(ValueError,match='Arithmetic mismatch'):elder.run(db,settings,out/'out')
    with sqlite3.connect(db) as c:assert c.execute('SELECT COUNT(*) FROM a1_elder_annual').fetchone()[0]==44

def test_terminal_error_quarantine_only_outside_gangnam(fixture):
    db,path,settings,out=fixture
    with path.open('a',encoding='utf-8') as f:f.write('"다른동","일반","여","독거노인현황(성별)","","1","1')
    r=elder.run(db,settings,out/'out');assert r['quarantined_outside_gangnam_records']==1
    mapping={f'동{i}':str(i) for i in range(22)}
    with pytest.raises(ValueError,match='malformed CSV'):elder.read_source(path,mapping,False)

def test_bad_gangnam_terminal_error_rejected(fixture):
    db,path,settings,out=fixture;s=path.read_text(encoding='utf-8-sig');s=s[:s.index('"송파구"')]
    path.write_text(s+'"동0","일반","여","독거노인현황(성별)","","1","1',encoding='utf-8-sig')
    with pytest.raises(ValueError,match='malformed CSV'):elder.run(db,settings,out/'out')

def test_duplicate_and_incomplete_grid_rejected(fixture):
    db,path,settings,out=fixture;lines=path.read_text(encoding='utf-8-sig').splitlines();lines.pop(15);path.write_text('\n'.join(lines),encoding='utf-8-sig')
    with pytest.raises(ValueError,match='Incomplete'):elder.run(db,settings,out/'out')

def test_h1_context_uses_previous_reference_year(fixture):
    db,path,settings,out=fixture
    with sqlite3.connect(db) as c:c.execute("INSERT INTO a1_context VALUES('0','동0','2025H1','type')")
    elder.run(db,settings,out/'out')
    with sqlite3.connect(db) as c:assert c.execute("SELECT elder_year FROM v_a1_elder_context WHERE period='2025H1'").fetchone()[0]==2024

def test_invalid_publication_before_year_completion(fixture):
    db,path,settings,out=fixture;settings['analysis1']['elderly_living_alone']['available_from']={'2025':'2025-06-01'}
    with pytest.raises(ValueError,match='completed reference year'):elder.run(db,settings,out/'out')
    with sqlite3.connect(db) as c:assert c.execute('SELECT COUNT(*) FROM a1_elder_year').fetchone()[0]==0

def test_valid_but_revised_past_snapshot_rejected(fixture):
    db,path,settings,out=fixture;elder.run(db,settings,out/'out')
    parsed=list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig'))))
    for r in parsed[1:]:
        for i in range(5,len(r)-1):r[i]=str(int(r[i])*2)
    with path.open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerows(parsed)
    with pytest.raises(ValueError,match='historical elderly snapshot changed'):elder.run(db,settings,out/'out')
    with sqlite3.connect(db) as c:assert c.execute("SELECT SUM(value) FROM a1_elder_observation WHERE year=2025 AND category='합계' AND sex='계'").fetchone()[0]==2200

def test_archive_preserves_exact_source_bytes(fixture):
    db,path,settings,out=fixture;archive=out/'archive';settings['analysis1']['elderly_living_alone']['source_archive']=str(archive)
    original=path.read_bytes();elder.run(db,settings,out/'out')
    files=list(archive.glob('*.csv'));assert len(files)==1 and files[0].read_bytes()==original

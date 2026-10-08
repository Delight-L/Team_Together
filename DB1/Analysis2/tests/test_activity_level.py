import unittest,copy,tempfile,sqlite3,json
from pathlib import Path
from contextlib import closing
try:
    from activity_level import compute,run,episode_events
except ModuleNotFoundError:
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from activity_level import compute,run,episode_events
def fixture():
    rows=[]
    for y in range(2022,2026):
        for month in range(1,13):
            for code in range(11):
                r={'adm_cd':str(code),'date':f'{y}-{month:02d}-01','age_band':'30s','행정동':'fixture','total_population':1000}
                for m in ['call_contacts','text_contacts','weekday_move_count','weekend_move_count']:
                    r[m]=100 if month==9 else 80 if month==10 else 90 if month==11 else 100
                    r[m+'_valid_population']=1000
                rows.append(r)
    return rows,[{'adm_cd':'0','age_band':'30s','date':'2025-10-01','model_version':'d1','communication_signal':1,'mobility_signal':0}]
class Checks(unittest.TestCase):
    def test_repeated_seasonal_drop_is_normalized(self):
        f,e=fixture();_,t,_=compute(f,e)
        self.assertEqual(t[0]['raw_state'],'both_below_reference')
        self.assertEqual(t[0]['seasonal_state'],'recovered_to_reference')
    def test_common_drop_does_not_become_local(self):
        f,e=fixture()
        for r in f:
            if r['date']>='2025-10-01':
                for m in ['call_contacts','text_contacts']:r[m]*=.8
        _,t,_=compute(f,e)
        self.assertEqual(t[-1]['seasonal_state'],'both_below_reference')
        self.assertEqual(t[-1]['local_state'],'recovered_to_reference')
        self.assertEqual(t[-1]['consecutive_both_below_months'],3)
    def test_target_persistent_low_then_recovery(self):
        f,e=fixture()
        for r in f:
            if r['adm_cd']=='0' and '2025-10-01'<=r['date']<'2025-12-01':
                for m in ['call_contacts','text_contacts']:r[m]*=.8
        _,t,_=compute(f,e)
        self.assertEqual(t[1]['local_state'],'both_below_reference')
        self.assertEqual(t[-1]['seasonal_state'],'recovered_to_reference')
        self.assertEqual(t[-1]['consecutive_both_below_months'],0)
    def test_invalid_anchor_is_unavailable(self):
        f,e=fixture()
        next(r for r in f if r['adm_cd']=='0' and r['date']=='2025-09-01')['call_contacts_valid_population']=100
        _,t,_=compute(f,e);self.assertEqual(t[0]['seasonal_state'],'unavailable')
        self.assertIsNone(t[0]['raw_change_pct']['call_contacts'])
    def test_insufficient_years(self):
        f,e=fixture();f=[r for r in f if r['date']>='2023-01-01']
        _,t,_=compute(f,e);self.assertEqual(t[0]['seasonal_state'],'unavailable')
    def test_future_values_do_not_rewrite_past(self):
        f,e=fixture();_,old,_=compute(f,e)
        new=copy.deepcopy([r for r in f if r['date']=='2025-01-01'])
        for r in new:r['date']='2026-01-01';r['call_contacts']=1
        _,current,_=compute(f+new,e);self.assertEqual(old,current[:3])
    def test_missing_month_rejected(self):
        f,e=fixture();f=[r for r in f if r['date']!='2025-08-01']
        with self.assertRaisesRegex(ValueError,'Missing monthly'):compute(f,e)
    def test_partial_grid_rejected(self):
        f,e=fixture()
        with self.assertRaisesRegex(ValueError,'Incomplete monthly'):compute(f[:-1],e)
    def test_communication_recovery_with_mobility_still_low(self):
        f,e=fixture();e[0]['mobility_signal']=1
        for r in f:
            if r['adm_cd']=='0' and r['date']>='2025-10-01':
                for m in ['weekday_move_count','weekend_move_count']:r[m]*=.5
                if r['date']<'2025-12-01':
                    for m in ['call_contacts','text_contacts']:r[m]*=.5
        _,t,_=compute(f,e);latest=t[-1]
        self.assertEqual(latest['domain_states']['communication']['recovery_status'],'reference_level_reached')
        self.assertEqual(latest['domain_states']['mobility']['recovery_status'],'below_reference')
        self.assertEqual(latest['overall_recovery_status'],'partial_recovery')
        self.assertEqual(latest['raw_state'],latest['domain_states']['communication']['raw_state'])
        self.assertEqual(len(latest['tracked_metrics']),4)
    def test_one_movement_metric_stays_low(self):
        f,e=fixture()
        next(r for r in f if r['adm_cd']=='0' and r['date']=='2025-12-01')['weekend_move_count']=50
        _,t,_=compute(f,e)
        self.assertEqual(t[-1]['domain_states']['mobility']['raw_state'],'mixed_recovery')
        self.assertEqual(t[-1]['metric_states']['weekday_move_count']['raw'],'at_or_above_reference')
        self.assertEqual(t[-1]['metric_states']['weekend_move_count']['raw'],'below_reference')
    def test_invalid_movement_does_not_hide_valid_communication(self):
        f,e=fixture()
        next(r for r in f if r['adm_cd']=='0' and r['date']=='2025-12-01')['weekday_move_count_valid_population']=100
        _,t,_=compute(f,e)
        self.assertEqual(t[-1]['domain_states']['communication']['recovery_status'],'reference_level_reached')
        self.assertEqual(t[-1]['domain_states']['mobility']['recovery_status'],'unavailable')
        self.assertEqual(t[-1]['overall_recovery_status'],'unavailable_or_partial')
    def test_relative_recovery_not_absolute_recovery(self):
        f,e=fixture()
        for r in f:
            if r['date']>='2025-10-01':
                for m in ['call_contacts','text_contacts','weekday_move_count','weekend_move_count']:r[m]*=.5
        _,t,_=compute(f,e)
        self.assertEqual(t[-1]['domain_states']['mobility']['local_state'],'recovered_to_reference')
        self.assertEqual(t[-1]['overall_recovery_status'],'below_reference')
    def test_continuing_signals_keep_first_anchor(self):
        f,e=fixture();continuing=copy.deepcopy(e[0]);continuing['date']='2025-11-01'
        _,t,_=compute(f,e+[continuing])
        self.assertEqual(len(t),3)
        self.assertEqual({r['reference_date'] for r in t},{'2025-09-01'})
    def test_separate_episode_retains_old_episode(self):
        f,e=fixture();new=copy.deepcopy(e[0]);new['date']='2025-12-01'
        _,t,_=compute(f,e+[new])
        self.assertEqual(len(t),4)
        december=[r for r in t if r['date']=='2025-12-01']
        self.assertEqual({r['reference_date'] for r in december},{'2025-09-01','2025-11-01'})
    def test_explicit_v1_migration_preserves_legacy(self):
        f,e=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'db.sqlite'
            with closing(sqlite3.connect(db)) as c,c:
                c.executescript('CREATE TABLE a2_age_feature(adm_cd TEXT,date TEXT,age_scheme TEXT,age_band TEXT,feature_json TEXT);CREATE TABLE a2_age_detection(adm_cd TEXT,date TEXT,age_band TEXT,model_version TEXT,communication_signal INTEGER,mobility_signal INTEGER);CREATE TABLE a2_activity_model(version TEXT PRIMARY KEY,settings_json TEXT,baseline_fingerprint TEXT);')
                c.executemany('INSERT INTO a2_age_feature VALUES(?,?,?,?,?)',[(r['adm_cd'],r['date'],'service',r['age_band'],json.dumps(r)) for r in f])
                c.executemany('INSERT INTO a2_age_detection VALUES(?,?,?,?,?,?)',[(r['adm_cd'],r['date'],r['age_band'],r['model_version'],1,0) for r in e])
                c.execute('INSERT INTO a2_activity_model VALUES(?,?,?)',('legacy_v1',json.dumps({'method':'a2_activity_level_v1'}),'old_fingerprint'))
            with self.assertRaisesRegex(ValueError,'migrate-from-v1'):run(db)
            with closing(sqlite3.connect(db)) as c:
                self.assertFalse(c.execute("SELECT 1 FROM sqlite_master WHERE name='a2_activity_active_model'").fetchone())
            run(db,migrate_from_v1=True);run(db)
            with closing(sqlite3.connect(db)) as c:
                self.assertEqual(c.execute("SELECT baseline_fingerprint FROM a2_activity_model WHERE version='legacy_v1'").fetchone()[0],'old_fingerprint')
                self.assertEqual(c.execute('SELECT count(*) FROM a2_activity_model').fetchone()[0],2)
                self.assertEqual(c.execute('SELECT count(DISTINCT version) FROM v_a2_activity_followup').fetchone()[0],1)
    def test_rerun_append_and_revision_guard(self):
        f,e=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'db.sqlite'
            with closing(sqlite3.connect(db)) as c,c:
                c.execute('CREATE TABLE a2_age_feature(adm_cd TEXT,date TEXT,age_scheme TEXT,age_band TEXT,feature_json TEXT)')
                c.execute('CREATE TABLE a2_age_detection(adm_cd TEXT,date TEXT,age_band TEXT,model_version TEXT,communication_signal INTEGER,mobility_signal INTEGER)')
                c.executemany('INSERT INTO a2_age_feature VALUES(?,?,?,?,?)',[(r['adm_cd'],r['date'],'service',r['age_band'],json.dumps(r)) for r in f])
                c.executemany('INSERT INTO a2_age_detection VALUES(?,?,?,?,?,?)',[(r['adm_cd'],r['date'],r['age_band'],r['model_version'],1,0) for r in e])
            run(db);r=run(db);self.assertEqual(sum(r['inserted'].values()),0)
            future=copy.deepcopy([r for r in f if r['date']=='2025-01-01'])
            with closing(sqlite3.connect(db)) as c,c:
                for r in future:
                    r['date']='2026-01-01';c.execute('INSERT INTO a2_age_feature VALUES(?,?,?,?,?)',(r['adm_cd'],r['date'],'service',r['age_band'],json.dumps(r)))
            r=run(db);self.assertEqual(r['inserted']['a2_activity_followup'],1)
            with closing(sqlite3.connect(db)) as c,c:
                changed=next(r for r in f if r['adm_cd']=='0' and r['date']=='2025-10-01').copy();changed['call_contacts']=1
                c.execute('UPDATE a2_age_feature SET feature_json=? WHERE adm_cd=? AND date=?',(json.dumps(changed),'0','2025-10-01'))
            with self.assertRaisesRegex(ValueError,'historical'):run(db)
            with closing(sqlite3.connect(db)) as c,c:
                changed=next(r for r in f if r['adm_cd']=='0' and r['date']=='2024-10-01').copy();changed['call_contacts']=1
                c.execute('UPDATE a2_age_feature SET feature_json=? WHERE adm_cd=? AND date=?',(json.dumps(changed),'0','2024-10-01'))
            with self.assertRaisesRegex(ValueError,'migration'):run(db)
if __name__=='__main__':unittest.main()

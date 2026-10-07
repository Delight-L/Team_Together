import copy
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import weather_tracking as w
from source_semantics import window,canonical

def fixture():
    c=sqlite3.connect(':memory:')
    c.executescript('CREATE TABLE ctx_weather_month(period TEXT PRIMARY KEY,payload_json TEXT);CREATE TABLE ctx_weather_window(date TEXT PRIMARY KEY,payload_json TEXT);'+w.SCHEMA)
    stored={p:{'period':p,'rainfall_mm':float(int(p[5:])*10),'rain_days':float(int(p[5:])),'snow_days':0.} for p in w.months('2022-01','2025-12')}
    c.executemany('INSERT INTO ctx_weather_month VALUES(?,?)',[(p,canonical(v)) for p,v in stored.items()])
    for label in ('2025-07-01','2025-10-01','2025-12-01'):
        win=window(label)
        win['totals']={m:sum(stored[p][m] for p in win['observation_months']) for m in w.METRICS}
        c.execute('INSERT INTO ctx_weather_window VALUES(?,?)',(label,canonical(win)))
    return c,stored

class WeatherTrackingTests(unittest.TestCase):
    def test_months_and_windows_kept_separate(self):
        c,stored=fixture()
        with closing(c),c:
            result=w.run(c)
            self.assertEqual(result['new_or_enriched_months'],6)
            p=json.loads(c.execute("SELECT payload_json FROM ctx_weather_window_tracking WHERE date='2025-10-01'").fetchone()[0])
            self.assertEqual(p['observation_months'],['2025-07','2025-08','2025-09'])
            self.assertEqual(p['metrics']['rainfall_mm']['current'],240.)
            self.assertEqual(p['metrics']['rainfall_mm']['baseline_periods'],['2022-10-01','2023-10-01','2024-10-01'])
    def test_no_future_month_enters_reference(self):
        _,stored=fixture()
        stored['2025-07']['rainfall_mm']=100000.
        p=w.payload(stored,'2025-07')
        self.assertEqual(p['metrics']['rainfall_mm']['baseline_mean'],70.)
        self.assertEqual(p['metrics']['rainfall_mm']['baseline_n'],3)
    def test_zero_snow_baseline_not_zero_percent(self):
        _,stored=fixture()
        p=w.payload(stored,'2025-12')
        self.assertIsNone(p['metrics']['snow_days']['change_pct'])
        self.assertEqual(p['metrics']['snow_days']['difference'],0.)
        self.assertEqual(p['metrics']['snow_days']['percent_status'],'zero_baseline_mean')
    def test_idempotence(self):
        c,_=fixture()
        with closing(c),c:
            w.run(c);result=w.run(c)
            self.assertEqual(result['new_or_enriched_months'],0)
            self.assertEqual(result['new_or_enriched_windows'],0)
    def test_fixed_baseline_revision_blocked(self):
        c,stored=fixture()
        with closing(c),c:
            w.run(c);stored['2022-07']['rainfall_mm']+=10
            c.execute('UPDATE ctx_weather_month SET payload_json=? WHERE period=?',(canonical(stored['2022-07']),'2022-07'))
            with self.assertRaisesRegex(ValueError,'baseline revision'):w.run(c)
    def test_2026_updates_keep_existing_rows(self):
        c,stored=fixture()
        with closing(c),c:
            w.run(c)
            old=c.execute('SELECT payload_json FROM ctx_weather_window_tracking ORDER BY date').fetchall()
            new={'period':'2026-01','rainfall_mm':11.,'rain_days':3.,'snow_days':1.}
            c.execute('INSERT INTO ctx_weather_month VALUES(?,?)',('2026-01',canonical(new)))
            win=window('2026-01-01');win['totals']={m:sum(stored[p][m] for p in win['observation_months']) for m in w.METRICS}
            c.execute('INSERT INTO ctx_weather_window VALUES(?,?)',('2026-01-01',canonical(win)))
            w.run(c)
            self.assertEqual(old,c.execute("SELECT payload_json FROM ctx_weather_window_tracking WHERE date<'2026-01-01' ORDER BY date").fetchall())
            p=json.loads(c.execute("SELECT payload_json FROM ctx_weather_window_tracking WHERE date='2026-01-01'").fetchone()[0])
            self.assertEqual(p['metrics']['rainfall_mm']['baseline_n'],3)
            monthly=json.loads(c.execute("SELECT payload_json FROM ctx_weather_month_tracking WHERE period='2026-01'").fetchone()[0])
            self.assertEqual(monthly['metrics']['rainfall_mm']['baseline_n'],4)
    def test_incomplete_window_not_partial_sum(self):
        _,stored=fixture();win=window('2025-10-01')
        win['totals']={'rainfall_mm':None,'rain_days':None,'snow_days':None}
        p=w.payload(stored,'2025-10-01',win)
        self.assertIsNone(p['metrics']['rainfall_mm']['difference'])
        self.assertEqual(p['quality_status'],'unavailable')
    def test_sparse_history_unavailable(self):
        _,stored=fixture();stored.pop('2022-07')
        p=w.payload(stored,'2025-07')
        self.assertEqual(p['metrics']['rainfall_mm']['baseline_n'],2)
        self.assertIsNone(p['metrics']['rainfall_mm']['difference'])
    def test_late_missing_current_enrichment_audited(self):
        c,stored=fixture()
        with closing(c),c:
            p=w.payload(stored,'2025-07');p['metrics']['rainfall_mm']['current']=None
            w.upsert(c,'month','2025-07',p)
            w.upsert(c,'month','2025-07',w.payload(stored,'2025-07'))
            self.assertEqual(c.execute('SELECT count(*) FROM ctx_weather_tracking_revision').fetchone()[0],1)
    def test_known_current_revision_blocked(self):
        c,stored=fixture()
        with closing(c),c:
            w.run(c);stored['2025-07']['rainfall_mm']+=10
            with self.assertRaisesRegex(ValueError,'Historical tracked weather change'):w.upsert(c,'month','2025-07',w.payload(stored,'2025-07'))

if __name__=='__main__':unittest.main()

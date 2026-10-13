"""Dependency-light regression checks for the annual survey adapter."""
from pathlib import Path
import sys,sqlite3,tempfile,unittest
from contextlib import closing
from unittest.mock import patch
import numpy as np,pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import survey
MAP={'parent':'p','sick':'s','money':'m','emotion':'e','family':'f','outside':'o','weight':'w','household':'id','district':'gu','age':'age'}
def data():return pd.DataFrame({'p':[2,1,1],'s':[np.nan,1,2],'m':[np.nan,2,2],'e':[np.nan,1,2],'f':[5,1,3],'o':[5,2,4],'w':[1.,2.,3.],'id':[1,2,2],'gu':[680]*3,'age':[4]*3})
class Checks(unittest.TestCase):
 def test_structural_no_support(self):
  r={x[3]:x for x in survey.summarize_seoul(data(),'seoul_2022',MAP) if x[1:3]==('gangnam','40s')}
  self.assertAlmostEqual(r['no_support_sick'][4],4/6)
  self.assertAlmostEqual(r['no_support_parent'][4],1/6)
  self.assertAlmostEqual(r['no_support_all3'][4],4/6)
  self.assertAlmostEqual(r['no_support3_and_lonely_outside'][4],4/6)
  self.assertAlmostEqual(r['loneliness_family_mean10'][4],25/6)
  self.assertEqual(r['no_support_all3'][7:10],(3,2,2))
  self.assertEqual(r['no_support_all3'][11],'small_sample')
 def test_item_nonresponse(self):
  d=data();d.loc[1,'s']=np.nan
  r=next(x for x in survey.summarize_seoul(d,'seoul_2022',MAP) if x[1:4]==('gangnam','40s','no_support_sick'))
  self.assertEqual(r[7],2);self.assertEqual(r[4],1)
 def test_bad_code(self):
  for field in ['p','s']:
   d=data();d.loc[0,field]=9
   with self.assertRaises(ValueError):survey.summarize_seoul(d,'seoul_2022',MAP)
 def test_bad_weights(self):
  for value in [0,np.nan,-1,np.inf]:
   d=data();d.loc[0,'w']=value
   with self.assertRaises(ValueError):survey.summarize_seoul(d,'seoul_2022',MAP)
 def test_contradictory_support(self):
  d=data();d.loc[0,'s']=1
  with self.assertRaises(ValueError):survey.normalize(d,MAP)
 def test_time_available_and_cardinality(self):
  with sqlite3.connect(':memory:') as c:
   c.executescript(survey.SCHEMA);c.execute('CREATE TABLE base(adm_cd TEXT,date TEXT,age_band TEXT)');c.execute('CREATE VIEW v_a123_age_elder_context AS SELECT * FROM base')
   c.executemany('INSERT INTO base VALUES(?,?,?)',[('x','2025-07-01','40s'),('y','2025-12-01','40s'),('z','2026-01-01','50s')])
   for year,date in [(2024,'2025-09-12'),(2025,'2026-04-09')]:
    source=f'seoul_{year}';c.execute('INSERT INTO ctx_survey_source VALUES(?,?,?,?,?,?)',(source,'seoul_survey',year,'hash',date,'{}'))
    for age in ['40s','50s']:c.execute('INSERT INTO ctx_survey_metric VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(source,'gangnam',age,'test',.1,'proportion',100,100,10,80,90,'available','{}'))
   survey.refresh_views(c)
   self.assertEqual(c.execute('SELECT COUNT(*) FROM v_a123_age_survey_context').fetchone()[0],3)
   self.assertEqual([r[0] for r in c.execute('SELECT survey_year FROM v_a123_age_survey_context ORDER BY date')],[2025,2025,2025])
   self.assertEqual([r[0] for r in c.execute('SELECT survey_year FROM v_a123_age_survey_available_context ORDER BY date')],[None,2024,2024])
 def test_historical_correction_blocked(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'t.sqlite';source=Path(td)/'f.xlsx';source.write_bytes(b'changed')
   with closing(sqlite3.connect(db)) as c:
    c.executescript(survey.SCHEMA);c.execute('INSERT INTO ctx_survey_source VALUES(?,?,?,?,?,?)',('seoul_2022','seoul_survey',2022,'old',None,'{}'));c.commit()
   with self.assertRaisesRegex(ValueError,'correction'):survey.run(db,{'survey_context':{'seoul_years':{'2022':{'path':str(source)}}}},Path(td)/'out')
   with closing(sqlite3.connect(db)) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM ctx_survey_metric').fetchone()[0],0)
 def test_new_year_append_and_repeat(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);db=root/'db.sqlite';years={}
   for year in [2025,2026]:
    path=root/f'{year}.xlsx';path.write_bytes(str(year).encode());years[str(year)]={'path':str(path),'mapping':{}}
   def packet(year,opt):
    sid=f'seoul_{year}'
    row=(sid,'gangnam','40s','test',.1 if year==2025 else .2,'proportion',100,100,10,80,90,'available','{}')
    return {'source_id':sid,'survey':'seoul_survey','year':year,'fingerprint':survey.sha(opt['path']),'available_from':None,'metadata':{'path':opt['path'],'mapping':{}},'rows':[row],'guides':[]}
   with patch.object(survey,'ROOT',root),patch.object(survey,'packet_seoul',side_effect=packet):
    a=survey.run(db,{'survey_context':{'seoul_years':{'2025':years['2025']}}},root/'out')
    b=survey.run(db,{'survey_context':{'seoul_years':years}},root/'out')
    repeat=survey.run(db,{'survey_context':{'seoul_years':years}},root/'out')
    self.assertEqual((a['inserted_sources'],b['inserted_sources'],repeat['inserted_sources']),(1,1,0))
    years['2025']['available_from']='2026-04-09'
    filled=survey.run(db,{'survey_context':{'seoul_years':years}},root/'out')
    self.assertEqual(filled['publication_dates_filled'],1)
    years['2025']['available_from']='2026-04-10'
    with self.assertRaisesRegex(ValueError,'Publication'):survey.run(db,{'survey_context':{'seoul_years':years}},root/'out')
   with closing(sqlite3.connect(db)) as c:self.assertEqual(c.execute('SELECT year,value FROM v_survey_annual ORDER BY year').fetchall(),[(2025,.1),(2026,.2)])
if __name__=='__main__':unittest.main()

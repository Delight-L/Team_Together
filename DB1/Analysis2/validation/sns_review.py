from pathlib import Path
from contextlib import closing
import sqlite3,json
R=Path(__file__).resolve().parent
DB1=next(p for p in R.parents if (p/'run_db1.py').exists())
O=DB1/'outputs/validation/retrospective_20261007';O.mkdir(parents=True,exist_ok=True)
with closing(sqlite3.connect('file:'+(DB1/'outputs/db1.sqlite').as_posix()+'?mode=ro',uri=True)) as c:
 cases=[]
 for code,label,age,sns,window in c.execute("SELECT adm_cd,source_label_date,age_band,same_period_sns_json,observation_window_json FROM v_a123_age_source_context WHERE source_label_date BETWEEN '2025-07-01' AND '2025-12-01' AND (communication_signal=1 OR mobility_signal=1) ORDER BY source_label_date,adm_cd,age_band"):
  s=json.loads(sns);cases.append(dict(adm_cd=code,signal_date=label,age_band=age,dong=s['adm_nm'],same_period_context=s,observation_window=json.loads(window)))
(O/'sns_review.json').write_text(json.dumps(dict(cases=cases,negative_values_valid=True,time_comparison_allowed=False,percent_change_allowed=False,contact_substitution_confirmed=False,correction='Previous percentage changes and 8 quality-failure claims withdrawn; standardized negative values are valid.'),ensure_ascii=False,indent=2),encoding='utf-8')
print('Corrected SNS same-period review:',len(cases))

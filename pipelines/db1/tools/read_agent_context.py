from pathlib import Path as _DatabasePath
import sys as _database_sys
_database_sys.path.insert(0, str(next(p for p in _DatabasePath(__file__).resolve().parents if (p/'pipelines/db1').is_dir())))
from pipelines.db1 import database
"""Read DB1 evidence without modifying the database. Outputs retrospective context."""
from pathlib import Path
from contextlib import closing
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Context'))
from evidence_reader import enrich

def read(db,label=None,dong=None,age=None,signals_only=False,limit=10,as_of=None):
    if not 1<=limit<=1000:raise ValueError('limit must be 1..1000')
    filters=[];params=[]
    if label:filters.append('source_label_date=%s');params.append(label)
    if dong:filters.append('adm_cd=%s');params.append(dong)
    if age:filters.append('age_band=%s');params.append(age)
    if signals_only:filters.append('(communication_signal=1 OR mobility_signal=1)')
    sql='SELECT * FROM v_a123_age_source_context'+(' WHERE '+' AND '.join(filters) if filters else '')+' ORDER BY source_label_date DESC,adm_cd,age_band LIMIT %s'
    params.append(limit)
    with closing(database.connect(db,readonly=True)) as c:
        c.dict_rows=True
        rows=[]
        for r in c.execute(sql,params).fetchall():
            item=dict(r)
            for k in list(item):
                if k.endswith('_json'):item[k]=json.loads(item[k]) if item[k] else None
            key=(item['adm_cd'],item['age_band'],item['source_label_date'])
            # Restrict followup to the requested label; do not silently join latest future rows.
            follow=c.execute('SELECT payload_json FROM v_a2_activity_followup WHERE adm_cd=%s AND age_band=%s AND date=%s',key).fetchone()
            item['activity_followup_same_label']=json.loads(follow[0]) if follow else None
            survey=c.execute('SELECT survey_year,survey_available_from,survey_geography_alignment,survey_time_alignment,survey_context_json,elder_age_alignment,elder_context_json FROM v_a123_age_survey_context WHERE adm_cd=%s AND age_band=%s AND date=%s',key).fetchone()
            item['survey_and_elder_background']=dict(survey) if survey else None
            if survey:
                for k in ['survey_context_json','elder_context_json']:
                    item['survey_and_elder_background'][k]=json.loads(survey[k]) if survey[k] else None
            item['retrospective_only']=True
            item=enrich(c,item,as_of)
            if item is not None:rows.append(item)
        return {'database':database.workspace(db),'mode':'read_only','rows':rows,'live_availability_verified':False,'sns_time_comparison_allowed':False,'as_of':as_of,'as_of_scope':'registered_input_history_and_auxiliary_release_filter; not a reconstructed real-time model deployment'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',default='db1_pipeline')
    p.add_argument('--label',help='aggregation label YYYY-MM-01, not the observation month')
    p.add_argument('--dong',help='7-digit DB1 administrative code');p.add_argument('--age',choices=['20s','30s','40s','50s','60plus'])
    p.add_argument('--signals-only',action='store_true');p.add_argument('--limit',type=int,default=10)
    p.add_argument('--as-of',help='YYYY-MM-DD; unknown core input releases exclude rows')
    a=p.parse_args();print(json.dumps(read(a.db,a.label,a.dong,a.age,a.signals_only,a.limit,a.as_of),ensure_ascii=False,indent=2))

if __name__=='__main__':main()

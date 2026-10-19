from pathlib import Path as _DatabasePath
import sys as _database_sys
_database_sys.path.insert(0, str(next(p for p in _DatabasePath(__file__).resolve().parents if (p/'pipelines/db1').is_dir())))
"""Export aggregate DB1 context without changing the authoritative DB1 database."""
from pathlib import Path
import argparse,csv,json,hashlib,math


def export(source, target, workspace_schema=None):
    from pipelines.db1 import database
    def records(path):
        with path.open(encoding='utf-8-sig') as stream:
            return list(csv.DictReader(stream))
    def numeric(value):
        if value in ('',None):
            return None
        n=float(value)
        if not math.isfinite(n):
            return None
        return n
    typologies=[]
    paths=sorted((source/'Analysis1/outputs/periods').glob('*/context.csv'))
    for path in paths:
        for r in records(path):
            typologies.append({'period':path.parent.name,'code':r['adm_cd'],'name':r['dong_name'],
                               'cluster':int(r['cluster']),'type':r['cluster_type']})
    path=source/'Analysis3/outputs/a3a_comparison.csv'
    consumption=[{'period':r['period'],'code':r['adm_cd'],'age':r['age'],'domain':r['domain'],
                  'change':numeric(r['change_pct']),'available':r['comparison_available']=='1',
                  'baselineN':int(r['baseline_n']),'baselinePeriods':json.loads(r['baseline_periods']),
                  'baselineDaily':numeric(r['baseline_daily_mean']),'currentDaily':numeric(r['matched_current_daily_count']),
                  'reason':r['comparison_reason']} for r in records(path)]
    with database.connect(workspace_schema,readonly=True) as conn:
        conn.dict_rows=True
        surveys=[dict(r) for r in conn.execute("SELECT year,district,age_band,metric,value,n_valid,effective_n,quality_status FROM v_survey_annual WHERE survey='seoul_survey' AND district IN ('gangnam','seoul') AND metric IN ('no_support_emotion','no_support_sick','loneliness_outside_agree')")]
    names={r['name'] for r in typologies}
    assert len(names)==22 and '개포3동' in names
    assert len({(r['period'],r['code'],r['age'],r['domain']) for r in consumption})==len(consumption)
    payload={'city':'강남구','scope':'regional_context','typologies':typologies,'consumption':consumption,
             'surveys':surveys,'consumptionScope':'merchant_dong_customer_age','surveyScope':'district_age_annual',
             'alignment':'retrospective_context',
             'sourceHashes':{str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*paths,path]}}
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    return {key:len(payload[key]) for key in ('typologies','consumption','surveys')}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db1-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[2]/'data/processed/region_insights.json')
    args=parser.parse_args()
    print(export(args.db1_root.resolve(),args.output.resolve()))

from pathlib import Path
import argparse,json,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
from preprocessing.monthly_features import build_month_feature_table
from data.monthly_validation import validate_history,validate_feature_rows
from run_analysis2_sequential import find_month_file,validate_current_month
from analysis.sequential import run_month
from analysis.outputs import build_evidence_card
import db1_store as store
from age_features import sync_age_history
from age_detection import run as detect_age


def sync_age(settings, db, through):
    sync_age_history(settings, db, through, ROOT/'Analysis2/outputs/age')
    detect_age(db,ROOT/'Analysis2/outputs/age_detection')


def initialize(settings,db):
    initial=pd.read_csv(ROOT/'Analysis2/data/reference/analysis2_initial_history_202201_202506.csv')
    initial['date']=pd.to_datetime(initial.date)
    validate_history(initial)
    store.seed_history(db,initial)
    sync_age(settings,db,initial.date.max())


def process(settings,db,month):
    period=pd.Period(month,freq='M').to_timestamp()
    a2=settings['analysis2']
    telecom=find_month_file(Path(a2['telecom_dir']),period.year,period.month,'29개')
    interest=find_month_file(Path(a2['interest_dir']),period.year,period.month,'10개')
    current=build_month_feature_table(telecom,interest,a2['rain'],a2['diary'],period.year,period.month)
    validate_feature_rows(current)
    digest=store.fingerprint(current,['date','행정동코드'])
    with store.connect(db) as con:
        if store.already_processed(con,'analysis2',str(period.date()),digest):
            sync_age(settings,db,period)
            store.export_csv(db,ROOT/settings['exports'])
            print(f'{month}: already processed, no duplicate insert',flush=True)
            return
        history=store.history(con)
        context_period,context=store.context_for(con,period)
    validate_history(history)
    validate_current_month(history,current,period)
    full_result=run_month(history,current,context,return_history=True)
    result=full_result.loc[full_result.date==period].copy()
    evidence=build_evidence_card(full_result)
    evidence=evidence.loc[pd.to_datetime(evidence.date)==period].copy()
    saved=store.commit_a2(db,current,result,evidence,context_period,{'telecom':str(telecom),'interest':str(interest),'rain':a2['rain'],'diary':a2['diary']})
    sync_age(settings,db,period)
    store.export_csv(db,ROOT/settings['exports'])
    with store.connect(db) as con: updated=store.history(con)
    print(json.dumps({'analysis':'analysis2','month':month,'saved':saved,'history_rows':len(updated),'signals':int(result.any_signal.sum()),'context_period':context_period}),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--db');p.add_argument('--month');p.add_argument('--initialize',action='store_true');p.add_argument('--scan',action='store_true');a=p.parse_args()
    settings=json.loads(Path(a.config).read_text(encoding='utf-8'));db=Path(a.db) if a.db else ROOT/settings['database']
    if a.initialize:
        initialize(settings,db);store.export_csv(db,ROOT/settings['exports']);return
    if a.scan:
        with store.connect(db) as con: latest_history=store.history(con)
        if not latest_history.empty: sync_age(settings,db,latest_history.date.max())
        while True:
            with store.connect(db) as con: history=store.history(con)
            if history.empty: raise ValueError('Run initialize first')
            period=(history.date.max().to_period('M')+1).to_timestamp()
            a2=settings['analysis2']
            try:
                find_month_file(Path(a2['telecom_dir']),period.year,period.month,'29개')
                find_month_file(Path(a2['interest_dir']),period.year,period.month,'10개')
            except FileNotFoundError:
                print(f'Waiting for complete raw files: {period:%Y-%m}',flush=True);break
            process(settings,db,period.strftime('%Y-%m'))
    else:
        if not a.month: p.error('--month is required')
        process(settings,db,a.month)

if __name__=='__main__':main()

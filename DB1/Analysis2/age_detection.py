"""Prospective dong/age behavior-change detection with baseline-only calibration."""
from pathlib import Path
from contextlib import closing
import argparse
import hashlib
import json
import sqlite3

import numpy as np
import pandas as pd

CORE = ['call_contacts', 'text_contacts', 'weekday_move_count', 'weekend_move_count']
DISTANCE = ['weekday_move_distance', 'weekend_move_distance']
INTEREST = ['comm_low_rate', 'weekday_outing_low_rate', 'weekend_outing_low_rate']
KEY = ['_area', 'age_band']
BANDS = ['20s', '30s', '40s', '50s', '60plus']
DEFAULT = {
    'method': 'a2_age_detection_v1', 'age_scheme': 'service',
    'baseline_start': '2022-01-01', 'baseline_end': '2025-06-01',
    'detection_start': '2025-07-01', 'min_history': 12,
    'min_valid_population': 200, 'min_coverage': 0.80, 'min_peer_dongs': 11,
    'scale': 0.6745, 'lower_quantile': 0.025, 'threshold_cap': -2.0,
    'min_calibration_scores': 24,
}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS a2_age_model (
 model_version TEXT PRIMARY KEY, baseline_end TEXT NOT NULL, baseline_fingerprint TEXT NOT NULL,
 settings_json TEXT NOT NULL, calibration_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS a2_age_detection (
 adm_cd TEXT NOT NULL, date TEXT NOT NULL, age_scheme TEXT NOT NULL, age_band TEXT NOT NULL,
 model_version TEXT NOT NULL, assessment_status TEXT NOT NULL,
 communication_signal INTEGER, mobility_signal INTEGER, combined_signal INTEGER,
 isolation_related_candidate INTEGER, result_json TEXT NOT NULL,
 PRIMARY KEY(adm_cd,date,age_scheme,age_band,model_version),
 FOREIGN KEY(adm_cd,date,age_scheme,age_band) REFERENCES a2_age_feature(adm_cd,date,age_scheme,age_band),
 FOREIGN KEY(model_version) REFERENCES a2_age_model(model_version));
CREATE TABLE IF NOT EXISTS a2_age_common_change (
 date TEXT NOT NULL, age_band TEXT NOT NULL, model_version TEXT NOT NULL,
 result_json TEXT NOT NULL, PRIMARY KEY(date,age_band,model_version),
 FOREIGN KEY(model_version) REFERENCES a2_age_model(model_version));
CREATE VIEW IF NOT EXISTS v_a2_age_detection AS
 SELECT adm_cd,date,age_scheme,age_band,model_version,assessment_status,
 communication_signal,mobility_signal,combined_signal,isolation_related_candidate,result_json
 FROM a2_age_detection;
'''


def records(frame):
    return json.loads(frame.to_json(orient='records', date_format='iso', force_ascii=False, double_precision=15))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def validate_features(frame, settings):
    f = frame.copy()
    f['date'] = pd.to_datetime(f.date, format='mixed')
    f['_area'] = f['행정동코드'].astype(str)
    f = f.loc[f.age_scheme.eq(settings['age_scheme'])].copy()
    if f.empty: raise ValueError('No age feature history; rebuild first')
    if not f.date.eq(f.date.dt.to_period('M').dt.to_timestamp()).all():
        raise ValueError('Age dates must be month starts')
    if f.duplicated(['date']+KEY).any(): raise ValueError('Duplicate age history keys')
    dates = pd.DatetimeIndex(sorted(f.date.unique()))
    expected = pd.date_range(settings['baseline_start'], dates.max(), freq='MS')
    if not dates.equals(expected): raise ValueError('Age history has missing months')
    codes = set(f.loc[f.date.eq(dates[0]), '_area'])
    for _, group in f.groupby('date'):
        if len(codes) != 22 or len(group) != 110 or set(group.age_band) != set(BANDS) or set(group['_area']) != codes:
            raise ValueError('Expected all 22 dongs and five age bands per month')
    if dates.max() < pd.Timestamp(settings['baseline_end']): raise ValueError('Incomplete initial age baseline')
    return f.sort_values(KEY+['date']).reset_index(drop=True)


def historical_z(values, minimum, scale):
    """Current/future values never enter the current month's location/scale."""
    values = np.asarray(values, dtype=float)
    scores = np.full(len(values), np.nan)
    counts = np.zeros(len(values), dtype=int)
    medians = np.full(len(values), np.nan)
    mads = np.full(len(values), np.nan)
    for pos, value in enumerate(values):
        history = values[:pos][np.isfinite(values[:pos])]
        counts[pos] = len(history)
        if len(history) < minimum or not np.isfinite(value): continue
        median = np.median(history); mad = np.median(np.abs(history-median))
        medians[pos] = median; mads[pos] = mad
        if mad > 0: scores[pos] = scale * (value-median)/mad
    return scores, counts, medians, mads


def add_scores(frame, grouping, value_column, prefix, settings):
    for suffix in ['rz', 'baseline_n', 'history_median', 'history_mad']:
        frame[prefix+'_'+suffix] = np.nan
    for _, group in frame.groupby(grouping, sort=False):
        results = historical_z(group[value_column], settings['min_history'], settings['scale'])
        for suffix, values in zip(['rz', 'baseline_n', 'history_median', 'history_mad'], results):
            frame.loc[group.index, prefix+'_'+suffix] = values


def compute_scores(frame, settings):
    f = validate_features(frame, settings)
    for metric in CORE+DISTANCE:
        v = pd.to_numeric(f[metric], errors='coerce')
        pop = pd.to_numeric(f[metric+'_valid_population'], errors='coerce')
        total = pd.to_numeric(f.total_population, errors='coerce')
        coverage = pop / total.where(total.gt(0))
        f[metric+'_coverage'] = coverage
        f[metric+'_valid'] = (np.isfinite(v) & v.gt(0) & np.isfinite(pop)
                              & pop.ge(settings['min_valid_population'])
                              & coverage.ge(settings['min_coverage']) & coverage.le(1.00000001))
        safe = np.log(v.where(f[metric+'_valid']))
        f[metric+'_log_change'] = safe.groupby([f[k] for k in KEY]).diff()
        monthly = f.groupby(['date','age_band'])[metric+'_log_change']
        f[metric+'_peer_n'] = monthly.transform('count')
        f[metric+'_common_change'] = monthly.transform('median').where(f[metric+'_peer_n'].ge(settings['min_peer_dongs']))
        f[metric+'_residual'] = f[metric+'_log_change']-f[metric+'_common_change']
        if metric in CORE:
            add_scores(f, KEY, metric+'_log_change', metric+'_absolute', settings)
            add_scores(f, KEY, metric+'_residual', metric+'_local', settings)
    # Interest evidence is usable only with valid counts and no structural issue in both months.
    interest_valid = (~f.interest_structural_issue.astype(bool) & f.interest_one_person_population.gt(0))
    f['interest_evidence_available'] = interest_valid & interest_valid.groupby([f[k] for k in KEY]).shift(1).eq(True)
    for metric in INTEREST:
        f[metric+'_change'] = f.groupby(KEY)[metric].diff().where(f.interest_evidence_available)
    common = f.groupby(['date','age_band'], as_index=False).agg({
        **{m+'_common_change':'first' for m in CORE},
        **{m+'_peer_n':'first' for m in CORE}}).sort_values(['age_band','date']).reset_index(drop=True)
    for metric in CORE:
        add_scores(common, ['age_band'], metric+'_common_change', metric+'_common', settings)
    return f, common


def calibrate(scores, common, settings):
    rows = []
    for scope, source in [('absolute',scores),('local',scores),('common',common)]:
        baseline = source.loc[source.date.le(pd.Timestamp(settings['baseline_end']))]
        for age, group in baseline.groupby('age_band'):
            for metric in CORE:
                values = group[metric+'_'+scope+'_rz'].dropna()
                enough = len(values) >= settings['min_calibration_scores']
                lower = float(values.quantile(settings['lower_quantile'])) if enough else None
                threshold = min(settings['threshold_cap'], lower) if enough else None
                rows.append({'scope':scope,'age_band':age,'metric':metric,'n_scores':len(values),
                             'lower_quantile':lower,'threshold':threshold,
                             'calibration_status':'baseline_calibrated_exploratory' if enough else 'insufficient_calibration',
                             'interpretation':'historical lower-tail calibration; not false-positive rate or isolation probability'})
    return pd.DataFrame(rows)


def scope_flags(frame, scope, calibration):
    f = frame
    for metric in CORE:
        mapping = calibration.loc[calibration.scope.eq(scope) & calibration.metric.eq(metric)].set_index('age_band').threshold
        f[metric+'_'+scope+'_threshold'] = f.age_band.map(mapping)
        f[metric+'_'+scope+'_assessable'] = f[metric+'_'+scope+'_rz'].notna() & f[metric+'_'+scope+'_threshold'].notna()
        change = metric+'_common_change' if scope == 'common' else metric+'_log_change'
        f[metric+'_'+scope+'_signal'] = (f[metric+'_'+scope+'_rz'].le(f[metric+'_'+scope+'_threshold']) & f[change].lt(0)).where(f[metric+'_'+scope+'_assessable']).astype('boolean')
    for domain, metrics in [('communication',CORE[:2]),('mobility',CORE[2:])]:
        assessable = f[[m+'_'+scope+'_assessable' for m in metrics]].all(axis=1)
        signal = f[[m+'_'+scope+'_signal' for m in metrics]].fillna(False).all(axis=1)
        f[domain+'_'+scope+'_assessable'] = assessable
        f[domain+'_'+scope+'_signal'] = signal.where(assessable).astype('boolean')
    f['combined_'+scope+'_signal'] = f['communication_'+scope+'_signal'] & f['mobility_'+scope+'_signal']


def detect(scores, common, calibration, settings):
    f = scores.copy(); c = common.copy()
    for scope in ['absolute','local']: scope_flags(f,scope,calibration)
    scope_flags(c,'common',calibration)
    for domain in ['communication','mobility']:
        assessable = f[domain+'_absolute_assessable'] | f[domain+'_local_assessable']
        signal = f[domain+'_absolute_signal'].fillna(False) | f[domain+'_local_signal'].fillna(False)
        f[domain+'_signal'] = signal.where(assessable).astype('boolean')
    # Both behavior domains may be supported by different scopes, but all flagged metrics must actually fall.
    f['combined_signal'] = f.communication_signal & f.mobility_signal
    f['any_signal'] = f.communication_signal | f.mobility_signal
    f['assessment_status'] = np.where(
        f.communication_signal.notna() & f.mobility_signal.notna(), 'assessed',
        np.where(f.communication_signal.notna() | f.mobility_signal.notna(), 'partially_assessed', 'deferred'))
    f['isolation_related_candidate'] = f.combined_signal
    f['interest_support'] = (f.comm_low_rate_change.gt(0) &
        (f.weekday_outing_low_rate_change.gt(0) | f.weekend_outing_low_rate_change.gt(0))).where(f.interest_evidence_available).astype('boolean')
    f['distance_support'] = (f.weekday_move_distance_log_change.lt(0) | f.weekend_move_distance_log_change.lt(0)).where(f[ [m+'_log_change' for m in DISTANCE]].notna().any(axis=1)).astype('boolean')
    f['evidence_level'] = 'no_detected_joint_behavior_change'
    f.loc[f.combined_signal.fillna(False), 'evidence_level'] = 'joint_behavior_change_candidate'
    f.loc[f.combined_signal.fillna(False) & f.interest_support.fillna(False) & f.distance_support.fillna(False), 'evidence_level'] = 'joint_candidate_with_supporting_evidence'
    f.loc[f.assessment_status.eq('deferred'), 'evidence_level'] = 'assessment_deferred'
    f.loc[f.assessment_status.eq('partially_assessed') & ~f.combined_signal.fillna(False), 'evidence_level'] = 'partial_assessment'
    # Detect large source-population changes as a review reason, not proof of a demographic cause.
    f['estimated_population_change_pct'] = f.groupby(KEY).total_population.pct_change(fill_method=None)*100
    f['population_shift_review'] = f.estimated_population_change_pct.abs().ge(10)
    if 'source_male_ratio' not in f: f['source_male_ratio'] = np.nan
    f['sex_composition_change_pp'] = f.groupby(KEY).source_male_ratio.diff()*100
    f['sex_composition_shift_review'] = f.sex_composition_change_pp.abs().ge(5)
    f['review_reasons'] = ''
    for mask, label in [
        (~f.interest_evidence_available, 'interest_evidence_unavailable'),
        (f.assessment_status.ne('assessed'),'some_behavior_domains_unassessable'),
        (f.population_shift_review,'estimated_population_shift_10pct'),
        (f.sex_composition_shift_review,'sex_composition_shift_5pp'),
        (f[ [m+'_absolute_history_mad' for m in CORE]].eq(0).any(axis=1),'zero_historical_mad'),
    ]:
        f.loc[mask, 'review_reasons'] += label+';'
    start = pd.Timestamp(settings['detection_start'])
    f['signal_status'] = 'baseline_only'
    f['adjacent_signal_run'] = 0
    for _, group in f.groupby(KEY, sort=False):
        previous = None; run_length = 0
        for idx in group.index:
            if f.at[idx,'date'] < start: continue
            signal = f.at[idx,'any_signal']
            if pd.isna(signal):
                status = 'Deferred'; previous = None; run_length = 0
            elif signal:
                status = 'Continuing' if previous is True else ('New_after_gap' if previous is None and f.at[idx,'date'] > start else 'New')
                run_length = run_length+1 if previous is True else 1; previous = True
            else:
                status = 'No_signal'; run_length = 0; previous = False
            f.at[idx,'signal_status'] = status; f.at[idx,'adjacent_signal_run'] = run_length
    f['signal_interpretation'] = 'aggregate isolation-related behavior-change screening; not confirmed social isolation or individual diagnosis'
    f['persistence_note'] = 'adjacent months can overlap in the source three-month aggregation; run length is not independent repeated evidence'
    return f, c


def pipeline(frame, settings=None):
    settings = {**DEFAULT, **(settings or {})}
    scores, common = compute_scores(frame, settings)
    calibration = calibrate(scores,common,settings)
    result, common = detect(scores,common,calibration,settings)
    baseline = scores.loc[scores.date.le(pd.Timestamp(settings['baseline_end']))].drop(columns=['_area']).sort_values(['date','행정동코드','age_band'])
    fingerprint = hashlib.sha256(canonical(records(baseline)).encode()).hexdigest()
    version = settings['method']+'_'+hashlib.sha256((canonical(settings)+fingerprint).encode()).hexdigest()[:12]
    result['detection_model_version'] = version; common['detection_model_version'] = version
    model = {'model_version':version,'baseline_fingerprint':fingerprint,'settings':settings,'calibration':records(calibration)}
    return result.drop(columns=['_area']), common, calibration, model


def add_context(con, result, model_version):
    result = result.copy()
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='a1_context'").fetchone(): return result
    contexts = pd.read_sql_query('SELECT adm_cd,period,effective_from,cluster,cluster_type FROM a1_context',con)
    if contexts.empty: return result
    result['context_period'] = None; result['a1_cluster_type'] = None
    saved_context = {
        (row[0],row[1],row[2]):(row[3],row[4])
        for row in con.execute("SELECT adm_cd,date,age_band,json_extract(result_json,'$.context_period'),json_extract(result_json,'$.a1_cluster_type') FROM a2_age_detection WHERE model_version=?",(model_version,))
    }
    for idx,row in result.iterrows():
        key=(str(row['행정동코드']),row['date'].strftime('%Y-%m-%d'),row['age_band'])
        if key in saved_context:
            result.at[idx,'context_period'],result.at[idx,'a1_cluster_type']=saved_context[key]
            continue
        context = contexts.loc[contexts.adm_cd.astype(str).eq(str(row['행정동코드'])) & pd.to_datetime(contexts.effective_from).le(row['date'])].sort_values('effective_from')
        if not context.empty:
            result.at[idx,'context_period'] = context.iloc[-1].period
            result.at[idx,'a1_cluster_type'] = context.iloc[-1].cluster_type
    return result


def load_features(db):
    with closing(sqlite3.connect(db)) as con:
        frame = pd.DataFrame([json.loads(row[0]) for row in con.execute("SELECT feature_json FROM a2_age_feature WHERE age_scheme='service' ORDER BY date,adm_cd,age_band")])
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='a2_age_raw'").fetchone():
            raw = pd.read_sql_query("SELECT date,adm_cd,sex,age_code,json_extract(raw_json,'$.총인구수') AS population FROM a2_age_raw WHERE kind='telecom'",con)
            if not raw.empty:
                raw['age_band'] = raw.age_code.map(lambda a:'60plus' if a>=60 else f'{a//10*10}s')
                total = raw.groupby(['date','adm_cd','age_band']).population.sum()
                male = raw.loc[raw.sex.eq(1)].groupby(['date','adm_cd','age_band']).population.sum()
                ratio = (male/total.where(total.gt(0))).rename('source_male_ratio').reset_index().rename(columns={'adm_cd':'행정동코드'})
                ratio['행정동코드']=ratio['행정동코드'].astype(int)
                ratio['date']=pd.to_datetime(ratio.date)
                frame['date']=pd.to_datetime(frame.date,format='mixed')
                frame=frame.merge(ratio,on=['date','행정동코드','age_band'],how='left',validate='one_to_one')
        return frame


def commit(con, result, common, model):
    version = model['model_version']
    con.execute('INSERT OR IGNORE INTO a2_age_model VALUES (?,?,?,?,?)', (version,model['settings']['baseline_end'],model['baseline_fingerprint'],canonical(model['settings']),canonical(model['calibration'])))
    saved = 0
    for row in records(result):
        date = pd.Timestamp(row['date']).strftime('%Y-%m-%d')
        key = (str(row['행정동코드']),date,row['age_scheme'],row['age_band'],version)
        existing = con.execute('SELECT result_json FROM a2_age_detection WHERE adm_cd=? AND date=? AND age_scheme=? AND age_band=? AND model_version=?',key).fetchone()
        payload = canonical(row)
        if existing:
            if existing[0] != payload: raise ValueError(f'{key}: changed detection result; explicit model revision required')
            continue
        flags = [None if row[k] is None else int(row[k]) for k in ['communication_signal','mobility_signal','combined_signal','isolation_related_candidate']]
        con.execute('INSERT INTO a2_age_detection VALUES (?,?,?,?,?,?,?,?,?,?,?)',(*key,row['assessment_status'],*flags,payload)); saved+=1
    for row in records(common):
        date = pd.Timestamp(row['date']).strftime('%Y-%m-%d'); payload=canonical(row)
        old=con.execute('SELECT result_json FROM a2_age_common_change WHERE date=? AND age_band=? AND model_version=?',(date,row['age_band'],version)).fetchone()
        if old and old[0] != payload: raise ValueError('Common age change results differ on rerun')
        con.execute('INSERT OR IGNORE INTO a2_age_common_change VALUES (?,?,?,?)',(date,row['age_band'],version,payload))
    return saved


def export(db, output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(db)) as con:
        for table,filename in [('a2_age_detection','analysis2_age_detection.csv'),('a2_age_common_change','analysis2_age_common_change.csv')]:
            frame=pd.DataFrame([json.loads(row[0]) for row in con.execute(f'SELECT result_json FROM {table}')])
            if not frame.empty: frame.sort_values(['date','age_band']).to_csv(output/filename,index=False,encoding='utf-8-sig')


def run(db, output, settings=None):
    result,common,calibration,model=pipeline(load_features(db),settings)
    start=pd.Timestamp(model['settings']['detection_start'])
    diagnostic=result.copy()
    common_history=common.copy()
    result=result.loc[result.date.ge(start)].copy()
    common=common.loc[common.date.ge(start)].copy()
    with closing(sqlite3.connect(db)) as con,con:
        con.execute('PRAGMA foreign_keys=ON');con.executescript(SCHEMA)
        # Existing model baseline/config cannot silently change when future data arrive.
        old=con.execute('SELECT model_version FROM a2_age_model').fetchall()
        if old and model['model_version'] not in [r[0] for r in old]:
            raise ValueError('Existing age baseline/settings changed; explicit version migration required')
        result=add_context(con,result,model['model_version'])
        saved=commit(con,result,common,model)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    calibration.to_csv(output/'age_detection_calibration.csv',index=False,encoding='utf-8-sig')
    diagnostic.to_csv(output/'age_detection_score_history.csv',index=False,encoding='utf-8-sig')
    (output/'age_detection_model.json').write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8')
    export(db,output)
    signal_columns=['date','행정동코드','행정동','age_band','assessment_status','communication_signal','mobility_signal','combined_signal','isolation_related_candidate','signal_status','evidence_level','interest_support','distance_support','review_reasons','context_period','a1_cluster_type']
    signal_columns=[col for col in signal_columns if col in result]
    result.loc[result.any_signal.fillna(False),signal_columns].sort_values(['date','행정동코드','age_band']).to_csv(output/'age_detection_signal_list.csv',index=False,encoding='utf-8-sig')
    result.loc[result.review_reasons.ne(''),signal_columns].sort_values(['date','행정동코드','age_band']).to_csv(output/'age_detection_quality_review.csv',index=False,encoding='utf-8-sig')
    summary=build_summary(result)
    summary.to_csv(output/'age_detection_monthly_summary.csv',index=False,encoding='utf-8-sig')
    sensitivity=[]
    for threshold in [-2.0,-2.5,-3.0,-4.0]:
        modified=calibration.copy();modified['threshold']=threshold
        scores=diagnostic.assign(_area=diagnostic['행정동코드'].astype(str))
        f,_=detect(scores,common_history,modified,model['settings']); f=f.loc[f.date.le(pd.Timestamp(model['settings']['baseline_end'])) & f.date.ge(pd.Timestamp('2023-02-01'))]
        sensitivity.append({'threshold':threshold,'baseline_fully_assessed_rows':int(f.assessment_status.eq('assessed').sum()),'baseline_partially_assessed_rows':int(f.assessment_status.eq('partially_assessed').sum()),'baseline_any_signal_rows':int(f.any_signal.fillna(False).sum()),'baseline_joint_signal_rows':int(f.combined_signal.fillna(False).sum()),'note':'baseline screening frequency, not false positives or accuracy'})
    pd.DataFrame(sensitivity).to_csv(output/'age_detection_baseline_sensitivity.csv',index=False,encoding='utf-8-sig')
    print(json.dumps({'model_version':model['model_version'],'rows':len(result),'saved_rows':saved,'joint_candidates':int(result.combined_signal.fillna(False).sum()),'partially_assessed':int(result.assessment_status.eq('partially_assessed').sum()),'deferred':int(result.assessment_status.eq('deferred').sum())},ensure_ascii=False),flush=True)
    return result,common,model


def build_summary(result):
    return result.groupby(['date','age_band'],as_index=False).agg(
        rows=('행정동코드','size'), assessed=('assessment_status',lambda x:int(x.eq('assessed').sum())),
        partially_assessed=('assessment_status',lambda x:int(x.eq('partially_assessed').sum())),
        deferred=('assessment_status',lambda x:int(x.eq('deferred').sum())),
        communication_signals=('communication_signal',lambda x:int(x.fillna(False).sum())),
        mobility_signals=('mobility_signal',lambda x:int(x.fillna(False).sum())),
        joint_candidates=('combined_signal',lambda x:int(x.fillna(False).sum())),
        joint_with_support=('evidence_level',lambda x:int(x.eq('joint_candidate_with_supporting_evidence').sum())))


def main():
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',default=str(root/'outputs/db1.sqlite'))
    parser.add_argument('--output',default=str(root/'Analysis2/outputs/age_detection'))
    parser.add_argument('--settings',help='Optional JSON settings; changes require explicit model migration after first run')
    parser.add_argument('--export-only',action='store_true')
    a=parser.parse_args()
    if a.export_only: export(a.db,a.output)
    else: run(a.db,a.output,json.loads(Path(a.settings).read_text(encoding='utf-8')) if a.settings else None)


if __name__=='__main__': main()

"""Transactional, period-aware storage shared by the two analysis workers."""
from pathlib import Path
import hashlib
import json
import sqlite3
import pandas as pd

BASELINE_VERSION = "analysis1_2025H2"

SCHEMA = """
CREATE TABLE IF NOT EXISTS db1_run (
 analysis TEXT NOT NULL, period TEXT NOT NULL, fingerprint TEXT NOT NULL,
 model_version TEXT NOT NULL, metadata_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(analysis,period));
CREATE TABLE IF NOT EXISTS a1_input (
 adm_cd TEXT NOT NULL, period TEXT NOT NULL, input_json TEXT NOT NULL,
 PRIMARY KEY(adm_cd,period));
CREATE TABLE IF NOT EXISTS a1_context (
 adm_cd TEXT NOT NULL, period TEXT NOT NULL, adm_nm TEXT NOT NULL,
 effective_from TEXT NOT NULL, model_version TEXT NOT NULL,
 cluster INTEGER NOT NULL, cluster_type TEXT NOT NULL, feature_json TEXT NOT NULL,
 PRIMARY KEY(adm_cd,period));
CREATE TABLE IF NOT EXISTS a2_feature (
 adm_cd TEXT NOT NULL, date TEXT NOT NULL, adm_nm TEXT NOT NULL,
 is_initial INTEGER NOT NULL, feature_json TEXT NOT NULL, PRIMARY KEY(adm_cd,date));
CREATE TABLE IF NOT EXISTS a2_detection (
 adm_cd TEXT NOT NULL, date TEXT NOT NULL, context_period TEXT NOT NULL,
 model_version TEXT NOT NULL, any_signal INTEGER NOT NULL,
 communication_signal INTEGER NOT NULL, mobility_signal INTEGER NOT NULL,
 combined_signal INTEGER NOT NULL, signal_status TEXT, result_json TEXT NOT NULL,
 PRIMARY KEY(adm_cd,date), FOREIGN KEY(adm_cd,date) REFERENCES a2_feature(adm_cd,date),
 FOREIGN KEY(adm_cd,context_period) REFERENCES a1_context(adm_cd,period));
CREATE TABLE IF NOT EXISTS a2_evidence (
 adm_cd TEXT NOT NULL,date TEXT NOT NULL,evidence_json TEXT NOT NULL,
 PRIMARY KEY(adm_cd,date), FOREIGN KEY(adm_cd,date) REFERENCES a2_detection(adm_cd,date));
CREATE INDEX IF NOT EXISTS idx_a1_effective ON a1_context(effective_from);
CREATE VIEW IF NOT EXISTS v_db1_integrated AS
 SELECT d.date,d.adm_cd,c.adm_nm,d.any_signal,d.communication_signal,
 d.mobility_signal,d.combined_signal,d.signal_status,d.context_period,
 d.model_version,c.cluster AS a1_cluster,c.cluster_type AS a1_cluster_type,
 c.feature_json AS a1_features,d.result_json AS a2_result,e.evidence_json AS a2_evidence,
 x.cluster_changed AS a1_cluster_changed,
 x.activity_domain_delta,x.time_domain_delta,x.demographic_domain_delta,x.structural_domain_delta
 FROM a2_detection d JOIN a1_context c ON c.adm_cd=d.adm_cd AND c.period=d.context_period
 LEFT JOIN a2_evidence e ON e.adm_cd=d.adm_cd AND e.date=d.date
 LEFT JOIN a1_change_detection x ON x.adm_cd=d.adm_cd AND x.current_period=d.context_period;
"""


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=60)
    con.execute("PRAGMA foreign_keys=ON")
    return con


def initialize(path):
    with connect(path) as con:
        con.executescript((Path(__file__).parent / "Analysis1/db/schema.sql").read_text(encoding="utf-8"))
        con.executescript(SCHEMA)


def records(frame):
    # Preserve Python float round trips; pandas JSON decimal rounding can alter History.
    rows=frame.astype(object).where(pd.notna(frame),None).to_dict(orient='records')
    for row in rows:
        for key,value in row.items():
            if isinstance(value,pd.Timestamp): row[key]=value.isoformat()
            elif hasattr(value,'item'): row[key]=value.item()
    return rows


def payload(row):
    return json.dumps(row, ensure_ascii=False, allow_nan=False, sort_keys=True)


def fingerprint(frame, keys):
    ordered = frame.sort_values(keys).reset_index(drop=True)
    return hashlib.sha256(payload(records(ordered)).encode()).hexdigest()


def already_processed(con, analysis, period, digest):
    found = con.execute("SELECT fingerprint FROM db1_run WHERE analysis=? AND period=?", (analysis,period)).fetchone()
    if not found:
        return False
    if found[0] != digest:
        raise ValueError(f"{analysis} {period}: already stored with different data; automatic overwrite blocked")
    return True


def history(con):
    rows = con.execute("SELECT feature_json FROM a2_feature ORDER BY date,adm_cd").fetchall()
    df = pd.DataFrame([json.loads(r[0]) for r in rows])
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def context_for(con, date):
    selected = con.execute("SELECT period FROM a1_context WHERE effective_from<=? GROUP BY period ORDER BY MAX(effective_from) DESC LIMIT 1", (str(pd.Timestamp(date).date()),)).fetchone()
    if selected is None:
        raise ValueError(f"No applicable Analysis1 Context for {date}")
    period = selected[0]
    rows = con.execute("SELECT adm_cd,adm_nm,cluster,cluster_type,model_version FROM a1_context WHERE period=?", (period,)).fetchall()
    return period, pd.DataFrame(rows, columns=["adm_cd","dong_name","cluster","cluster_type","model_version"])


def commit_a1(path, input_df, features, clusters, period, effective_from, baseline, change=None, metadata=None):
    digest = fingerprint(input_df, ["adm_cd"])
    initialize(path)
    with connect(path) as con:
        con.execute("BEGIN IMMEDIATE")
        if already_processed(con,"analysis1",period,digest):
            return False
        if len(input_df)!=22 or len(features)!=22 or len(clusters)!=22:
            raise ValueError("Analysis1 requires 22 complete rows")
        features = features.copy()
        features["adm_cd"] = features.adm_cd.astype(str)
        by_code = {str(r["adm_cd"]): r for r in records(features)}
        for row in records(input_df):
            con.execute("INSERT INTO a1_input VALUES(?,?,?)", (str(row["adm_cd"]),period,payload(row)))
        for row in records(clusters):
            code = str(row["adm_cd"])
            f = by_code[code]
            con.execute("INSERT INTO a1_context VALUES(?,?,?,?,?,?,?,?)",(code,period,row["dong_name"],effective_from,BASELINE_VERSION,int(row["cluster"]),row["cluster_type"],payload(f)))
            if baseline:
                con.execute("INSERT INTO a1_region_baseline(adm_cd,adm_nm,baseline_period,cluster_id,cluster_label,centroid_distance) VALUES(?,?,?,?,?,?) ON CONFLICT(adm_cd,baseline_period) DO UPDATE SET adm_nm=excluded.adm_nm,cluster_id=excluded.cluster_id,cluster_label=excluded.cluster_label,centroid_distance=excluded.centroid_distance",(code,row["dong_name"],period,int(row["cluster"]),row["cluster_type"],row.get("centroid_distance")))
            for name, domain in (metadata or {})["feature_domains"].items():
                con.execute("INSERT INTO a1_region_feature(adm_cd,adm_nm,period,feature_name,domain,feature_value,is_baseline) VALUES(?,?,?,?,?,?,?) ON CONFLICT(adm_cd,period,feature_name) DO UPDATE SET feature_value=excluded.feature_value",(code,row["dong_name"],period,name,domain,float(f[name]),int(baseline)))
        if change is not None:
            for row in records(change):
                code = str(row["adm_cd"])
                con.execute("INSERT INTO a1_change_detection(adm_cd,adm_nm,baseline_period,current_period,baseline_cluster_id,current_cluster_id,baseline_cluster_label,current_cluster_label,cluster_changed,centroid_distance,centroid_distance_delta,activity_domain_delta,time_domain_delta,demographic_domain_delta,structural_domain_delta) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(code,row["dong_name"],"2025H2",period,int(row["baseline_cluster"]),int(row["current_cluster"]),row["baseline_cluster_type"],row["current_cluster_type"],int(row["cluster_changed"]),row["current_centroid_distance"],row["centroid_distance_delta"],row["activity_distance_from_baseline"],row["life_activity_distance_from_baseline"],row["population_household_distance_from_baseline"],row["structural_welfare_distance_from_baseline"]))
                for name, domain in metadata["feature_domains"].items():
                    current = float(by_code[code][name])
                    delta = float(row["delta_"+name])
                    original = current-delta
                    con.execute("INSERT INTO a1_change_feature VALUES(?,?,?,?,?,?,?,?)",(code,period,name,domain,original,current,delta,None if original==0 else delta/original))
        con.execute("INSERT INTO db1_run(analysis,period,fingerprint,model_version,metadata_json) VALUES(?,?,?,?,?)",("analysis1",period,digest,BASELINE_VERSION,payload(metadata or {})))
    return True


def seed_history(path, initial):
    initialize(path)
    with connect(path) as con:
        con.execute("BEGIN IMMEDIATE")
        stored = con.execute("SELECT COUNT(*) FROM a2_feature").fetchone()[0]
        if stored:
            return
        if len(initial)!=924 or pd.to_datetime(initial.date).max()!=pd.Timestamp("2025-06-01"):
            raise ValueError("Initial History must be 2022-01..2025-06, 924 rows")
        for row in records(initial):
            date = str(pd.Timestamp(row["date"]).date())
            con.execute("INSERT INTO a2_feature VALUES(?,?,?,?,?)",(str(row["행정동코드"]),date,row["행정동"],1,payload(row)))


def commit_a2(path, current, result, evidence, context_period, metadata=None):
    period = str(pd.to_datetime(current.date).iloc[0].date())
    digest = fingerprint(current,["date","행정동코드"])
    with connect(path) as con:
        con.execute("BEGIN IMMEDIATE")
        if already_processed(con,"analysis2",period,digest):
            return False
        last = con.execute("SELECT MAX(date) FROM a2_feature").fetchone()[0]
        expected = (pd.Timestamp(last).to_period("M")+1).to_timestamp()
        if pd.Timestamp(period)!=expected:
            raise ValueError(f"Expected next month {expected:%Y-%m}; concurrent or out-of-order update blocked")
        if len(result)!=22 or result[["cluster","cluster_type"]].isna().any().any():
            raise ValueError("Incomplete detection/Context; update aborted")
        if set(result['행정동코드'].astype(str))!=set(current['행정동코드'].astype(str)) or not pd.to_datetime(result.date).eq(pd.Timestamp(period)).all():
            raise ValueError('Detection keys/dates differ from current Feature')
        for row in records(current):
            con.execute("INSERT INTO a2_feature VALUES(?,?,?,?,?)",(str(row["행정동코드"]),period,row["행정동"],0,payload(row)))
        for row in records(result):
            con.execute("INSERT INTO a2_detection VALUES(?,?,?,?,?,?,?,?,?,?)",(str(row["행정동코드"]),period,context_period,BASELINE_VERSION,int(row["any_signal"]),int(row["communication_signal"]),int(row["mobility_signal"]),int(row["combined_signal"]),row["signal_status"],payload(row)))
        for row in records(evidence):
            con.execute("INSERT INTO a2_evidence VALUES(?,?,?)",(str(row["행정동코드"]),period,payload(row)))
        con.execute("INSERT INTO db1_run(analysis,period,fingerprint,model_version,metadata_json) VALUES(?,?,?,?,?)",("analysis2",period,digest,BASELINE_VERSION,payload(metadata or {})))
    return True


def export_csv(path, directory, analysis2_directory=None):
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    a2_directory=Path(analysis2_directory) if analysis2_directory else Path(__file__).resolve().parent/'Analysis2/outputs'
    a2_directory.mkdir(parents=True,exist_ok=True)
    def write(frame,target):
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_suffix(target.suffix+'.tmp')
        frame.to_csv(temporary,index=False,encoding='utf-8-sig',date_format='%Y-%m-%d')
        temporary.replace(target)
    with connect(path) as con:
        h=history(con)
        write(h,a2_directory/'history.csv')
        write(pd.read_sql_query('SELECT * FROM v_db1_integrated ORDER BY date,adm_cd',con),directory/'db1_integrated.csv')
        detections=pd.DataFrame([json.loads(r[0]) for r in con.execute('SELECT result_json FROM a2_detection ORDER BY date,adm_cd')])
        evidence=pd.DataFrame([json.loads(r[0]) for r in con.execute('SELECT evidence_json FROM a2_evidence ORDER BY date,adm_cd')])
        write(detections,a2_directory/'detection.csv')
        write(evidence,a2_directory/'evidence.csv')
        if not detections.empty:
            for month,g in detections.groupby(pd.to_datetime(detections.date).dt.strftime('%Y-%m')):
                write(g,a2_directory/'monthly'/month/'detection.csv')
                write(h[pd.to_datetime(h.date).dt.strftime('%Y-%m').eq(month)],a2_directory/'monthly'/month/'features.csv')

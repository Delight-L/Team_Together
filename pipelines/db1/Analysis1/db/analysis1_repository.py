from __future__ import annotations
from pathlib import Path as _DatabasePath
import sys as _database_sys
_database_sys.path.insert(0, str(next(p for p in _DatabasePath(__file__).resolve().parents if (p/'pipelines/db1').is_dir())))
from pipelines.db1 import database
from pathlib import Path
import pandas as pd

class Analysis1Repository:
    def __init__(self, db_path):
        self.db_path = database.workspace(db_path)

    def connect(self):
        con = database.connect(self.db_path)
        con.execute('SET CONSTRAINTS ALL IMMEDIATE;')
        return con

    def initialize(self, schema_path=None):
        schema_path = Path(schema_path) if schema_path else Path(__file__).with_name("schema.sql")
        database.ensure_workspace(self.db_path)
        with self.connect() as con:
            con.executescript(schema_path.read_text(encoding="utf-8"))

    def upsert_baseline(self, df: pd.DataFrame):
        cols = ["adm_cd","adm_nm","baseline_period","cluster_id","cluster_label","pca1","pca2","centroid_distance"]
        rows = df[cols].where(pd.notna(df[cols]), None).itertuples(index=False, name=None)
        sql = 'INSERT INTO a1_region_baseline\n        (adm_cd,adm_nm,baseline_period,cluster_id,cluster_label,pca1,pca2,centroid_distance)\n        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (adm_cd,baseline_period) DO UPDATE SET "adm_nm"=excluded."adm_nm","cluster_id"=excluded."cluster_id","cluster_label"=excluded."cluster_label","pca1"=excluded."pca1","pca2"=excluded."pca2","centroid_distance"=excluded."centroid_distance"'
        with self.connect() as con:
            con.executemany(sql, list(rows))

    def upsert_features(self, df: pd.DataFrame):
        cols = ["adm_cd","adm_nm","period","feature_name","domain","feature_value","is_baseline"]
        rows = df[cols].itertuples(index=False, name=None)
        sql = 'INSERT INTO a1_region_feature\n        (adm_cd,adm_nm,period,feature_name,domain,feature_value,is_baseline)\n        VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (adm_cd,period,feature_name) DO UPDATE SET "adm_nm"=excluded."adm_nm","domain"=excluded."domain","feature_value"=excluded."feature_value","is_baseline"=excluded."is_baseline"'
        with self.connect() as con:
            con.executemany(sql, list(rows))

    def upsert_change_detection(self, summary: pd.DataFrame, features: pd.DataFrame):
        s_cols = ["adm_cd","adm_nm","baseline_period","current_period","baseline_cluster_id",
                  "current_cluster_id","baseline_cluster_label","current_cluster_label","cluster_changed",
                  "centroid_distance","centroid_distance_delta","activity_domain_delta","time_domain_delta",
                  "demographic_domain_delta","structural_domain_delta"]
        f_cols = ["adm_cd","current_period","feature_name","domain","baseline_value","current_value","delta","pct_change"]
        with self.connect() as con:
            con.executemany(
                """INSERT INTO a1_change_detection
                (adm_cd,adm_nm,baseline_period,current_period,baseline_cluster_id,current_cluster_id,
                 baseline_cluster_label,current_cluster_label,cluster_changed,centroid_distance,
                 centroid_distance_delta,activity_domain_delta,time_domain_delta,demographic_domain_delta,
                 structural_domain_delta) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (adm_cd,current_period) DO UPDATE SET \"adm_nm\"=excluded.\"adm_nm\",\"baseline_period\"=excluded.\"baseline_period\",\"baseline_cluster_id\"=excluded.\"baseline_cluster_id\",\"current_cluster_id\"=excluded.\"current_cluster_id\",\"baseline_cluster_label\"=excluded.\"baseline_cluster_label\",\"current_cluster_label\"=excluded.\"current_cluster_label\",\"cluster_changed\"=excluded.\"cluster_changed\",\"centroid_distance\"=excluded.\"centroid_distance\",\"centroid_distance_delta\"=excluded.\"centroid_distance_delta\",\"activity_domain_delta\"=excluded.\"activity_domain_delta\",\"time_domain_delta\"=excluded.\"time_domain_delta\",\"demographic_domain_delta\"=excluded.\"demographic_domain_delta\",\"structural_domain_delta\"=excluded.\"structural_domain_delta\"""",
                list(summary[s_cols].where(pd.notna(summary[s_cols]), None).itertuples(index=False, name=None))
            )
            con.executemany(
                'INSERT INTO a1_change_feature\n                (adm_cd,current_period,feature_name,domain,baseline_value,current_value,delta,pct_change)\n                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (adm_cd,current_period,feature_name) DO UPDATE SET "domain"=excluded."domain","baseline_value"=excluded."baseline_value","current_value"=excluded."current_value","delta"=excluded."delta","pct_change"=excluded."pct_change"',
                list(features[f_cols].where(pd.notna(features[f_cols]), None).itertuples(index=False, name=None))
            )

    def table_count(self, table):
        with self.connect() as con:
            return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

from __future__ import annotations
import sqlite3
from pathlib import Path
import pandas as pd

class Analysis1Repository:
    def __init__(self, db_path):
        self.db_path = Path(db_path)

    def connect(self):
        con = sqlite3.connect(self.db_path)
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def initialize(self, schema_path=None):
        schema_path = Path(schema_path) if schema_path else Path(__file__).with_name("schema.sql")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript(schema_path.read_text(encoding="utf-8"))

    def upsert_baseline(self, df: pd.DataFrame):
        cols = ["adm_cd","adm_nm","baseline_period","cluster_id","cluster_label","pca1","pca2","centroid_distance"]
        rows = df[cols].where(pd.notna(df[cols]), None).itertuples(index=False, name=None)
        sql = """INSERT OR REPLACE INTO a1_region_baseline
        (adm_cd,adm_nm,baseline_period,cluster_id,cluster_label,pca1,pca2,centroid_distance)
        VALUES (?,?,?,?,?,?,?,?)"""
        with self.connect() as con:
            con.executemany(sql, list(rows))

    def upsert_features(self, df: pd.DataFrame):
        cols = ["adm_cd","adm_nm","period","feature_name","domain","feature_value","is_baseline"]
        rows = df[cols].itertuples(index=False, name=None)
        sql = """INSERT OR REPLACE INTO a1_region_feature
        (adm_cd,adm_nm,period,feature_name,domain,feature_value,is_baseline)
        VALUES (?,?,?,?,?,?,?)"""
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
                """INSERT OR REPLACE INTO a1_change_detection
                (adm_cd,adm_nm,baseline_period,current_period,baseline_cluster_id,current_cluster_id,
                 baseline_cluster_label,current_cluster_label,cluster_changed,centroid_distance,
                 centroid_distance_delta,activity_domain_delta,time_domain_delta,demographic_domain_delta,
                 structural_domain_delta) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                list(summary[s_cols].where(pd.notna(summary[s_cols]), None).itertuples(index=False, name=None))
            )
            con.executemany(
                """INSERT OR REPLACE INTO a1_change_feature
                (adm_cd,current_period,feature_name,domain,baseline_value,current_value,delta,pct_change)
                VALUES (?,?,?,?,?,?,?,?)""",
                list(features[f_cols].where(pd.notna(features[f_cols]), None).itertuples(index=False, name=None))
            )

    def table_count(self, table):
        with self.connect() as con:
            return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

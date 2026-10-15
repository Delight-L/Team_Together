"""Migrate the approved 2025H2 regional typology to the elder-v2 feature set.

The migration deliberately preserves ``disability_ratio`` in the stored raw
regional background, but removes it from the K-means feature vector.  It is
replaced by ``elderly_living_alone_rate_65plus``.  A SQLite backup is made
before any mutation and the migration refuses to run if the approved model
would alter the 22 baseline cluster assignments.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "DB1"))
sys.path.insert(0, str(ROOT / "DB1" / "Analysis1"))

import db1_store as store
from analysis.change_detector import detect_changes
from common.config import CONFIG


MODEL_VERSION = "analysis1_2025H2_elder_v2"
PERIOD = "2025H2"


def _payload(row: dict) -> str:
    return json.dumps(row, ensure_ascii=False, allow_nan=False, sort_keys=True)


def _records(frame: pd.DataFrame) -> list[dict]:
    rows = frame.astype(object).where(pd.notna(frame), None).to_dict(orient="records")
    for row in rows:
        for key, value in row.items():
            if hasattr(value, "item"):
                row[key] = value.item()
    return rows


def migrate(db_path: Path, model_path: Path, *, apply: bool) -> dict:
    source = ROOT / "DB1" / "Analysis1" / "data" / "reference" / "reference_pca_input_2025H2.csv"
    frame = pd.read_csv(source, dtype={"adm_cd": str})
    # Keep the exact processed-input fingerprint separate from display-only
    # fields added below. The startup worker reads this source CSV verbatim.
    model_input_frame = frame.copy()
    model = joblib.load(model_path)

    with sqlite3.connect(db_path) as con:
        existing = {
            str(code): json.loads(raw)
            for code, raw in con.execute("SELECT adm_cd,input_json FROM a1_input WHERE period=?", (PERIOD,))
        }
        old_clusters = {
            str(code): int(cluster)
            for code, cluster in con.execute("SELECT adm_cd,cluster FROM a1_context WHERE period=?", (PERIOD,))
        }

    if len(existing) != 22 or len(old_clusters) != 22:
        raise ValueError("Expected a complete 22-dong 2025H2 baseline before migration.")

    # Keep disability as a display-only regional background value if it was in
    # v16's original input. It is not a model feature in elder-v2.
    frame["disability_ratio"] = frame["adm_cd"].map(
        lambda code: existing[str(code)].get("disability_ratio")
    )
    if frame["disability_ratio"].isna().any():
        raise ValueError("Cannot preserve display-only disability ratios from the existing baseline.")

    features, balanced, changes = detect_changes(frame, model, PERIOD)
    new_clusters = dict(zip(features.adm_cd.astype(str), changes.current_cluster.astype(int)))
    if old_clusters != new_clusters:
        raise ValueError("Elder-v2 would change baseline cluster assignments; review is required.")
    if changes.filter(like="delta_").abs().to_numpy().max() > 1e-10:
        raise ValueError("Elder-v2 does not reproduce its approved reference features.")

    clusters = features[["adm_cd", "dong_name"]].copy()
    clusters["cluster"] = changes.current_cluster.astype(int)
    clusters["cluster_type"] = changes.current_cluster_type
    clusters["centroid_distance"] = np.linalg.norm(
        balanced.to_numpy() - model["kmeans"].cluster_centers_[clusters.cluster.to_numpy()], axis=1
    )
    summary = {
        "model_version": MODEL_VERSION,
        "rows": len(frame),
        "cluster_assignments_unchanged": True,
        "features": [f for columns in CONFIG.domains.values() for f in columns],
        "display_only_background": ["disability_ratio"],
    }
    if not apply:
        return {"dry_run": True, **summary}

    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / f"db1_before_analysis1_elder_v2_{datetime.now():%Y%m%d_%H%M%S}.sqlite"
    with sqlite3.connect(db_path) as source_con, sqlite3.connect(backup) as backup_con:
        source_con.backup(backup_con)

    model_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
    feature_domains = {feature: domain for domain, columns in CONFIG.domains.items() for feature in columns}
    raw_by_code = {str(row["adm_cd"]): row for row in _records(frame)}
    feature_by_code = {str(row["adm_cd"]): row for row in _records(features)}
    cluster_by_code = {str(row["adm_cd"]): row for row in _records(clusters)}

    with sqlite3.connect(db_path) as con:
        con.execute("PRAGMA foreign_keys=ON")
        with con:
            for code, raw in raw_by_code.items():
                current = cluster_by_code[code]
                feature = feature_by_code[code]
                con.execute("UPDATE a1_input SET input_json=? WHERE adm_cd=? AND period=?", (_payload(raw), code, PERIOD))
                con.execute(
                    "UPDATE a1_context SET model_version=?,cluster=?,cluster_type=?,feature_json=? WHERE adm_cd=? AND period=?",
                    (MODEL_VERSION, current["cluster"], current["cluster_type"], _payload(feature), code, PERIOD),
                )
                con.execute(
                    "UPDATE a1_region_baseline SET cluster_id=?,cluster_label=?,centroid_distance=? WHERE adm_cd=? AND baseline_period=?",
                    (current["cluster"], current["cluster_type"], current["centroid_distance"], code, PERIOD),
                )
            con.execute("DELETE FROM a1_region_feature WHERE period=?", (PERIOD,))
            for code, feature in feature_by_code.items():
                for name, domain in feature_domains.items():
                    con.execute(
                        "INSERT INTO a1_region_feature(adm_cd,adm_nm,period,feature_name,domain,feature_value,is_baseline) VALUES(?,?,?,?,?,?,1)",
                        (code, feature["dong_name"], PERIOD, name, domain, float(feature[name])),
                    )
            old_meta = con.execute("SELECT metadata_json FROM db1_run WHERE analysis='analysis1' AND period=?", (PERIOD,)).fetchone()
            metadata = json.loads(old_meta[0]) if old_meta else {}
            metadata.update({
                "feature_domains": feature_domains,
                "model_sha256": model_sha,
                "model_file": "Analysis1/models/2025H2_elder_v2/analysis1_baseline_2025H2.joblib",
                "model_version": MODEL_VERSION,
                "migration": "elder-v2: disability display-only; elderly living-alone rate used for clustering",
            })
            con.execute(
                "UPDATE db1_run SET fingerprint=?,model_version=?,metadata_json=? WHERE analysis='analysis1' AND period=?",
                (store.fingerprint(model_input_frame, ["adm_cd"]), MODEL_VERSION, _payload(metadata), PERIOD),
            )
    return {"backup": str(backup), **summary}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "outputs" / "db1.sqlite"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    model = ROOT / "DB1" / "Analysis1" / "models" / "2025H2_elder_v2" / "analysis1_baseline_2025H2.joblib"
    print(json.dumps(migrate(Path(args.db), model, apply=args.apply), ensure_ascii=False, indent=2))

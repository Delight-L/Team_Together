PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS a1_region_baseline (
    adm_cd TEXT NOT NULL,
    adm_nm TEXT NOT NULL,
    baseline_period TEXT NOT NULL,
    cluster_id INTEGER NOT NULL,
    cluster_label TEXT NOT NULL,
    pca1 REAL,
    pca2 REAL,
    centroid_distance REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (adm_cd, baseline_period)
);

CREATE TABLE IF NOT EXISTS a1_region_feature (
    adm_cd TEXT NOT NULL,
    adm_nm TEXT NOT NULL,
    period TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    domain TEXT NOT NULL,
    feature_value REAL NOT NULL,
    is_baseline INTEGER NOT NULL DEFAULT 0 CHECK (is_baseline IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (adm_cd, period, feature_name)
);

CREATE TABLE IF NOT EXISTS a1_change_detection (
    adm_cd TEXT NOT NULL,
    adm_nm TEXT NOT NULL,
    baseline_period TEXT NOT NULL,
    current_period TEXT NOT NULL,
    baseline_cluster_id INTEGER NOT NULL,
    current_cluster_id INTEGER NOT NULL,
    baseline_cluster_label TEXT NOT NULL,
    current_cluster_label TEXT NOT NULL,
    cluster_changed INTEGER NOT NULL CHECK (cluster_changed IN (0,1)),
    centroid_distance REAL,
    centroid_distance_delta REAL,
    activity_domain_delta REAL,
    time_domain_delta REAL,
    demographic_domain_delta REAL,
    structural_domain_delta REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (adm_cd, current_period)
);

CREATE TABLE IF NOT EXISTS a1_change_feature (
    adm_cd TEXT NOT NULL,
    current_period TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    domain TEXT NOT NULL,
    baseline_value REAL NOT NULL,
    current_value REAL NOT NULL,
    delta REAL NOT NULL,
    pct_change REAL,
    PRIMARY KEY (adm_cd, current_period, feature_name),
    FOREIGN KEY (adm_cd, current_period)
        REFERENCES a1_change_detection(adm_cd, current_period)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_a1_baseline_cluster
ON a1_region_baseline(cluster_id);

CREATE INDEX IF NOT EXISTS idx_a1_feature_period_domain
ON a1_region_feature(period, domain);

CREATE INDEX IF NOT EXISTS idx_a1_change_period
ON a1_change_detection(current_period, cluster_changed);

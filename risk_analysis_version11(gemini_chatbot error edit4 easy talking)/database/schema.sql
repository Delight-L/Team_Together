CREATE TABLE IF NOT EXISTS db1.analysis1_region_typology (
    run_id TEXT NOT NULL,
    adm_cd TEXT NOT NULL,
    dong_name TEXT NOT NULL,
    cluster BIGINT,
    cluster_type TEXT,
    payload JSONB NOT NULL,
    source_file TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, adm_cd)
);

CREATE TABLE IF NOT EXISTS db1.analysis2_monthly_features (
    run_id TEXT NOT NULL,
    reference_month DATE NOT NULL,
    admin_dong_code TEXT NOT NULL,
    dong_name TEXT NOT NULL,
    interest_structural_issue BOOLEAN,
    payload JSONB NOT NULL,
    source_file TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, reference_month, admin_dong_code)
);

CREATE TABLE IF NOT EXISTS db1.analysis2_detections (
    run_id TEXT NOT NULL,
    reference_month DATE NOT NULL,
    admin_dong_code TEXT NOT NULL,
    dong_name TEXT NOT NULL,
    communication_signal BOOLEAN NOT NULL DEFAULT FALSE,
    mobility_signal BOOLEAN NOT NULL DEFAULT FALSE,
    combined_signal BOOLEAN NOT NULL DEFAULT FALSE,
    any_signal BOOLEAN NOT NULL DEFAULT FALSE,
    signal_type TEXT,
    payload JSONB NOT NULL,
    source_file TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, reference_month, admin_dong_code)
);

CREATE TABLE IF NOT EXISTS db1.analysis2_evidence_cards (
    run_id TEXT NOT NULL,
    reference_month DATE NOT NULL,
    admin_dong_code TEXT NOT NULL,
    dong_name TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    signal_status TEXT,
    cluster BIGINT,
    cluster_type TEXT,
    payload JSONB NOT NULL,
    source_file TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, reference_month, admin_dong_code, signal_type)
);

CREATE INDEX IF NOT EXISTS analysis2_monthly_features_lookup_idx
    ON db1.analysis2_monthly_features (reference_month DESC, admin_dong_code);
CREATE INDEX IF NOT EXISTS analysis2_detections_signal_idx
    ON db1.analysis2_detections (reference_month DESC, any_signal);
CREATE INDEX IF NOT EXISTS analysis2_evidence_cards_lookup_idx
    ON db1.analysis2_evidence_cards (reference_month DESC, admin_dong_code);

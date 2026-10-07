CREATE SCHEMA IF NOT EXISTS db2;

CREATE TABLE IF NOT EXISTS db2.welfare_collection_runs (
    run_id uuid PRIMARY KEY,
    scope text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status text NOT NULL DEFAULT 'running',
    daily_budget integer NOT NULL,
    request_count integer NOT NULL DEFAULT 0,
    list_count integer NOT NULL DEFAULT 0,
    detail_count integer NOT NULL DEFAULT 0,
    error_count integer NOT NULL DEFAULT 0,
    reported_total integer,
    error_message text
);

CREATE TABLE IF NOT EXISTS db2.welfare_api_daily_usage (
    usage_date date PRIMARY KEY,
    request_count integer NOT NULL CHECK (request_count > 0)
);

CREATE TABLE IF NOT EXISTS db2.local_welfare_services (
    service_id text PRIMARY KEY,
    name text NOT NULL,
    province text,
    district text,
    summary text,
    source_url text,
    source_modified text,
    target_text text,
    eligibility_text text,
    benefit_text text,
    application_text text,
    effective_start date,
    effective_end date,
    list_payload jsonb NOT NULL,
    detail_payload jsonb,
    detail_pending boolean NOT NULL DEFAULT true,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    detail_checked_at timestamptz,
    detail_attempted_at timestamptz,
    detail_error text
);
CREATE INDEX IF NOT EXISTS local_welfare_refresh_idx
    ON db2.local_welfare_services (detail_attempted_at, service_id);

CREATE TABLE IF NOT EXISTS db2.welfare_api_snapshots (
    snapshot_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES db2.welfare_collection_runs(run_id),
    operation text NOT NULL CHECK (operation IN ('list','detail')),
    service_id text,
    collected_at timestamptz NOT NULL DEFAULT now(),
    response_xml text NOT NULL
);
CREATE INDEX IF NOT EXISTS welfare_snapshot_service_idx
    ON db2.welfare_api_snapshots(service_id, collected_at);

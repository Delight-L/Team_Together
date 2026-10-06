from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
from psycopg import sql


BASE_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
REQUIRED_ENV = ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD")


def load_connection_settings(env_path: Path) -> dict[str, str]:
    """Read a local, Git-ignored PostgreSQL environment file."""
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    missing = [key for key in REQUIRED_ENV if not values.get(key)]
    if missing:
        raise ValueError(f"DB 접속 정보 누락: {', '.join(missing)}")
    return values


def _connect(settings: dict[str, str]) -> psycopg.Connection:
    kwargs: dict[str, str] = {
        "host": settings["PGHOST"],
        "port": settings["PGPORT"],
        "dbname": settings["PGDATABASE"],
        "user": settings["PGUSER"],
        "password": settings["PGPASSWORD"],
    }
    if settings.get("PGSSLMODE"):
        kwargs["sslmode"] = settings["PGSSLMODE"]
    return psycopg.connect(**kwargs)


def _json_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _payload(row: pd.Series, excluded: set[str]) -> dict[str, Any]:
    return {
        str(column): _json_value(value)
        for column, value in row.items()
        if str(column) not in excluded
    }


def _bool(value: Any) -> bool:
    return bool(value) if value is not None and not pd.isna(value) else False


def _date(value: Any) -> date:
    return pd.Timestamp(value).date()


def _execute_schema(cursor: psycopg.Cursor) -> None:
    statements = [statement.strip() for statement in SCHEMA_PATH.read_text(encoding="utf-8").split(";")]
    for statement in statements:
        if statement:
            cursor.execute(statement)


def _insert_analysis1_input(cursor: psycopg.Cursor, frame: pd.DataFrame, run_id: str) -> int:
    columns = list(frame.columns)
    statement = sql.SQL("INSERT INTO db1.demo_analysis1_input ({}) VALUES ({})").format(
        sql.SQL(", ").join([sql.Identifier("run_id"), *(sql.Identifier(column) for column in columns)]),
        sql.SQL(", ").join(sql.Placeholder() for _ in range(len(columns) + 1)),
    )
    rows = [
        (run_id, *(_json_value(value) for value in row))
        for row in frame.itertuples(index=False, name=None)
    ]
    cursor.executemany(statement, rows)
    return len(rows)


def _insert_region_typology(cursor: psycopg.Cursor, frame: pd.DataFrame, run_id: str, source_file: str) -> int:
    statement = """
        INSERT INTO db1.analysis1_region_typology
        (run_id, adm_cd, dong_name, cluster, cluster_type, payload, source_file)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
    """
    rows = []
    for _, row in frame.iterrows():
        rows.append((
            run_id, str(row["adm_cd"]), str(row["dong_name"]),
            _json_value(row.get("cluster")), _json_value(row.get("cluster_type")),
            json.dumps(_payload(row, {"adm_cd", "dong_name", "cluster", "cluster_type"}), ensure_ascii=False),
            source_file,
        ))
    cursor.executemany(statement, rows)
    return len(rows)


def _insert_monthly_features(cursor: psycopg.Cursor, frame: pd.DataFrame, run_id: str, source_file: str) -> int:
    statement = """
        INSERT INTO db1.analysis2_monthly_features
        (run_id, reference_month, admin_dong_code, dong_name, interest_structural_issue, payload, source_file)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
    """
    rows = []
    for _, row in frame.iterrows():
        rows.append((
            run_id, _date(row["date"]), str(row["행정동코드"]), str(row["행정동"]),
            _bool(row.get("interest_structural_issue")),
            json.dumps(_payload(row, {"date", "행정동코드", "행정동", "interest_structural_issue"}), ensure_ascii=False),
            source_file,
        ))
    cursor.executemany(statement, rows)
    return len(rows)


def _insert_detections(cursor: psycopg.Cursor, frame: pd.DataFrame, run_id: str, source_file: str) -> int:
    statement = """
        INSERT INTO db1.analysis2_detections
        (run_id, reference_month, admin_dong_code, dong_name, communication_signal, mobility_signal,
         combined_signal, any_signal, signal_type, payload, source_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
    """
    direct = {"date", "행정동코드", "행정동", "communication_signal", "mobility_signal", "combined_signal", "any_signal", "signal_type"}
    rows = []
    for _, row in frame.iterrows():
        rows.append((
            run_id, _date(row["date"]), str(row["행정동코드"]), str(row["행정동"]),
            _bool(row.get("communication_signal")), _bool(row.get("mobility_signal")),
            _bool(row.get("combined_signal")), _bool(row.get("any_signal")), _json_value(row.get("signal_type")),
            json.dumps(_payload(row, direct), ensure_ascii=False), source_file,
        ))
    cursor.executemany(statement, rows)
    return len(rows)


def _insert_evidence_cards(cursor: psycopg.Cursor, frame: pd.DataFrame, run_id: str, source_file: str) -> int:
    statement = """
        INSERT INTO db1.analysis2_evidence_cards
        (run_id, reference_month, admin_dong_code, dong_name, signal_type, signal_status,
         cluster, cluster_type, payload, source_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
    """
    direct = {"date", "행정동코드", "행정동", "signal_type", "signal_status", "cluster", "cluster_type"}
    rows = []
    for _, row in frame.iterrows():
        rows.append((
            run_id, _date(row["date"]), str(row["행정동코드"]), str(row["행정동"]),
            str(row["signal_type"]), _json_value(row.get("signal_status")),
            _json_value(row.get("cluster")), _json_value(row.get("cluster_type")),
            json.dumps(_payload(row, direct), ensure_ascii=False), source_file,
        ))
    cursor.executemany(statement, rows)
    return len(rows)


def persist_current_outputs(env_path: Path) -> dict[str, int | str]:
    """Store the current Analysis1 and Analysis2 CSV outputs in db1."""
    paths = {
        "analysis1_input": BASE_DIR / "preprocessing_agent1" / "outputs" / "analysis1_preprocessed" / "analysis1_input.csv",
        "region_typology": BASE_DIR / "Analysis2" / "reference" / "gangnam_analysis1_final_region_typology_2025H2.csv",
        "monthly_features": BASE_DIR / "Analysis2" / "gangnam_analysis2_feature_table_2022_2025.csv",
        "detections": BASE_DIR / "Analysis2" / "outputs" / "gangnam_analysis2_detection_2022_2025.csv",
        "evidence_cards": BASE_DIR / "Analysis2" / "outputs" / "gangnam_analysis2_evidence_card_2022_2025.csv",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"적재할 결과 파일이 없습니다: {', '.join(missing)}")

    frames = {name: pd.read_csv(path, encoding="utf-8-sig") for name, path in paths.items()}
    run_id = str(uuid.uuid4())
    settings = load_connection_settings(env_path)

    with _connect(settings) as connection, connection.cursor() as cursor:
        _execute_schema(cursor)
        counts = {
            "analysis1_input": _insert_analysis1_input(cursor, frames["analysis1_input"], run_id),
            "region_typology": _insert_region_typology(cursor, frames["region_typology"], run_id, str(paths["region_typology"].name)),
            "monthly_features": _insert_monthly_features(cursor, frames["monthly_features"], run_id, str(paths["monthly_features"].name)),
            "detections": _insert_detections(cursor, frames["detections"], run_id, str(paths["detections"].name)),
            "evidence_cards": _insert_evidence_cards(cursor, frames["evidence_cards"], run_id, str(paths["evidence_cards"].name)),
        }
        for kind, count in counts.items():
            cursor.execute(
                """INSERT INTO db1.demo_ingestions
                   (run_id, kind, source_name, period, row_count, created_at, actor, rule_version)
                   VALUES (%s, %s, %s, %s, %s, NOW()::text, %s, %s)""",
                (run_id, kind, paths[kind].name, "2022-01~2025-12", count, "analysis2_loader", "v11"),
            )
    return {"run_id": run_id, **counts}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analysis1·Analysis2 결과를 team_together PostgreSQL에 저장합니다.")
    parser.add_argument("--env", type=Path, default=BASE_DIR.parent / ".env.team_together")
    args = parser.parse_args()
    print(json.dumps(persist_current_outputs(args.env), ensure_ascii=False, indent=2))

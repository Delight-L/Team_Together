"""보미 복지자료 저장소. Oracle Cloud의 기존 PostgreSQL 연결과 db2를 사용합니다.

적재: python -m backend.db.welfare_chatbot_repository import-json
서버에서는 SELECT만 수행하며 테이블 생성·JSON 적재는 위 명령으로 분리합니다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sqlalchemy import (JSON, Boolean, Column, DateTime, Integer, MetaData, Table,
                        Text, func, select, text)
from sqlalchemy.dialects.postgresql import JSONB, insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

DATA_DIR = Path(__file__).resolve().parents[1] / "chatbot/welfare/data"
SCHEMA = "db2"
metadata = MetaData(schema=SCHEMA)
json_type = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")

datasets = Table(
    "chatbot_policy_datasets", metadata,
    Column("dataset_key", Text, primary_key=True),
    Column("file_name", Text, nullable=False),
    Column("sha256", Text, nullable=False),
    Column("record_count", Integer, nullable=False),
    Column("document_metadata", json_type, nullable=False),
    Column("imported_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
candidates = Table(
    "chatbot_policy_candidates", metadata,
    Column("id", Text, primary_key=True),
    Column("position", Integer, nullable=False),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("category", Text),
    Column("reference_region", Text, nullable=False),
    Column("source_id", Text, nullable=False),
    Column("source_file", Text, nullable=False),
    Column("source_pdf_pages", json_type, nullable=False),
    Column("source_year", Integer),
    Column("information_kind", Text, nullable=False),
    Column("current_operation_verified", Boolean, nullable=False),
    Column("latest_verified_date", Text),
    Column("official_application_url", Text),
    Column("eligible_regions", json_type),
    Column("eligibility_reviewed", Boolean, nullable=False),
    Column("application_details_verified", Boolean, nullable=False),
    Column("import_ready", Boolean, nullable=False),
    Column("notes", Text, nullable=False),
)
plans = Table(
    "chatbot_policy_plans", metadata,
    Column("plan_index", Integer, primary_key=True),
    Column("name", Text, nullable=False),
    Column("target", Text, nullable=False),
    Column("agency", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("procedure", Text, nullable=False),
    Column("source_file", Text, nullable=False),
    Column("source_pages", Text, nullable=False),
    Column("plan_period", Text, nullable=False),
    Column("status", Text, nullable=False),
)
PLAN_FIELDS = {
    "name": "사업명", "target": "대상", "agency": "기관", "description": "지원내용",
    "procedure": "확인절차", "source_file": "출처파일", "source_pages": "PDF페이지",
    "plan_period": "계획기간", "status": "상태",
}
CANDIDATE_FIELDS = tuple(c.name for c in candidates.columns if c.name != "position")


class WelfareDataError(RuntimeError):
    """DB 장애나 적재 누락을 JSON 자료로 숨기지 않고 알립니다."""


def get_engine():
    from backend.db.connection import engine
    return engine


def _upsert(conn, table, rows):
    if not rows:
        return
    insert = pg_insert if conn.dialect.name == "postgresql" else sqlite_insert
    statement = insert(table)
    primary = [c.name for c in table.primary_key]
    statement = statement.on_conflict_do_update(
        index_elements=primary,
        set_={c.name: statement.excluded[c.name] for c in table.columns if c.name not in primary},
    )
    conn.execute(statement, rows)


def _read_json(data_dir):
    result = []
    for key, filename in (("candidates", "policy_candidates.json"),
                          ("plans", "gangnam_policy_plans_2025.json")):
        raw = (Path(data_dir) / filename).read_bytes()
        document = json.loads(raw.decode("utf-8"))
        rows = document["records"] if key == "candidates" else document
        if not isinstance(rows, list) or not rows:
            raise ValueError(filename + ": 자료 목록이 비어 있습니다.")
        if key == "candidates":
            if len({r["id"] for r in rows}) != len(rows):
                raise ValueError(filename + ": 중복 ID가 있습니다.")
            for row in rows:
                if set(row) != set(CANDIDATE_FIELDS):
                    raise ValueError(filename + ": 후보 자료 필드를 확인하세요.")
                if not isinstance(row["source_pdf_pages"], list):
                    raise ValueError(filename + ": 페이지 목록이 필요합니다.")
                for field in ("current_operation_verified", "eligibility_reviewed",
                              "application_details_verified", "import_ready"):
                    if type(row[field]) is not bool:
                        raise ValueError(filename + ": 확인 상태는 true/false여야 합니다.")
            header = {k: v for k, v in document.items() if k != "records"}
        else:
            if any(set(r) != set(PLAN_FIELDS.values()) for r in rows):
                raise ValueError(filename + ": 사업계획 필드를 확인하세요.")
            header = {}
        result.append((dict(dataset_key=key, file_name=filename,
                            sha256=hashlib.sha256(raw).hexdigest(), record_count=len(rows),
                            document_metadata=header), rows))
    return result


def import_json(data_dir=DATA_DIR, *, engine=None):
    """두 JSON을 하나의 트랜잭션으로 적재합니다. 기존 ID는 갱신하고 다른 행은 보존합니다."""
    documents = _read_json(data_dir)  # DB를 변경하기 전에 전체 파일 형식을 검사합니다.
    engine = engine if engine is not None else get_engine()
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(15108348)"))
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS db2"))
        metadata.create_all(conn)
        for header, rows in documents:
            # 반복 적재 시 갱신 시각도 함께 변경합니다.
            header["imported_at"] = conn.execute(select(func.current_timestamp())).scalar_one()
            _upsert(conn, datasets, [header])
            if header["dataset_key"] == "candidates":
                _upsert(conn, candidates, [dict(row, position=i) for i, row in enumerate(rows)])
            else:
                _upsert(conn, plans, [dict(plan_index=i, **{k: row[v] for k, v in PLAN_FIELDS.items()})
                                      for i, row in enumerate(rows)])
        # 배포에서 읽기 전용 계정을 사용해도 이 세 테이블을 조회할 수 있게 합니다.
        if conn.dialect.name == "postgresql" and conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='welfind_reader')")).scalar_one():
            conn.execute(text("GRANT USAGE ON SCHEMA db2 TO welfind_reader"))
            conn.execute(text("GRANT SELECT ON db2.chatbot_policy_datasets, "
                              "db2.chatbot_policy_candidates, db2.chatbot_policy_plans TO welfind_reader"))
    return {header["dataset_key"]: len(rows) for header, rows in documents}


def load_dataset_rows(*, engine=None):
    """JSON과 같은 필드 구조로 DB 행을 읽습니다. 계획 ID는 plan_index로 유지합니다."""
    try:
        engine = engine if engine is not None else get_engine()
        with engine.connect() as conn:
            if conn.dialect.name == "postgresql":
                # 적재 트랜잭션이 중간에 끝나도 두 테이블은 같은 시점의 자료를 읽습니다.
                conn = conn.execution_options(isolation_level="REPEATABLE READ")
            rows = conn.execute(select(candidates).order_by(candidates.c.position, candidates.c.id)).mappings()
            candidate_rows = [{field: row[field] for field in CANDIDATE_FIELDS} for row in rows]
            rows = conn.execute(select(plans).order_by(plans.c.plan_index)).mappings()
            plan_rows = [(row["plan_index"], {v: row[k] for k, v in PLAN_FIELDS.items()}) for row in rows]
    except (SQLAlchemyError, KeyError):
        raise WelfareDataError("복지자료 DB를 읽지 못했습니다. DB 연결과 "
                               "python -m backend.db.welfare_chatbot_repository import-json 적재 여부를 확인하세요.") from None
    if not candidate_rows or not plan_rows:
        raise WelfareDataError("복지자료 DB가 비어 있습니다. JSON 적재 명령을 먼저 실행하세요.")
    return candidate_rows, plan_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["import-json", "check"])
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    try:
        result = import_json(args.data_dir) if args.action == "import-json" else {
            key: len(rows) for key, rows in zip(("candidates", "plans"), load_dataset_rows())}
        print(json.dumps(result, ensure_ascii=False))
    except (SQLAlchemyError, WelfareDataError, KeyError):
        raise SystemExit("복지자료 DB 작업에 실패했습니다. DB 연결·생성 권한·테이블 적재 상태를 확인하세요.") from None


if __name__ == "__main__":
    main()

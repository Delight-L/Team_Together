"""보미 복지자료 저장소. Oracle Cloud의 기존 PostgreSQL 연결과 db2를 사용합니다.

적재: python -m backend.db.welfare_chatbot_repository import-json
서버에서는 SELECT만 수행하며 테이블 생성·JSON 적재는 위 명령으로 분리합니다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    Table,
    Text,
    and_,
    case,
    func,
    literal,
    or_,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from backend.common import get_engine, seoul_now

DATA_DIR = Path(__file__).resolve().parents[1] / "chatbot/welfare/data"
SCHEMA = "db2"
metadata = MetaData(schema=SCHEMA)
json_type = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")

datasets = Table(
    "chatbot_policy_datasets",
    metadata,
    Column("dataset_key", Text, primary_key=True),
    Column("file_name", Text, nullable=False),
    Column("sha256", Text, nullable=False),
    Column("record_count", Integer, nullable=False),
    Column("document_metadata", json_type, nullable=False),
    Column("imported_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
candidates = Table(
    "chatbot_policy_candidates",
    metadata,
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
    "chatbot_policy_plans",
    metadata,
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
    "name": "사업명",
    "target": "대상",
    "agency": "기관",
    "description": "지원내용",
    "procedure": "확인절차",
    "source_file": "출처파일",
    "source_pages": "PDF페이지",
    "plan_period": "계획기간",
    "status": "상태",
}
CANDIDATE_FIELDS = tuple(c.name for c in candidates.columns if c.name != "position")

# 이미 존재하는 DB2 테이블의 조회용 정의입니다. import_json의 create_all에 포함하지 않습니다.
catalog_metadata = MetaData(schema=SCHEMA)
local_services = Table(
    "local_welfare_services",
    catalog_metadata,
    Column("service_id", Text, primary_key=True),
    Column("name", Text),
    *[
        Column(k, Text)
        for k in (
            "province",
            "district",
            "summary",
            "source_url",
            "source_modified",
            "target_text",
            "eligibility_text",
            "benefit_text",
            "application_text",
        )
    ],
    Column("effective_start", Date),
    Column("effective_end", Date),
    Column("detail_pending", Boolean),
    Column("detail_checked_at", DateTime(timezone=True)),
)
regions = Table(
    "regions",
    catalog_metadata,
    Column("region_id", Text, primary_key=True),
    Column("province_name", Text),
    Column("district_name", Text),
)
sources = Table(
    "sources", catalog_metadata, Column("source_id", Text, primary_key=True), Column("name", Text)
)
services = Table(
    "welfare_services",
    catalog_metadata,
    Column("source_id", Text, primary_key=True),
    Column("region_id", Text, primary_key=True),
    Column("external_id", Text, primary_key=True),
    *[
        Column(k, Text)
        for k in (
            "name",
            "summary",
            "target_text",
            "eligibility_text",
            "benefit_text",
            "application_text",
            "period_text",
            "source_url",
            "coverage_scope",
            "residency_text",
            "review_status",
            "source_updated_date",
        )
    ],
    Column("contacts", json_type),
    Column("effective_start", Date),
    Column("effective_end", Date),
    Column("updated_at", DateTime(timezone=True)),
)
programs = Table(
    "programs",
    catalog_metadata,
    Column("source_id", Text, primary_key=True),
    Column("region_id", Text, primary_key=True),
    Column("external_id", Text, primary_key=True),
    Column("name", Text),
    Column("organizer_name", Text),
    Column("description", Text),
    Column("source_url", Text),
)
sessions = Table(
    "program_sessions",
    catalog_metadata,
    *[
        Column(k, Text, primary_key=True)
        for k in ("source_id", "region_id", "program_id", "session_id")
    ],
    *[
        Column(k, Text)
        for k in (
            "session_name",
            "target_text",
            "contact",
            "period_text",
            "application_url",
            "source_url",
            "evidence_status",
            "review_status",
        )
    ],
    *[Column(k, Date) for k in ("application_start", "application_end", "starts_on", "ends_on")],
    Column("last_verified_at", DateTime(timezone=True)),
)
CITY_PROVINCES = {
    "강남구": ("서울특별시", "서울시", "서울"),
    "춘천시": ("강원특별자치도", "강원도"),
    "서울시": ("서울특별시", "서울시", "서울"),
    "서울": ("서울특별시", "서울시", "서울"),
}
REJECTED = ("rejected", "excluded", "invalid", "withdrawn")


def database_id(kind, *parts):
    """출처·지역·사업·회차를 포함해 이름이 같아도 다른 자료는 구분합니다."""
    return "db:" + json.dumps([kind, *parts], ensure_ascii=False, separators=(",", ":"))


def _catalog_queries():
    """대용량 원문 JSON/XML 대신 답변에 필요한 열만 조회합니다."""
    a = local_services.c
    api = select(
        literal("api").label("kind"),
        literal("local").label("source_id"),
        a.service_id.label("external_id"),
        literal("").label("region_id"),
        literal("").label("session_id"),
        a.name,
        a.province,
        a.district,
        a.summary,
        a.target_text,
        a.eligibility_text,
        a.benefit_text,
        a.application_text,
        a.effective_start,
        a.effective_end,
        a.source_url,
        a.source_modified,
        a.detail_pending,
        a.detail_checked_at,
        literal("지자체복지서비스 API").label("source_name"),
    )
    w = services.c
    service = select(
        literal("service").label("kind"),
        w.source_id,
        w.region_id,
        w.external_id,
        literal("").label("session_id"),
        w.name,
        regions.c.province_name.label("province"),
        regions.c.district_name.label("district"),
        w.summary,
        w.target_text,
        w.eligibility_text,
        w.benefit_text,
        w.application_text,
        w.effective_start,
        w.effective_end,
        w.source_url,
        w.source_updated_date.label("source_modified"),
        w.updated_at.label("detail_checked_at"),
        w.contacts,
        w.coverage_scope,
        w.residency_text,
        w.review_status,
        w.period_text,
        func.coalesce(sources.c.name, w.source_id).label("source_name"),
    ).select_from(
        services.outerjoin(regions, w.region_id == regions.c.region_id).outerjoin(
            sources, w.source_id == sources.c.source_id
        )
    )
    s, p = sessions.c, programs.c
    session = select(
        literal("session").label("kind"),
        s.source_id,
        s.region_id,
        s.program_id.label("external_id"),
        s.session_id,
        p.name,
        regions.c.province_name.label("province"),
        regions.c.district_name.label("district"),
        p.description.label("summary"),
        s.target_text,
        p.description.label("benefit_text"),
        p.organizer_name.label("agency"),
        s.contact.label("contacts"),
        s.period_text,
        s.starts_on.label("effective_start"),
        s.ends_on.label("effective_end"),
        s.application_start,
        s.application_end,
        s.review_status,
        s.evidence_status,
        s.session_name,
        func.coalesce(s.source_url, p.source_url).label("source_url"),
        s.application_url,
        s.last_verified_at.label("detail_checked_at"),
        func.coalesce(sources.c.name, s.source_id).label("source_name"),
    ).select_from(
        sessions.join(
            programs,
            and_(
                s.source_id == p.source_id,
                s.region_id == p.region_id,
                s.program_id == p.external_id,
            ),
        )
        .outerjoin(regions, s.region_id == regions.c.region_id)
        .outerjoin(sources, s.source_id == sources.c.source_id)
    )
    return (api.subquery(), service.subquery(), session.subquery())


def _local_scope(province, district, city):
    national = province.in_(("전국", "대한민국"))
    if not city:
        return literal(True)
    if city in ("서울", "서울시"):
        return or_(national, province.in_(CITY_PROVINCES[city]))
    if city in CITY_PROVINCES:
        return or_(
            national,
            and_(
                province.in_(CITY_PROVINCES[city]),
                or_(district == city, func.coalesce(func.trim(district), "").in_(("", "-"))),
            ),
        )
    return or_(national, district == city)


def search_catalog(
    query,
    terms=(),
    *,
    city="",
    include_reference=False,
    include_past=False,
    support_terms=(),
    target_term="",
    name_only=False,
    resource_ids=None,
    limit=80,
    engine=None,
    browse=False,
    offset=0,
):
    """기존 DB2에서 지역·기간·질문에 맞는 자료만 제한된 개수로 조회합니다."""
    if limit < 1 or resource_ids == []:
        return []
    query = re.sub(r"[^가-힣a-zA-Z0-9]", "", query).lower()[:3000]
    terms = sorted({str(t)[:100] for t in terms if t})[:16]
    identities = []
    for value in resource_ids or []:
        try:
            item = json.loads(value[3:]) if value.startswith("db:") else None
            if (
                isinstance(item, list)
                and len(item) in (2, 4, 5)
                and all(isinstance(part, str) for part in item)
            ):
                identities.append(item)
        except (ValueError, TypeError):
            pass
    if resource_ids is not None and not identities:
        return []
    today = seoul_now().date()
    result = []
    try:
        engine = engine if engine is not None else get_engine()
        with engine.connect() as conn:
            for table in _catalog_queries():
                c = table.c
                fields = (
                    [c.name] if name_only else [c.name, c.summary, c.benefit_text, c.target_text]
                )
                body = literal("")
                for field in fields:
                    body = body + " " + func.coalesce(field, "")
                normalized = func.regexp_replace(
                    func.lower(func.coalesce(c.name, "")), "[^가-힣a-z0-9]", "", "g"
                )
                named = and_(func.length(normalized) >= 3, literal(query).contains(normalized))
                score = case((named, 10000), else_=0)
                matches = [named]
                for term in terms:
                    match = body.contains(term, autoescape=True)
                    matches.append(match)
                    score = score + case(
                        (c.name.contains(term, autoescape=True), 4), (match, 1), else_=0
                    )
                statement = select(
                    table, _local_scope(c.province, c.district, city).label("local_scope")
                )
                if resource_ids is not None:
                    keys = []
                    for item in identities:
                        if item[0] == "api" and len(item) == 2:
                            keys.append(and_(c.kind == "api", c.external_id == item[1]))
                        elif item[0] == "service" and len(item) == 4:
                            keys.append(
                                and_(
                                    c.kind == "service",
                                    c.source_id == item[1],
                                    c.region_id == item[2],
                                    c.external_id == item[3],
                                )
                            )
                        elif item[0] == "session" and len(item) == 5:
                            keys.append(
                                and_(
                                    c.kind == "session",
                                    c.source_id == item[1],
                                    c.region_id == item[2],
                                    c.external_id == item[3],
                                    c.session_id == item[4],
                                )
                            )
                    if not keys:
                        continue
                    statement = statement.where(or_(*keys))
                else:
                    if not browse:
                        statement = statement.where(or_(*matches))
                    if not include_reference:
                        statement = statement.where(_local_scope(c.province, c.district, city))
                    if not include_past:
                        statement = statement.where(
                            or_(c.effective_end.is_(None), c.effective_end >= today)
                        )
                        if "application_start" not in c:
                            statement = statement.where(
                                or_(c.effective_start.is_(None), c.effective_start <= today)
                            )
                    if not include_past and "application_end" in c:
                        statement = statement.where(
                            or_(c.application_end.is_(None), c.application_end >= today),
                            or_(c.application_start.is_(None), c.application_start <= today),
                        )
                    if support_terms:
                        support = (
                            func.coalesce(c.name, "") + " " + func.coalesce(c.benefit_text, "")
                        )
                        statement = statement.where(
                            or_(
                                named,
                                *(support.contains(t, autoescape=True) for t in support_terms),
                            )
                        )
                    if target_term:
                        target = func.regexp_replace(body, "[^가-힣a-zA-Z0-9]", "", "g")
                        statement = statement.where(
                            or_(named, target.contains(target_term, autoescape=True))
                        )
                if "coverage_scope" in c:
                    # API 원본과 같은 서비스 ID인 등록 행은 원본 한 건으로 취급합니다.
                    duplicate = (
                        select(local_services.c.service_id)
                        .where(local_services.c.service_id == c.external_id)
                        .exists()
                    )
                    statement = statement.where(or_(c.source_id != "local", ~duplicate))
                if "review_status" in c:
                    statement = statement.where(
                        func.coalesce(c.review_status, "pending").not_in(REJECTED)
                    )
                statement = (
                    statement.order_by(
                        score.desc(),
                        case((_local_scope(c.province, c.district, city), 1), else_=0).desc(),
                        c.name,
                        c.external_id,
                        c.session_id,
                    )
                    .limit(min(limit, 200))
                    .offset(max(0, offset))
                )
                result.extend(dict(row) for row in conn.execute(statement).mappings())
    except (SQLAlchemyError, KeyError):
        raise WelfareDataError(
            "기존 복지 DB2 조회에 실패했습니다. 연결·조회 권한·테이블 구성을 확인하세요."
        ) from None
    return result


def catalog_counts(*, engine=None):
    """대용량 자료를 가져오지 않고 개수만 조회합니다. local API 중복 행은 제외합니다."""
    try:
        engine = engine if engine is not None else get_engine()
        with engine.connect() as conn:
            names = select(candidates.c.name).union_all(select(plans.c.name)).subquery()
            duplicate_api = (
                select(local_services.c.service_id)
                .where(local_services.c.service_id == services.c.external_id)
                .exists()
            )
            return {
                "documents": conn.execute(
                    select(func.count(func.distinct(names.c.name)))
                ).scalar_one(),
                "local_welfare_services": conn.execute(
                    select(func.count()).select_from(local_services)
                ).scalar_one(),
                "welfare_services": conn.execute(
                    select(func.count())
                    .select_from(services)
                    .where(
                        or_(services.c.source_id != "local", ~duplicate_api),
                        func.coalesce(services.c.review_status, "pending").not_in(REJECTED),
                    )
                ).scalar_one(),
                "program_sessions": conn.execute(
                    select(func.count())
                    .select_from(sessions)
                    .where(func.coalesce(sessions.c.review_status, "pending").not_in(REJECTED))
                ).scalar_one(),
            }
    except (SQLAlchemyError, KeyError):
        raise WelfareDataError(
            "복지자료 수를 조회하지 못했습니다. DB 연결과 테이블 구성을 확인하세요."
        ) from None


class WelfareDataError(RuntimeError):
    """DB 장애나 적재 누락을 JSON 자료로 숨기지 않고 알립니다."""


def _upsert(conn, table, rows):
    if not rows:
        return
    insert = pg_insert
    statement = insert(table)
    primary = [c.name for c in table.primary_key]
    statement = statement.on_conflict_do_update(
        index_elements=primary,
        set_={c.name: statement.excluded[c.name] for c in table.columns if c.name not in primary},
    )
    conn.execute(statement, rows)


def _read_json(data_dir):
    result = []
    for key, filename in (
        ("candidates", "policy_candidates.json"),
        ("plans", "gangnam_policy_plans_2025.json"),
    ):
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
                for field in (
                    "current_operation_verified",
                    "eligibility_reviewed",
                    "application_details_verified",
                    "import_ready",
                ):
                    if type(row[field]) is not bool:
                        raise ValueError(filename + ": 확인 상태는 true/false여야 합니다.")
            header = {k: v for k, v in document.items() if k != "records"}
        else:
            if any(set(r) != set(PLAN_FIELDS.values()) for r in rows):
                raise ValueError(filename + ": 사업계획 필드를 확인하세요.")
            header = {}
        result.append(
            (
                dict(
                    dataset_key=key,
                    file_name=filename,
                    sha256=hashlib.sha256(raw).hexdigest(),
                    record_count=len(rows),
                    document_metadata=header,
                ),
                rows,
            )
        )
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
                _upsert(
                    conn,
                    plans,
                    [
                        dict(plan_index=i, **{k: row[v] for k, v in PLAN_FIELDS.items()})
                        for i, row in enumerate(rows)
                    ],
                )
        # 배포에서 읽기 전용 계정을 사용해도 이 세 테이블을 조회할 수 있게 합니다.
        if (
            conn.dialect.name == "postgresql"
            and conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='welfind_reader')")
            ).scalar_one()
        ):
            conn.execute(text("GRANT USAGE ON SCHEMA db2 TO welfind_reader"))
            conn.execute(
                text(
                    "GRANT SELECT ON db2.chatbot_policy_datasets, "
                    "db2.chatbot_policy_candidates, db2.chatbot_policy_plans TO welfind_reader"
                )
            )
    return {header["dataset_key"]: len(rows) for header, rows in documents}


def load_dataset_rows(*, engine=None):
    """JSON과 같은 필드 구조로 DB 행을 읽습니다. 계획 ID는 plan_index로 유지합니다."""
    try:
        engine = engine if engine is not None else get_engine()
        with engine.connect() as conn:
            if conn.dialect.name == "postgresql":
                # 적재 트랜잭션이 중간에 끝나도 두 테이블은 같은 시점의 자료를 읽습니다.
                conn = conn.execution_options(isolation_level="REPEATABLE READ")
            rows = conn.execute(
                select(candidates).order_by(candidates.c.position, candidates.c.id)
            ).mappings()
            candidate_rows = [{field: row[field] for field in CANDIDATE_FIELDS} for row in rows]
            rows = conn.execute(select(plans).order_by(plans.c.plan_index)).mappings()
            plan_rows = [
                (row["plan_index"], {v: row[k] for k, v in PLAN_FIELDS.items()}) for row in rows
            ]
    except (SQLAlchemyError, KeyError):
        raise WelfareDataError(
            "복지자료 DB를 읽지 못했습니다. DB 연결과 "
            "python -m backend.db.welfare_chatbot_repository import-json 적재 여부를 확인하세요."
        ) from None
    if not candidate_rows or not plan_rows:
        raise WelfareDataError("복지자료 DB가 비어 있습니다. JSON 적재 명령을 먼저 실행하세요.")
    return candidate_rows, plan_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["import-json", "check"])
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    try:
        result = (
            import_json(args.data_dir)
            if args.action == "import-json"
            else {key: len(rows) for key, rows in zip(("candidates", "plans"), load_dataset_rows())}
        )
        print(json.dumps(result, ensure_ascii=False))
    except (SQLAlchemyError, WelfareDataError, KeyError):
        raise SystemExit(
            "복지자료 DB 작업에 실패했습니다. DB 연결·생성 권한·테이블 적재 상태를 확인하세요."
        ) from None


if __name__ == "__main__":
    main()

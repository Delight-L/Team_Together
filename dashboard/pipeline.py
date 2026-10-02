"""업로드 검사·분석·DB1 저장. 원본과 분석 결과는 실행 버전별로 보관합니다."""

import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sqlalchemy import inspect, text

from agent.risk_analysis_version1.analyzer import run_risk_analysis
from agent.risk_analysis_version1.data_provider import (
    validate_preprocessed_data,
    resolve_risk_metrics,
)
from agent.risk_analysis_version1.region_context import REGION_CODE_CLUSTER_K3
from agent.risk_analysis_version1.preprocessing_agent.preprocessor import (
    read_csv,
    preprocess_raw_dir,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
SCHEMA = "db1"  # PostgreSQL에서 확인한 실제 스키마 이름입니다.
RULE_VERSION = "risk-analysis-v1"


def get_engine():
    from db_init import engine

    return engine


def now_text():
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


def monthly_upload(content, filename):
    """월별 행동 CSV/XLSX를 검사합니다. 원본 5종 전처리와 다른 입력입니다."""
    if Path(filename).suffix.lower() == ".xlsx":
        data = pd.read_excel(BytesIO(content), dtype={"행정동코드": str})
    else:
        data = None
        for encoding in ["utf-8-sig", "cp949", "euc-kr"]:
            try:
                data = pd.read_csv(
                    BytesIO(content), encoding=encoding, dtype={"행정동코드": str}
                )
                break
            except UnicodeError:
                continue
        if data is None:
            raise ValueError("CSV 한글 인코딩을 읽지 못했습니다.")
    identifiers = ["행정동코드", "행정동명", "기준연월"]
    if all(column in data for column in identifiers):
        for column in identifiers:
            if (
                data[column].isna().any()
                or data[column].astype(str).str.strip().eq("").any()
            ):
                raise ValueError(f"{column}: 빈 값은 사용할 수 없습니다.")
    data = validate_preprocessed_data(data)
    if data.empty or data[["행정동코드", "행정동명", "기준연월"]].isna().any().any():
        raise ValueError("행정동·기준월 값이 비어 있거나 자료가 없습니다.")
    if not data["행정동코드"].isin(REGION_CODE_CLUSTER_K3).all():
        raise ValueError(
            "현재 시연은 강남구 행정동 코드 자료만 지원합니다. 다른 지역 자료는 별도 연결이 필요합니다."
        )
    for _, group in data.groupby("행정동코드"):
        periods = pd.PeriodIndex(sorted(group["기준연월"]), freq="M")
        if len(periods) > 1 and not np.all(np.diff(periods.asi8) == 1):
            raise ValueError("동별 월이 연속되지 않습니다. 빠진 월을 확인하세요.")
    metrics = resolve_risk_metrics(data)
    for metric in metrics:
        values = pd.to_numeric(data[metric.column], errors="raise")
        if not np.isfinite(values).all():
            raise ValueError(f"{metric.column}: 빈 값·무한대는 사용할 수 없습니다.")
        data[metric.column] = values
    data = data[
        ["행정동코드", "행정동명", "기준연월"] + [metric.column for metric in metrics]
    ].copy()
    result = run_risk_analysis(data)
    return {
        "kind": "monthly",
        "source": Path(filename).name,
        "data": data,
        "assessment": result.assessment,
        "signals": result.signals,
        "alerts": result.region_alerts,
        "period": f"{data['기준연월'].min()} ~ {data['기준연월'].max()}",
    }


def structure_upload(raw_dir, source="지역 구조자료 5종"):
    data, profile, report = preprocess_raw_dir(raw_dir)
    return {
        "kind": "structure",
        "source": source,
        "data": data,
        "period": report["period"],
        "report": report,
    }


def append_frame(connection, table, data, run_id):
    saved = data.copy()
    saved.insert(0, "run_id", run_id)
    saved.to_sql(table, connection, schema=SCHEMA, if_exists="append", index=False)


def publish(prepared, actor="admin"):
    """전체 표와 반영 이력을 한 트랜잭션에 저장합니다. 실패하면 모두 롤백합니다."""
    run_id = str(uuid4())
    metadata = pd.DataFrame(
        [
            {
                "run_id": run_id,
                "kind": prepared["kind"],
                "source_name": prepared["source"],
                "period": prepared["period"],
                "row_count": len(prepared["data"]),
                "created_at": now_text(),
                "actor": actor,
                "rule_version": RULE_VERSION,
            }
        ]
    )
    with get_engine().begin() as connection:
        if prepared["kind"] == "monthly":
            append_frame(connection, "demo_monthly_behavior", prepared["data"], run_id)
            append_frame(
                connection, "demo_risk_assessment", prepared["assessment"], run_id
            )
            append_frame(connection, "demo_risk_signals", prepared["signals"], run_id)
            append_frame(connection, "demo_risk_alerts", prepared["alerts"], run_id)
        else:
            append_frame(connection, "demo_analysis1_input", prepared["data"], run_id)
        metadata.to_sql(
            "demo_ingestions",
            connection,
            schema=SCHEMA,
            if_exists="append",
            index=False,
        )
        pd.DataFrame(
            [
                {
                    "created_at": now_text(),
                    "actor": actor,
                    "kind": "데이터",
                    "detail": f"{prepared['source']} 반영 ({len(prepared['data'])}행)",
                    "result": "성공",
                    "run_id": run_id,
                }
            ]
        ).to_sql(
            "demo_activity", connection, schema=SCHEMA, if_exists="append", index=False
        )
    return run_id


def records(data):
    """NaN을 JSON의 null로 바꿉니다."""
    return json.loads(
        data.to_json(
            orient="records", date_format="iso", double_precision=15, force_ascii=False
        )
    )


def load_dashboard_data():
    """최신 반영 버전만 조회하며, 아직 적재 전이면 빈 목록을 반환합니다."""
    result = {
        "connected": False,
        "runs": [],
        "assessment": [],
        "signals": [],
        "alerts": [],
        "activity": [],
    }
    with get_engine().connect() as connection:
        result["connected"] = True
        tables = inspect(connection).get_table_names(schema=SCHEMA)
        if "demo_ingestions" not in tables:
            return result
        runs = pd.read_sql(
            text("SELECT * FROM db1.demo_ingestions ORDER BY created_at DESC"),
            connection,
        )
        result["runs"] = records(runs)
        monthly = runs[runs["kind"] == "monthly"]
        if not monthly.empty:
            run_id = monthly.iloc[0]["run_id"]
            for key, table in [
                ("assessment", "demo_risk_assessment"),
                ("signals", "demo_risk_signals"),
                ("alerts", "demo_risk_alerts"),
            ]:
                frame = pd.read_sql(
                    text(f"SELECT * FROM db1.{table} WHERE run_id=:run_id"),
                    connection,
                    params={"run_id": run_id},
                )
                result[key] = records(frame)
            result["runId"] = run_id
        if "demo_activity" in tables:
            result["activity"] = records(
                pd.read_sql(
                    text(
                        "SELECT * FROM db1.demo_activity ORDER BY created_at DESC LIMIT 100"
                    ),
                    connection,
                )
            )
    return result

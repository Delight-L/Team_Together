"""업로드 검사·분석·DB1 저장. 원본과 분석 결과는 실행 버전별로 보관합니다."""

import json
from copy import deepcopy
from functools import lru_cache
from datetime import datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sqlalchemy import inspect, text

ROOT_DIR = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT_DIR / "agents" / "regional_analysis"
DETECTION_FILE = ANALYSIS_DIR / "Analysis2/outputs/gangnam_analysis2_detection_2022_2025.csv"

from preprocessing.regional_types.preprocessor import preprocess_raw_dir

SCHEMA = "db1"  # PostgreSQL에서 확인한 실제 스키마 이름입니다.
RULE_VERSION = "analysis2-v11"


def get_engine():
    from db.connection import engine

    return engine


def now_text():
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


def monthly_upload(content, filename):
    """Analysis2 탐지 결과 CSV/XLSX를 읽고 화면용 자료로 변환합니다."""
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
    return prepare_analysis2(data, Path(filename).name)


def prepare_analysis2(data, source):
    """version11이 계산한 결과를 화면에서 사용하는 열 이름으로 바꿉니다."""
    required = ["date", "행정동코드", "행정동", "communication_signal", "mobility_signal", "any_signal"]
    metrics = {
        "call_contacts": ("전화 연락", "communication_signal"),
        "text_contacts": ("문자 연락", "communication_signal"),
        "weekday_move_count": ("평일 이동", "mobility_signal"),
        "weekend_move_count": ("휴일 이동", "mobility_signal"),
    }
    for metric in metrics:
        required.extend([metric + "_log_change", metric + "_residual_change", metric + "_residual_change_expanding_rz"])
    missing = [column for column in required if column not in data.columns]
    if missing or data.empty:
        raise ValueError("version11의 Analysis2 탐지 결과 CSV를 사용하세요. 누락 열: " + ", ".join(missing))
    # 문자열 'False'를 bool()로 바꾸면 True가 되므로 명시적으로 검사합니다.
    for column in ["communication_signal", "mobility_signal", "any_signal"]:
        values = data[column].astype(str).str.lower()
        if not values.isin(["true", "false"]).all():
            raise ValueError(column + ": True 또는 False가 필요합니다.")
        data[column] = values.eq("true")
    data["행정동코드"] = data["행정동코드"].astype(str)
    months = pd.to_datetime(data["date"], errors="raise").dt.strftime("%Y-%m")
    if months.isna().any() or data.duplicated(["date", "행정동코드"]).any():
        raise ValueError("날짜가 비어 있거나 동·월 결과가 중복되었습니다.")
    rows = []
    for metric, (label, signal_column) in metrics.items():
        frame = pd.DataFrame()
        frame["행정동코드"] = data["행정동코드"]
        frame["행정동명"] = data["행정동"]
        frame["기준연월"] = months
        frame["metric_label"] = label
        # 브리핑 그래프는 변화율과 같은 CSV의 실제 입력값을 표시합니다.
        # 구버전 업로드에 원자료 열이 없으면 null로 전달하여 값을 만들어내지 않습니다.
        frame["metric_value"] = pd.to_numeric(data[metric], errors="coerce") if metric in data.columns else np.nan
        frame["metric_unit"] = "명" if metric in ("call_contacts", "text_contacts") else "회"
        frame["change_pct"] = np.expm1(pd.to_numeric(data[metric + "_log_change"])) * 100
        frame["relative_change_pp"] = pd.to_numeric(data[metric + "_residual_change"]) * 100
        frame["risk_robust_z"] = pd.to_numeric(data[metric + "_residual_change_expanding_rz"])
        frame["has_enough_history"] = frame["risk_robust_z"].notna()
        frame["is_risk_signal"] = data[signal_column]
        frame["explanation"] = frame["행정동명"] + " " + label + " · Analysis2 탐지 결과"
        frame["context_note"] = "지역 집계자료의 변화이며 개인의 고립 판정이 아닙니다."
        rows.append(frame)
    assessment = pd.concat(rows, ignore_index=True)
    alerts = data.loc[data["any_signal"], ["date", "행정동코드", "행정동"]].copy()
    return {
        "kind": "monthly", "source": source, "data": data,
        "assessment": assessment,
        "signals": assessment[assessment["is_risk_signal"]].copy(),
        "alerts": alerts,
        "period": months.min() + " ~ " + months.max(),
    }


def load_analysis2_data():
    # 캐시 원본은 요청별 수정(지도 추가 등)으로부터 보호합니다.
    return deepcopy(_load_analysis2_data(str(DETECTION_FILE.resolve()), DETECTION_FILE.stat().st_mtime_ns))

@lru_cache(maxsize=4)
def _load_analysis2_data(source_path, modified_ns):
    """DB 적재 없이 version11의 저장된 분석 결과를 읽습니다."""
    source = Path(source_path)
    prepared = monthly_upload(source.read_bytes(), source.name)
    run_id = "analysis2-" + str(modified_ns)
    return {
        "connected": True, "isDemo": False, "source": "Analysis2 CSV",
        "runId": run_id,
        "assessment": records(prepared["assessment"]),
        "signals": records(prepared["signals"]), "alerts": records(prepared["alerts"]),
        "activity": [], "runs": [{"run_id": run_id, "kind": "monthly", "source_name": str(source),
            "period": prepared["period"], "created_at": "CSV 결과", "rule_version": "analysis2-v11"}],
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

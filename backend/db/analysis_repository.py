"""업로드 검사·분석·DB1 저장. 원본과 분석 결과는 실행 버전별로 보관합니다."""

import json
import logging
import os
import time
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

ROOT_DIR = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT_DIR / "pipelines" / "regional_analysis"
DETECTION_FILE = ROOT_DIR / "pipelines/db1/Analysis2/outputs/detection.csv"

from dotenv import load_dotenv

# DB 접속 정보와 WELFIND_DATA_SOURCE를 db.connection import 전에도 확인하므로 여기서 먼저 읽습니다.
load_dotenv(ROOT_DIR / ".env")

from pipelines.preprocessing.regional_types.preprocessor import preprocess_raw_dir

LOGGER = logging.getLogger(__name__)
SCHEMA = "db1"  # PostgreSQL에서 확인한 실제 스키마 이름입니다.
RULE_VERSION = "analysis2-v11"


def get_engine():
    from backend.db.connection import engine

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
    """Convert legacy v11 and sequential DB1 output to the service contract."""
    data = data.copy()
    for metric in ("call_contacts", "text_contacts", "weekday_move_count", "weekend_move_count"):
        for old, new in [("_residual", "_residual_change"), ("_rz", "_residual_change_expanding_rz")]:
            if metric + old in data:
                data[metric + new] = data[metric + new].combine_first(data[metric + old]) if metric + new in data else data[metric + old]
    for old, new in [("adm_cd", "행정동코드"), ("dong_name", "행정동"), ("signal_status", "signal_type")]:
        if old in data:
            data[new] = data[new].combine_first(data[old]) if new in data else data[old]
    required = ["date", "행정동코드", "행정동", "communication_signal", "mobility_signal", "any_signal"]
    metrics = {
        "call_contacts": ("전화 연락", "communication_signal"),
        "text_contacts": ("문자 연락", "communication_signal"),
        "weekday_move_count": ("평일 이동", "mobility_signal"),
        "weekend_move_count": ("휴일 이동", "mobility_signal"),
    }
    for metric in metrics:
        required.extend([metric + "_log_change", metric + "_residual_change", metric + "_residual_change_expanding_rz"])
    missing = []
    for column in required:
        if column not in data.columns:
            missing.append(column)
    if missing or data.empty:
        raise ValueError("Analysis2 탐지 결과 CSV를 사용하세요. 누락 열: " + ", ".join(missing))
    # 문자열 'False'를 bool()로 바꾸면 True가 되므로 명시적으로 검사합니다.
    for column in ["communication_signal", "mobility_signal", "any_signal"]:
        values = data[column].astype(str).str.lower()
        if not values.isin(["true", "false", "1", "0"]).all():
            raise ValueError(column + ": True 또는 False가 필요합니다.")
        data[column] = values.isin(["true", "1"])
    data["행정동코드"] = data["행정동코드"].astype(str)
    months = pd.to_datetime(data["date"], format='ISO8601', errors="raise").dt.strftime("%Y-%m")
    if months.isna().any() or data.assign(_month=months).duplicated(["_month", "행정동코드"]).any():
        raise ValueError("날짜가 비어 있거나 동·월 결과가 중복되었습니다.")
    data["date"] = pd.to_datetime(months, format="%Y-%m")
    if "combined_signal" not in data:
        data["combined_signal"] = data.communication_signal & data.mobility_signal
    else:
        values = data.combined_signal.astype(str).str.lower()
        if not values.isin(["true", "false", "1", "0"]).all():
            raise ValueError("combined_signal: True 또는 False가 필요합니다.")
        data["combined_signal"] = values.isin(["true", "1"])
    if not data.any_signal.eq(data.communication_signal | data.mobility_signal).all() or not data.combined_signal.eq(data.communication_signal & data.mobility_signal).all():
        raise ValueError("통신·이동 신호와 any_signal/combined_signal이 일치하지 않습니다.")
    if "signal_type" not in data:
        data["signal_type"] = np.select([data.combined_signal, data.communication_signal, data.mobility_signal], ["combined", "communication", "mobility"], default="none")
    if 'analysis_model_version' not in data:
        data['analysis_model_version'] = 'analysis2-sequential-v1' if 'call_contacts_rz' in data else RULE_VERSION
    rows = []
    for metric, (label, signal_column) in metrics.items():
        frame = pd.DataFrame()
        frame["행정동코드"] = data["행정동코드"]
        frame["행정동명"] = data["행정동"]
        frame["기준연월"] = months
        frame["metric_label"] = label
        # 브리핑 그래프는 변화율과 같은 CSV의 실제 입력값을 표시합니다.
        # 구버전 업로드에 원자료 열이 없으면 null로 전달하여 값을 만들어내지 않습니다.
        if metric in data.columns:
            frame["metric_value"] = pd.to_numeric(data[metric], errors="coerce")
        else:
            frame["metric_value"] = np.nan
        frame["metric_unit"] = "명" if metric in ("call_contacts", "text_contacts") else "회"
        frame["change_pct"] = np.expm1(pd.to_numeric(data[metric + "_log_change"])) * 100
        frame["relative_change_pp"] = pd.to_numeric(data[metric + "_residual_change"]) * 100
        frame["risk_robust_z"] = pd.to_numeric(data[metric + "_residual_change_expanding_rz"])
        frame["has_enough_history"] = frame["risk_robust_z"].notna()
        frame["is_risk_signal"] = data[signal_column]
        frame["explanation"] = frame["행정동명"] + " " + label + " · 전월 및 과거 흐름과 비교한 분석 결과"
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
    """대시보드 자료를 읽습니다.

    WELFIND_DATA_SOURCE (.env)
      auto(기본): DB 접속 정보가 있으면 DB1을 먼저 읽고, 실패하면 로컬 CSV로 대체합니다.
      db: DB1만 사용합니다. 실패하면 오류를 그대로 표시합니다(클라우드 DB 점검용).
      csv: 로컬 Analysis2 CSV만 사용합니다(DB 없이 개발할 때).
    CSV는 Git에서 제외되므로, 새로 clone한 PC는 DB(클라우드) 경로로 화면을 채웁니다.
    """
    mode = (os.getenv("WELFIND_DATA_SOURCE") or "auto").strip().lower()
    if mode not in {"auto", "db", "csv"}:
        raise ValueError("WELFIND_DATA_SOURCE는 auto, db, csv 중 하나여야 합니다.")
    if mode in {"auto", "db"} and db_configured():
        try:
            run_id = _latest_detection_run()
            if run_id:
                # 캐시 원본은 요청별 수정(지도 추가 등)으로부터 보호합니다.
                return deepcopy(_load_analysis2_from_db(run_id))
            if mode == "db":
                raise LookupError("db1.analysis2_detections에 적재된 결과가 없습니다.")
        except Exception:
            if mode == "db" or not DETECTION_FILE.exists():
                raise
            LOGGER.warning("DB1 분석 결과를 읽지 못해 로컬 CSV로 대체합니다.", exc_info=True)
    elif mode == "db":
        raise RuntimeError(".env에 DB_HOST, DB_NAME, DB_USER, DB_PASSWORD를 설정하세요.")
    if not DETECTION_FILE.exists():
        raise FileNotFoundError(
            "분석 자료가 없습니다. .env에 공용 DB 접속 정보를 넣거나 " + str(DETECTION_FILE.relative_to(ROOT_DIR)) + " 파일을 받으세요."
        )
    legacy = ROOT_DIR / 'pipelines/db1/Analysis2/data/reference/gangnam_analysis2_detection_2022_2025.csv'
    return deepcopy(_load_analysis2_data(str(DETECTION_FILE.resolve()), DETECTION_FILE.stat().st_mtime_ns,
                                        legacy.stat().st_mtime_ns if legacy.exists() else 0))


def db_configured():
    return all(os.getenv(key) for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"))


_RUN_CHECK = {"at": 0.0, "run_id": None}
_RUN_CHECK_SECONDS = 60


def _latest_detection_run():
    """최신 run_id만 60초 간격으로 확인합니다. 원격 DB 왕복을 요청마다 반복하지 않습니다."""
    now = time.monotonic()
    if _RUN_CHECK["run_id"] and now - _RUN_CHECK["at"] < _RUN_CHECK_SECONDS:
        return _RUN_CHECK["run_id"]
    with get_engine().connect() as connection:
        run_id = connection.execute(text(
            f"SELECT run_id FROM {SCHEMA}.analysis2_detections GROUP BY run_id ORDER BY max(created_at) DESC LIMIT 1"
        )).scalar()
    _RUN_CHECK.update(at=now, run_id=run_id)
    return run_id


@lru_cache(maxsize=4)
def _load_analysis2_from_db(run_id):
    """DB1에 적재된 Analysis2 결과를 CSV와 같은 열 구조로 되돌려 같은 변환을 거칩니다."""
    with get_engine().connect() as connection:
        rows = connection.execute(text(
            f"""SELECT reference_month, admin_dong_code, dong_name, communication_signal, mobility_signal,
                       combined_signal, any_signal, signal_type, payload, source_file, created_at
                FROM {SCHEMA}.analysis2_detections WHERE run_id = :run_id
                ORDER BY reference_month, admin_dong_code"""
        ), {"run_id": run_id}).mappings().all()
        structures = connection.execute(text('''SELECT adm_cd, dong_name, cluster_type, payload, source_file FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY adm_cd ORDER BY created_at DESC) AS position
            FROM db1.analysis1_region_typology) latest WHERE position=1 ORDER BY adm_cd''')).mappings().all()
    structures = [dict(r, payload=json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"]) for r in structures]
    if not rows:
        raise LookupError("run_id " + str(run_id) + "의 분석 결과가 없습니다.")
    records_ = []
    for row in rows:
        payload = row["payload"] or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        record = dict(payload)
        record.update({
            "date": pd.Timestamp(row["reference_month"]).date().isoformat(), "행정동코드": str(row["admin_dong_code"]),
            "행정동": row["dong_name"], "communication_signal": bool(row["communication_signal"]),
            "mobility_signal": bool(row["mobility_signal"]), "combined_signal": bool(row["combined_signal"]),
            "any_signal": bool(row["any_signal"]), "signal_type": row["signal_type"],
        })
        records_.append(record)
    data = pd.DataFrame.from_records(records_)
    # JSON null은 None으로 오므로 숫자 열은 NaN으로 맞춥니다(CSV 경로와 동일한 결과).
    for column in data.columns:
        if column not in {"date", "행정동코드", "행정동", "signal_type"} and data[column].dtype == object:
            converted = pd.to_numeric(data[column], errors="coerce")
            if converted.notna().sum() == data[column].notna().sum():
                data[column] = converted
    source_file = rows[0]["source_file"] or "analysis2_detections"
    prepared = prepare_analysis2(data, source_file)
    model_versions = sorted(prepared['data'].analysis_model_version.dropna().unique().tolist())
    created = max(pd.Timestamp(row["created_at"]) for row in rows)
    return {
        "connected": True, "isDemo": False, "source": "동별 통화·문자·이동 분석 자료 (공용 저장 자료)",
        "runId": str(run_id),
        "assessment": records(prepared["assessment"]),
        "signals": records(prepared["signals"]), "alerts": records(prepared["alerts"]),
        "activity": [], "runs": [{"run_id": str(run_id), "kind": "monthly", "source_name": f"{SCHEMA}.analysis2_detections ({source_file})",
            "period": prepared["period"], "created_at": created.isoformat(timespec="seconds"), "rule_version": ' / '.join(model_versions)}],
        "dataLoadedAt": created.isoformat(timespec="seconds"),
        "regionalStructures": [dict(row) for row in structures],
    }

@lru_cache(maxsize=4)
def _load_analysis2_data(source_path, modified_ns, legacy_modified_ns=0):
    """DB 적재 없이 version11의 저장된 분석 결과를 읽습니다."""
    source = Path(source_path)
    prepared = monthly_upload(source.read_bytes(), source.name)
    legacy = ROOT_DIR / 'pipelines/db1/Analysis2/data/reference/gangnam_analysis2_detection_2022_2025.csv'
    if source.resolve() == DETECTION_FILE.resolve() and legacy.exists():
        previous = monthly_upload(legacy.read_bytes(), legacy.name)
        combined = pd.concat([previous['data'], prepared['data']], ignore_index=True)
        combined = combined.drop_duplicates(['date', '행정동코드'], keep='last')
        prepared = prepare_analysis2(combined, source.name)
    run_id = "analysis2-" + str(modified_ns) + '-' + str(legacy_modified_ns)
    return {
        "connected": True, "isDemo": False, "source": "동별 통화·문자·이동 분석 자료 (저장된 파일)",
        "runId": run_id,
        "assessment": records(prepared["assessment"]),
        "signals": records(prepared["signals"]), "alerts": records(prepared["alerts"]),
        "activity": [], "runs": [{"run_id": run_id, "kind": "monthly", "source_name": str(source),
            "period": prepared["period"], "created_at": "CSV 결과", "rule_version": ' / '.join(sorted(prepared['data'].analysis_model_version.dropna().unique().tolist()))}],
    }


def structure_upload(raw_dir, source="지역 구조자료 5종 · 독거노인 포함"):
    data, profile, report = preprocess_raw_dir(raw_dir)
    return {
        "kind": "structure",
        "source": source,
        "data": data,
        "context": profile,
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
                "rule_version": prepared.get("report", {}).get("rule_version", "analysis2-sequential-v1" if "call_contacts_rz" in prepared["data"] else RULE_VERSION),
            }
        ]
    )
    with get_engine().begin() as connection:
        from backend.db.db1_service import save_results
        save_results(connection, prepared, run_id)
        if prepared["kind"] == "monthly":
            append_frame(
                connection, "demo_risk_assessment", prepared["assessment"], run_id
            )
            append_frame(connection, "demo_risk_signals", prepared["signals"], run_id)
            append_frame(connection, "demo_risk_alerts", prepared["alerts"], run_id)
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
    _RUN_CHECK.update(at=0.0, run_id=None)
    _load_analysis2_from_db.cache_clear()
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
        if 'service_imports' in tables:
            imports = pd.read_sql(text("SELECT run_id, source_name, created_at FROM db1.service_imports ORDER BY created_at DESC LIMIT 100"), connection)
            result['activity'] = [dict(run_id=row['run_id'], created_at=row['created_at'], actor='DB1 실행기', kind='데이터', detail=row['source_name'], result='성공') for row in records(imports)]
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
            result["activity"] += records(
                pd.read_sql(
                    text(
                        "SELECT * FROM db1.demo_activity ORDER BY created_at DESC LIMIT 100"
                    ),
                    connection,
                )
            )
            result['activity'] = sorted(result['activity'], key=lambda row: row['created_at'], reverse=True)[:100]
    return result

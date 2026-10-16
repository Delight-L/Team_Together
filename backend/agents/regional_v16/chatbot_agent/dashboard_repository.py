"""Current-dashboard-compatible DB1 reader.

The team's existing dashboard already combines the published PostgreSQL
district tables with the delivered age-detection CSV.  This adapter gives the
regional agent exactly that same read model when the newer ``db1_v16`` serving
views have not been provisioned yet.  It is intentionally read-only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .repository import AGE_LABEL, CORE


ROOT = Path(__file__).resolve().parents[4]
AGE_CSV = ROOT / "pipelines" / "db1" / "Analysis2" / "outputs" / "age_detection" / "analysis2_age_detection.csv"


def _json(value: Any) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        return json.loads(value)
    return {}


def _flag(value: Any) -> bool | None:
    if value is None or pd.isna(value) or value == "":
        return None
    if isinstance(value, bool):
        return value
    if str(value).strip().lower() in {"true", "1", "1.0"}:
        return True
    if str(value).strip().lower() in {"false", "0", "0.0"}:
        return False
    return None


def _signal_type(row: dict) -> str:
    if _flag(row.get("combined_signal")) is True:
        return "combined"
    if _flag(row.get("communication_signal")) is True:
        return "communication"
    if _flag(row.get("mobility_signal")) is True:
        return "mobility"
    return "none"


class DashboardDb1Repository:
    """Read the same DB1 inputs as the existing dashboard, without writes."""

    def __init__(self, engine):
        self.engine = engine
        self._district: pd.DataFrame | None = None
        self._age: pd.DataFrame | None = None
        self._run_id: str | None = None

    def close(self):
        return None

    def _run(self) -> str | None:
        if self._run_id is None:
            with self.engine.connect() as connection:
                self._run_id = connection.exec_driver_sql(
                    "SELECT run_id FROM db1.latest_detection_run"
                ).scalar()
        return self._run_id

    def has_data(self) -> bool:
        return bool(self._run())

    def _district_frame(self) -> pd.DataFrame:
        if self._district is not None:
            return self._district.copy()
        run_id = self._run()
        if not run_id:
            self._district = pd.DataFrame()
            return self._district.copy()
        with self.engine.connect() as connection:
            rows = connection.exec_driver_sql(
                """SELECT reference_month, admin_dong_code, dong_name,
                          communication_signal, mobility_signal, combined_signal,
                          any_signal, signal_type, payload
                   FROM db1.analysis2_detections
                   WHERE run_id=%s ORDER BY reference_month, admin_dong_code""",
                (run_id,),
            ).mappings().all()
        records = []
        for source in rows:
            row = _json(source["payload"])
            row.update({
                "date": str(source["reference_month"])[:10],
                "행정동": source["dong_name"],
                "adm_cd": str(source["admin_dong_code"] or row.get("adm_cd") or ""),
                "communication_signal": _flag(source["communication_signal"]),
                "mobility_signal": _flag(source["mobility_signal"]),
                "combined_signal": _flag(source["combined_signal"]),
                "any_signal": _flag(source["any_signal"]),
                # Some published rows contain lifecycle values such as ``New``
                # here. Detection flags are the source of truth for the domain.
                "signal_type": (str(source["signal_type"]).lower()
                                if str(source["signal_type"] or "").lower() in
                                {"communication", "mobility", "combined"}
                                else _signal_type({
                                    "communication_signal": source["communication_signal"],
                                    "mobility_signal": source["mobility_signal"],
                                    "combined_signal": source["combined_signal"],
                                })),
                "assessment_status": row.get("assessment_status", "assessed"),
            })
            records.append(row)
        self._district = pd.DataFrame(records)
        return self._district.copy()

    def _age_frame(self) -> pd.DataFrame:
        if self._age is not None:
            return self._age.copy()
        if not AGE_CSV.is_file():
            self._age = pd.DataFrame()
            return self._age.copy()
        frame = pd.read_csv(AGE_CSV, dtype={"행정동코드": str})
        if frame.empty:
            self._age = frame
            return frame.copy()
        frame["date"] = pd.to_datetime(frame["date"], format="mixed").dt.strftime("%Y-%m-%d")
        frame["행정동"] = frame["행정동"].replace({"일원2동": "개포3동"})
        for name in ("communication_signal", "mobility_signal", "combined_signal", "any_signal"):
            if name in frame:
                frame[name] = frame[name].map(_flag)
        if "any_signal" not in frame:
            frame["any_signal"] = frame["communication_signal"].eq(True) | frame["mobility_signal"].eq(True)
        frame["signal_type"] = frame.apply(lambda row: _signal_type(row.to_dict()), axis=1)
        frame["assessment_status"] = frame.get("assessment_status", "assessed")
        self._age = frame
        return frame.copy()

    @staticmethod
    def _filter(frame: pd.DataFrame, dong=None, start=None, end=None, age_band=None) -> pd.DataFrame:
        if frame.empty:
            return frame.copy()
        result = frame.copy()
        months = result["date"].astype(str).str[:7]
        if dong:
            result = result.loc[result["행정동"].eq(dong)]
            months = result["date"].astype(str).str[:7]
        if start:
            result = result.loc[months.ge(start)]
            months = result["date"].astype(str).str[:7]
        if end:
            result = result.loc[months.le(end)]
        if age_band and "age_band" in result:
            result = result.loc[result["age_band"].eq(age_band)]
        return result.sort_values(["date", "행정동"] + (["age_band"] if "age_band" in result else []))

    def districts(self) -> set[str]:
        frames = [self._district_frame(), self._age_frame()]
        return {str(name) for frame in frames if "행정동" in frame for name in frame["행정동"].dropna()}

    def available_period(self) -> tuple[str, str]:
        frame = self._district_frame()
        if frame.empty:
            frame = self._age_frame()
        if frame.empty:
            return ("2025-07", "2025-07")
        months = frame["date"].astype(str).str[:7]
        return (months.min(), months.max())

    def consumption_period(self) -> tuple[str, str]:
        return self.available_period()

    def pipeline_status(self) -> dict:
        start, end = self.available_period()
        return {
            "history_end": "2025-06", "history_rows": None,
            "detection_rows": len(self._district_frame()),
            "age_detection_rows": len(self._age_frame()),
            "waiting_for": {"month": end}, "source": "dashboard-compatible",
        }

    def district_codes(self) -> dict[str, str]:
        frame = self._district_frame()
        if frame.empty:
            return {}
        return {str(row["행정동"]): str(row.get("adm_cd") or "") for _, row in frame.iterrows()}

    def activity(self, dong=None, start=None, end=None, age_band=None) -> pd.DataFrame:
        frame = self._age_frame() if age_band else self._district_frame()
        return self._filter(frame, dong, start, end, age_band)

    def signals(self, start=None, end=None, dong=None, signal="any", age_band=None) -> pd.DataFrame:
        frame = self.activity(dong, start, end, age_band)
        column = {"any": "any_signal", "communication": "communication_signal",
                  "mobility": "mobility_signal", "combined": "combined_signal"}[signal]
        return frame.loc[frame.get(column, pd.Series(False, index=frame.index)).eq(True)].copy()

    def age_signal_cases(self, start=None, end=None, dong=None, signal="any", age_band=None) -> pd.DataFrame:
        frame = self._filter(self._age_frame(), dong, start, end, age_band)
        column = {"any": "any_signal", "communication": "communication_signal",
                  "mobility": "mobility_signal", "combined": "combined_signal"}[signal]
        return frame.loc[frame.get(column, pd.Series(False, index=frame.index)).eq(True)].copy()

    def anomalies(self, start=None, end=None, metric=None, age_band=None, dongs=()):
        frame = self.activity(None, start, end, age_band)
        if dongs:
            frame = frame.loc[frame["행정동"].isin(dongs)]
        metric = metric or "weekday_move_count"
        column = metric + "_residual_change_expanding_rz"
        if column not in frame:
            return frame.iloc[0:0].copy(), column
        return frame.loc[frame[column].notna()].sort_values(column).head(10), column

    def evidence(self, dong, start=None, end=None, age_band=None) -> pd.DataFrame:
        return self.signals(start, end, dong, "any", age_band)

    def context(self, dong, as_of=None) -> pd.DataFrame:
        with self.engine.connect() as connection:
            rows = connection.exec_driver_sql(
                "SELECT dong_name, cluster_type, payload FROM db1.latest_region_typology WHERE dong_name=%s",
                (dong,),
            ).mappings().all()
        records = []
        for source in rows:
            row = _json(source["payload"])
            row.update({"dong_name": source["dong_name"], "cluster_type": source["cluster_type"]})
            records.append(row)
        return pd.DataFrame(records)

    def supplements(self, names, dates, age_band=None) -> dict[str, Any]:
        return {"analysis1": [], "analysis3_dong": [], "analysis3_district_shared": [],
                "weather": [], "regional_context": [], "shown_context_dongs": len(names)}

    def consumption_evidence(self, names, start, end, age):
        return [], {}

    def consumption_payloads(self, table, *, periods=None, adm_cds=None, ages=None, districts=None):
        return []

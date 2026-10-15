"""The one projection used by dashboard cards and the first chatbot message."""
from __future__ import annotations

import hashlib
import pandas as pd

from chatbot_agent.repository import CORE, DataRepository
from chatbot_agent.observation_period import observation_period, observation_period_text

METRICS = {
    "call_contacts": ("통화 상대 번호 수", "명"),
    "text_contacts": ("문자 상대 번호 수", "명"),
    "weekday_move_count": ("평일 이동 횟수", "회"),
    "weekend_move_count": ("휴일 이동 횟수", "회"),
}


def _number(value):
    if value is None: return None
    try:
        if value != value: return None
        return round(float(value), 2)
    except (TypeError, ValueError): return None


def build_brief(repo: DataRepository, *, dong: str, label_month: str, age_band: str | None,
                snapshot_id: str, revision: int) -> dict:
    """Read once from the pinned DB and create JSON-safe display/narrative together."""
    if dong not in repo.districts():
        return {"status": "invalid_scope", "display": {"scope": {"dong": dong, "label_month": label_month, "age_band": age_band}, "observation_period": _observation_display(label_month), "events": [], "metrics": []}, "narrative": "선택한 동을 확인할 수 없습니다.", "limitations": ["동 이름과 공개된 관측기간을 확인해 주세요."]}
    frame = repo.activity(dong, label_month, label_month, age_band)
    if frame.empty:
        return {"status": "invalid_scope", "display": {"scope": {"dong": dong, "label_month": label_month, "age_band": age_band}, "observation_period": _observation_display(label_month), "events": [], "metrics": []}, "narrative": "선택한 관측기간의 공개 데이터를 확인할 수 없습니다.", "limitations": ["공개된 관측기간을 선택해 주세요."]}
    row = frame.iloc[0]
    previous_month = (pd.Timestamp(frame.date.iloc[0]).to_period("M") - 1).strftime("%Y-%m")
    previous = repo.activity(dong, previous_month, previous_month, age_band)
    prior = previous.iloc[0] if not previous.empty else None
    assessment = str(row.get("assessment_status") or ("assessed" if not age_band else "deferred"))
    signals = [name for name, column in (("소통", "communication_signal"), ("이동", "mobility_signal"), ("복합", "combined_signal")) if row.get(column) is True or row.get(column) == 1]
    event = {"event_id": hashlib.sha256(f"{snapshot_id}|{dong}|{label_month}|{age_band or 'all'}|{row.get('model_version', 'core')}".encode()).hexdigest()[:16],
             "group_id": f"{dong}:{age_band or 'all'}", "model_version": str(row.get('model_version', 'core')),
             "age_scope": "service" if age_band else "all", "age_band": age_band or "전체 연령",
             "signals": signals, "assessment_status": assessment}
    events = [event]
    # An overall dashboard selection keeps the four official aggregate cards,
    # while exposing every available service-age event for an age breakdown.
    if age_band is None:
        events = []
        for band in ("20s", "30s", "40s", "50s", "60plus"):
            age_frame = repo.activity(dong, label_month, label_month, band)
            if age_frame.empty:
                continue
            age_row = age_frame.iloc[0]
            age_signals = [name for name, column in (("소통", "communication_signal"), ("이동", "mobility_signal"), ("복합", "combined_signal")) if age_row.get(column) is True or age_row.get(column) == 1]
            age_assessment = str(age_row.get("assessment_status") or "deferred")
            events.append({"event_id": hashlib.sha256(f"{snapshot_id}|{dong}|{label_month}|{band}|{age_row.get('model_version', 'age')}".encode()).hexdigest()[:16],
                           "group_id": f"{dong}:{band}", "model_version": str(age_row.get("model_version", "age")),
                           "age_scope": "service", "age_band": band, "signals": age_signals,
                           "assessment_status": age_assessment})
    metrics = []
    for metric, (label, unit) in METRICS.items():
        value = _number(row.get(metric)); before = _number(prior.get(metric)) if prior is not None else None
        metrics.append({"metric_id": metric, "label": label, "value": value, "unit": unit,
                        "comparison_value": before, "change_value": None if value is None or before is None else round(value-before, 2),
                        "change_unit": unit, "assessment_status": assessment})
    if assessment in {"deferred", "not_assessable"}:
        status = "not_assessable"
    elif assessment in {"partially_assessed", "partial"}:
        status = "partial"
    else:
        status = "ready" if signals else "no_signal"
    observed = observation_period(label_month)
    display = {"scope": {"dong": dong, "label_month": label_month, "age_band": age_band},
               "observation_period": _observation_display(label_month),
               "events": events, "metrics": metrics,
               "evidence_status": status}
    changes = []
    for item in metrics[:2]:
        if item["change_value"] is not None: changes.append(f"{item['label']}는 직전 기준월의 관측값보다 {item['change_value']:+.2f}{item['unit']}")
    signal_text = "·".join(signals) + " 변화 신호" if signals else "공식 변화 신호는 관찰되지 않았습니다"
    if status == "not_assessable": signal_text = "평가에 필요한 자료가 충분하지 않아 판정을 보류했습니다"
    narrative = f"{dong} · {observation_period_text(label_month)}에 {event['age_band']}에서 {signal_text}."
    if changes: narrative += " " + ", ".join(changes) + "."
    narrative += " 이 결과는 집단의 변화이며 개인의 위험이나 원인을 뜻하지 않습니다."
    return {"status": status, "display": display, "narrative": narrative,
            "limitations": ["표시한 기간은 기준월 직전 3개월 관측입니다. 직전 기준월의 관측기간과 두 달이 겹칠 수 있습니다. 값이 없거나 판정이 보류된 경우 신호 없음으로 바꾸지 않습니다."],
            "context_segment_id": event["event_id"]}


def _observation_display(label_month: str) -> dict:
    observed = observation_period(label_month)
    return {"start_month": observed[0] if observed else None,
            "end_month": observed[1] if observed else None,
            "display": observation_period_text(label_month)}

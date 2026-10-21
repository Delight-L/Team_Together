"""Convert internal source-label months into user-facing observation periods."""

from __future__ import annotations

from datetime import date, timedelta
import re


_LABEL_MONTH = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")


def observation_period(label_month: str | None) -> tuple[str, str] | None:
    """Return the three complete months observed before a source label month.

    The provider uses the first day of the label month as an aggregation label.
    Therefore a ``2025-12`` label represents observations from September through
    November 2025, rather than observations made in December.
    """
    text = str(label_month or "").strip()
    if not _LABEL_MONTH.fullmatch(text):
        return None
    try:
        year, month = map(int, text.split("-"))
        label_start = date(year, month, 1)
    except (TypeError, ValueError):
        return None
    observation_end = label_start - timedelta(days=1)
    start_month = observation_end.month - 2
    start_year = observation_end.year
    if start_month <= 0:
        start_month += 12
        start_year -= 1
    observation_start = date(start_year, start_month, 1)
    return observation_start.strftime("%Y-%m"), observation_end.strftime("%Y-%m")


def observation_period_text(label_month: str | None) -> str:
    """Render both the reporting reference month and its real observation months."""
    period = observation_period(label_month)
    if period is None:
        return "관측기간 확인 불가"
    label = str(label_month).strip()
    label_year, label_month_number = label.split("-")
    start, end = period
    start_year, start_month = start.split("-")
    end_year, end_month = end.split("-")
    if start_year == end_year:
        observed = f"{start_year}년 {int(start_month)}~{int(end_month)}월"
    else:
        observed = f"{start_year}년 {int(start_month)}월~{end_year}년 {int(end_month)}월"
    return f"{label_year}년 {int(label_month_number)}월 기준 (관측: {observed})"


def observation_range_text(start_label: str | None, end_label: str | None) -> str:
    """Render the full observation range covered by a label-month query."""
    start = observation_period(start_label)
    end = observation_period(end_label)
    if start is None or end is None:
        return "관측기간 확인 불가"
    return _month_range_text(start[0], end[1])


def _month_range_text(start: str, end: str) -> str:
    start_year, start_month = start.split("-")
    end_year, end_month = end.split("-")
    if start == end:
        return f"{start_year}년 {int(start_month)}월 관측"
    if start_year == end_year:
        return f"{start_year}년 {int(start_month)}~{int(end_month)}월 관측"
    return f"{start_year}년 {int(start_month)}월~{end_year}년 {int(end_month)}월 관측"

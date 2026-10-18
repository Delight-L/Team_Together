"""Read-only, descriptive changes in merchant-area transaction activity."""
from __future__ import annotations

import math

from .repository import AGE_LABEL
from .period_matching import nearest_period


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _months(start, end):
    year, month = map(int, start.split("-"))
    final_year, final_month = map(int, end.split("-"))
    first, final = year * 12 + month - 1, final_year * 12 + final_month - 1
    return [f"{index // 12:04d}-{index % 12 + 1:02d}" for index in range(first, final + 1)]


def _previous_month(month):
    year, number = map(int, month.split("-"))
    index = year * 12 + number - 2
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def _previous_quarter(period):
    year, number = int(period[:4]), int(period[-1])
    return f"{year}Q{number - 1}" if number > 1 else f"{year - 1}Q4"


def _quarter_for(month):
    return f"{month[:4]}Q{(int(month[5:]) - 1) // 3 + 1}"


def _complete_quarters(months):
    selected = set(months)
    periods = sorted({f"{month[:4]}Q{(int(month[5:]) - 1) // 3 + 1}" for month in months})
    return [period for period in periods if all(
        f"{period[:4]}-{number:02d}" in selected
        for number in range((int(period[-1]) - 1) * 3 + 1, int(period[-1]) * 3 + 1)
    )]


def _base(scope, period, domain=None, age=None, name=None):
    row = {
        "scope": scope, "period": period, "domain": domain, "age": age,
        "current_daily_count": None, "previous_daily_count": None,
        "change_pct": None, "comparison_period": None,
        "comparison_basis": None, "matched_industries": None,
        "status": "baseline_unavailable",
    }
    if scope == "merchant_dong":
        row["행정동"] = name
    else:
        row["district"] = "강남구"
    return row


def _counts(row, current, previous, matched, *, monthly=False):
    """Expose totals only when the stored matched rate covers both full cells."""
    if not current or not previous or not _finite(matched) or matched <= 0:
        return
    full_match = (matched == current.get("observed_industries")
                  and matched == previous.get("observed_industries"))
    if monthly:
        full_match = full_match and all(
            _finite(cell.get("observed_industry_days_min"))
            and cell["observed_industry_days_min"] >= cell.get("days", float("inf"))
            for cell in (current, previous)
        )
    if full_match:
        for target, cell in (("current_daily_count", current), ("previous_daily_count", previous)):
            if _finite(cell.get("daily_count")):
                row[target] = float(cell["daily_count"])


def _rank(rows, limit):
    """Rank increases; when none increase, keep the largest actual changes."""
    comparable = [row for row in rows if _finite(row["change_pct"])
                  and row["status"] in {"ready", "ready_matched_change_only"}]
    increases = [row for row in comparable if row["change_pct"] > 0]
    chosen = sorted(increases or comparable, key=lambda row: (
        -row["change_pct"], str(row.get("age") or ""), str(row.get("domain") or "")
    ))[:limit]
    if chosen:
        return chosen
    partial = [row for row in rows if _finite(row["change_pct"])]
    if partial:
        return sorted(partial, key=lambda row: -row["change_pct"])[:limit]
    # One real unavailable cell communicates a missing baseline without invented 0%.
    return rows[:1]


def consumption_trends(repo, names, start, end, age_band=None, limit=3, include_district=True):
    """Return top descriptive daily transaction changes for each scope and period.

    Local merchant-dong data is quarterly: only fully selected calendar quarters
    are compared, using the stored same-industry qoq rate. District data is monthly
    and uses its stored matched-industry month-on-month rate. Without an age filter,
    individual age-by-domain cells are ranked and their customer ages stay explicit;
    no overall rate is fabricated. ``matched_industries`` is a matched industry COUNT:
    the actual qoq/monthly match lists are absent from the legacy aggregate database.
    Five consumption domains are available, not granular industries or product items.
    Rates measure transaction counts per day, not spending amounts or resident use.
    No new anomaly threshold is applied. Missing baselines remain None. The database
    is only read; existing detector results and source context are never recalculated.
    With ``include_district=False``, only local quarterly data is read and returned.
    """
    months = _months(start, end)
    if not months:
        return []
    quarters = _complete_quarters(months)
    names = list(dict.fromkeys(names))
    age_label = AGE_LABEL.get(age_band, age_band) if age_band else None
    result = []
    codes = repo.district_codes()
    # The selected period is often one dashboard month while local data is
    # quarterly. Read the source's available periods so a nearest comparable
    # reference can be shown instead of an empty answer.
    wanted_codes = [codes[name] for name in names if name in codes]
    ages = [age_label] if age_label else None
    features = {(row["adm_cd"], row["period"], row["age"], row["domain"]): row
                for row in repo.consumption_payloads("a3a_feature", adm_cds=wanted_codes, ages=ages)}
    comparisons = {(row["adm_cd"], row["period"], row["age"], row["domain"]): row
                   for row in repo.consumption_payloads("a3a_comparison", adm_cds=wanted_codes, ages=ages)}
    monthly = ({(row["period"], row["age"], row["domain"]): row
                for row in repo.consumption_payloads("a3b_feature", districts=["11680"], ages=ages)
                if row.get("district", "11680") == "11680"}
               if include_district else {})

    def merchant_ready(code, quarter):
        for (adm_cd, period, age, domain), current in features.items():
            if adm_cd != code or period != quarter or age_label and age != age_label:
                continue
            previous = features.get((code, _previous_quarter(quarter), age, domain))
            comparison = comparisons.get((code, quarter, age, domain), {})
            if previous and not current.get("missing_domain") and not previous.get("missing_domain"):
                if _finite(comparison.get("qoq_daily_change_pct")) and _finite(comparison.get("qoq_matched_industry_count")) and comparison["qoq_matched_industry_count"] > 0:
                    return True
        return False

    def district_ready(month):
        for (period, age, domain), current in monthly.items():
            if period != month or age_label and age != age_label:
                continue
            previous = monthly.get((_previous_month(month), age, domain))
            if previous and not current.get("missing_domain") and not previous.get("missing_domain"):
                if _finite(current.get("matched_mom_daily_change_pct")) and _finite(current.get("matched_industry_count")) and current["matched_industry_count"] > 0:
                    return True
        return False

    for name in names:
        code = codes.get(name)
        requested = quarters or [_quarter_for(end)]
        selected_quarters = [quarter for quarter in requested if merchant_ready(code, quarter)]
        if not selected_quarters:
            available = {period for adm_cd, period, age, _ in features
                         if adm_cd == code and (not age_label or age == age_label) and merchant_ready(code, period)}
            closest = nearest_period(available, _quarter_for(end))
            selected_quarters = [closest] if closest else []
        if not selected_quarters:
            row = _base("merchant_dong", f"{start}~{end}", age=age_label, name=name)
            row["status"] = "quarter_not_fully_selected"
            result.append(row)
            continue
        for quarter in selected_quarters:
            rows = []
            for key, current in features.items():
                adm_cd, period, age, domain = key
                if adm_cd != code or period != quarter or age_label and age != age_label:
                    continue
                previous_period = _previous_quarter(quarter)
                previous = features.get((code, previous_period, age, domain))
                comparison = comparisons.get(key, {})
                row = _base("merchant_dong", quarter, domain, age, name)
                row.update(comparison_period=previous_period,
                           comparison_basis="previous_quarter_matched_industry_daily_count",
                           matched_industries=comparison.get("qoq_matched_industry_count"))
                if quarter not in quarters:
                    row.update(selection_alignment="nearest_comparable_period", requested_period=f"{start}~{end}")
                rate = comparison.get("qoq_daily_change_pct")
                matched = row["matched_industries"]
                if current.get("missing_domain"):
                    row["status"] = "current_category_unavailable"
                elif not previous or previous.get("missing_domain"):
                    row["status"] = "previous_category_unavailable"
                elif _finite(rate) and _finite(matched) and matched > 0:
                    row.update(change_pct=float(rate), status="ready_matched_change_only")
                    _counts(row, current, previous, matched)
                    if row["current_daily_count"] is not None and row["previous_daily_count"] is not None:
                        row["status"] = "ready"
                rows.append(row)
            if not rows:
                row = _base("merchant_dong", quarter, age=age_label, name=name)
                row["status"] = "current_period_unavailable"
                rows.append(row)
            result.extend(_rank(rows, limit))
    selected_months = list(months)
    if include_district and not any(district_ready(month) for month in selected_months):
        closest = nearest_period((period for period, _, _ in monthly if district_ready(period)), end)
        selected_months = [closest] if closest else selected_months
    for month in selected_months if include_district else ():
        rows = []
        for (period, age, domain), current in monthly.items():
            if period != month or age_label and age != age_label:
                continue
            previous_period = _previous_month(month)
            previous = monthly.get((previous_period, age, domain))
            row = _base("merchant_district_shared", month, domain, age)
            row.update(comparison_period=previous_period,
                       comparison_basis="previous_month_matched_industry_daily_count",
                       matched_industries=current.get("matched_industry_count"))
            if month not in months:
                row.update(selection_alignment="nearest_comparable_period", requested_period=f"{start}~{end}")
            rate = current.get("matched_mom_daily_change_pct")
            matched = row["matched_industries"]
            if current.get("missing_domain"):
                row["status"] = "current_category_unavailable"
            elif not previous or previous.get("missing_domain"):
                row["status"] = "previous_category_unavailable"
            elif _finite(rate) and _finite(matched) and matched > 0:
                row.update(change_pct=float(rate), status="ready_matched_change_only")
                _counts(row, current, previous, matched, monthly=True)
                if row["current_daily_count"] is not None and row["previous_daily_count"] is not None:
                    row["status"] = "ready"
                if any(not _finite(cell.get("observed_industry_days_min"))
                       or cell["observed_industry_days_min"] < cell.get("days", float("inf"))
                       for cell in (current, previous)):
                    row["status"] = "ready_partial_day_coverage"
            rows.append(row)
        if not rows:
            row = _base("merchant_district_shared", month, age=age_label)
            row["status"] = "current_period_unavailable"
            rows.append(row)
        result.extend(_rank(rows, limit))
    return result

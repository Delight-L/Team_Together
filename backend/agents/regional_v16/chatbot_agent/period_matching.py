"""Choose the nearest available contextual period without changing core facts."""
from __future__ import annotations


def period_index(period: str) -> int:
    """Return a sortable month/quarter index for YYYY-MM or YYYYQn."""
    if len(period) == 7 and period[4] == "-":
        year, month = period.split("-")
        return int(year) * 12 + int(month) - 1
    if len(period) == 6 and period[4] == "Q":
        return int(period[:4]) * 12 + (int(period[-1]) - 1) * 3
    raise ValueError(f"Unsupported period: {period!r}")


def nearest_period(periods, requested: str) -> str | None:
    """Pick the closest available period, preferring an earlier tie.

    The caller is responsible for ensuring each candidate is actually usable
    for its source (for example, that a prior comparison period exists).
    """
    candidates = sorted({str(period) for period in periods if period})
    if not candidates:
        return None
    target = period_index(requested)
    return min(candidates, key=lambda period: (abs(period_index(period) - target), period_index(period) > target, period))

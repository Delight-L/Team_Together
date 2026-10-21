"""Compare analysis content, independently of file location, timestamps or row order."""

import hashlib
import json
import math
from decimal import Decimal

# Labels and file paths do not change values, methods, thresholds or model versions.
PRESENTATION_FIELDS = frozenset(
    {
        'source_file',
        'source_path',
        'source_district',
        'explanation',
        'context_note',
        'metric_label',
        'detection_path',
    }
)


def _canonical(value):
    if isinstance(value, dict):
        return {
            key: _canonical(item) for key, item in value.items() if key not in PRESENTATION_FIELDS
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            return None
        return {'$number': str(Decimal(str(value)).normalize())}
    return value


def evidence_fingerprint(rows):
    """Hash every stored evidence value; preserve missing/null/boolean distinctions."""
    normalized = sorted(
        json.dumps(
            _canonical(row),
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
            allow_nan=False,
        )
        for row in rows
    )
    return hashlib.sha256(
        json.dumps(normalized, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    ).hexdigest()


# Only measurements accept arithmetic noise. Identifiers, counts, flags and
# model versions remain exact; the original values and run fingerprint stay intact.
MEASUREMENT_FIELDS = frozenset(
    {
        'metric_value',
        'change_pct',
        'relative_change_pp',
        'risk_robust_z',
        'threshold',
        'absolute_rz',
        'local_rz',
        'absolute_threshold',
        'local_threshold',
    }
)
MEASUREMENT_TOLERANCE = Decimal('0.00000001')
COMPARISON_IGNORED_FIELDS = PRESENTATION_FIELDS - {'detection_path'}


def _same_value(left, right, field=None):
    if isinstance(left, dict) and isinstance(right, dict):
        keys = left.keys() - COMPARISON_IGNORED_FIELDS
        if keys != right.keys() - COMPARISON_IGNORED_FIELDS:
            return False
        return all(_same_value(left[key], right[key], key) for key in keys)
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(
            _same_value(a, b, field) for a, b in zip(left, right)
        )
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if not math.isfinite(left) or not math.isfinite(right):
            return left == right or (math.isnan(left) and math.isnan(right))
        if field in MEASUREMENT_FIELDS:
            return abs(Decimal(str(left)) - Decimal(str(right))) <= MEASUREMENT_TOLERANCE
        return left == right
    return type(left) is type(right) and left == right


def evidence_matches(saved, current):
    """Compare unordered evidence rows with absolute 1e-8 measurement tolerance.

    Match one to one so duplicate/missing rows cannot disappear, even where
    several rows are within tolerance of one another.
    """
    if len(saved) != len(current):
        return False
    candidates = [[i for i, row in enumerate(current) if _same_value(old, row)] for old in saved]
    if any(not choices for choices in candidates):
        return False
    matched = {}

    def assign(index, seen):
        for candidate in candidates[index]:
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate not in matched or assign(matched[candidate], seen):
                matched[candidate] = index
                return True
        return False

    return all(assign(index, set()) for index in range(len(saved)))

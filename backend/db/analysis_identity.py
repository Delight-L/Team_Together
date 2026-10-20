"""Compare analysis content, independently of file location, timestamps or row order."""
import hashlib
import json
import math
from decimal import Decimal

# Labels and file paths do not change values, methods, thresholds or model versions.
PRESENTATION_FIELDS = frozenset({
    'source_file', 'source_path', 'source_district', 'explanation', 'context_note',
    'metric_label', 'detection_path',
})


def _canonical(value):
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in value.items() if key not in PRESENTATION_FIELDS}
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
    normalized = sorted(json.dumps(_canonical(row), ensure_ascii=False, sort_keys=True,
                                   separators=(',', ':'), allow_nan=False) for row in rows)
    return hashlib.sha256(json.dumps(normalized, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()

"""Validate sequential 32-case contract without synthesizing inputs."""

import argparse
import json
import re
from pathlib import Path

PATHS = {f"PATH-{n:02d}" for n in range(1, 5)}


def validate(path):
    rows = [
        json.loads(s) for s in Path(path).read_text(encoding="utf-8-sig").splitlines() if s.strip()
    ]
    errors = []
    if len(rows) != 32 or len({r.get('case_id') for r in rows}) != 32:
        errors.append("Exactly 32 unique cases required")
    for item in rows:
        label = item.get('case_id', '?')
        refs = item.get('reference_answers') or []
        if not refs or any(not isinstance(r, str) or not r.strip() for r in refs):
            errors.append(f'{label}: missing references')
        if not re.fullmatch('[0-9a-f]{64}', item.get('snapshot_sha256', '')):
            errors.append(f'{label}: missing verified snapshot hash')
        steps = item.get('steps') or []
        if (
            not steps
            or sum(bool(s.get('score_target')) for s in steps) != 1
            or not steps[-1].get('score_target')
        ):
            errors.append(f'{label}: exactly final step must be score target')
        for step in steps:
            if step.get('action') == 'chat':
                if not str(step.get('text', '')).strip():
                    errors.append(f'{label}: empty input')
            elif step.get('action') == 'dashboard_selection':
                s = step.get('selection') or {}
                if not s.get('dong') or not s.get('label_month') or 'age_band' not in s:
                    errors.append(f'{label}: incomplete selection')
                if s.get('age_band') not in {None, '20s', '30s', '40s', '50s', '60plus'}:
                    errors.append(f'{label}: invalid age')
                if not isinstance(step.get('selection_revision'), int):
                    errors.append(f'{label}: revision required')
            else:
                errors.append(f'{label}: unsupported action')
        if item.get('path_id') in {'PATH-01', 'PATH-02'} and any(
            s.get('action') != 'chat' for s in steps
        ):
            errors.append(f'{label}: chat path contains selection')
        if item.get('path_id') in {'PATH-03', 'PATH-04'} and (
            not steps or steps[0].get('action') != 'dashboard_selection'
        ):
            errors.append(f'{label}: missing dashboard precondition')
    if any(sum(r.get('path_id') == p for r in rows) != 8 for p in PATHS):
        errors.append('Each path must contain 8 cases')
    if errors:
        raise ValueError('\n'.join(errors))
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset', type=Path)
    args = parser.parse_args()
    print(json.dumps({'valid': True, 'case_count': len(validate(args.dataset))}))

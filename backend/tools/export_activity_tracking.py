"""Deliver existing DB1 follow-up records without recalculating detection or recovery."""
import csv
import hashlib
import json
from pathlib import Path

AGES = {'20s':'20대','30s':'30대','40s':'40대','50s':'50대','60plus':'60대 이상'}

def activity_tracking(source):
    source = Path(source)
    detection = source / 'Analysis2/outputs/age_detection/analysis2_age_detection.csv'
    followup = source / 'Analysis2/outputs/activity_level/activity_followup.csv'
    if not detection.is_file() or not followup.is_file():
        return {'events': [], 'months': [], 'available': False}
    def records(path):
        with path.open(encoding='utf-8-sig') as stream:
            return list(csv.DictReader(stream))
    detected = records(detection)
    versions = {r['detection_model_version'] for r in detected}
    if len(versions) != 1:
        raise ValueError('Tracking requires one active detection model')
    version = next(iter(versions))
    signals = {(r['행정동코드'], r['age_band'], r['date'][:7]): r for r in detected}
    events = {}
    tracking_versions = set()
    for row in records(followup):
        r = json.loads(row['payload_json'])
        if r['detection_model_version'] != version:
            continue
        tracking_versions.add(row['version'])
        key = (r['adm_cd'], r['age_band'], r['signal_date'][:7])
        signal = signals.get(key)
        if signal is None:
            raise ValueError('Follow-up event is missing its source detection')
        flag = lambda k: str(signal.get(k, '')).lower() in ('true', '1', '1.0')
        if not (flag('communication_signal') or flag('mobility_signal')):
            raise ValueError('Follow-up event is not a detected case')
        event = events.setdefault(key, {
            'id': '/'.join((*key, version)), 'code': key[0], 'ageBand': key[1],
            'age': AGES[key[1]], 'district': '개포3동' if key[0] == '1123074' else signal['행정동'],
            'signalMonth': key[2], 'referenceMonth': r['reference_date'][:7],
            'modelVersion': version, 'trackingVersion': row['version'],
            'signals': {d: {'absolute':flag(d+'_absolute_signal'), 'local':flag(d+'_local_signal')}
                        for d in ('communication','mobility')}, 'points': [],
        })
        if any(p['month'] == r['date'][:7] for p in event['points']):
            raise ValueError('Duplicate follow-up month or tracking model')
        event['points'].append({
            'month':r['date'][:7], 'raw':r['raw_change_pct'], 'seasonal':r['seasonal_change_pct'],
            'local':r['local_change_pct'], 'domains':r['domain_states'],
            'overallRecoveryStatus':r['overall_recovery_status'], 'quality':r['quality'],
            'referenceQuality':r['reference_quality'],
        })
    if len(tracking_versions) > 1:
        raise ValueError('Multiple tracking models must not be mixed')
    for event in events.values():
        event['points'].sort(key=lambda p:p['month'])
    return {'available':bool(events), 'events':sorted(events.values(),key=lambda e:(e['signalMonth'],e['code'],e['ageBand'])),
            'months':sorted({r['date'][:7] for r in detected}), 'observationWindowMonths':3,
            'recoveryMeaning':'descriptive_level_comparison_only_not_sustained_recovery_confirmation',
            'sourceHashes':{str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (detection,followup)}}

def update_snapshot(source, target):
    target = Path(target)
    data = json.loads(target.read_text(encoding='utf-8'))
    data['activityTracking'] = activity_tracking(source)
    target.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    return {'events':len(data['activityTracking']['events']),
            'points':sum(len(e['points']) for e in data['activityTracking']['events'])}

if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db1-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(update_snapshot(args.db1_root,args.output))

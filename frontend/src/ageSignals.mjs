import { orderedCases } from './caseOrder.mjs';
export function signalCount(rows) {
  const flagged = rows.filter((r) => r.is_risk_signal);
  return rows.some((r) => r.case_id) ? new Set(flagged.map((r) => r.case_id)).size : flagged.length;
}

export function relevantScores(rows) {
  const flagged = rows.filter((r) => r.is_risk_signal);
  return (flagged.length ? flagged : rows).map((r) => r.risk_robust_z).filter(Number.isFinite);
}

// Accept older API/cache names while retaining the unchanged administrative code.
export function normalizeAgeNames(data) {
  if (data.analysisScope !== 'dong_age') return data;
  const name = (row) => ((row.code || row['행정동코드']) === '1123074' ? '개포3동' : null);
  return {
    ...data,
    assessment: data.assessment.map((r) =>
      name(r)
        ? { ...r, source_district: r.source_district || r['행정동명'], 행정동명: name(r) }
        : r,
    ),
    ageDetections: (data.ageDetections || []).map((r) =>
      name(r) ? { ...r, source_district: r.source_district || r.district, district: name(r) } : r,
    ),
    alerts: (data.alerts || []).map((r) =>
      name(r) ? { ...r, source_district: r.source_district || r.district, district: name(r) } : r,
    ),
  };
}

export function ageStatus(cases, group) {
  const band = {
    '20대': '20s',
    '30대': '30s',
    '40대': '40s',
    '50대': '50s',
    '60대 이상': '60plus',
  }[group.age];
  const row = cases.find(
    (r) => r.code === group.code && r.month === group.month && r.age_band === band,
  );
  if (!row) return undefined;
  return {
    status: row.any_signal
      ? row.signal_status === 'Continuing'
        ? '연속 후보'
        : row.signal_status === 'New_after_gap'
          ? '판정 보류 후 탐지'
          : '신규 후보'
      : row.assessment_status !== 'assessed'
        ? '판단 보류'
        : '기준 미해당',
    count: row.any_signal ? 1 : 0,
    scope: 'dong_age',
    sex_scope: '성별 통합',
    age: row.age,
  };
}

export function detectionTabs(cases, city, month) {
  const unique = new Map();
  for (const r of cases.filter((r) => r.month === month && r.any_signal)) {
    const g = { city, code: r.code, district: r.district, age: r.age, sex: '통합', month };
    unique.set([g.code, g.age].join('/'), g);
  }
  return orderedCases([...unique.values()]);
}

export function observationWindow(month) {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month || '')) return '';
  const [year, m] = month.split('-').map(Number);
  const start = new Date(Date.UTC(year, m - 4, 1)).toISOString().slice(0, 7).replace('-', '.');
  const end = new Date(Date.UTC(year, m - 2, 1)).toISOString().slice(0, 7).replace('-', '.');
  return start.slice(0, 4) === end.slice(0, 4) ? `${start}–${end.slice(5)}` : `${start}–${end}`;
}

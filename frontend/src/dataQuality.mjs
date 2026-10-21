import { orderedCases } from './caseOrder.mjs';
export const COVERAGE_MINIMUM = 0.8;
const METRICS = [
  ['call_contacts', '전화 연락'],
  ['text_contacts', '문자 연락'],
  ['weekday_move_count', '평일 이동'],
  ['weekend_move_count', '휴일 이동'],
];
const finite = (v) => typeof v === 'number' && Number.isFinite(v);
const nextMonth = (month) => {
  const [y, m] = month.split('-').map(Number);
  return new Date(Date.UTC(y, m, 1)).toISOString().slice(0, 7);
};
const monthLabel = (m) => `${Number(m.slice(5))}월`;
const qualityGroupKey = (item) => `${item.code || item.district}/${item.age}`;

// Build from the active analysis payload, never from a hard-coded list of dongs.
// A low-quality month also blocks the following month's change when its prior value is excluded.
export function qualityGroups(cases, months, minimum = COVERAGE_MINIMUM) {
  const allowed = new Set(months),
    groups = new Map();
  for (const row of cases.filter((r) => allowed.has(r.month))) {
    const key = qualityGroupKey(row);
    if (!groups.has(key))
      groups.set(key, { code: row.code, district: row.district, age: row.age, rows: [] });
    groups.get(key).rows.push(row);
  }
  const result = [];
  for (const group of groups.values()) {
    const rows = group.rows.sort((a, b) => a.month.localeCompare(b.month)),
      byMonth = new Map(rows.map((r) => [r.month, r]));
    const issues = [];
    for (const row of rows)
      for (const [metric, label] of METRICS) {
        const p = row.payload || {},
          coverage = p[metric + '_coverage'];
        if (!finite(coverage) || coverage >= minimum) continue;
        const total = p.total_population,
          valid = p[metric + '_valid_population'];
        issues.push({
          month: row.month,
          metric,
          label,
          coverage,
          total: finite(total) ? total : null,
          unestimated: finite(total) && finite(valid) ? Math.max(0, total - valid) : null,
          valueAvailable: finite(p[metric]),
        });
      }
    if (!issues.length) continue;
    const affected = new Map();
    for (const issue of issues) {
      affected.set(issue.month, { month: issue.month, label: '유효 비율 미달', kind: 'limited' });
      const next = byMonth.get(nextMonth(issue.month)),
        p = next?.payload || {};
      if (next && !finite(p[issue.metric + '_log_change']) && !affected.has(next.month))
        affected.set(next.month, {
          month: next.month,
          label: '전월 자료 제외로 변화량 계산 불가',
          kind: 'limited',
        });
    }
    const timeline = [...affected.values()].sort((a, b) => a.month.localeCompare(b.month));
    const last = timeline.at(-1).month;
    const recovered = rows.find(
      (r) => r.month > last && issues.every((i) => finite(r.payload?.[i.metric + '_log_change'])),
    );
    if (recovered) {
      const domains = [
        recovered.communication_signal === true ? '통신' : null,
        recovered.mobility_signal === true ? '이동' : null,
      ].filter(Boolean);
      timeline.push({
        month: recovered.month,
        label: `판정 가능 · ${domains.length ? domains.join('·') + ' 감소 탐지' : '미탐지'}`,
        kind: 'recovered',
      });
    }
    result.push({
      ...group,
      id: qualityGroupKey(group),
      issues,
      timeline,
      affectedMonths: [...affected.keys()].sort(),
      firstIssue: issues[0],
      hasValues: issues.every((i) => i.valueAvailable),
    });
  }
  return orderedCases(result);
}
export function qualityPageFor(groups, id, pageSize = 2) {
  const index = groups.findIndex((g) => g.id === id);
  return index < 0 ? 0 : Math.floor(index / pageSize);
}
export function qualityMonthText(months) {
  const values = [...new Set(months)].sort();
  if (!values.length) return '없음';
  if (values.every((m) => m.slice(0, 4) === values[0].slice(0, 4)))
    return `${values[0].slice(0, 4)}년 ${values.map(monthLabel).join('·')}`;
  return values.join(' · ');
}

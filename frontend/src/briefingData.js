export const statusTone = (status) => status === '신규 후보' || status === '변화 후보' ? 'new-candidate'
  : status === '연속 후보' ? 'continuing-candidate' : status === '판단 보류' ? 'pending-region' : 'quiet';

export function briefingStats(regions, assessment, city, month, months) {
  const previous = [...months].filter((m) => m < month).sort().at(-1);
  const comparable = regions.some((region) => region.rows.some((row) => row.has_enough_history)) &&
    assessment.some((row) => city === '강남구' && row['기준연월'] === previous && row.has_enough_history);
  return [
    { label: '신규 확인 후보', value: comparable ? regions.filter((r) => r.status === '신규 후보').length : null, tone: statusTone('신규 후보'), icon: 'chart' },
    { label: '연속 확인 후보', value: comparable ? regions.filter((r) => r.status === '연속 후보').length : null, tone: statusTone('연속 후보'), icon: 'chart' },
    { label: '판단 보류 지역', value: regions.filter((r) => r.pending).length, tone: statusTone('판단 보류'), icon: 'report' },
  ];
}

export function rankedCases(regions) {
  return regions.filter((region) => region.rows.length).slice().sort((a, b) =>
    b.count - a.count || Number(b.pending) - Number(a.pending) ||
    (a.minZ ?? Infinity) - (b.minZ ?? Infinity) || a.name.localeCompare(b.name, 'ko'));
}

// 신규/연속 후보가 5개를 넘더라도 빠지지 않도록 전체 목록을 페이지로 나눕니다.
export function casePage(ordered, requestedPage = 0, pageSize = 7) {
  const totalPages = Math.max(1, Math.ceil(ordered.length / pageSize));
  const page = Math.max(0, Math.min(requestedPage, totalPages - 1));
  const start = page * pageSize;
  return { page, totalPages, start, items: ordered.slice(start, start + pageSize) };
}

export function caseMetrics(region) {
  return [...(region?.rows || [])].sort((a, b) =>
    Number(b.is_risk_signal) - Number(a.is_risk_signal) ||
    (a.risk_robust_z ?? Infinity) - (b.risk_robust_z ?? Infinity)).slice(0, 2);
}

export function sixMonths(month) {
  if (!/^\d{4}-\d{2}$/.test(month)) return [];
  const [year, m] = month.split('-').map(Number);
  return Array.from({ length: 6 }, (_, i) => {
    const date = new Date(Date.UTC(year, m - 6 + i, 1));
    return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`;
  });
}

export function metricSeries(assessment, name, metric, month) {
  const rows = new Map(assessment.filter((row) => row['행정동명'] === name && row.metric_label === metric && row['기준연월'] <= month)
    .map((row) => [row['기준연월'], row]));
  const series = sixMonths(month).map((date) => ({ month: date, row: rows.get(date) }));
  // 원자료가 없으면 계산된 변화율을 표시하고 축 단위도 함께 바꿉니다.
  const raw = series.some(({ row }) => Number.isFinite(row?.metric_value));
  return { raw, unit: raw ? series.find(({ row }) => row?.metric_unit)?.row.metric_unit || '' : '%',
    points: series.map(({ month: date, row }) => ({ month: date,
      value: Number.isFinite(raw ? row?.metric_value : row?.change_pct) ? raw ? row.metric_value : row.change_pct : null })),
  };
}

const changeText = (row) => !Number.isFinite(row.change_pct) ? `${row.metric_label}의 전월 변화율은 확인되지 않았습니다`
  : `${row.metric_label}은 전월 대비 ${Math.abs(row.change_pct).toFixed(1)}% ${row.change_pct < 0 ? '감소' : row.change_pct > 0 ? '증가' : '유지'}했습니다`;

export function caseNarrative(region, metrics) {
  if (!region) return '';
  const changes = metrics.map(changeText).join('. ') + (metrics.length ? '.' : '');
  const note = region.count > 0 ? '공통 변화를 보정한 지표에서 변화 후보가 감지됐습니다. 관련 원인은 추가 확인이 필요합니다.'
    : region.pending ? '일부 지표의 비교 이력이 부족해 판단을 보류했습니다.'
      : '현재 탐지 기준에 해당하는 변화 후보는 없습니다. 집계값의 흐름을 참고하세요.';
  return `${changes} ${note}`;
}

export function caseQuestion(region, month, metrics) {
  const topic = metrics.map((row) => `${row.metric_label} ${Number.isFinite(row.change_pct) ? row.change_pct < 0 ? '감소' : row.change_pct > 0 ? '증가' : '유지' : '변화율 미확인'}`).join(' · ');
  return `${region.name}의 ${topic}는 어떤 의미일까요?`;
}

export function caseQuestionDraft(region, city, month, metrics) {
  const evidence = metrics.map((row) => `${row.metric_label}: 전월 변화율 ${Number.isFinite(row.change_pct) ? row.change_pct.toFixed(1) + '%' : '미확인'}, ` +
    `공통 변화 보정값 ${Number.isFinite(row.relative_change_pp) ? row.relative_change_pp.toFixed(2) : '미확인'}, Robust Z ${Number.isFinite(row.risk_robust_z) ? row.risk_robust_z.toFixed(2) : '미확인'}`).join('; ');
  return `${city} ${region.name}, ${month} 지역 집계 분석입니다. ${evidence}. 분석 상태는 ${region.status}입니다. ` +
    '원인을 단정하지 말고 추가로 확인할 요인과 지역 돌봄 관점에서 검토할 복지지원 방향을 알려주세요. 개인의 고립 판정이나 지원 자격을 확정하지 마세요.';
}

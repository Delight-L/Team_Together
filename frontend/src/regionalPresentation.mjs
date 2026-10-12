export const ratioPercent = value => Number.isFinite(value) && value >= 0 && value <= 1 ? value * 100 : null;
export const logPercent = value => {
  const result = Number.isFinite(value) ? Math.expm1(value) * 100 : NaN;
  return Number.isFinite(result) ? result : null;
};
export function householdParts(payload = {}) {
  const parts = [['hh_1_ratio', '1인'], ['hh_2_ratio', '2인'], ['hh_3_ratio', '3인'], ['hh_4plus_ratio', '4인 이상']].map(([key, label]) => ({ label, value: ratioPercent(payload[key]) }));
  return parts.every(p => p.value !== null) && Math.abs(parts.reduce((n, p) => n + p.value, 0) - 100) < 0.1 ? parts : [];
}
export function comparisonRows(payload = {}) {
  return [['call_contacts', '전화 연락'], ['weekday_move_count', '평일 이동']].map(([key, label]) => ({ label, local: logPercent(payload[key + '_log_change']), common: logPercent(payload[key + '_gangnam_median_change']) }));
}
export function signedBar(value, extent) {
  const width = Number.isFinite(value) && extent > 0 ? Math.min(Math.abs(value) / extent, 1) * 50 : 0;
  return { left: `${value < 0 ? 50 - width : 50}%`, width: `${width}%` };
}

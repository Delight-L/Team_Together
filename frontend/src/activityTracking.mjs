export const TRACKING_AGES = ['20대', '30대', '40대', '50대', '60대 이상'];
export const DOMAINS = [
  {
    key: 'communication',
    label: '통신',
    metrics: [
      ['call_contacts', '전화 연락', '#243b63'],
      ['text_contacts', '문자 연락', '#7b8798'],
    ],
  },
  {
    key: 'mobility',
    label: '이동',
    metrics: [
      ['weekday_move_count', '평일 이동', '#243b63'],
      ['weekend_move_count', '휴일 이동', '#7b8798'],
    ],
  },
];
export function pathState(signal = {}) {
  if (signal.absolute && signal.local) return 'both';
  if (signal.absolute) return 'absolute';
  if (signal.local) return 'local';
  return 'none';
}
export function trackingMonthOptions(tracking, endMonth) {
  return (tracking?.months || [])
    .filter((month) => month <= endMonth)
    .map((month) => ({
      month,
      count: (tracking.events || []).filter((e) => e.signalMonth === month).length,
    }))
    .filter((item) => item.count > 0);
}
export function eventsInMonth(tracking, month) {
  return (tracking?.events || []).filter((e) => e.signalMonth === month);
}
export function preferredMonthlyEvent(events, district, age) {
  return (
    events.find((e) => e.district === district && e.age === age) ||
    events.find((e) => e.district === district) ||
    events.find((e) => e.age === age) ||
    events[0]
  );
}
export function trackingSeries(event, endMonth, scope = 'raw') {
  if (!event || event.signalMonth > endMonth) return [];
  const points = event.points.filter((p) => p.month <= endMonth);
  const keys = DOMAINS.flatMap((d) => d.metrics.map((m) => m[0]));
  const reference = Object.fromEntries(
    keys.map((k) => [k, points.some((p) => Number.isFinite(p[scope]?.[k])) ? 100 : null]),
  );
  return [
    { month: event.referenceMonth, values: reference },
    ...points.map((p) => ({
      month: p.month,
      values: Object.fromEntries(
        keys.map((k) => [k, Number.isFinite(p[scope]?.[k]) ? 100 + p[scope][k] : null]),
      ),
    })),
  ];
}
export function latestObservation(event, endMonth) {
  return event?.points.filter((p) => p.month <= endMonth).at(-1) || null;
}
const stateText = {
  both_below_reference: '두 지표 모두 기준 미달',
  recovered_to_reference: '두 지표 모두 기준 이상',
  mixed_recovery: '두 지표 흐름이 다름',
  unavailable: '비교 자료 부족',
};
export function stateLabel(value) {
  return stateText[value] || '비교 자료 부족';
}

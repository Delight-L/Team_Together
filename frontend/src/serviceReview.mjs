import { compareDistrictAge } from './caseOrder.mjs';
import { serviceDomains } from './serviceCase.mjs';

export const reviewCaseKey = (item) =>
  `${item.code || item.district}/${item.age}/${item.signalMonth}`;

// The selected month is the review month; evidence and saved work keep the original detection month.
export function serviceReviewCases(analysis, tracking, context) {
  if (context.city !== '강남구' || !context.month) return [];
  const unique = new Map();
  for (const detection of analysis?.ageDetections || []) {
    if (!detection.any_signal || detection.month > context.month) continue;
    const signalMonth = detection.month;
    const event = tracking?.events?.find(
      (e) =>
        e.signalMonth === signalMonth &&
        (detection.code ? e.code === detection.code : e.district === detection.district) &&
        e.age === detection.age,
    );
    // Missing/invalid observations cannot establish recovery. Never use a future observation.
    const point = event?.points?.find((p) => p.month === context.month);
    const domains = serviceDomains(detection);
    const recovered =
      domains.length > 0 &&
      domains.every((d) => point?.domains?.[d.key]?.raw_state === 'recovered_to_reference');
    if (signalMonth < context.month && recovered) continue;
    const item = {
      city: context.city,
      code: detection.code,
      district: detection.district,
      age: detection.age,
      month: context.month,
      signalMonth,
      lifecycle: signalMonth === context.month ? 'new' : 'tracking',
    };
    unique.set(reviewCaseKey(item), item);
  }
  return [...unique.values()].sort(
    (a, b) => b.signalMonth.localeCompare(a.signalMonth) || compareDistrictAge(a, b),
  );
}

export function selectedReviewCase(items, context, signalMonth) {
  const sameGroup = items.filter(
    (item) => item.district === context.district && item.age === context.age,
  );
  return (
    sameGroup.find((item) => item.signalMonth === signalMonth) ||
    sameGroup[0] ||
    (context.district && context.age ? null : items[0]) ||
    null
  );
}

export function serviceReviewContext(context, selected) {
  return selected
    ? {
        city: context.city,
        district: selected.district,
        age: selected.age,
        month: selected.signalMonth,
      }
    : { city: context.city, district: '', month: context.month };
}

export function reviewMonthGroups(items) {
  const counts = new Map();
  for (const item of items) {
    const key = `${item.signalMonth}/${item.lifecycle}`;
    const group = counts.get(key) || {
      month: item.signalMonth,
      lifecycle: item.lifecycle,
      count: 0,
    };
    group.count++;
    counts.set(key, group);
  }
  return [...counts.values()].sort((a, b) => b.month.localeCompare(a.month));
}

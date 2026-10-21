import { orderedCases } from './caseOrder.mjs';
import { detectionTabs } from './ageSignals.mjs';
import { groupKey } from './groupTabs.mjs';

// 사용자가 직접 고른 그룹은 탐지 사례가 아니어도 열 수 있습니다.
// 탐지 건수와 탐지 선택 목록은 detectionTabs가 만든 결과를 사용합니다.
export function overviewWorkspace(cases, city, month, selection, previous) {
  const observations = orderedCases(cases.filter((row) => row.month === month));
  const tabs = detectionTabs(cases, city, month);
  const hasRequestedGroup = selection?.district && selection?.age;
  let row;
  if (hasRequestedGroup) {
    row = observations.find(
      (item) => item.district === selection.district && item.age === selection.age,
    );
  } else {
    row = observations.find((item) => item.code === previous?.code && item.age === previous?.age);
    row = row || observations.find((item) => item.any_signal) || observations[0];
  }
  const selected = row
    ? { city, code: row.code, district: row.district, age: row.age, sex: '통합', month }
    : null;
  if (selected && !tabs.some((group) => groupKey(group) === groupKey(selected))) {
    tabs.push(selected);
  }
  return { tabs, active: selected ? groupKey(selected) : '' };
}

// 두 화면이 같은 지역·연령·기간 조건과 정렬 순서를 쓰도록 한곳에서 고릅니다.
function matchingEvents(tracking, context) {
  return (tracking?.events || [])
    .filter(
      (event) =>
        event.district === context.district &&
        event.age === context.age &&
        event.signalMonth <= context.month,
    )
    .sort((a, b) => a.signalMonth.localeCompare(b.signalMonth));
}

export function trackingCase(tracking, context, signalMonth) {
  const events = (tracking?.events || []).filter((event) => event.signalMonth <= context.month);
  const months = [...new Set(events.map((event) => event.signalMonth))].sort();
  const matching = matchingEvents(tracking, context);
  const requestedEvent = matching.find((event) => event.signalMonth === signalMonth);
  const latestGroupMonth = matching.at(-1)?.signalMonth;
  const fallbackMonth = months.includes(signalMonth) ? signalMonth : months.at(-1) || context.month;
  const month = requestedEvent?.signalMonth || latestGroupMonth || fallbackMonth;
  return { month, event: matching.find((event) => event.signalMonth === month) || null };
}

export function signalForGroup(tracking, context, preferred) {
  const matching = matchingEvents(tracking, context);
  return (
    matching.find((event) => event.signalMonth === preferred)?.signalMonth ||
    matching.at(-1)?.signalMonth ||
    preferred
  );
}

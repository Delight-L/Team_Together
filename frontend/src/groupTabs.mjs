export const groupKey = (g) => [g.city, g.code, g.month, g.age, g.sex].join('/');
export const groupLabel = (g) => `${g.district} · ${g.age}${g.sex === '통합' ? '' : ` · ${g.sex}`}`;
export function openGroup(state, group) {
  const id = groupKey(group);
  return {
    ...state,
    tabs: state.tabs.some((t) => groupKey(t) === id) ? state.tabs : [...state.tabs, group],
    active: id,
  };
}

const validMonth = (m) => typeof m === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(m);
export function restoreWorkspace(value, city) {
  const tabs = [],
    seen = new Set();
  for (const g of Array.isArray(value?.tabs) ? value.tabs : []) {
    if (
      !g ||
      g.city !== city ||
      !{ 강남구: /^11230\d{2}$/, 춘천시: /^32010\d{2}$/ }[city]?.test(g.code) ||
      !validMonth(g.month) ||
      !['10대', '20대', '30대', '40대', '50대', '60대 이상'].includes(g.age) ||
      !['남성', '여성', '통합'].includes(g.sex) ||
      typeof g.district !== 'string'
    )
      continue;
    const id = groupKey(g);
    if (!seen.has(id)) {
      seen.add(id);
      tabs.push({
        city,
        code: g.code,
        month: g.month,
        age: g.age,
        sex: g.sex,
        district: g.district,
      });
    }
  }
  return {
    ...(typeof value?.analysisVersion === 'string'
      ? { analysisVersion: value.analysisVersion }
      : {}),
    tabs,
    active: seen.has(value?.active) ? value.active : tabs.length ? groupKey(tabs[0]) : '',
    month: validMonth(value?.month) ? value.month : '',
    initialized:
      value?.initialized === false ? false : value?.initialized === true || tabs.length > 0,
  };
}

export function availableWorkspace(state, catalog, preferredMonth) {
  const names = new Map(catalog.districts.map((d) => [d.code, d.name]));
  const tabs = state.tabs
    .filter(
      (g) =>
        names.has(g.code) &&
        catalog.months.includes(g.month) &&
        catalog.ages.includes(g.age) &&
        (g.sex === '통합' || catalog.sexes.includes(g.sex)),
    )
    .map((g) => ({ ...g, district: names.get(g.code) }));
  return {
    ...state,
    tabs,
    active: tabs.some((g) => groupKey(g) === state.active)
      ? state.active
      : tabs.length
        ? groupKey(tabs[0])
        : '',
    month: catalog.months.includes(state.month || preferredMonth)
      ? state.month || preferredMonth
      : catalog.months.at(-1) || '',
  };
}

// 후보 판정 우선순위: 신규 → 연속 → 변화 후보. 그 밖의 판정은 같은 순위로 취급합니다.
export const CANDIDATE_ORDER = ['신규 후보', '연속 후보', '판정 보류 후 탐지'];
const candidateRank = (status) => {
  const i = CANDIDATE_ORDER.indexOf(status);
  return i < 0 ? CANDIDATE_ORDER.length : i;
};
const decline = (g) => (Number.isFinite(g.change_pct) ? g.change_pct : Infinity);

// 조사 파일 목록 순서: 후보 동의 그룹이 먼저(판정 순위 → 후보 지표 수), 같은 동에서는 유동량이 많이 줄어든 그룹부터.
// 후보가 아닌 동은 원래 순서를 유지합니다. statusOf(group)는 { status, count } 또는 undefined를 돌려줍니다.
function rankGroups(groups, statusOf) {
  return groups
    .map((group, index) => ({ group, index, status: statusOf(group) }))
    .sort((a, b) => {
      const firstRank = candidateRank(a.status?.status);
      const secondRank = candidateRank(b.status?.status);
      if (firstRank !== secondRank) return firstRank - secondRank;
      if (firstRank === CANDIDATE_ORDER.length) return a.index - b.index;
      return (
        (b.status.count || 0) - (a.status.count || 0) ||
        a.group.district.localeCompare(b.group.district, 'ko') ||
        decline(a.group) - decline(b.group) ||
        a.index - b.index
      );
    })
    .map((item) => item.group);
}

// 처음 방문할 때 열 그룹: 1순위 후보 동에서 유동량이 가장 많이 줄어든 그룹.
// 후보 동이 없으면(예: 후보 판정 자료가 없는 지역) 전체에서 유동량이 가장 많이 줄어든 그룹을 엽니다.
export function pickInitialGroup(groups, statusOf) {
  if (!groups.length) return null;
  const ranked = rankGroups(groups, statusOf);
  const top = ranked[0];
  if (candidateRank(statusOf(top)?.status) < CANDIDATE_ORDER.length) return top;
  return [...groups].sort((a, b) => decline(a) - decline(b))[0];
}

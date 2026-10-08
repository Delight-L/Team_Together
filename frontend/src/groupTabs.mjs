export const groupKey = g => [g.city, g.code, g.month, g.age, g.sex].join('/');
export const groupLabel = g => `${g.district} · ${g.age} · ${g.sex}`;
export function openGroup(state, group) {
  const id = groupKey(group);
  return { ...state, tabs: state.tabs.some(t => groupKey(t) === id) ? state.tabs : [...state.tabs, group], active: id };
}
export function closeGroup(state, id) {
  const index = state.tabs.findIndex(t => groupKey(t) === id);
  const tabs = state.tabs.filter(t => groupKey(t) !== id);
  return { ...state, tabs, active: state.active === id ? (tabs.length ? groupKey(tabs[Math.min(index, tabs.length - 1)]) : '') : state.active };
}

const validMonth = m => typeof m === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(m);
export function restoreWorkspace(value, city) {
  const tabs = [], seen = new Set();
  for (const g of Array.isArray(value?.tabs) ? value.tabs : []) {
    if (!g || g.city !== city || !/^11230\d{2}$/.test(g.code) || !validMonth(g.month)
      || !['10대', '20대', '30대', '40대', '50대', '60대 이상'].includes(g.age)
      || !['남성', '여성'].includes(g.sex) || typeof g.district !== 'string') continue;
    const id = groupKey(g);
    if (!seen.has(id)) { seen.add(id); tabs.push({ city, code: g.code, month: g.month, age: g.age, sex: g.sex, district: g.district }); }
  }
  return { tabs, active: seen.has(value?.active) ? value.active : tabs.length ? groupKey(tabs[0]) : '',
    month: validMonth(value?.month) ? value.month : '', initialized: value?.initialized === true || tabs.length > 0 };
}

export function availableWorkspace(state, catalog, preferredMonth) {
  const names = new Map(catalog.districts.map(d => [d.code, d.name]));
  const tabs = state.tabs.filter(g => names.has(g.code) && catalog.months.includes(g.month)
    && catalog.ages.includes(g.age) && catalog.sexes.includes(g.sex))
    .map(g => ({ ...g, district: names.get(g.code) }));
  return { ...state, tabs, active: tabs.some(g => groupKey(g) === state.active) ? state.active : tabs.length ? groupKey(tabs[0]) : '',
    month: catalog.months.includes(state.month || preferredMonth) ? state.month || preferredMonth : catalog.months.at(-1) || '' };
}

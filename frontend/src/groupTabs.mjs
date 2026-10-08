export const groupKey = g => [g.city, g.code, g.month, g.age, g.sex].join('/');
export const groupLabel = g => `${g.district} · ${g.age} · ${g.sex}`;
export function openGroup(state, group) {
  const id = groupKey(group);
  return { tabs: state.tabs.some(t => groupKey(t) === id) ? state.tabs : [...state.tabs, group], active: id };
}
export function closeGroup(state, id) {
  const index = state.tabs.findIndex(t => groupKey(t) === id);
  const tabs = state.tabs.filter(t => groupKey(t) !== id);
  return { tabs, active: state.active === id ? (tabs.length ? groupKey(tabs[Math.min(index, tabs.length - 1)]) : '') : state.active };
}

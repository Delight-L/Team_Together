import test from 'node:test';
import assert from 'node:assert/strict';
import { openGroup, closeGroup, groupKey, restoreWorkspace, availableWorkspace } from '../src/groupTabs.mjs';

const a = { city: '강남구', code: '1123065', district: '역삼2동', month: '2025-12', age: '30대', sex: '남성' };
test('same group opens once; sex, month and age have distinct tabs', () => {
  let state = openGroup({ tabs: [], active: '' }, a);
  state = openGroup(state, { ...a }); assert.equal(state.tabs.length, 1);
  state = openGroup(state, { ...a, sex: '여성' });
  state = openGroup(state, { ...a, age: '40대' });
  state = openGroup(state, { ...a, month: '2025-11' });
  assert.equal(state.tabs.length, 4);
  state = openGroup(state, a); assert.equal(state.active, groupKey(a));
});

test('restores selected tab and period while rejecting broken and cross-city entries', () => {
  const state = restoreWorkspace({ tabs: [a, { ...a }, null, { ...a, city: '춘천시' }, { ...a, month: '2025-99' }], active: groupKey(a), month: '2025-11' }, '강남구');
  assert.deepEqual(state.tabs, [a]); assert.equal(state.active, groupKey(a));
  assert.equal(state.month, '2025-11'); assert.equal(state.initialized, true);
  assert.deepEqual(restoreWorkspace('broken', '강남구'), { tabs: [], active: '', month: '', initialized: false });
});

test('closed workspace stays closed after restoration and retains its period', () => {
  const state = closeGroup({ ...openGroup({ tabs: [], active: '' }, a), month: '2025-11', initialized: true }, groupKey(a));
  assert.deepEqual(restoreWorkspace(JSON.parse(JSON.stringify(state)), '강남구'), { tabs: [], active: '', month: '2025-11', initialized: true });
});

test('DB catalogue removes unavailable tabs, repairs names and picks an available month', () => {
  const catalog = { months: ['2025-11', '2025-12'], districts: [{ code: a.code, name: '현재 동명' }], ages: ['30대'], sexes: ['남성'] };
  const state = restoreWorkspace({ tabs: [{ ...a, month: '2025-10' }, a], active: 'missing', month: '2025-01' }, '강남구');
  const result = availableWorkspace(state, catalog, '2025-01');
  assert.equal(result.month, '2025-12'); assert.equal(result.tabs.length, 1);
  assert.equal(result.tabs[0].district, '현재 동명'); assert.equal(result.active, groupKey(a));
  assert.equal(availableWorkspace(result, { ...catalog, months: [], districts: [] }, '').tabs.length, 0);
});
test('closing inactive tab keeps selection; closing active chooses neighbor and last closes cleanly', () => {
  const b = { ...a, sex: '여성' };
  let state = openGroup(openGroup({ tabs: [], active: '' }, a), b);
  state = closeGroup(state, groupKey(a)); assert.equal(state.active, groupKey(b));
  state = closeGroup(state, groupKey(b)); assert.deepEqual(state, { tabs: [], active: '' });
});

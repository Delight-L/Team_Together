import test from 'node:test';
import assert from 'node:assert/strict';
import { openGroup, closeGroup, groupKey } from '../src/groupTabs.mjs';

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
test('closing inactive tab keeps selection; closing active chooses neighbor and last closes cleanly', () => {
  const b = { ...a, sex: '여성' };
  let state = openGroup(openGroup({ tabs: [], active: '' }, a), b);
  state = closeGroup(state, groupKey(a)); assert.equal(state.active, groupKey(b));
  state = closeGroup(state, groupKey(b)); assert.deepEqual(state, { tabs: [], active: '' });
});

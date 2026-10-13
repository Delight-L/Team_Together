import test from 'node:test';
import assert from 'node:assert/strict';
import { tabPage, tabPageForSelected } from '../src/tabPaging.mjs';

test('pages contain only whole tabs at the available width', () => {
  const widths = [215, 170, 336, 336, 336, 336];
  assert.deepEqual(tabPage(widths, 0, 889), { start: 0, end: 3, previous: 0 });
  assert.deepEqual(tabPage(widths, 3, 889), { start: 3, end: 5, previous: 0 });
  assert.deepEqual(tabPage(widths, 5, 889), { start: 5, end: 6, previous: 3 });
  assert.equal(tabPage(widths, 0, 1057).end, 4);
});

test('narrow pages, closing the last tab and empty workspaces remain navigable', () => {
  assert.deepEqual(tabPage([215, 170, 336], 0, 366), { start: 0, end: 1, previous: 0 });
  assert.deepEqual(tabPage([215, 170, 336], 2, 366), { start: 2, end: 3, previous: 1 });
  assert.deepEqual(tabPage([215, 170, 336], 5, 366), { start: 2, end: 3, previous: 1 });
  assert.deepEqual(tabPage([], 5, 366), { start: 0, end: 0, previous: 0 });
});

test('selecting the first file or widening the panel restores both fixed tabs', () => {
  const widths = [215, 170, 336, 336];
  assert.equal(tabPageForSelected(widths, 1, 336).start, 1);
  assert.equal(tabPageForSelected(widths, 2, 366).start, 2);
  const wide = tabPageForSelected(widths, 2, 1057);
  assert.equal(wide.start, 0);
  assert.ok(wide.end >= 3);
  assert.equal(tabPageForSelected(widths, 1, 1057).start, 0);
});

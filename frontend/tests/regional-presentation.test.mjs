import test from 'node:test';
import assert from 'node:assert/strict';
import { householdParts, ratioPercent, logPercent, comparisonRows, signedBar } from '../src/regionalPresentation.mjs';
test('missing, invalid and zero values stay distinct', () => {
  assert.equal(ratioPercent(null), null); assert.equal(ratioPercent(-.1), null); assert.equal(ratioPercent(0), 0);
  assert.equal(logPercent(null), null); assert.equal(logPercent(9999), null); assert.equal(logPercent(0), 0);
  assert.ok(Math.abs(logPercent(Math.log(.8)) + 20) < 1e-10);
  assert.equal(comparisonRows({})[0].common, null);
});
test('household stack requires complete consistent proportions', () => {
  assert.deepEqual(householdParts({hh_1_ratio:.4}), []);
  assert.deepEqual(householdParts({hh_1_ratio:.4,hh_2_ratio:.4,hh_3_ratio:.4,hh_4plus_ratio:.4}), []);
  assert.equal(householdParts({hh_1_ratio:.4,hh_2_ratio:.2,hh_3_ratio:.2,hh_4plus_ratio:.2}).length,4);
});
test('shared scale puts decreases left and increases right of zero', () => {
  assert.deepEqual(signedBar(-20,40), {left:'25%',width:'25%'});
  assert.deepEqual(signedBar(20,40), {left:'50%',width:'25%'});
  assert.deepEqual(signedBar(null,40), {left:'50%',width:'0%'});
});

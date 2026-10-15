import test from 'node:test';
import assert from 'node:assert/strict';
import { householdParts, ratioPercent, logPercent, comparisonRows, signedBar, areaUnit } from '../src/regionalPresentation.mjs';
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

test('new and legacy common changes use the same percentage scale, preserving zero', () => {
  assert.ok(Math.abs(comparisonRows({call_contacts_common_change:Math.log(.9)})[0].common + 10) < 1e-10);
  assert.equal(comparisonRows({call_contacts_gangnam_median_change:0,call_contacts_common_change:.2})[0].common, 0);
});
test('autonomous districts call sub-areas 동, cities and counties keep 읍·면·동', () => {
  assert.equal(areaUnit('강남구'), '동'); assert.equal(areaUnit('춘천시'), '읍·면·동'); assert.equal(areaUnit('양평군'), '읍·면·동'); assert.equal(areaUnit(undefined), '읍·면·동');
});

test('overview reuses common-change math for all four metrics without turning missing data into zero', () => {
 const metrics=[['call_contacts','전화 연락'],['text_contacts','문자 연락'],['weekday_move_count','평일 이동'],['weekend_move_count','휴일 이동']];
 const rows=comparisonRows({text_contacts_log_change:Math.log(.95),text_contacts_common_change:Math.log(.96)},metrics);
 assert.equal(rows.length,4);
 assert.ok(Math.abs(rows[1].local+5)<1e-9);
 assert.ok(Math.abs(rows[1].common+4)<1e-9);
 assert.equal(rows[3].local,null);
 assert.equal(rows[3].common,null);
});

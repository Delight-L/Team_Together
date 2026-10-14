import test from 'node:test';
import assert from 'node:assert/strict';
import { fitDomain } from '../src/chartScale.mjs';

test('좁은 범위의 값은 0이 아닌 자료 범위로 축을 잡는다', () => {
  const d = fitDomain([91, 93, 92, 94, 95, 93]);
  assert.ok(d.low > 0 && d.low <= 91);
  assert.ok(d.high >= 95 && d.high - d.low <= 10);
  assert.equal(d.fromZero, false);
  assert.equal(d.ticks.length, 3);
});

test('0 근처 값은 음수로 내려가지 않는다', () => {
  const d = fitDomain([1, 40, 80]);
  assert.equal(d.low, 0);
  assert.equal(d.fromZero, true);
  assert.ok(d.high >= 80);
});

test('값이 모두 같거나 없으면 안전한 범위를 돌려준다', () => {
  const same = fitDomain([50, 50]);
  assert.ok(same.low < 50 && same.high > 50);
  assert.deepEqual(fitDomain([NaN]).ticks, [0, 0.5, 1]);
});

test('가운데 눈금도 간격의 배수가 된다', () => {
  const d = fitDomain([10.6, 10.9, 11.2, 11.5, 11.0, 10.75]);
  const step = (d.ticks[1] - d.ticks[0]);
  assert.ok(Math.abs(d.ticks[2] - d.ticks[1] - step) < 1e-9);
  assert.ok(Math.abs(d.ticks[1] / step - Math.round(d.ticks[1] / step)) < 1e-9);
});

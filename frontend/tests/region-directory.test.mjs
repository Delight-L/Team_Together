import assert from 'node:assert/strict';
import { test } from 'node:test';
import { candidateFirst } from '../src/regionDirectory.mjs';

test('초기 분석 선택과 목록은 후보 지표 수를 우선하고 같은 수는 낮은 점수순', () => {
  const rows = [{ name: '대치동', count: 0, minZ: -5 }, { name: '삼성동', count: 2, minZ: -2 }, { name: '역삼동', count: 2, minZ: -3 }];
  assert.deepEqual([...rows].sort(candidateFirst).map(row => row.name), ['역삼동', '삼성동', '대치동']);
  assert.equal(rows[0].name, '대치동');
});
test('자료가 없는 동끼리는 점수 비교의 NaN 없이 이름순으로 정렬', () => {
  assert.deepEqual([{ name: '하동', count: 0, minZ: null }, { name: '가동', count: 0, minZ: null }].sort(candidateFirst).map(row => row.name), ['가동', '하동']);
  assert.equal(candidateFirst({ name: '가동', count: 0, minZ: null }, { name: '가동', count: 0, minZ: null }), 0);
});

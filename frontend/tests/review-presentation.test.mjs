import assert from 'node:assert/strict';
import { test } from 'node:test';
import { matchesNeed, reviewGroups } from '../src/reviewPresentation.mjs';
test('지원 목적은 사업 내용에서 확인하고 자격 조건의 가족 문구를 근거로 쓰지 않는다', () => {
  const match = { service: { name: '교류 모임', eligibility_text: '생계 지원 대상자의 가족', summary: '관계 활동' } };
  assert.equal(matchesNeed(match, '관계·사회참여'), true);
  assert.equal(matchesNeed(match, '생활·경제'), false);
  assert.equal(matchesNeed(match, ''), true);
});
test('같은 사업의 최신 판단과 이전 내역을 분리하며 원본은 보존한다', () => {
  const reviews = [{ service_key: 'a', decision: '보류' }, { service_key: 'b', decision: '적합' }, { service_key: 'a', decision: '부적합' }];
  const groups = reviewGroups(reviews);
  assert.equal(groups[0].latest.decision, '부적합');
  assert.deepEqual(groups[0].history, [reviews[0]]);
  assert.equal(reviews.length, 3);
  assert.equal(reviewGroups([{ name: '이전 기록' }])[0].key, 'record:0');
});

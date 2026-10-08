import test from 'node:test';
import assert from 'node:assert/strict';
import { draftKey, readDraft, writeDraft, removeDraft, clearDrafts, draftEpoch, draftStorageFailed } from '../src/draftStore.mjs';

const data = {};
globalThis.sessionStorage = {
  getItem: key => data[key] ?? null,
  setItem: (key, value) => { data[key] = value; },
  removeItem: key => { delete data[key]; },
};
const user = { id: 'a' }, context = { city: '강남구', district: '세곡동', month: '2025-01' };
const key = draftKey(user, context, 'review');
test('계정·체험·지역·월·작성 화면별 임시 보관 분리', () => {
  const keys = [key,
    draftKey({ id: 'b' }, context, 'review'),
    draftKey({ ...user, trial: true }, context, 'review'),
    draftKey(user, { ...context, district: '수서동' }, 'review'),
    draftKey(user, { ...context, month: '2025-02' }, 'review'),
    draftKey(user, context, 'report')];
  assert.equal(new Set(keys).size, keys.length);
  writeDraft(key, { note: '작성 중' });
  assert.equal(readDraft(key).note, '작성 중');
  keys.slice(1).forEach(k => assert.equal(readDraft(k), null));
});
test('새 실행에서도 세션 저장소에서 복원', async () => {
  const fresh = await import('../src/draftStore.mjs?reload');
  assert.equal(fresh.readDraft(key).note, '작성 중');
  fresh.removeDraft(key);
});
test('저장 성공 후 제거, 저장소 실패 시 메모리 보존, 로그아웃 시 폐기', () => {
  removeDraft(key);
  assert.equal(readDraft(key), null);
  sessionStorage.setItem = () => { throw new Error('quota'); };
  assert.equal(writeDraft(key, { note: '보존할 내용' }), false);
  assert.equal(readDraft(key).note, '보존할 내용');
  assert.equal(draftStorageFailed(key), true);
  const before = draftEpoch();
  clearDrafts();
  assert.equal(draftEpoch(), before + 1);
  assert.equal(readDraft(key), null);
  assert.equal(draftStorageFailed(key), false);
});

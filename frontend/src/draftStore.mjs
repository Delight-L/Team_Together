const prefix = 'welfind-draft-v1:';
const memory = new Map();
const failed = new Set();
let epoch = 0;
export const draftEpoch = () => epoch;
export const draftStorageFailed = key => failed.has(key);
export function hasDrafts() {
  if (memory.size) return true;
  try { return Object.keys(sessionStorage).some(key => key.startsWith(prefix)); } catch { return false; }
}
if (typeof window !== 'undefined') window.addEventListener('beforeunload', event => {
  if (failed.size) { event.preventDefault(); event.returnValue = ''; }
});
export const draftKey = (user, context, form) => prefix + JSON.stringify([
  user.id, !!user.trial, context.city, context.district, context.month, form,
]);
export function readDraft(key) {
  if (memory.has(key)) return memory.get(key);
  try { return JSON.parse(sessionStorage.getItem(key) || 'null'); } catch { return null; }
}
export function writeDraft(key, value) {
  memory.set(key, value);
  try { sessionStorage.setItem(key, JSON.stringify(value)); failed.delete(key); return true; }
  catch { failed.add(key); return false; }
}
export function removeDraft(key) {
  memory.delete(key);
  failed.delete(key);
  try { sessionStorage.removeItem(key); } catch { /* 메모리 보관은 별도로 정리합니다. */ }
}
export function clearDrafts() {
  memory.clear();
  failed.clear();
  epoch += 1;
  try {
    Object.keys(sessionStorage).filter(key => key.startsWith(prefix)).forEach(key => sessionStorage.removeItem(key));
  } catch { /* 저장소 접근이 제한된 브라우저도 로그아웃할 수 있습니다. */ }
}

import { useRef, useState } from 'react';
import { readDraft, writeDraft, removeDraft, draftEpoch, draftStorageFailed } from './draftStore.mjs';

// 입력 이벤트에서 바로 보관하므로 메뉴 이동과 effect 실행 순서에 의존하지 않습니다.
export function useDraft(key, initial) {
  const [value, setValue] = useState(() => readDraft(key) ?? initial);
  const current = useRef(value);
  const epoch = useRef(draftEpoch());
  const [storageFailed, setStorageFailed] = useState(() => draftStorageFailed(key));
  function update(next) {
    if (epoch.current !== draftEpoch()) return;
    current.current = typeof next === 'function' ? next(current.current) : next;
    setStorageFailed(!writeDraft(key, current.current));
    setValue(current.current);
  }
  function clear(next = initial) {
    if (epoch.current !== draftEpoch()) return;
    removeDraft(key);
    current.current = next;
    setValue(next);
    setStorageFailed(false);
  }
  return [value, update, clear, storageFailed];
}

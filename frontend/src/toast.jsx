import React, { useEffect, useRef, useState } from 'react';
import { MESSAGE_DURATION_MS } from './useTransientMessage';

// 저장 성공 같은 짧은 알림: 화면 아래에 잠시 보였다가 사라집니다.
// 오류는 놓치면 안 되므로 여기로 보내지 말고 화면 안에 남겨 두세요.
const EVENT = 'welfind-toast';

export function showToast(message) {
  window.dispatchEvent(new CustomEvent(EVENT, { detail: message }));
}

export function Toaster() {
  const [items, setItems] = useState([]);
  const nextId = useRef(0);
  useEffect(() => {
    const timers = new Set();
    const add = (event) => {
      const id = ++nextId.current;
      // 같은 알림이 연달아 오면 하나만 보이게 하고, 최대 3개까지 쌓습니다.
      setItems(list => [...list.filter(t => t.message !== event.detail), { id, message: event.detail }].slice(-3));
      const timer = setTimeout(() => { timers.delete(timer); setItems(list => list.filter(t => t.id !== id)); }, MESSAGE_DURATION_MS);
      timers.add(timer);
    };
    window.addEventListener(EVENT, add);
    return () => { window.removeEventListener(EVENT, add); timers.forEach(clearTimeout); };
  }, []);
  return <div className="toast-stack" role="status" aria-live="polite">
    {items.map(t => <p key={t.id} className="toast">{t.message}</p>)}
  </div>;
}

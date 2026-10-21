import { useCallback, useEffect, useState } from 'react';

const MESSAGE_DURATION_MS = 3500;

// 같은 문구가 다시 표시되어도 마지막 알림부터 표시 시간을 계산합니다.
export function useTransientMessage() {
  const [message, setMessage] = useState({ text: '' });
  const showMessage = useCallback(
    (text, { persistent = false } = {}) => setMessage({ text, persistent }),
    [],
  );
  useEffect(() => {
    if (!message.text || message.persistent) return;
    const timer = setTimeout(() => setMessage({ text: '' }), MESSAGE_DURATION_MS);
    return () => clearTimeout(timer);
  }, [message]);
  return [message.text, showMessage];
}

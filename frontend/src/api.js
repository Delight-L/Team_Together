// 화면 → Python 서버 통신을 한곳에 모읍니다.
// body가 없으면 GET(조회), 있으면 POST(질문/저장)를 사용합니다.
// 실패 시 서버의 error 문구를 Error로 만들어 화면의 catch에서 표시합니다.
export async function api(path, body, options = {}) {
  const response = await fetch(`/api${path}`, {
    credentials: 'same-origin',
    ...options,
    ...(body === undefined
      ? {}
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '요청에 실패했습니다.');
  return data;
}
export const query = (context) => new URLSearchParams(context).toString();
export const number = (value, digits = 1) => (Number.isFinite(value) ? value.toFixed(digits) : '—');

// 특강/chat_test2의 fetch SSE 방식을 기존 로그인 세션과 지역 맥락에 연결합니다.
export async function streamWelfareChat(context, messages, onEvent, signal) {
  const response = await fetch('/api/chat', {
    method: 'POST', credentials: 'same-origin', signal,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...context, messages, stream: true }),
  });
  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.error || '챗봇 요청에 실패했습니다.');
  }
  if (!response.body) throw new Error('스트리밍 응답을 받을 수 없습니다.');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '', completed = false;
  function dispatch(raw) {
    let event = 'message';
    const data = [];
    for (const line of raw.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data.push(line.slice(5).trim());
    }
    if (!data.length) return;
    if (event === 'done') completed = true;
    onEvent(event, JSON.parse(data.join('\n')));
  }
  try {
    for (;;) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, '\n');
      let index;
      while ((index = buffer.indexOf('\n\n')) >= 0) {
        dispatch(buffer.slice(0, index));
        buffer = buffer.slice(index + 2);
      }
      if (done) break;
    }
    if (buffer.trim()) dispatch(buffer);
    if (!completed) throw new Error('응답 연결이 중단되었습니다. 다시 질문해 주세요.');
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

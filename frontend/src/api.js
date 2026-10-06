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

// 이전 업무 기록에는 계정 ID가 남아 있으므로 화면에서 이름으로 표시합니다.
const names = { gangnam01: '김강남', chuncheon01: '이춘천', admin: '박관리' };
export const personName = value => names[value] || value;
export const userName = user => user.name || personName(user.account_id || user.id);

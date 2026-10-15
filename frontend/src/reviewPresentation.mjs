export const SERVICE_CHECKS = [['residency', '선택 지역 주민의 이용 가능 여부'], ['eligibility', '연령·소득 등 대상 조건'], ['application', '현재 접수 여부·정원·신청 방법']];
export const NEED_TERMS = {
  '관계·사회참여': ['교류', '사회참여', '사회 참여', '모임', '관계망', '여가'],
  '안부·돌봄': ['안부', '돌봄', '방문', '상담'],
  '생활·경제': ['생활', '생계', '경제', '긴급', '지원금'],
};
export function matchesNeed(match, need) {
  if (!need) return true;
  const service = match.service;
  const text = ['name', 'benefit_text', 'support_text', 'summary'].map(key => service[key] || '').join(' ');
  return (NEED_TERMS[need] || []).some(term => text.includes(term));
}
export function reviewGroups(reviews = []) {
  const groups = new Map();
  reviews.forEach((review, index) => {
    const key = review.service_key || `record:${index}`;
    const previous = groups.get(key);
    groups.set(key, { key, latest: review, history: previous ? [...previous.history, previous.latest] : [] });
  });
  return [...groups.values()];
}

// 지자체 복지사업 원문은 "- 항목 : 내용"이 줄바꿈 없이 붙어 있고, 한 칸에 대상·지원·신청이 섞여 있습니다.
// AI로 바꿔 쓰면 자격 조건이 달라질 수 있으므로, 원문 문장을 항목으로 나누고 짧게 자르기만 합니다.

// 원문을 항목 목록으로 나눕니다. "- 지원대상 : …- 지원내용 : …"처럼 붙은 항목도 나눕니다.
export function splitItems(text) {
  return String(text || '')
    .replace(/[ \t ]+/g, ' ')
    .replace(/\s*-\s+(?=[가-힣A-Za-z ]{1,15}:)/g, '\n')
    .replace(/\s*[○●■□▶•]\s*/g, '\n')
    .replace(/\s*(?=[①-⑳])/g, '\n')
    .replace(/(^|[^\dA-Za-z.])\s*(\d{1,2}\.\s+)(?=[가-힣])/g, '$1\n$2')
    .replace(/(^|[^A-Za-z])O\s+(?=[가-힣])/g, '$1\n')
    .replace(/([)\]])\s*(?=[가-힣]{2,8}\s*:)/g, '$1\n')
    .split(/\n+/)
    .map((item) => item.replace(/^[-·*\s]+/, '').replace(/\s+:\s*/, ' : ').trim())
    .filter(Boolean);
}

// 항목을 " · "로 이어 한 줄로 만들고, 길면 잘라 끝에 …를 붙입니다.
export function brief(text, max = 90) {
  const line = splitItems(text).join(' · ');
  return line.length > max ? line.slice(0, max).trimEnd() + '…' : line;
}

const same = (a, b) => splitItems(a).join(' ') === splitItems(b).join(' ');

// 카드에 보일 요약 3줄. 대상은 이용 조건과 지원 대상 중 더 짧은 쪽이 보통 핵심만 담고 있습니다.
export function serviceBrief(service) {
  const target = service.target_text || service.description || '';
  const eligibility = service.eligibility_text || '';
  const who = eligibility && (!target || eligibility.length <= target.length) ? eligibility : target;
  return {
    intro: brief(service.summary, 80),
    target: brief(who),
    support: brief(service.support_text || service.benefit_text),
    application: brief(service.application_text),
  };
}

// '원문 보기'에 펼칠 칸별 항목. 지원 대상과 글자가 같은 이용 조건은 한 번만 보여 줍니다.
export function serviceSections(service) {
  const target = service.target_text || service.description;
  return [
    ['지원 대상', target],
    ['이용 조건', same(service.eligibility_text, target) ? '' : service.eligibility_text],
    ['지원 내용', service.support_text || service.benefit_text],
    ['신청 방법', service.application_text],
  ].map(([label, text]) => ({ label, items: splitItems(text) })).filter((section) => section.items.length);
}

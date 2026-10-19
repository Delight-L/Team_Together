// Extract from stored text without generating eligibility or benefit claims.
export function cleanServiceText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}
export function briefServiceText(value, limit = 150) {
  const text = cleanServiceText(value);
  if (text.length <= limit) return text;
  const sentence = text.match(/^.*?[.!?](?:\s|$)/u)?.[0]?.trim();
  if (sentence && sentence.length <= limit && sentence.length >= 20) return sentence;
  return text.slice(0, limit).trimEnd() + '…';
}
export function serviceIntroduction(value) {
  let text = String(value || '').trim()
    .replace(/^(?:[ㅇ○●■□▪▶•*\-]+\s*|\d+[.)]\s*)+/u, '')
    .split(/\n\s*(?:[ㅇ○●■□▪▶•*]|※)/u)[0];
  text = cleanServiceText(text).replace(/^(?:사업\s*(?:목적|개요|내용)|지원\s*내용)\s*[:：]\s*/u, '');
  if (!text) return '사업 소개는 상세 내용이나 원문에서 확인하세요.';
  // Use the first complete sentence; never cut at decimal points or an arbitrary character.
  text = (text.match(/^.*?(?:입니다|합니다|됩니다|있습니다|줍니다|돕습니다|제공한다|지원한다)[.!?。](?:\s|$)/u)?.[0] || text)
    .trim().replace(/[.!?。]+$/u, '');
  if (/사업입니다$/u.test(text)) return text + '.';
  if (/사업(?:임)?$/u.test(text)) return text.replace(/사업(?:임)?$/u, '사업입니다.');
  const endings = [
    [/하고 있습니다$/u, '하는 사업입니다.'],
    [/하고 있음$/u, '하는 사업입니다.'],
    [/합니다$/u, '하는 사업입니다.'],
    [/됩니다$/u, '되는 사업입니다.'],
    [/제공한다$/u, '제공하는 사업입니다.'],
    [/지원한다$/u, '지원하는 사업입니다.'],
    [/돕습니다$/u, '돕는 사업입니다.'],
    [/제공함$/u, '제공하는 사업입니다.'],
    [/지원함$/u, '지원하는 사업입니다.'],
  ];
  for (const [pattern, replacement] of endings) {
    if (pattern.test(text)) return text.replace(pattern, replacement);
  }
  const action = text.match(/^(.*?)\s+(지원|조성|운영|제공|지급|보장|예방|확대|연계|개선|조성·운영|지원·운영)$/u);
  if (action) {
    const [, subject, verb] = action;
    const last = subject.charCodeAt(subject.length - 1);
    const particle = /(?:을|를|에|으로|로)$/u.test(subject) ? ''
      : last >= 0xac00 && last <= 0xd7a3 ? ((last - 0xac00) % 28 ? '을' : '를') : '';
    return `${subject}${particle} ${verb}하는 사업입니다.`;
  }
  // Unrecognized fragments remain quoted, rather than inventing a benefit or rewriting a condition.
  return `‘${text}’을 주요 내용으로 하는 사업입니다.`;
}
export function serviceCardContent(service) {
  const fields = [
    ['사업 소개', service.summary || service.description],
    ['지원 내용', service.support_text],
    ['지원 혜택', service.benefit_text],
    ['지원 대상', service.target_text],
    ['이용 조건', service.eligibility_text],
    ['신청 방법', service.application_text],
    ['상세 안내', service.content],
  ];
  const unique = new Map();
  for (const [label, raw] of fields) {
    const text = cleanServiceText(raw);
    if (!text) continue;
    const key = text.replace(/\s/g, '');
    if (unique.has(key)) unique.get(key).labels.push(label);
    else unique.set(key, {labels:[label], text});
  }
  return {
    introduction: serviceIntroduction(service.summary || service.description || service.support_text || service.benefit_text),
    target: briefServiceText(service.target_text || '지원 대상은 운영기관에 확인하세요.', 100),
    details: [...unique.values()],
  };
}

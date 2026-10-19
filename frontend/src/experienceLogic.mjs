import { reviewGroups } from './reviewPresentation.mjs';

// 서버 report_writer.py와 같은 문구입니다. 구상 보고서 제안 칸 안내와 보미 대화 초안의 검토 전 표시입니다.
export const PLANNING_PROPOSAL = '검토한 사업 없음. 구상한 사업이나 제안 내용을 직접 작성';
export const PENDING_TEXT = '담당자 검토 전';

export function reportChecks(content, workflow) {
  const text = ['summary', 'situation', 'proposal', 'next_steps'].map(k => content?.[k] || '').join('\n');
  const evidence = workflow.analysis_evidence || [];
  const numbers = [...text.matchAll(/([-+−]?\d+(?:\.\d+)?)\s*(%p?)(?:\s*(감소|하락|증가|상승))?/g)].map(match => {
    const value = Number(match[1].replace('−', '-'));
    return { value: !/^[-+−]/.test(match[1]) && ['감소', '하락'].includes(match[3]) ? -value : value, unit: match[2] };
  });
  const unmatched = [...new Set(numbers.filter(number => !evidence.some(row => {
    const value = row[number.unit === '%p' ? 'relative_change_pp' : 'change_pct'];
    return Number.isFinite(value) && Math.abs(number.value - value) <= 0.11;
  })).map(number => number.value))];
  const reviews = reviewGroups(workflow.reviews).filter(group => !content.selection || content.selection.services?.includes(group.key)).map(group => group.latest);
  return {
    strong: /고립(?:자|가구|위험)?(?:로|으로)?\s*(?:확정|판정)|고립이\s*(?:확실|확정)|반드시\s*효과/.test(text),
    unmatched,
    missingSource: !workflow.analysis_source,
    missingServiceSource: reviews.some(r => !r.source_url),
    // 제안 칸 안내 문구가 그대로 남아 있으면 Word 파일을 만들 수 없습니다.
    placeholder: (content?.proposal || '').includes(PLANNING_PROPOSAL),
    // 최종 저장 전에 고칠지 확인하도록 '담당자 검토 전' 표시 개수를 셉니다(저장을 막지는 않음).
    pending: text.split(PENDING_TEXT).length - 1,
  };
}

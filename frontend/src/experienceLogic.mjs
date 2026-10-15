import { reviewGroups } from './reviewPresentation.mjs';

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
  };
}

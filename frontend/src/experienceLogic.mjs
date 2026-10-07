export function reportChecks(content, workflow) {
  const text = ['summary', 'situation', 'proposal', 'next_steps'].map(k => content?.[k] || '').join('\n');
  const evidence = workflow.analysis_evidence || [];
  const values = evidence.flatMap(r => ['change_pct', 'relative_change_pp', 'risk_robust_z'].map(k => r[k])).filter(Number.isFinite);
  const numbers = [...text.matchAll(/([-+−]?\d+(?:\.\d+)?)\s*%/g)].map(m => Number(m[1].replace('−', '-')));
  const unmatched = [...new Set(numbers.filter(n => !values.some(v => Math.abs(n - v) <= 0.11)))];
  return {
    strong: /고립(?:자|가구|위험)?(?:로|으로)?\s*(?:확정|판정)|고립이\s*(?:확실|확정)|반드시\s*효과/.test(text),
    unmatched,
    missingSource: !workflow.analysis_source,
    missingServiceSource: (workflow.reviews || []).some(r => !r.source_url),
  };
}
